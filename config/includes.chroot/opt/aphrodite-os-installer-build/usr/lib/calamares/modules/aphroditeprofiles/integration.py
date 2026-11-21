"""Verified launcher resolution, installation manifest and first-login pin policy."""
from configparser import ConfigParser, Error as ConfigError
import json
from pathlib import Path
import re
import tempfile

from selection import APPS

STATE = 'var/lib/aphrodite-os'
DESKTOP_ID = re.compile(r'[A-Za-z0-9_.+\-]+\.desktop')
FOLDERS = ('usr/share/applications', 'usr/local/share/applications',
           'var/lib/flatpak/exports/share/applications')


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, indent=2)
        stream.write('\n')
    try:
        temporary.chmod(0o644)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def desktop_file(root, identity):
    if not DESKTOP_ID.fullmatch(identity):
        raise ValueError('Invalid desktop entry identity')
    root = Path(root).resolve()
    for folder in FOLDERS:
        path = root / folder / identity
        for _ in range(12):
            if not path.is_symlink():
                break
            link = path.readlink()
            path = root / str(link).lstrip('/') if link.is_absolute() else path.parent / link
        if not path.resolve().is_relative_to(root):
            continue
        if path.is_file():
            data = ConfigParser(interpolation=None, strict=False)
            try:
                data.read(path)
            except (ConfigError, UnicodeError, OSError):
                continue
            if (data.get('Desktop Entry', 'Type', fallback='') == 'Application'
                    and data.get('Desktop Entry', 'Exec', fallback='').strip()
                    and data.get('Desktop Entry', 'Hidden', fallback='false') != 'true'):
                return path
    return None


def launcher(key, method):
    app = APPS[key]
    if method == 'flatpak':
        return app['methods'][method]['ref'] + '.desktop'
    if method == 'source':
        return key + '.desktop'
    return app.get('launcher') or None


class Manifest:
    def __init__(self, root, plan):
        self.path = Path(root) / STATE / 'install-manifest.json'
        self.value = {'version': 1, 'selection': plan, 'applications': {}}
        self.value['gaming_session'] = {'requested': plan['session'],
                                       'status': 'not-requested' if plan['session'] == 'off' else 'waiting',
                                       'reason': None}
        for key, method in plan['apps'].items():
            app, spec = APPS[key], APPS[key]['methods'][method]
            self.value['applications'][key] = {
                'name': app['name'], 'selected': True, 'method': method,
                'source': spec.get('source', ''), 'packages': spec.get('packages', []),
                'repository': app.get('source'), 'commit': spec.get('commit'),
                'dependencies': spec.get('packages', []), 'optional_information': app.get('extra', []),
                'flatpak_ref': spec.get('ref'), 'launcher': launcher(key, method),
                'status': 'waiting', 'reason': None,
                'verification': 'package status plus available executable/desktop or Flatpak deployment checks',
            }
        self.save()

    def save(self):
        atomic_json(self.path, self.value)

    def result(self, key, status, reason=None):
        self.value['applications'][key].update(status=status, reason=reason)
        self.save()


def write_pins(root, plan, manifest):
    root = Path(root)
    pins = plan.get('pins', {'enabled': True, 'core': True, 'apps': []})
    identities = []
    if pins.get('enabled', True):
        if pins.get('core', True):
            identities.extend(['org.gnome.Nautilus.desktop', 'com.raggesilver.BlackBox.desktop',
                               'org.gnome.Software.desktop', 'systemsettings.desktop'])
        wanted = ([plan['browser']] if plan.get('browser') else []) + pins.get('apps', [])
        for key in wanted:
            result = manifest.value['applications'].get(key, {})
            if result.get('status') not in ('complete', 'already installed'):
                continue
            identity = result.get('launcher')
            if identity:
                identities.append(identity)
    identities = list(dict.fromkeys(identity for identity in identities if desktop_file(root, identity)))
    path = root / 'etc/xdg/aphrodite-os-taskbar.conf'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[Launchers]\nenabled=true\nurls=' + ','.join('applications:' + value for value in identities) + '\n')
    atomic_json(root / STATE / 'verified-taskbar.json', {'version': 1, 'launchers': identities})
    return identities
