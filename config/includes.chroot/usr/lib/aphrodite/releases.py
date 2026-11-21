"""Check and explicitly install Aphrodite packages from public GitHub Releases.

Trust: HTTPS and the configured GitHub repository owner's release assets.
Digests detect corruption; they are not independent publisher signatures.
No branch archive, release body, or downloaded shell script is executed.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = 'seandotmkv/Aphrodite'
API = 'https://api.github.com/repos/' + REPOSITORY + '/releases/latest'
MANIFEST = 'aphrodite-update.json'
STATE = Path('/var/lib/aphrodite/updates')
TRANSACTIONAL = Path('/etc/aphrodite/transactional.json')
TAG = re.compile(r'[A-Za-z0-9][A-Za-z0-9._+\-]{0,95}')
VERSION = re.compile(r'[0-9][A-Za-z0-9.+:~\-]{0,95}')
PACKAGE = re.compile(r'aphrodite-[a-z0-9][a-z0-9+\-]{0,62}')
DIGEST = re.compile(r'sha256:([a-f0-9]{64})')
MAX_ASSET = 256 * 1024**2


class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        host = parsed.hostname or ''
        if parsed.scheme != 'https' or not (host in ('github.com', 'api.github.com') or
                                           host.endswith('.githubusercontent.com')):
            raise ValueError('Release download redirected outside GitHub HTTPS')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, limit, etag=None, destination=None):
    headers = {'User-Agent': 'Aphrodite-OS-release-updater', 'Accept': 'application/vnd.github+json'}
    if etag:
        headers['If-None-Match'] = etag
    request = urllib.request.Request(url, headers=headers)
    try:
        response = urllib.request.build_opener(Redirects()).open(request, timeout=25)
    except urllib.error.HTTPError as error:
        if error.code == 304:
            return None, etag
        raise
    with response:
        total, data, digest = 0, bytearray(), hashlib.sha256()
        import time
        deadline = time.monotonic() + (600 if destination else 45)
        while True:
            block = response.read(65536)
            if not block:
                break
            total += len(block)
            if total > limit or time.monotonic() > deadline:
                raise ValueError('Release download exceeded its size or time limit')
            digest.update(block)
            if destination:
                destination.write(block)
            else:
                data.extend(block)
        return (digest.hexdigest() if destination else bytes(data)), response.headers.get('ETag')


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, indent=2)
        stream.write('\n')
    try:
        temporary.chmod(0o644)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def release_info(data):
    if not isinstance(data, dict) or data.get('draft') or data.get('prerelease'):
        raise ValueError('Expected a published stable release')
    if type(data.get('id')) is not int or not TAG.fullmatch(data.get('tag_name', '')):
        raise ValueError('Invalid release identity')
    assets = data.get('assets', [])
    if not isinstance(assets, list) or len(assets) > 100:
        raise ValueError('Too many release assets')
    names = set()
    for asset in assets:
        name = asset.get('name', '')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+\-]{0,160}', name) or name in names:
            raise ValueError('Invalid or duplicate release asset')
        names.add(name)
    return data


def fingerprint(release):
    items = sorted((a['name'], a.get('digest'), a.get('size'), a.get('updated_at'))
                   for a in release['assets'])
    return hashlib.sha256(json.dumps([release['id'], release['tag_name'], items], sort_keys=True).encode()).hexdigest()


def cached_release(cache):
    path = cache / 'release.json'
    try:
        old = json.loads(path.read_text())
    except (OSError, ValueError):
        old = {}
    raw, etag = fetch(API, 1024**2, old.get('etag'))
    release = release_info(json.loads(raw) if raw is not None else old['release'])
    atomic(path, {'etag': etag, 'release': release})
    return release


def asset_info(release, name):
    asset = next((a for a in release['assets'] if a['name'] == name), None)
    if not asset or asset.get('state') != 'uploaded' or not DIGEST.fullmatch(asset.get('digest') or ''):
        raise ValueError('Missing uploaded asset or GitHub SHA256 digest: ' + name)
    url = asset.get('browser_download_url', '')
    prefix = 'https://github.com/' + REPOSITORY + '/releases/download/'
    parts = urllib.parse.urlsplit(url)
    if not url.startswith(prefix) or parts.query or parts.fragment:
        raise ValueError('Asset URL does not belong to the configured repository')
    if type(asset.get('size')) is not int or not 0 < asset['size'] <= MAX_ASSET:
        raise ValueError('Release asset exceeds the supported size')
    return asset


def download(release, name, directory):
    asset = asset_info(release, name)
    if name == MANIFEST and asset['size'] > 128 * 1024:
        raise ValueError('Update manifest is too large')
    path = directory / name
    with path.open('xb') as stream:
        actual, _ = fetch(asset['browser_download_url'], asset['size'], destination=stream)
    if path.stat().st_size != asset['size'] or 'sha256:' + actual != asset['digest']:
        raise ValueError('GitHub release asset digest mismatch: ' + name)
    return path


def checked_manifest(value):
    if (not isinstance(value, dict) or value.get('schema') != 1 or value.get('os') != 'aphrodite'
            or value.get('series') != '0' or value.get('architecture') != 'amd64'):
        raise ValueError('This release is not an Aphrodite OS 0 amd64 package update')
    packages = value.get('packages')
    if not isinstance(packages, list) or not 1 <= len(packages) <= 32:
        raise ValueError('The update needs 1 to 32 Aphrodite packages')
    names, assets = set(), set()
    for item in packages:
        if not isinstance(item, dict):
            raise ValueError('Invalid package record')
        if not PACKAGE.fullmatch(item.get('name', '')) or item['name'] in names:
            raise ValueError('Only distinct Aphrodite packages may be shipped in this channel')
        if not VERSION.fullmatch(item.get('version', '')):
            raise ValueError('Invalid Debian package version')
        if not re.fullmatch(r'aphrodite-[A-Za-z0-9._+\-]+\.deb', item.get('asset', '')) or item['asset'] in assets:
            raise ValueError('Invalid or duplicate package asset')
        if not re.fullmatch(r'[a-f0-9]{64}', item.get('sha256', '')):
            raise ValueError('Missing package checksum')
        names.add(item['name']); assets.add(item['asset'])
    return value


def run(*args, timeout=1800, capture=False):
    result = subprocess.run(list(map(os.fspath, args)), check=True, timeout=timeout,
                            text=True, capture_output=capture,
                            env=dict(os.environ, LC_ALL='C', DEBIAN_FRONTEND='noninteractive'))
    return result.stdout.strip() if capture else None


def installed_version(name):
    try:
        status = run('dpkg-query', '-W', '-f=${db:Status-Status}\t${Version}', name, capture=True, timeout=20)
        state, version = status.split('\t')
        return version if state == 'installed' else None
    except (ValueError, subprocess.CalledProcessError):
        return None


def verify_package(path, item):
    fields = {key: run('dpkg-deb', '-f', path, key, capture=True, timeout=30)
              for key in ('Package', 'Version', 'Architecture')}
    if fields['Package'] != item['name'] or fields['Version'] != item['version'] or fields['Architecture'] not in ('all', 'amd64'):
        raise ValueError('Debian package metadata differs from manifest: ' + item['asset'])
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != item['sha256']:
        raise ValueError('Manifest package checksum mismatch')


def require_target():
    if Path('/run/live/medium').is_dir():
        raise ValueError('Install updates in the installed OS; rebuild the ISO to update the live image')
    if 'ID=aphrodite' not in Path('/etc/os-release').read_text().splitlines():
        raise ValueError('This updater is for an installed Aphrodite OS system')
    if os.geteuid():
        raise ValueError('Run installation with sudo aphrodite-update install')


@contextmanager
def update_lock():
    import fcntl
    with open('/run/lock/aphrodite-update.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def install(release):
    require_target()
    STATE.mkdir(parents=True, exist_ok=True)
    with update_lock():
        with tempfile.TemporaryDirectory(prefix='download-', dir=STATE) as directory:
            directory = Path(directory)
            manifest_path = download(release, MANIFEST, directory)
            if manifest_path.stat().st_size > 128 * 1024:
                raise ValueError('Update manifest is too large')
            manifest = checked_manifest(json.loads(manifest_path.read_text()))
            files = []
            for item in manifest['packages']:
                path = download(release, item['asset'], directory)
                verify_package(path, item)
                old = installed_version(item['name'])
                if old == item['version']:
                    continue
                if old and subprocess.run(['dpkg', '--compare-versions', item['version'], 'gt', old]).returncode:
                    raise ValueError('Refusing package downgrade: ' + item['name'])
                files.append(path)
            result = {'repository': REPOSITORY, 'tag': release['tag_name'], 'fingerprint': fingerprint(release),
                      'packages': manifest['packages'], 'time': datetime.now(timezone.utc).isoformat()}
            if files:
                if TRANSACTIONAL.is_file():
                    # A staging failure never upgrades the active read-only root.
                    receipt = directory / 'receipt.json'
                    atomic(receipt, result)
                    run('/usr/bin/aphrodite-system', 'release', receipt, *files, timeout=7200)
                    # Keep pending separate: do not claim a deployment was booted.
                    atomic(STATE / 'pending.json', result)
                    print('GitHub release staged. Reboot, then check aphrodite-system status.')
                    return
                run('apt-get', '-o', 'DPkg::Lock::Timeout=45', 'update', timeout=300)
                run('apt-get', '-s', '--no-remove', 'install', *files, timeout=180)
                run('apt-get', '-y', '--no-remove', 'install', *files, timeout=3600)
                run('apt-get', 'check', timeout=180)
                for item in manifest['packages']:
                    if installed_version(item['name']) != item['version']:
                        raise ValueError('Post-update package verification failed: ' + item['name'])
            atomic(STATE / 'applied.json', result)
            print('Release packages are installed:', release['tag_name'])


def check(release, cache, notify=False):
    identity = fingerprint(release)
    try:
        current = json.loads((STATE / 'applied.json').read_text()).get('fingerprint')
    except (OSError, ValueError):
        current = None
    available = identity != current
    ready = any(a['name'] == MANIFEST for a in release['assets'])
    print('GitHub release:', release['tag_name'])
    print('https://github.com/' + REPOSITORY + '/releases/tag/' + urllib.parse.quote(release['tag_name'], safe=''))
    print(('Release changed or available.' if available else 'Installed release is current.') +
          (' Package update assets present.' if ready else ' No package update manifest; this may be an ISO/source release.'))
    notified = cache / 'notified.json'
    try:
        previous = json.loads(notified.read_text()).get('fingerprint')
    except (OSError, ValueError):
        previous = None
    if notify and available and identity != previous:
        body = 'Run sudo aphrodite-update install.' if ready else 'New release files are available on GitHub.'
        run('notify-send', '--app-name=Aphrodite OS', '--icon=aphrodite',
            'Aphrodite release ' + release['tag_name'], body, timeout=10)
        atomic(notified, {'fingerprint': identity})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'install'), nargs='?', default='check')
    parser.add_argument('--notify', action='store_true', help='Notify once per new release/asset set')
    args = parser.parse_args(argv)
    if args.notify and Path('/run/live/medium').is_dir():
        return 0
    if args.action == 'install':
        require_target()
    cache = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'aphrodite-updates'
    if args.action == 'install':
        cache = STATE / 'metadata'
    cache.mkdir(parents=True, exist_ok=True)
    try:
        release = cached_release(cache)
        if args.action == 'install':
            install(release)
        else:
            check(release, cache, args.notify)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            print('No published stable release is available at ' + REPOSITORY + '.')
            return 0 if args.action == 'check' else 1
        print('GitHub check failed (HTTP ' + str(error.code) + '). Retry later.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print('Release update stopped:', error, file=sys.stderr)
        print('Logs: journalctl --user -u aphrodite-update.service or /var/log/aphrodite-update.log', file=sys.stderr)
        raise SystemExit(1)
