"""Release-channel and login policy checks; never touch host packages or disks."""
from contextlib import nullcontext
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = spec_from_file_location('test_' + name, ROOT / 'config/includes.chroot/usr/lib/aphrodite' / (name + '.py'))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


updates = load('releases')
login = load('login')


class ReleaseTests(unittest.TestCase):
    def release(self):
        return {'id': 5, 'tag_name': 'v0.2', 'draft': False, 'prerelease': False,
                'assets': [{'name': updates.MANIFEST, 'state': 'uploaded', 'size': 100,
                            'digest': 'sha256:' + 'a' * 64, 'updated_at': '2026-11-21T12:00:00Z',
                            'browser_download_url': 'https://github.com/seandotmkv/Aphrodite/releases/download/v0.2/' + updates.MANIFEST}]}

    def manifest(self):
        return {'schema': 1, 'os': 'aphrodite', 'series': '0', 'architecture': 'amd64',
                'packages': [{'name': 'aphrodite-base', 'version': '0.3',
                              'asset': 'aphrodite-base_0.3_all.deb', 'sha256': 'b' * 64}]}

    def test_changed_assets_trigger_a_new_fingerprint(self):
        release = self.release()
        before = updates.fingerprint(updates.release_info(release))
        release['assets'][0]['digest'] = 'sha256:' + 'c' * 64
        self.assertNotEqual(before, updates.fingerprint(release))

    def test_drafts_prereleases_and_unsafe_tags_rejected(self):
        for key, value in [('draft', True), ('prerelease', True), ('tag_name', '\x1b[31m')]:
            release = self.release(); release[key] = value
            with self.assertRaises(ValueError):
                updates.release_info(release)

    def test_download_requires_github_digest_and_repository(self):
        for key, value in [('digest', None), ('browser_download_url', 'https://example.org/payload')]:
            release = self.release(); release['assets'][0][key] = value
            with self.assertRaises(ValueError):
                updates.asset_info(release, updates.MANIFEST)

    def test_corrupt_download_is_rejected_before_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            def corrupt(url, limit, **kwargs):
                kwargs['destination'].write(b'bad')
                return '0' * 64, None
            with patch.object(updates, 'fetch', side_effect=corrupt):
                with self.assertRaises(ValueError):
                    updates.download(self.release(), updates.MANIFEST, Path(directory))

    def test_manifest_rejects_unrelated_packages_path_traversal_and_other_os(self):
        for field, value in [('name', 'sudo'), ('asset', '../bad.deb'), ('version', '--bad'), ('sha256', 'invalid')]:
            manifest = self.manifest(); manifest['packages'][0][field] = value
            with self.assertRaises(ValueError):
                updates.checked_manifest(manifest)
        value = self.manifest(); value['os'] = 'debian'
        with self.assertRaises(ValueError):
            updates.checked_manifest(value)

    def test_etag_304_reuses_valid_cached_release(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            updates.atomic(cache / 'release.json', {'etag': 'etag-1', 'release': self.release()})
            with patch.object(updates, 'fetch', return_value=(None, 'etag-1')) as fetch:
                self.assertEqual(updates.cached_release(cache)['tag_name'], 'v0.2')
                self.assertEqual(fetch.call_args.args[2], 'etag-1')

    def test_actual_debian_fields_and_manifest_checksum_are_both_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'aphrodite-base_0.3_all.deb'
            path.write_bytes(b'fixture package')
            item = self.manifest()['packages'][0]
            item['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            fields = {'Package': 'aphrodite-base', 'Version': '0.3', 'Architecture': 'all'}
            with patch.object(updates, 'run', side_effect=lambda *args, **kwargs: fields[args[-1]]):
                updates.verify_package(path, item)
                fields['Package'] = 'unrelated'
                with self.assertRaises(ValueError):
                    updates.verify_package(path, item)
                fields['Package'] = 'aphrodite-base'
                path.write_bytes(b'changed')
                with self.assertRaises(ValueError):
                    updates.verify_package(path, item)

    def test_notifications_deduplicate_and_retry_after_notification_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            with patch.object(updates, 'STATE', cache / 'system'), patch.object(updates, 'run') as run:
                updates.check(self.release(), cache, notify=True)
                updates.check(self.release(), cache, notify=True)
                self.assertEqual(run.call_count, 1)
                release = self.release(); release['assets'][0]['updated_at'] = 'changed'
                run.side_effect = subprocess.CalledProcessError(1, 'notify-send')
                with self.assertRaises(subprocess.CalledProcessError):
                    updates.check(release, cache, notify=True)
                run.side_effect = None
                updates.check(release, cache, notify=True)
                self.assertEqual(run.call_count, 3)

    def fixture_install(self, directory, immutable=False, old='0.2'):
        root = Path(directory)
        transaction = root / 'transactional.json'
        if immutable:
            transaction.write_text('{}')
        def download(release, name, target):
            path = target / name
            path.write_text(json.dumps(self.manifest()) if name == updates.MANIFEST else 'deb')
            return path
        def installed(name):
            return old if calls['count'] == 0 else '0.3'
        calls = {'count': 0}
        def command(*args, **kwargs):
            if args[:2] == ('apt-get', '-y'):
                calls['count'] += 1
        return (patch.object(updates, 'STATE', root / 'state'),
                patch.object(updates, 'TRANSACTIONAL', transaction),
                patch.object(updates, 'require_target'),
                patch.object(updates, 'update_lock', side_effect=nullcontext),
                patch.object(updates, 'download', side_effect=download),
                patch.object(updates, 'verify_package'),
                patch.object(updates, 'installed_version', side_effect=installed),
                patch.object(updates, 'run', side_effect=command),
                patch.object(updates.subprocess, 'run', return_value=Mock(returncode=0)))

    def test_mutable_update_simulates_no_removals_and_verifies_before_success(self):
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            contexts = self.fixture_install(directory)
            values = [stack.enter_context(context) for context in contexts]
            updates.install(self.release())
            commands = values[7].call_args_list
            self.assertTrue(any(call.args[:4] == ('apt-get', '-s', '--no-remove', 'install') for call in commands))
            self.assertTrue((Path(directory) / 'state/applied.json').is_file())

    def test_immutable_update_routes_to_staging_without_live_apt(self):
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            values = [stack.enter_context(context) for context in self.fixture_install(directory, immutable=True)]
            updates.install(self.release())
            calls = values[7].call_args_list
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0].args[:2], ('/usr/bin/aphrodite-system', 'release'))
            self.assertTrue((Path(directory) / 'state/pending.json').is_file())
            self.assertFalse((Path(directory) / 'state/applied.json').exists())

    def test_downgrades_never_reach_apt(self):
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            values = [stack.enter_context(context) for context in self.fixture_install(directory, old='0.4')]
            values[8].return_value.returncode = 1
            with self.assertRaises(ValueError):
                updates.install(self.release())
            values[7].assert_not_called()

    def test_apt_failure_never_records_success(self):
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            values = [stack.enter_context(context) for context in self.fixture_install(directory)]
            values[7].side_effect = subprocess.CalledProcessError(1, 'apt-get')
            with self.assertRaises(subprocess.CalledProcessError):
                updates.install(self.release())
            self.assertFalse((Path(directory) / 'state/applied.json').exists())


class LoginTests(unittest.TestCase):
    def test_installed_toggle_replaces_live_login_and_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'etc/sddm.conf'
            config.parent.mkdir()
            config.write_text('[Theme]\nCurrent=breeze\n[Autologin]\nUser=live\nRelogin=true\n')
            login.configure(root, 'sean', automatic=False)
            self.assertIn('User=\n', config.read_text())
            self.assertIn('Relogin=false', config.read_text())
            self.assertIn('Current=breeze', config.read_text())
            login.configure(root, 'sean', automatic=True, session='aphrodite-os-gaming.desktop')
            self.assertIn('User=sean', config.read_text())
            self.assertIn('Session=aphrodite-os-gaming.desktop', config.read_text())
            self.assertNotIn('password', config.read_text().lower())

    def test_live_policy_has_explicit_session_and_relogin(self):
        with tempfile.TemporaryDirectory() as directory:
            login.configure(directory, 'live', automatic=True, live=True)
            data = (Path(directory) / 'etc/sddm.conf').read_text()
            for text in ('User=live', 'Session=plasma.desktop', 'Relogin=true'):
                self.assertIn(text, data)

    def test_invalid_login_options_cannot_inject_config(self):
        for kwargs in ({'username': 'sean\nUser=root'}, {'username': 'sean', 'automatic': 'false'},
                       {'username': 'sean', 'session': '../bad.desktop'}):
            with self.assertRaises(ValueError):
                login.configure('/unused', **kwargs)


if __name__ == '__main__':
    unittest.main()
