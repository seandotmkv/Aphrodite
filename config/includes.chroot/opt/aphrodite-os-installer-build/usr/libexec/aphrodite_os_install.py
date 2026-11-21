"""Whole-disk installation from the official aphrodite-os live image."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from uuid import uuid4
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

LIBEXEC = Path(__file__).resolve().parent
MODULES = LIBEXEC.parent / "lib/calamares/modules"
sys.path.insert(0, str(MODULES / "aphroditeprofiles"))
from selection import validate
from processio import run as run_process, CommandTimeout
# Image execution uses /usr/lib/aphrodite. Build-host validation imports this
# backend directly from includes.chroot, where the runtime is a sibling of opt.
RUNTIME = Path('/usr/lib/aphrodite')
for ancestor in LIBEXEC.parents:
    if ancestor.name == 'includes.chroot':
        RUNTIME = ancestor / 'usr/lib/aphrodite'
        break
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(MODULES / "aphroditeclock"))
from main import setup_input_method

IMAGE = Path("/run/live/medium/live/filesystem.squashfs")
LOG_DIR = Path("/var/log/aphrodite-os")
MIN_BYTES = 16 * 1024**3
DEVICE = re.compile(r"/dev/[A-Za-z0-9_.-]+")


class InstallError(RuntimeError):
    pass


def read_command(*args):
    result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=8,
                            env=dict(os.environ, LC_ALL="C"))
    return result.stdout.strip()


def protected_devices():
    try:
        devices = set(read_command(str(LIBEXEC / "aphrodite-os-protect-medium"),
                                   "--identify").splitlines())
    except subprocess.CalledProcessError as error:
        raise InstallError(error.stderr.strip() or "Live-medium identification failed") from None
    if not devices or any(not DEVICE.fullmatch(path) for path in devices):
        raise InstallError("Live-medium protection did not return valid device paths")
    return devices


def block_path(path):
    status = Path(path).stat()
    if not stat.S_ISBLK(status.st_mode):
        raise InstallError(f"{path} is no longer a block device")
    number = f"{os.major(status.st_rdev)}:{os.minor(status.st_rdev)}"
    return number, Path("/sys/dev/block", number).resolve(strict=True)


def disk_identity(path):
    number, node = block_path(path)
    sequence = int((node / "diskseq").read_text())
    if sequence <= 0 or (node / "partition").exists():
        raise InstallError(f"{path} has no valid whole-disk generation")
    return number, sequence, int((node / "size").read_text()) * 512


def disk_rows():
    rows = json.loads(read_command("lsblk", "--json", "--list", "--bytes", "--paths",
                                  "--output", "PATH,TYPE,SIZE,MODEL,RO,MAJ:MIN,PKNAME,MOUNTPOINTS"))
    return rows["blockdevices"]


def partitions(path, rows):
    return [row for row in rows if row["type"] == "part" and
            row.get("pkname") in (path, Path(path).name)]


def blocked_reason(row, children):
    if row["ro"]:
        return "Read-only"
    if int(row["size"]) < MIN_BYTES:
        return "Requires at least 16 GiB"
    devices = [row, *children]
    for entry in devices:
        if any(entry.get("mountpoints") or []):
            return "Mounted or active swap"
        number, node = block_path(entry["path"])
        if number != entry["maj:min"] or any((node / "holders").iterdir()):
            return "In use or device identity changed"
    return ""


def check_unused(path, identity):
    """Check the reviewed generation, mount/swap state, and kernel exclusive access."""
    if not DEVICE.fullmatch(path) or disk_identity(path) != identity:
        raise InstallError(f"{path} changed since review. Scan and select it again.")
    rows = disk_rows()
    row = next((row for row in rows if row["path"] == path and row["type"] == "disk"), None)
    if row is None or row["maj:min"] != identity[0] or int(row["size"]) != identity[2]:
        raise InstallError(f"{path} is no longer the reviewed disk")
    reason = blocked_reason(row, partitions(path, rows))
    if reason:
        raise InstallError(f"{path} is unavailable: {reason}")
    # O_EXCL on a block device rejects active mounts and other kernel claims.
    fd = os.open(path, os.O_RDONLY | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        status = os.fstat(fd)
        number = f"{os.major(status.st_rdev)}:{os.minor(status.st_rdev)}"
        if not stat.S_ISBLK(status.st_mode) or number != identity[0] or disk_identity(path) != identity:
            raise InstallError(f"{path} changed during the exclusive-access check")
    finally:
        os.close(fd)


def firmware():
    efi = Path("/sys/firmware/efi")
    if not efi.is_dir():
        return "bios"
    if (efi / "fw_platform_size").read_text().strip() != "64":
        raise InstallError("This installer requires 64-bit UEFI firmware")
    variables = efi / "efivars"
    if not variables.is_mount():
        raise InstallError("Cannot verify Secure Boot: EFI variables are unavailable")
    for variable in variables.glob("SecureBoot-*"):
        if variable.read_bytes()[4:] != b"\x00":
            raise InstallError("Disable Secure Boot before using the terminal installer")
    return "uefi"


class Installer:
    def __init__(self, notify, log):
        self.notify = notify
        self.log = log
        self.current_stage = None

    def event(self, event):
        self.notify(event)

    def stage(self, key, text):
        if self.current_stage:
            self.event({"kind": "stage", "id": self.current_stage, "state": "complete"})
        self.current_stage = key
        self.report(text)
        self.event({"kind": "stage", "id": key, "text": text})

    def report(self, message):
        print(datetime.now(timezone.utc).isoformat(), message, file=self.log, flush=True)
        self.event({"kind": "log", "text": message,
                    "timestamp": datetime.now(timezone.utc).isoformat()})

    def command(self, *args, input_text=None, secret=False, timeout=1800):
        args = [os.fspath(arg) for arg in args]
        self.report("$ " + shlex.join(args))
        self.event({"kind": "command", "text": shlex.join(args)})
        env = dict(os.environ, LC_ALL="C", DEBIAN_FRONTEND="noninteractive")
        if secret:
            # Passwords travel over stdin. Suppress both streams and never
            # include the input in any diagnostic, including command failures.
            try:
                result = subprocess.run(args, input=input_text, encoding="utf-8", env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        start_new_session=True, timeout=120)
            except subprocess.TimeoutExpired:
                raise InstallError(f"{args[0]} timed out. See the diagnostic log.") from None
            status = result.returncode
        else:
            def output(line):
                message = line.strip()
                if args[0] == "unsquashfs" and "-percentage" in args and message.isdecimal():
                    self.event({"kind": "fraction", "id": "extract", "value": int(message) / 100})
                    message = f"Extracting filesystem: {message}%"
                if message:
                    self.report(message)
            try:
                status, _, _ = run_process(args, env=env, output=output, timeout=timeout,
                                          input_text=input_text,
                                          heartbeat=lambda elapsed: self.event({"kind": "heartbeat", "elapsed": elapsed}))
            except CommandTimeout as error:
                raise InstallError(str(error)) from None
        if status:
            raise InstallError(f"{args[0]} exited with status {status}. See the diagnostic log.")

    def target(self, root, *args, **kwargs):
        self.command("chroot", root, *args, **kwargs)

    @contextmanager
    def mounted_target(self, partition, filesystem):
        with tempfile.TemporaryDirectory(prefix="aphrodite-os-target-", dir="/run") as directory:
            root = Path(directory)
            immutable = getattr(self, 'immutable', False)
            if immutable:
                import transactional
                self.command('mount', '--source', partition, '--target', root, '-t', 'btrfs')
                try:
                    transactional.initial_layout(self.command, root)
                finally:
                    self.command('umount', root)
            options = ('-o', 'subvol=@deployments/initial/root') if immutable else ()
            self.command("mount", "--source", partition, "--target", root, "-t", filesystem, *options)
            try:
                if immutable:
                    (root / '.aphrodite-state').mkdir(mode=0o700)
                    (root / 'boot').mkdir()
                    self.command('mount', '-t', 'btrfs', '-o', 'rw,subvolid=5', partition, root / '.aphrodite-state')
                    self.command('mount', '-t', 'ext4', self.devices['boot'], root / 'boot')
                yield root
            finally:
                try:
                    self.command("umount", "--recursive", root)
                except InstallError:
                    # Detach only within the private mount namespace, while
                    # preserving the failure for the operator.
                    self.command("umount", "--lazy", root)
                    raise

    def find_partitions(self, path, identity, uuids):
        self.command("udevadm", "settle", "--timeout=20")
        if disk_identity(path) != identity:
            raise InstallError("Target disk changed after partitioning")
        table = json.loads(read_command("sfdisk", "--json", path))["partitiontable"]
        rows = table["partitions"]
        if table["label"] != "gpt" or len(rows) != len(uuids):
            raise InstallError("The new partition layout did not match the requested GPT")
        _, parent = block_path(path)
        found = {}
        for row in rows:
            device = row["node"]
            if not DEVICE.fullmatch(device):
                raise InstallError("Invalid partition device path")
            _, node = block_path(device)
            factor = table["sectorsize"] // 512
            if (node.parent != parent or not (node / "partition").is_file()
                    or int((node / "start").read_text()) != row["start"] * factor
                    or int((node / "size").read_text()) != row["size"] * factor):
                raise InstallError("The kernel did not enumerate the reviewed GPT partitions")
            value = row["uuid"].lower()
            if value not in uuids.values() or value in found:
                raise InstallError("A new partition does not match the written GPT")
            found[value] = device
        return {name: found[value] for name, value in uuids.items()}

    def populate(self, root, settings, password):
        self.stage("extract", "Copying the live system to the target")
        self.command("unsquashfs", "-force", "-percentage", "-d", root, IMAGE, timeout=7200)
        for name in ("dev", "sys"):
            self.command("mount", "--rbind", "/" + name, root / name)
        self.command("mount", "-t", "proc", "proc", root / "proc")
        self.command("mount", "-t", "tmpfs", "-o", "mode=0755,nosuid,nodev", "tmpfs", root / "run")

        self.stage("account", "Configuring hostname, locale, keyboard and user account")
        (root / "etc/hostname").write_text(settings.hostname + "\n")
        (root / "etc/hosts").write_text(
            f"127.0.0.1 localhost\n127.0.1.1 {settings.hostname}\n::1 localhost ip6-localhost ip6-loopback\n")
        (root / "etc/locale.gen").write_text(f"{settings.language} UTF-8\n")
        self.target(root, "locale-gen")
        (root / "etc/default/locale").write_text(f"LANG={settings.language}\n")
        (root / "etc/default/keyboard").write_text(
            f'XKBMODEL="pc105"\nXKBLAYOUT="{settings.keyboard}"\nXKBVARIANT="{settings.variant}"\nXKBOPTIONS=""\n')
        (root / "etc/xdg/kxkbrc").write_text(
            f"[Layout]\nUse=true\nLayoutList={settings.keyboard}\nVariantList={settings.variant}\n")
        localtime = root / "etc/localtime"
        localtime.unlink(missing_ok=True)
        localtime.symlink_to("/usr/share/zoneinfo/" + settings.timezone)
        (root / "etc/timezone").write_text(settings.timezone + "\n")
        (root / "etc/machine-id").write_text("")
        self.target(root, "systemd-machine-id-setup")
        existing_groups = {line.split(":")[0] for line in (root / "etc/group").read_text().splitlines()}
        groups = ",".join(group for group in ("sudo", "cdrom", "plugdev", "lpadmin", "scanner")
                          if group in existing_groups)
        self.target(root, "useradd", "--create-home", "--shell", "/bin/bash",
                    "--groups", groups, "--comment",
                    settings.full_name, "--", settings.username)
        self.target(root, "chpasswd", input_text=f"{settings.username}:{password}\n", secret=True)
        self.target(root, "passwd", "--lock", "root")
        setup_input_method(root, settings.language, settings.username)

    def configure_storage(self, root, devices, settings):
        filesystem = settings.filesystem
        root_uuid = read_command("blkid", "-p", "-s", "UUID", "-o", "value", devices["root"])
        fstab = [f"UUID={root_uuid} / {filesystem} defaults 0 {1 if filesystem == 'ext4' else 0}"]
        efi_uuid = None
        if "efi" in devices:
            partition = devices["efi"]
            location = root / "boot/efi"
            location.mkdir(parents=True, exist_ok=True)
            self.command("mount", "-t", "vfat", "-o", "umask=0077", partition, location)
            efi_uuid = read_command("blkid", "-p", "-s", "UUID", "-o", "value", partition)
            fstab.append(f"UUID={efi_uuid} /boot/efi vfat umask=0077 0 2")
        if settings.swap == "file":
            swap = (root / '.aphrodite-state/@shared/swap/swapfile' if getattr(settings, 'immutable', False)
                    else root / "swapfile")
            if filesystem == "btrfs":
                self.command("btrfs", "filesystem", "mkswapfile", "--size", "2g", swap)
            else:
                swap.touch(mode=0o600, exist_ok=False)
                self.command("dd", "if=/dev/zero", f"of={swap}", "bs=1M", "count=2048", "status=progress")
                self.command("mkswap", swap)
            fstab.append("/swapfile none swap sw 0 0")
        if getattr(settings, 'immutable', False):
            import transactional
            boot_uuid = read_command('blkid', '-p', '-s', 'UUID', '-o', 'value', devices['boot'])
            fstab = transactional.fstab(root_uuid, boot_uuid, swap=settings.swap == 'file', efi_uuid=efi_uuid).splitlines()
        (root / "etc/fstab").write_text("\n".join(fstab) + "\n")

    def packages(self, root, selection):
        from executor import apply

        self.report("Removing live-only packages and applying selected applications")
        policy = root / "usr/sbin/policy-rc.d"
        backup = policy.with_name("policy-rc.d.aphrodite-os")
        if backup.exists() or backup.is_symlink():
            raise InstallError("Unexpected policy-rc.d backup in the live image")
        had_policy = policy.exists() or policy.is_symlink()
        if had_policy:
            policy.rename(backup)
        try:
            policy.write_text("#!/bin/sh\nexit 101\n")
            policy.chmod(0o755)
            self.target(root, "/usr/libexec/aphrodite-os-clean-installed",
                        *(() if "firefox" in selection["apps"] else ("--remove-firefox",)))
            return apply(root, selection, self.report, self.log.name + ".packages",
                         progress=self.report, events=self.event)
        finally:
            policy.unlink(missing_ok=True)
            if had_policy:
                backup.rename(policy)

    def clock(self, root, settings):
        command = "enable" if settings.automatic_time else "disable"
        self.command("systemctl", "--root", root, command, "systemd-timesyncd.service")
        if settings.automatic_time and settings.ntp_servers.strip():
            destination = root / "etc/systemd/timesyncd.conf.d/50-aphrodite-os.conf"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("[Time]\nNTP=" + " ".join(settings.ntp_servers.split()) + "\n")
        if not settings.automatic_time:
            moment = datetime.strptime(settings.manual_time, "%Y-%m-%d %H:%M").replace(
                tzinfo=ZoneInfo(settings.timezone))
            self.command("timedatectl", "set-ntp", "false")
            self.command("timedatectl", "set-time", moment.astimezone().strftime("%Y-%m-%d %H:%M:%S"))

    def boot(self, root, path, identity, platform):
        self.report("Rebuilding initramfs and installing GRUB")
        config = root / "etc/initramfs-tools/conf.d/aphrodite-os"
        config.write_text("UMASK=0077\nRESUME=none\n")
        kernels = sorted((root / "boot").glob("vmlinuz-*"))
        if not kernels:
            raise InstallError("No installed kernel was found")
        for kernel in kernels:
            version = kernel.name.removeprefix("vmlinuz-")
            action = "-u" if (root / "boot" / f"initrd.img-{version}").exists() else "-c"
            self.target(root, "update-initramfs", action, "-k", version)
        (root / "etc/default/grub.d/50-aphrodite-os.cfg").write_text(
            'GRUB_DISTRIBUTOR="Aphrodite OS"\nGRUB_DISABLE_OS_PROBER=true\n')
        if disk_identity(path) != identity:
            raise InstallError("Target disk changed before bootloader installation")
        if platform == "uefi":
            options = ("--target=x86_64-efi", "--efi-directory=/boot/efi", "--bootloader-id=aphrodite-os")
            self.target(root, "grub-install", *options)
            self.target(root, "grub-install", *options, "--removable", "--no-nvram")
        else:
            self.target(root, "grub-install", "--target=i386-pc", path)
        self.target(root, "update-grub")
        if "menuentry " not in (root / "boot/grub/grub.cfg").read_text():
            raise InstallError("GRUB configuration does not contain a boot entry")

    def install(self, settings, identity, selection, password):
        self.stage("preflight", "Checking the live medium and reviewed target identity")
        path = settings.disk
        if settings.mode != "erase" or settings.encryption or settings.filesystem not in ("ext4", "btrfs"):
            raise InstallError("Unsupported storage configuration")
        validate_account(settings)
        self.immutable = getattr(settings, 'immutable', False)
        if self.immutable and (settings.filesystem != 'btrfs' or identity[2] < 32 * 1024**3):
            raise InstallError('Transactional installation requires Btrfs and a disk of at least 32 GiB')
        selection = validate(selection)
        self.report(f"Preflight: {path}, {identity[2]} bytes, device {identity[0]}, generation {identity[1]}")
        platform = firmware()
        if not IMAGE.is_file():
            raise InstallError("The live SquashFS is unavailable")
        self.command("unsquashfs", "-stat", IMAGE)
        protected = protected_devices()
        if path in protected or identity[0] in {block_path(disk)[0] for disk in protected}:
            raise InstallError("The selected target is the protected live disk")
        check_unused(path, identity)

        # The guard re-resolves and masks the live disk and its children in
        # this private namespace. Existing SquashFS mounts remain readable.
        self.command(LIBEXEC / "aphrodite-os-protect-medium", "--mask")
        if any(stat.S_ISBLK(Path(disk).stat().st_mode) for disk in protected):
            raise InstallError("The reviewed live medium was not masked")
        check_unused(path, identity)

        first = "efi" if platform == "uefi" else "bios"
        types = {"efi": ("512MiB", "C12A7328-F81F-11D2-BA4B-00A0C93EC93B"),
                 "bios": ("2MiB", "21686148-6449-6E6F-744E-656564454649")}
        size, kind = types[first]
        ids = {first: str(uuid4()), "root": str(uuid4())}
        if self.immutable:
            ids['boot'] = str(uuid4())
        layout = (f"label: gpt\n\nsize={size}, type={kind}, uuid={ids[first]}\n"
                  + (f"size=2GiB, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, uuid={ids['boot']}\n" if self.immutable else '') +
                  f"type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, uuid={ids['root']}\n")
        self.stage("storage", f"Erasing {path} and creating a {platform.upper()} GPT layout")
        self.command("sfdisk", "--lock=yes", "--wipe=always", "--wipe-partitions=always",
                     path, input_text=layout)
        devices = self.find_partitions(path, identity, ids)
        self.devices = devices
        if self.immutable:
            check_unused(path, identity)
            self.command('mkfs.ext4', '-L', 'APHRODITE_BOOT', devices['boot'])
        check_unused(path, identity)
        if "efi" in devices:
            self.command("mkfs.fat", "-F", "32", "-n", "APHRODITE", devices["efi"])
            check_unused(path, identity)
            if self.find_partitions(path, identity, ids) != devices:
                raise InstallError("Partition paths changed before formatting")
        if settings.filesystem == "btrfs":
            self.command("mkfs.btrfs", "-f", "-L", "aphrodite-os", devices["root"])
        else:
            self.command("mkfs.ext4", "-L", "aphrodite-os", devices["root"])
        check_unused(path, identity)
        if self.find_partitions(path, identity, ids) != devices:
            raise InstallError("Partition paths changed before mounting the target")
        with self.mounted_target(devices["root"], settings.filesystem) as root:
            try:
                mounted = read_command("findmnt", "--nofsroot", "-n", "-o", "SOURCE", "--mountpoint", root)
                if mounted != devices["root"] or disk_identity(path) != identity:
                    raise InstallError("The mounted root is not on the reviewed disk")
                self.populate(root, settings, password)
                if self.find_partitions(path, identity, ids) != devices:
                    raise InstallError("Partition paths changed before system configuration")
                self.stage("filesystem", "Configuring filesystems and swap")
                self.configure_storage(root, devices, settings)
                self.stage("packages", "Installing selected applications and dependencies")
                results = self.packages(root, selection)
                self.stage("boot", "Rebuilding initramfs and installing GRUB")
                self.boot(root, path, identity, platform)
                self.stage("services", "Configuring system time and services")
                self.clock(root, settings)
                from login import configure as configure_login
                session = 'aphrodite-os-gaming.desktop' if (
                    selection['session'] == 'gaming' and
                    (root / 'usr/local/share/wayland-sessions/aphrodite-os-gaming.desktop').is_file()
                ) else 'plasma.desktop'
                configure_login(root, settings.username,
                                automatic=getattr(settings, 'autologin', False), session=session)
                if self.immutable:
                    import transactional
                    self.report('Sealing the development transactional deployment')
                    transactional.seal_initial(self.command, root, devices, settings)
                self.stage("verify", "Saving diagnostics and synchronizing the target")
            except Exception as error:
                self.report(f"Target setup failed: {error}")
                raise
            finally:
                self.log.flush()
                if (root / "var/log").is_dir():
                    saved = root / "var/log/aphrodite-os-install.log"
                    shutil.copyfile(self.log.name, saved)
                    saved.chmod(0o600)
                self.command("sync", "-f", root)
        warnings = [line for line in results if " incomplete." in line or " skipped" in line]
        self.report("Installation completed and target unmounted" + (" with warnings" if warnings else ""))
        self.event({"kind": "stage", "id": "verify", "state": "complete"})
        return warnings


def validate_account(settings):
    import pwd

    if type(getattr(settings, 'autologin', False)) is not bool:
        raise InstallError('Automatic login must be enabled or disabled')

    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", settings.username):
        raise InstallError("Invalid username")
    try:
        pwd.getpwnam(settings.username)
    except KeyError:
        pass
    else:
        raise InstallError("Choose a username that is not reserved by the live system")
    if ":" in settings.full_name or any(not char.isprintable() for char in settings.full_name):
        raise InstallError("Your name cannot contain a colon or control characters")
    if settings.variant:
        rules = ElementTree.parse("/usr/share/X11/xkb/rules/evdev.xml")
        variants = {variant.findtext("configItem/name")
                    for layout in rules.findall("./layoutList/layout")
                    if layout.findtext("configItem/name") == settings.keyboard
                    for variant in layout.findall("./variantList/variant")}
        if settings.variant not in variants:
            raise InstallError(f"Unknown keyboard variant for {settings.keyboard}")


def install(settings, identity, selection, password, notify, log_path):
    with log_path.open("a", encoding="utf-8", buffering=1) as log:
        installer = Installer(notify, log)
        try:
            return installer.install(settings, identity, selection, password)
        except Exception as error:
            # Account passwords never form part of a command argument.
            installer.report(f"Installation stopped: {error}")
            installer.event({"kind": "error", "text": str(error)})
            raise


def new_log():
    LOG_DIR.mkdir(mode=0o700, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="install-", suffix=".log", dir=LOG_DIR,
                                     delete=False) as stream:
        return Path(stream.name)
