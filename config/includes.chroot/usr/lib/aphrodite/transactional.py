"""Development Btrfs deployments: staged Debian transactions and GRUB rollback.

No automatic conversion of existing mutable systems. Activation is restricted
to the explicit development installation path pending VM qualification.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

IDENTITY = re.compile(r'[a-z0-9][a-z0-9-]{0,63}')
UUID = re.compile(r'[A-Fa-f0-9-]{8,64}')
SHARED = {'home': 'home', 'root': 'root', 'log': 'var/log', 'cache': 'var/cache',
          'tmp': 'var/tmp', 'flatpak': 'var/lib/flatpak',
          'containers': 'var/lib/containers', 'docker': 'var/lib/docker'}
CONFIG = Path('/etc/aphrodite/transactional.json')
BOOT_STATE = Path('/boot/aphrodite/deployments.json')


def checked(value):
    if not isinstance(value, dict) or value.get('version') != 1:
        raise ValueError('Unknown transactional deployment format')
    for key in ('system_uuid', 'boot_uuid'):
        if not UUID.fullmatch(value.get(key, '')):
            raise ValueError('Invalid deployment filesystem identity')
    entries = value.get('deployments', [])
    if not entries or len(set(entries)) != len(entries) or any(not IDENTITY.fullmatch(x) for x in entries):
        raise ValueError('Invalid deployment list')
    if value.get('default') not in entries:
        raise ValueError('Default deployment is missing')
    return value


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        json.dump(data, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    try:
        temp.chmod(0o644)
        temp.replace(path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temp.unlink(missing_ok=True)


def grub_entries(data):
    data = checked(data)
    ordered = [data['default']] + [x for x in data['deployments'] if x != data['default']]
    output = []
    for index, name in enumerate(ordered):
        title = 'Aphrodite OS' + (' (rollback: ' + name + ')' if index else '')
        output += [f"menuentry '{title}' --id 'aphrodite-{name}' {{",
                   f"  search --no-floppy --fs-uuid --set=root {data['boot_uuid']}",
                   f"  linux /aphrodite/{name}/vmlinuz root=UUID={data['system_uuid']} ro rootfstype=btrfs rootflags=subvol=@deployments/{name}/root aphrodite.deployment={name}",
                   f"  initrd /aphrodite/{name}/initrd.img", '}']
    return '\n'.join(output) + '\n'


def run(*args, input_text=None, timeout=1800):
    print('$', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(os.fspath, args)), input=input_text, text=True, check=True,
                   timeout=timeout, env=dict(os.environ, LC_ALL='C', DEBIAN_FRONTEND='noninteractive'))


def output(*args):
    return subprocess.check_output(list(map(os.fspath, args)), text=True, timeout=20).strip()


def initial_layout(command, top):
    (top / '@deployments/initial').mkdir(parents=True)
    command('btrfs', 'subvolume', 'create', top / '@deployments/initial/root')
    command('btrfs', 'subvolume', 'create', top / '@shared')
    for name in SHARED:
        (top / '@shared' / name).mkdir(parents=True, exist_ok=True)
    (top / '@shared/swap').mkdir(exist_ok=True)


def fstab(system_uuid, boot_uuid, deployment='initial', swap=False, efi_uuid=None):
    if not UUID.fullmatch(system_uuid) or not UUID.fullmatch(boot_uuid) or not IDENTITY.fullmatch(deployment):
        raise ValueError('Invalid immutable storage identity')
    lines = [f'UUID={system_uuid} / btrfs ro,subvol=@deployments/{deployment}/root 0 0',
             f'UUID={system_uuid} /.aphrodite-state btrfs rw,subvolid=5,nosuid,nodev 0 0',
             f'UUID={boot_uuid} /boot ext4 defaults 0 2',
             f'/.aphrodite-state/@deployments/{deployment}/etc /etc none bind 0 0',
             f'/.aphrodite-state/@deployments/{deployment}/var /var none bind 0 0']
    for name, location in SHARED.items():
        lines.append(f'/.aphrodite-state/@shared/{name} /{location} none bind 0 0')
    lines.append('tmpfs /tmp tmpfs mode=1777,nosuid,nodev 0 0')
    if efi_uuid:
        if not UUID.fullmatch(efi_uuid):
            raise ValueError('Invalid EFI filesystem identity')
        lines.append(f'UUID={efi_uuid} /boot/efi vfat umask=0077 0 2')
    if swap:
        lines.append('/.aphrodite-state/@shared/swap/swapfile none swap sw 0 0')
    return '\n'.join(lines) + '\n'


def publish_kernel(command, root, name):
    kernels = list((root / 'boot').glob('vmlinuz-*'))
    if not kernels:
        raise ValueError('No kernel available for deployment')
    # Debian kernel names contain numeric ABI/version components.
    key = lambda p: [int(part) if part.isdecimal() else part for part in re.split(r'(\d+)', p.name)]
    kernel = sorted(kernels, key=key)[-1]
    initrd = root / 'boot' / ('initrd.img-' + kernel.name.removeprefix('vmlinuz-'))
    if not initrd.is_file():
        raise ValueError('Matching deployment initramfs is missing')
    destination = root / 'boot/aphrodite' / name
    destination.mkdir(parents=True, exist_ok=False)
    for source, filename in ((kernel, 'vmlinuz'), (initrd, 'initrd.img')):
        shutil.copyfile(source, destination / filename)
    command('sync', '-f', destination)
    return kernel.name.removeprefix('vmlinuz-')


def seal_initial(command, root, devices, settings):
    root = Path(root)
    top = root / '.aphrodite-state'
    if not os.path.ismount(root) or not os.path.ismount(top):
        raise ValueError('Expected the private mounted installation and Btrfs top level')
    # Only the immutable variant disables direct Debian updates in Software.
    # A scoped removal must not pull out the software manager or core packages.
    plan = output('chroot', root, 'apt-get', '-s', '--no-auto-remove', 'purge', 'gnome-software-plugin-deb')
    removals = {line.split()[1].split(':')[0] for line in plan.splitlines() if line.startswith(('Remv ', 'Purg '))}
    if removals - {'gnome-software-plugin-deb'}:
        raise ValueError('Debian software plugin removal would remove other packages')
    if removals:
        command('chroot', root, 'apt-get', '-y', '--no-download', '--no-auto-remove', 'purge', 'gnome-software-plugin-deb')
    system_uuid = output('blkid', '-p', '-s', 'UUID', '-o', 'value', devices['root'])
    boot_uuid = output('blkid', '-p', '-s', 'UUID', '-o', 'value', devices['boot'])
    config = {'version': 1, 'system_uuid': system_uuid, 'boot_uuid': boot_uuid,
              'deployment': 'initial', 'development': True}
    atomic_json(root / 'etc/aphrodite/transactional.json', config)
    # Both /etc and /var are versioned with the OS. Shared user/application data
    # are separate, so rollback does not replace homes or Flatpak deployments.
    for name in ('etc', 'var'):
        target = top / '@deployments/initial' / name
        command('btrfs', 'subvolume', 'create', target)
        command('cp', '-a', '--reflink=auto', str(root / name) + '/.', target)
    for name, location in SHARED.items():
        source, destination = root / location, top / '@shared' / name
        source.mkdir(parents=True, exist_ok=True)
        command('cp', '-a', '--reflink=auto', str(source) + '/.', destination)
    # Avoid retaining hidden copies of shared application data in deployment
    # roots and /var snapshots. The fixed paths are checked before removal.
    for name, location in SHARED.items():
        if not location.startswith('var/'):
            continue
        for source in (root / location, top / '@deployments/initial/var' / location[4:]):
            if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
                raise ValueError('Shared-data source escapes the reviewed target')
            mode = source.stat().st_mode & 0o7777
            shutil.rmtree(source)
            source.mkdir(mode=mode, parents=True)
    for name in ('etc', 'var'):
        command('mount', '--bind', top / '@deployments/initial' / name, root / name)
    for name, location in SHARED.items():
        (root / location).mkdir(parents=True, exist_ok=True)
        command('mount', '--bind', top / '@shared' / name, root / location)
    config['kernel_version'] = publish_kernel(command, root, 'initial')
    atomic_json(root / 'etc/aphrodite/transactional.json', config)
    state = {'version': 1, 'system_uuid': system_uuid, 'boot_uuid': boot_uuid,
             'deployments': ['initial'], 'default': 'initial'}
    atomic_json(root / 'boot/aphrodite/deployments.json', checked(state))
    command('chroot', root, 'update-grub')
    command('chroot', root, 'grub-script-check', '/boot/grub/grub.cfg')
    command('btrfs', 'property', 'set', '-ts', root, 'ro', 'true')
    if output('btrfs', 'property', 'get', '-ts', root, 'ro') != 'ro=true':
        raise ValueError('The deployment did not become read-only')


@contextmanager
def mounted(source, target, *options):
    target.mkdir(parents=True, exist_ok=True)
    run('mount', *options, source, target)
    try:
        yield target
    finally:
        run('umount', '--recursive', target)


def current_configuration():
    if not CONFIG.is_file():
        raise ValueError('This is a mutable installation; there is no automatic in-place conversion')
    config = json.loads(CONFIG.read_text())
    if config.get('version') != 1 or not IDENTITY.fullmatch(config.get('deployment', '')):
        raise ValueError('Invalid running deployment configuration')
    cmdline = Path('/proc/cmdline').read_text().split()
    if 'aphrodite.deployment=' + config['deployment'] not in cmdline:
        raise ValueError('The system was not booted through its transactional GRUB entry')
    data = checked(json.loads(BOOT_STATE.read_text()))
    if any(config[key] != data[key] for key in ('system_uuid', 'boot_uuid')):
        raise ValueError('Deployment storage identities differ')
    if output('findmnt', '-n', '-o', 'FSTYPE', '--target', '/') != 'btrfs':
        raise ValueError('The running deployment is not Btrfs')
    if output('findmnt', '-n', '-o', 'UUID', '--target', '/') != data['system_uuid']:
        raise ValueError('Running root filesystem differs from deployment metadata')
    if output('findmnt', '-n', '-o', 'UUID', '--mountpoint', '/boot') != data['boot_uuid']:
        raise ValueError('Mounted boot filesystem differs from deployment metadata')
    if output('btrfs', 'property', 'get', '-ts', '/', 'ro') != 'ro=true':
        raise ValueError('The active base is not read-only; refuse a transactional update')
    return config, data


def activate(data):
    # GRUB publication is the activation point. Root images already exist and
    # are read-only; no running root is ever upgraded in place.
    data = checked(data)
    for name in data['deployments']:
        for filename in ('vmlinuz', 'initrd.img'):
            if not (Path('/boot/aphrodite') / name / filename).is_file():
                raise ValueError('A deployment boot artifact is missing')
    atomic_json(BOOT_STATE, data)
    temporary = Path('/boot/grub/grub.cfg.aphrodite-next')
    run('grub-mkconfig', '-o', temporary)
    run('grub-script-check', temporary)
    run('sync', '-f', temporary)
    temporary.replace('/boot/grub/grub.cfg')
    run('sync', '-f', '/boot/grub')


def stage(action, packages):
    config, state = current_configuration()
    current = config['deployment']
    name = datetime.now(timezone.utc).strftime('d%Y%m%d%H%M%S') + '-' + os.urandom(3).hex()
    if not os.path.ismount('/boot'):
        raise ValueError('The dedicated boot filesystem is not mounted')
    with tempfile.TemporaryDirectory(prefix='aphrodite-transaction-', dir='/run') as directory:
        base = Path(directory)
        device = '/dev/disk/by-uuid/' + state['system_uuid']
        with mounted(device, base / 'volume', '-t', 'btrfs', '-o', 'rw,subvolid=5') as volume:
            destination = volume / '@deployments' / name
            destination.mkdir()
            for part in ('root', 'etc', 'var'):
                run('btrfs', 'subvolume', 'snapshot', volume / '@deployments' / current / part,
                    destination / part)
            try:
                with mounted(device, base / 'target', '-t', 'btrfs', '-o', f'rw,subvol=@deployments/{name}/root') as root:
                    version = config.get('kernel_version')
                    if not version or '/' in version or not re.fullmatch(r'[A-Za-z0-9.+_\-]+', version):
                        raise ValueError('Invalid running kernel identity')
                    (root / 'boot').mkdir(exist_ok=True)
                    shutil.copyfile(Path('/boot/aphrodite') / current / 'vmlinuz', root / 'boot' / ('vmlinuz-' + version))
                    shutil.copyfile(Path('/boot/aphrodite') / current / 'initrd.img', root / 'boot' / ('initrd.img-' + version))
                    # Deliberately avoid bind-mounting the active /boot: package
                    # scripts and initramfs generation write only staging files.
                    with mounted(destination / 'etc', root / 'etc', '--bind'), \
                         mounted(destination / 'var', root / 'var', '--bind'), \
                         mounted('/dev', root / 'dev', '--rbind'), \
                         mounted('/sys', root / 'sys', '--rbind'), \
                         mounted('proc', root / 'proc', '-t', 'proc'), \
                         mounted('tmpfs', root / 'run', '-t', 'tmpfs', '-o', 'mode=0755'):
                        (root / 'run/aphrodite-staging').write_text(name + '\n')
                        policy = root / 'usr/sbin/policy-rc.d'
                        original = policy.read_bytes() if policy.exists() else None
                        policy.write_text('#!/bin/sh\nexit 101\n'); policy.chmod(0o755)
                        try:
                            resolver = root / 'etc/resolv.conf'
                            link = os.readlink(resolver) if resolver.is_symlink() else None
                            old = resolver.read_bytes() if resolver.exists() else None
                            resolver.unlink(missing_ok=True)
                            resolver.write_bytes(Path('/etc/resolv.conf').read_bytes())
                            try:
                                if action == 'retry-apps':
                                    sys.path.insert(0, '/usr/lib/aphrodite/packages')
                                    from executor import apply
                                    from selection import validate
                                    selection = json.loads((root / 'var/lib/aphrodite-os/install-manifest.json').read_text())['selection']
                                    # Flatpak deployments are shared application
                                    # state, independent of the protected base.
                                    with mounted(volume / '@shared/flatpak', root / 'var/lib/flatpak', '--bind'):
                                        apply(root, validate(selection), progress=lambda line: print(line, flush=True))
                                else:
                                    run('chroot', root, 'apt-get', '-o', 'DPkg::Lock::Timeout=45', 'update', timeout=300)
                                    release_receipt = None
                                    if action == 'release':
                                        receipt_file, *debs = map(Path, packages)
                                        release_receipt = json.loads(receipt_file.read_text())
                                        update_dir = root / 'run/aphrodite-release'
                                        update_dir.mkdir()
                                        for deb in debs:
                                            shutil.copyfile(deb, update_dir / deb.name)
                                        command = ['install', '--no-install-recommends',
                                                   *['/run/aphrodite-release/' + deb.name for deb in debs]]
                                    else:
                                        command = ['install', '--no-install-recommends', *packages] if action == 'layer' else ['upgrade', '--with-new-pkgs']
                                    run('chroot', root, 'apt-get', '-s', '--no-remove', *command, timeout=180)
                                    run('chroot', root, 'apt-get', '-y', '--no-remove', *command, timeout=3600)
                                    run('chroot', root, 'apt-get', 'check', timeout=180)
                                    if release_receipt:
                                        for item in release_receipt['packages']:
                                            status = output('chroot', root, 'dpkg-query', '-W',
                                                            '-f=${db:Status-Status}\t${Version}', item['name'])
                                            if status != 'installed\t' + item['version']:
                                                raise ValueError('Staged release package verification failed: ' + item['name'])
                                        atomic_json(root / 'var/lib/aphrodite/updates/applied.json', release_receipt)
                                for kernel in (root / 'boot').glob('vmlinuz-*'):
                                    run('chroot', root, 'update-initramfs', '-u', '-k', kernel.name.removeprefix('vmlinuz-'))
                            finally:
                                resolver.unlink(missing_ok=True)
                                if link is not None:
                                    resolver.symlink_to(link)
                                elif old is not None:
                                    resolver.write_bytes(old)
                            key = lambda p: [int(part) if part.isdecimal() else part for part in re.split(r'(\d+)', p.name)]
                            selected_kernel = max((root / 'boot').glob('vmlinuz-*'), key=key)
                            config = dict(config, deployment=name, kernel_version=selected_kernel.name.removeprefix('vmlinuz-'))
                            atomic_json(root / 'etc/aphrodite/transactional.json', config)
                            fstab_file = root / 'etc/fstab'
                            fstab_file.write_text(fstab_file.read_text().replace('@deployments/' + current + '/', '@deployments/' + name + '/'))
                        finally:
                            if original is None:
                                policy.unlink(missing_ok=True)
                            else:
                                policy.write_bytes(original)
                    # Publish versioned boot copies to a new directory; existing
                    # deployment kernels are never overwritten.
                    kernels = sorted((root / 'boot').glob('vmlinuz-*'), key=lambda p: [int(part) if part.isdecimal() else part for part in re.split(r'(\d+)', p.name)])
                    if not kernels:
                        raise ValueError('Updated deployment has no kernel')
                    kernel = kernels[-1]
                    initrd = root / 'boot' / ('initrd.img-' + kernel.name.removeprefix('vmlinuz-'))
                    boot = Path('/boot/aphrodite') / name
                    boot.mkdir()
                    shutil.copyfile(kernel, boot / 'vmlinuz')
                    shutil.copyfile(initrd, boot / 'initrd.img')
                    run('sync', '-f', boot)
                run('btrfs', 'property', 'set', '-ts', destination / 'root', 'ro', 'true')
                state = dict(state, deployments=[name, *state['deployments']], default=name)
                activate(state)
                print('Deployment staged:', name, '\nReboot to activate. The previous entry remains available in GRUB.')
            except Exception:
                print('Staging failed. The running root was not replaced. Unactivated files retained at', destination, file=sys.stderr)
                raise


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('status', 'update', 'layer', 'rollback', 'retry-apps', 'release', 'grub-menu'))
    parser.add_argument('items', nargs='*')
    args = parser.parse_args(argv)
    if args.action == 'grub-menu':
        if BOOT_STATE.exists():
            print(grub_entries(json.loads(BOOT_STATE.read_text())), end='')
        return 0
    config, state = current_configuration()
    if args.action == 'status':
        print(json.dumps({'running': config['deployment'], 'next_boot': state['default'],
                          'deployments': state['deployments'], 'development': True}, indent=2))
        return 0
    if os.geteuid():
        parser.error('Run this action with sudo')
    import fcntl
    with open('/run/lock/aphrodite-system.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'rollback':
            target = args.items[0] if args.items else next((x for x in state['deployments'] if x != config['deployment']), None)
            if target not in state['deployments'] or target == config['deployment']:
                parser.error('Choose a different existing deployment')
            activate(dict(state, default=target))
            print('Rollback selected. Reboot to activate:', target)
        else:
            if args.action == 'release':
                if len(args.items) < 2:
                    parser.error('Release staging requires a verified receipt and package files')
                for item in args.items:
                    path = Path(item).resolve(strict=True)
                    if not path.is_relative_to('/var/lib/aphrodite/updates') or path.stat().st_uid != 0 or not path.is_file():
                        parser.error('Release files must be root-owned updater downloads')
            if args.action == 'layer' and (not args.items or any(not re.fullmatch(r'[a-z0-9][a-z0-9+.:\-]*', item) for item in args.items)):
                parser.error('Supply Debian package names without shell options')
            stage(args.action, args.items)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print('Transactional operation stopped:', error, file=sys.stderr)
        raise SystemExit(1)
