"""Exercise terminal confirmation, write ordering and package handoff without disks."""

from contextlib import contextmanager
from pathlib import Path
import stat
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_package_selection import executor, terminal


backend = terminal.backend
IDENTITY = ("252:0", 40, 24 * 1024**3)
TARGET = "/dev/vda"
LIVE = "/dev/sr0"


class TerminalInstallTests(unittest.TestCase):
    def setUp(self):
        self.app = terminal.App()
        self.app.snapshot = terminal.Snapshot(
            [terminal.Disk(TARGET, IDENTITY[2], "Disposable", IDENTITY[0], identity=IDENTITY)], True)
        self.app.settings.disk = TARGET
        self.app.settings.username = "somefixtureuser"
        self.app.settings.password = self.app.settings.confirmation = "fixture-password"
        self.app.set_value("package_preset", "Recommended")

    def wait_for_result(self):
        deadline = time.monotonic() + 3
        while not self.app.finished and time.monotonic() < deadline:
            self.app.poll()
            time.sleep(.01)
        self.assertTrue(self.app.finished)

    def test_exact_disk_confirmation_and_selection_are_passed_to_worker(self):
        with patch.object(backend, "install", return_value=["PDF Arranger skipped."]) as install:
            self.app.key("F2")
            review = terminal.render(self.app).text()
            self.assertIn("All partitions, files and existing operating systems will be lost", review)
            self.assertIn(f"Type ERASE {TARGET}", review)
            self.app.buffer = "ERASE /dev/sda"
            self.app.key("ENTER")
            install.assert_not_called()
            self.app.buffer = f"ERASE {TARGET}"
            self.app.key("ENTER")
            self.wait_for_result()
        settings, identity, selection, password, _, _ = install.call_args.args
        self.assertEqual(settings.disk, TARGET)
        self.assertEqual(identity, IDENTITY)
        self.assertEqual(selection["apps"], terminal.preset("Recommended"))
        self.assertEqual(password, "fixture-password")
        self.assertEqual(settings.password, "")
        self.assertIn("PDF Arranger skipped", terminal.render(self.app).text())

    def test_backend_error_is_displayed_and_returns_failure(self):
        with patch.object(backend, "install", side_effect=backend.InstallError("Target changed")):
            self.app.key("F2")
            self.app.buffer = f"ERASE {TARGET}"
            self.app.key("ENTER")
            self.wait_for_result()
        self.assertEqual(self.app.exit_status, 1)
        self.assertIn("Target changed", terminal.render(self.app).text())


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "target"
        (self.root / "var/log").mkdir(parents=True)
        self.image = Path(self.temporary.name) / "image.squashfs"
        self.image.touch()
        self.log = (Path(self.temporary.name) / "install.log").open("w")
        self.addCleanup(self.log.close)
        self.settings = terminal.Settings(disk=TARGET, username="somefixtureuser")
        self.installer = backend.Installer(lambda _: None, self.log)
        self.installer.command = Mock()
        self.installer.populate = Mock()
        self.installer.configure_storage = Mock()
        self.installer.boot = Mock()
        self.installer.clock = Mock()
        self.installer.find_partitions = Mock(return_value={"bios": "/dev/vda1", "root": "/dev/vda2"})
        self.unmounted = False

        @contextmanager
        def mounted_target(device, filesystem):
            self.assertEqual((device, filesystem), ("/dev/vda2", "ext4"))
            try:
                yield self.root
            finally:
                self.unmounted = True

        self.installer.mounted_target = mounted_target
        self.selection = {"version": 1, "apps": {"chromium": "apt", "keepassxc": "apt"},
                          "browser": "chromium", "session": "off"}
        self.enterContext(patch.object(backend, "IMAGE", self.image))
        self.enterContext(patch.object(backend, "firmware", return_value="bios"))
        self.detector = self.enterContext(patch.object(backend, "protected_devices", return_value={LIVE}))
        self.enterContext(patch.object(backend, "disk_identity", return_value=IDENTITY))
        self.enterContext(patch.object(backend, "block_path", return_value=("11:0", None)))
        self.unused = self.enterContext(patch.object(backend, "check_unused"))
        self.enterContext(patch.object(backend, "read_command", return_value="/dev/vda2"))
        self.apply = self.enterContext(patch.object(executor, "apply", return_value=["KeePassXC complete."]))

    def run_install(self):
        original_stat = Path.stat

        def masked(path, *args, **kwargs):
            if str(path) == LIVE:
                return SimpleNamespace(st_mode=stat.S_IFCHR)
            return original_stat(path, *args, **kwargs)

        with patch.object(Path, "stat", masked):
            return self.installer.install(self.settings, IDENTITY, self.selection, "secret")

    def test_backend_passes_selected_apps_to_executor_after_cleanup(self):
        (self.root / "usr/sbin").mkdir(parents=True)
        self.assertEqual(self.run_install(), [])
        self.assertTrue(self.unmounted)
        self.assertTrue((self.root / "var/log/aphrodite-os-install.log").exists())
        self.assertFalse((self.root / "usr/sbin/policy-rc.d").exists())
        args = self.apply.call_args.args
        self.assertEqual(args[0], self.root)
        self.assertEqual(args[1]["apps"], self.selection["apps"])
        self.assertEqual(args[1]["browser"], "chromium")
        commands = [call.args[0] for call in self.installer.command.call_args_list]
        self.assertEqual(commands, ["unsquashfs", backend.LIBEXEC / "aphrodite-os-protect-medium",
                                    "sfdisk", "mkfs.ext4", "chroot", "sync"])
        self.installer.boot.assert_called_once_with(self.root, TARGET, IDENTITY, "bios")

    def test_failed_medium_detection_and_changed_target_prevent_writes(self):
        for failure in (self.detector, self.unused):
            with self.subTest(failure=failure):
                failure.side_effect = backend.InstallError("Cannot verify identity")
                self.installer.command.reset_mock()
                with self.assertRaisesRegex(backend.InstallError, "Cannot verify"):
                    self.run_install()
                self.installer.command.assert_called_once_with("unsquashfs", "-stat", self.image)
                self.apply.assert_not_called()
                failure.side_effect = None

    def test_target_device_number_matching_live_medium_prevents_writes(self):
        with patch.object(backend, "block_path", return_value=(IDENTITY[0], None)):
            with self.assertRaisesRegex(backend.InstallError, "protected live disk"):
                self.run_install()
        self.installer.command.assert_called_once_with("unsquashfs", "-stat", self.image)

    def test_mask_failure_stops_before_partitioning(self):
        def command(*args, **kwargs):
            if args[-1] == "--mask":
                raise backend.InstallError("Mask failed")

        self.installer.command.side_effect = command
        with self.assertRaisesRegex(backend.InstallError, "Mask failed"):
            self.run_install()
        self.assertEqual(self.installer.command.call_count, 2)
        self.apply.assert_not_called()

    def test_dpkg_failure_restores_policy_unmounts_and_stops_before_bootloader(self):
        path = self.root / "usr/sbin/policy-rc.d"
        path.parent.mkdir(parents=True)
        path.write_text("previous policy")
        self.apply.side_effect = backend.InstallError("Cannot configure packages")
        with self.assertRaisesRegex(backend.InstallError, "Cannot configure packages"):
            self.run_install()
        self.installer.boot.assert_not_called()
        self.assertTrue(self.unmounted)
        self.assertEqual(path.read_text(), "previous policy")

    def test_password_stdin_diagnostics_are_discarded_on_error(self):
        installer = backend.Installer(lambda _: None, self.log)
        with patch.object(backend.subprocess, "run", return_value=Mock(returncode=1)) as run:
            with self.assertRaisesRegex(backend.InstallError, "chpasswd exited with status 1"):
                installer.command("chpasswd", input_text="user:fixture-secret\n", secret=True)
        self.assertEqual(run.call_args.kwargs["input"], "user:fixture-secret\n")
        self.assertEqual(run.call_args.kwargs["stderr"], subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs["stdout"], subprocess.DEVNULL)
        self.assertNotIn("fixture-secret", Path(self.log.name).read_text())


class IdentityTests(unittest.TestCase):
    def test_source_backend_imports_the_staged_login_runtime(self):
        import importlib
        module = importlib.import_module('login')
        expected = Path(__file__).resolve().parents[1] / 'config/includes.chroot/usr/lib/aphrodite/login.py'
        self.assertEqual(Path(module.__file__).resolve(), expected.resolve())

    def test_disk_generation_change_prevents_access_even_with_same_device_number(self):
        changed = (IDENTITY[0], IDENTITY[1] + 1, IDENTITY[2])
        with patch.object(backend, "disk_identity", return_value=changed), \
                patch.object(backend.os, "open") as device_open:
            with self.assertRaisesRegex(backend.InstallError, "changed since review"):
                backend.check_unused(TARGET, IDENTITY)
        device_open.assert_not_called()
