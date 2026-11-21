"""Release identity, application policy and immutable layout tests without disks."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import os
import json
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'config/includes.chroot/opt/aphrodite-os-installer-build'
MODULES = PAYLOAD / 'usr/lib/calamares/modules/aphroditeprofiles'
sys.path.insert(0, str(MODULES))
from selection import validate
from integration import Manifest, write_pins, desktop_file

spec = spec_from_file_location('transactional_contracts', ROOT / 'config/includes.chroot/usr/lib/aphrodite/transactional.py')
transactional = module_from_spec(spec)
spec.loader.exec_module(transactional)


class ApplicationPolicyTests(unittest.TestCase):
    def test_explicit_no_browser_is_preserved_and_invalid_primary_rejected(self):
        plan = validate({'version': 1, 'apps': {}, 'browser': None, 'session': 'off'})
        self.assertIsNone(plan['browser'])
        self.assertEqual(plan['apps'], {})
        with self.assertRaises(ValueError):
            validate({'version': 1, 'apps': {'firefox': 'apt'}, 'browser': None, 'session': 'off'})

    def test_desktop_only_has_no_implicit_gaming_selection(self):
        plan = validate({'version': 1, 'apps': {'brave': 'apt'}, 'browser': 'brave', 'session': 'off'})
        self.assertNotIn('steam', plan['apps'])
        self.assertNotIn('gamescope', plan['apps'])

    def test_pin_requests_must_be_selected_and_are_deduplicated(self):
        value = {'version': 1, 'apps': {'brave': 'apt'}, 'browser': 'brave', 'session': 'off',
                 'pins': {'enabled': True, 'core': False, 'apps': ['brave', 'brave']}}
        self.assertEqual(validate(value)['pins']['apps'], ['brave'])
        value['pins']['apps'] = ['steam']
        with self.assertRaises(ValueError):
            validate(value)

    def test_only_verified_apps_are_pinned_and_bootstrap_is_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apps = root / 'usr/share/applications'
            apps.mkdir(parents=True)
            for identity in ('brave-browser.desktop', 'steam.desktop', 'firefox-esr.desktop'):
                (apps / identity).write_text('[Desktop Entry]\nType=Application\nExec=/usr/bin/example\n')
            plan = validate({'version': 1, 'apps': {'brave': 'apt', 'steam': 'apt', 'firefox': 'apt'},
                             'browser': 'brave', 'session': 'off',
                             'pins': {'enabled': True, 'core': False, 'apps': ['brave', 'steam', 'firefox']}})
            manifest = Manifest(root, plan)
            manifest.result('brave', 'complete')
            manifest.result('steam', 'first-run-required')
            manifest.result('firefox', 'failed', 'offline')
            self.assertEqual(write_pins(root, plan, manifest), ['brave-browser.desktop'])
            data = json.loads(manifest.path.read_text())
            self.assertEqual(data['applications']['firefox']['reason'], 'offline')
            self.assertNotIn('password', manifest.path.read_text())

    def test_invalid_desktop_paths_cannot_escape_target(self):
        with tempfile.TemporaryDirectory() as directory:
            for invalid in ('../../secret.desktop', '/etc/passwd', 'file:///tmp/x.desktop'):
                with self.assertRaises(ValueError):
                    desktop_file(directory, invalid)


class ReleaseIdentityTests(unittest.TestCase):
    def test_os_identity_and_iso_naming(self):
        identity = (ROOT / 'config/hooks/normal/0600-aphrodite-os-identity.hook.chroot').read_text()
        for line in ('NAME="Aphrodite OS"', 'PRETTY_NAME="Aphrodite OS"', 'ID=aphrodite', 'ID_LIKE=debian'):
            self.assertIn(line, identity.splitlines())
        self.assertIn('${LB_IMAGE_NAME}-${LB_ARCHITECTURE}.iso', (ROOT / 'auto/build').read_text())

    def test_firefox_is_live_only_and_flatpak_manager_is_core(self):
        base = (ROOT / 'config/package-lists/applications.list.chroot').read_text().splitlines()
        self.assertNotIn('firefox-esr', base)
        self.assertIn('gnome-software-plugin-flatpak', base)
        self.assertIn('firefox-esr', (ROOT / 'config/package-lists/live-browser.list.chroot_live').read_text())


class TransactionalLayoutTests(unittest.TestCase):
    def state(self):
        return {'version': 1, 'system_uuid': '11111111-2222-3333-4444-555555555555',
                'boot_uuid': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
                'deployments': ['initial', 'd20261121'], 'default': 'd20261121'}

    def test_grub_keeps_previous_deployment_and_explicit_read_only_root(self):
        text = transactional.grub_entries(self.state())
        self.assertIn("--id 'aphrodite-d20261121'", text.splitlines()[0])
        self.assertIn('rollback: initial', text)
        self.assertIn(' ro rootfstype=btrfs ', text)
        self.assertIn('subvol=@deployments/d20261121/root', text)
        self.assertIn('aphrodite.deployment=d20261121', text)

    def test_boot_metadata_rejects_injection_and_missing_default(self):
        for state in (dict(self.state(), default='missing'), dict(self.state(), system_uuid="x'; reboot"),
                      dict(self.state(), deployments=['initial', '../escape']), dict(self.state(), deployments=[])):
            with self.assertRaises(ValueError):
                transactional.grub_entries(state)

    def test_writable_state_is_separate_and_swap_is_outside_root_snapshot(self):
        state = self.state()
        text = transactional.fstab(state['system_uuid'], state['boot_uuid'], swap=True)
        self.assertIn('/ btrfs ro,subvol=@deployments/initial/root', text)
        self.assertIn('/@deployments/initial/etc /etc none bind', text)
        self.assertIn('/@deployments/initial/var /var none bind', text)
        self.assertIn('/@shared/flatpak /var/lib/flatpak none bind', text)
        self.assertIn('/@shared/home /home none bind', text)
        self.assertIn('/@shared/swap/swapfile none swap', text)
        self.assertNotIn('/swapfile none swap', text.replace('/.aphrodite-state/@shared/swap/swapfile none swap', ''))


@unittest.skipUnless(os.name == 'posix', 'Linux package integration module')
class MultiarchVerificationTests(unittest.TestCase):
    def test_native_and_foreign_architectures_are_verified_individually(self):
        from test_package_selection import executor
        target = object.__new__(executor.Target)
        target.command = Mock(return_value='libvulkan1\tamd64\tinstalled\nlibvulkan1\ti386\tinstalled\n')
        self.assertTrue(target.installed('libvulkan1'))
        self.assertTrue(target.installed('libvulkan1:i386'))
        target.command.return_value = 'libvulkan1\ti386\tinstalled\n'
        self.assertFalse(target.installed('libvulkan1'))
        target.command.return_value = 'steam-installer\tall\tinstalled\n'
        self.assertTrue(target.installed('steam-installer'))
        target.command.return_value = 'libvulkan1\ti386\thalf-configured\n'
        self.assertFalse(target.installed('libvulkan1:i386'))


if __name__ == '__main__':
    unittest.main()
