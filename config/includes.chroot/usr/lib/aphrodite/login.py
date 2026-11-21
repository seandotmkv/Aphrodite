"""SDDM login policy shared by live-config and the terminal installer."""
from configparser import ConfigParser
from pathlib import Path
import re


def configure(root, username, automatic=False, session='plasma.desktop', live=False):
    if type(automatic) is not bool or type(live) is not bool:
        raise ValueError('Login choices must be boolean')
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', username):
        raise ValueError('Invalid login username')
    if session not in ('plasma.desktop', 'aphrodite-os-gaming.desktop'):
        raise ValueError('Unknown login session')
    root = Path(root)
    path = root / 'etc/sddm.conf'
    parser = ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(path)
    if not parser.has_section('Autologin'):
        parser.add_section('Autologin')
    parser['Autologin'].update(User=username if automatic else '', Session=session,
                               Relogin='true' if live else 'false')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as stream:
        parser.write(stream, space_around_delimiters=False)
    path.chmod(0o644)
    # The compatibility file above wins over all drop-ins. Remove our old
    # live-only drop-in, never unrelated administrator/desktop configuration.
    (root / 'etc/sddm.conf.d/99-live.conf').unlink(missing_ok=True)


def live_session():
    import os
    import pwd
    if not Path('/run/live/medium').is_dir():
        raise ValueError('This operation is restricted to the live environment')
    account = pwd.getpwnam('live')
    configure('/', 'live', automatic=True, live=True)
    # A live session needs no password at boot, after idle, or after resume.
    # This file goes only into the ephemeral live home, never /etc/skel.
    directory = Path(account.pw_dir) / '.config'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'kscreenlockerrc'
    path.write_text('[Daemon]\nAutolock=false\nLockOnResume=false\n')
    os.chown(directory, account.pw_uid, account.pw_gid)
    os.chown(path, account.pw_uid, account.pw_gid)


if __name__ == '__main__':
    import sys
    if sys.argv[1:] != ['--live']:
        raise SystemExit('Use --live through live-config')
    live_session()
