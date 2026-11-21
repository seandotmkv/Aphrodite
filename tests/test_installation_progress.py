"""Progress telemetry, responsiveness and subprocess tests; never access disks."""

from pathlib import Path
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

PAYLOAD = Path(__file__).resolve().parents[1] / "config/includes.chroot/opt/aphrodite-os-installer-build"
sys.path.insert(0, str(PAYLOAD / "usr/libexec"))
sys.path.insert(0, str(PAYLOAD / "usr/lib/calamares/modules/aphroditeprofiles"))
from aphrodite_os_progress import Inbox, Progress, Panels, draw, duration
from processio import run, CommandTimeout


class FakeCanvas:
    def __init__(self, width=80, height=24):
        self.width, self.height = width, height
        self.lines = {}

    def put(self, row, column, text, style=0, limit=None):
        if 0 <= row < self.height:
            self.lines[row] = str(text)[:max(0, self.width - column)]


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.progress = Progress(lambda: self.now)
        self.progress.begin({"gimp": "GIMP", "keepassxc": "KeePassXC"})
        self.panels = Panels(self.progress)

    def test_progress_comes_from_completed_stages_not_a_timer(self):
        self.now += 900
        self.assertEqual(self.progress.percentage, 0)
        self.progress.consume({"kind": "stage", "id": "storage"})
        self.assertEqual(self.progress.percentage, 0)
        self.progress.consume({"kind": "stage", "id": "storage", "state": "complete"})
        self.assertEqual(self.progress.percentage, 11)
        self.progress.finish(1, "storage failed")
        self.assertNotEqual(self.progress.percentage, 100)

    def test_counts_are_deduplicated_and_architectures_reconciled(self):
        self.progress.consume({"kind": "apt_plan", "packages": ["gimp", "libfoo:i386"]})
        self.progress.consume({"kind": "apt_plan", "packages": ["gimp"]})
        self.progress.consume({"kind": "apt_state", "id": "gimp:amd64", "state": "installing"})
        self.assertEqual(len(self.progress.packages), 2)
        self.progress.consume({"kind": "apt_state", "id": "gimp", "state": "complete"})
        self.assertIn("1 / 2 known", self.progress.package_counter())
        self.progress.consume({"kind": "apt_state", "id": "unplanned-trigger", "state": "installing"})
        self.assertEqual(len(self.progress.packages), 2)

    def test_app_completion_does_not_count_flatpaks_as_debian_packages(self):
        self.progress.consume({"kind": "app", "id": "gimp", "name": "GIMP", "state": "complete"})
        self.assertEqual(len(self.progress.packages), 0)
        self.assertEqual(self.progress.apps["gimp"]["state"], "complete")

    def test_unknown_and_bad_fractions_cannot_fake_completion(self):
        for value in (float("nan"), float("inf"), "58%"):
            self.progress.consume({"kind": "fraction", "id": "extract", "value": value})
        self.assertEqual(self.progress.percentage, 0)
        self.progress.consume({"kind": "fraction", "id": "extract", "value": 1})
        self.assertLess(self.progress.fractions["extract"], 1)

    def test_eta_is_unknown_until_copy_measurements_are_available(self):
        self.assertEqual(self.progress.eta(), "Time remaining: estimating")
        self.progress.consume({"kind": "stage", "id": "extract"})
        self.now += 10
        self.progress.consume({"kind": "fraction", "id": "extract", "value": .5})
        self.assertIn("Copy stage: about 0m 10s left", self.progress.eta())

    def test_panels_default_closed_and_toggling_preserves_install_state(self):
        self.assertEqual(self.panels.open, set())
        before = (self.progress.percentage, dict(self.progress.apps), self.progress.started)
        for key in ("1", "2", "3", "4", "ENTER", "TAB", "PGDN", "PGUP"):
            self.panels.key(key)
        self.assertEqual(before, (self.progress.percentage, self.progress.apps, self.progress.started))

    def test_reduced_motion_is_default_and_optional_animation_does_not_sleep(self):
        self.assertTrue(self.panels.reduced_motion)
        self.panels.key("F6")
        with patch("time.sleep", side_effect=AssertionError("UI must not sleep")):
            self.panels.key("1")
            self.assertIsNotNone(self.panels.transition)
            self.now += .13
            self.panels.update()
            self.assertIsNone(self.panels.transition)
            self.panels.key("1")
            self.now += .13
            self.panels.update()
            self.assertNotIn(0, self.panels.open)

    def test_critical_error_expands_logs_and_details(self):
        self.progress.consume({"kind": "error", "text": "disk changed"})
        self.panels.update()
        self.assertTrue({0, 2} <= self.panels.open)
        self.assertEqual(self.panels.focus, 2)

    def test_pausing_logs_freezes_view_only_and_resuming_catches_up(self):
        self.progress.consume({"kind": "log", "text": "first"})
        self.panels.key("p")
        self.progress.consume({"kind": "log", "text": "second"})
        self.assertNotIn("second", "\n".join(self.panels.content(2)))
        self.assertIn("second", self.progress.logs[-1])
        self.panels.key("p")
        self.assertIn("second", "\n".join(self.panels.content(2)))

    def test_search_filters_application_and_dependency_history(self):
        self.progress.consume({"kind": "app", "id": "keepassxc", "name": "KeePassXC", "state": "failed"})
        self.progress.consume({"kind": "app", "id": "gimp", "name": "GIMP", "state": "complete"})
        self.panels.key("/")
        for char in "keepass":
            self.panels.key(char)
        self.panels.key("ENTER")
        history = "\n".join(self.panels.content(1))
        self.assertIn("KeePassXC", history)
        self.assertNotIn("GIMP", history)
        self.assertIn("Recent package events", history)
        self.assertIn("[failed] KeePassXC", history)

    def test_progress_header_does_not_scroll_or_overlap_at_supported_sizes(self):
        for width, height in ((78, 22), (80, 24), (100, 30), (160, 48)):
            with self.subTest(size=(width, height)):
                canvas = FakeCanvas(width, height)
                draw(self.panels, canvas, None)
                header = {row: canvas.lines.get(row) for row in range(5, 12)}
                self.panels.key("2")
                self.panels.key("PGDN")
                draw(self.panels, canvas, None)
                self.assertEqual(header, {row: canvas.lines.get(row) for row in range(5, 12)})
                self.assertIn("%", canvas.lines[7])
                self.assertTrue(all(0 <= row < height for row in canvas.lines))
                self.panels.open.clear()

    def test_success_and_failure_have_distinct_completion_actions(self):
        self.progress.finish(1, "format failed")
        canvas = FakeCanvas()
        draw(self.panels, canvas, None)
        self.assertNotIn("Restart System", "\n".join(canvas.lines.values()))
        self.progress.finish(0, "complete")
        draw(self.panels, canvas, None)
        self.assertEqual(self.progress.percentage, 100)
        self.assertIn("installed successfully", canvas.lines[5])
        self.assertIn("Restart System", canvas.lines[8])

    def test_log_tail_and_inbox_are_bounded_without_losing_state_events(self):
        inbox = Inbox()
        for index in range(5000):
            inbox.put({"kind": "log", "text": str(index)})
        inbox.put({"kind": "error", "text": "critical"})
        events = inbox.drain()
        self.assertEqual(events[0]["kind"], "error")
        self.assertLessEqual(len(events), 256)
        self.assertGreater(inbox.dropped, 0)
        for event in events:
            self.progress.consume(event)
        self.assertEqual(self.progress.error, "critical")


class ProcessTests(unittest.TestCase):
    def run_python(self, program, **kwargs):
        return run([sys.executable, "-u", "-c", program], env=dict(os.environ),
                   output=kwargs.pop("output", lambda _: None), timeout=kwargs.pop("timeout", 3), **kwargs)

    def test_output_is_delivered_before_exit(self):
        seen = threading.Event()
        result = []
        def worker():
            result.append(self.run_python("import time; print('started',flush=True); time.sleep(.7)",
                                          output=lambda _: seen.set()))
        thread = threading.Thread(target=worker)
        thread.start()
        try:
            self.assertTrue(seen.wait(.6))
            self.assertTrue(thread.is_alive())
        finally:
            thread.join(4)
        self.assertEqual(result[0][0], 0)

    def test_carriage_returns_and_no_final_newline_are_preserved(self):
        lines = []
        code = "import sys; sys.stdout.write('10\\r20\\rfinished'); sys.stdout.flush()"
        status, output, _ = self.run_python(code, output=lines.append)
        self.assertEqual(status, 0)
        self.assertEqual(lines, ["10", "20", "finished"])

    def test_silent_and_no_newline_commands_have_deadlines(self):
        started = time.monotonic()
        with self.assertRaisesRegex(CommandTimeout, "timed out"):
            self.run_python("import sys,time; sys.stdout.write('pending'); sys.stdout.flush(); time.sleep(10)", timeout=.2)
        self.assertLess(time.monotonic() - started, 3)

    def test_large_output_does_not_deadlock_and_tail_is_bounded(self):
        status, text, length = self.run_python("print('x'*300000)")
        self.assertEqual(status, 0)
        self.assertGreater(length, 200000)
        self.assertLessEqual(len(text), 200001)

    def test_secret_output_is_never_captured_or_notified(self):
        lines = []
        status, text, length = self.run_python("print('private secret')", output=lines.append, secret=True)
        self.assertEqual((status, text, length, lines), (0, "", 0, []))

    @unittest.skipUnless(os.name == "posix", "APT descriptor passing requires Linux/POSIX")
    def test_apt_status_fd_is_inherited_and_streamed(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "apt-get"
            executable.write_text("#!/usr/bin/env python3\nimport os,sys\nfd=int(next(a.split('=')[1] for a in sys.argv if a.startswith('APT::Status-Fd=')))\nos.write(fd,b'pmstatus:gimp:amd64:75:Configuring\\n')\n")
            executable.chmod(0o755)
            lines = []
            run([str(executable)], env=dict(os.environ), output=lambda _: None, timeout=3, apt_status=lines.append)
            self.assertEqual(lines, ["pmstatus:gimp:amd64:75:Configuring"])


@unittest.skipUnless(os.name == "posix", "Terminal backend integration requires Linux/POSIX")
class InterfaceIntegrationTests(unittest.TestCase):
    def test_panel_input_never_starts_or_restarts_worker(self):
        from test_package_selection import terminal
        app = terminal.App(demo=True)
        app.demo = False  # Exercise active-install quit protection, not demo exit.
        app.installing = True
        app.progress.begin({})
        with patch.object(terminal.backend, "install") as install:
            for key in ("1", "2", "3", "4", "ENTER", "TAB", "PGDN", "/", "a", "ENTER", "q"):
                app.key(key)
            install.assert_not_called()
        self.assertFalse(app.done)
        self.assertTrue(app.installing)

    def test_time_tab_does_not_enumerate_zones_on_input_thread(self):
        from test_package_selection import terminal
        app = terminal.App(demo=True)
        app.page = 1
        with patch.object(terminal, "zones", side_effect=AssertionError("blocking zone scan")):
            app.fields()
            terminal.render(app)

    def test_apt_status_does_not_treat_global_percent_as_package_success(self):
        from test_package_selection import executor
        target = object.__new__(executor.Target)
        events = []
        target.events, target.output = events.append, lambda _: None
        target.apt_status("pmstatus:gimp:amd64:100:Configuring GIMP")
        self.assertEqual(events[-1], {"kind": "apt_state", "id": "gimp:amd64", "state": "installing"})

    def test_apt_installed_message_counts_configuration_before_transaction_exit(self):
        from test_package_selection import executor
        target = object.__new__(executor.Target)
        events = []
        target.events, target.output = events.append, lambda _: None
        target.apt_status("pmstatus:gimp:amd64:25:Installed gimp:amd64")
        self.assertEqual(events[-1]["state"], "configured")

    def test_log_export_and_clipboard_are_asynchronous_and_preserve_full_file(self):
        from test_package_selection import terminal
        with tempfile.TemporaryDirectory() as directory:
            app = terminal.App(demo=True)
            app.log_path = Path(directory) / "install.log"
            app.log_path.write_text("complete diagnostic\n" * 10000)
            app.log_action()
            deadline = time.monotonic() + 3
            while app.action_busy and time.monotonic() < deadline:
                app.poll()
                time.sleep(.01)
            exported = list(Path(directory).glob("saved-install-*.log"))
            self.assertEqual(len(exported), 1)
            self.assertEqual(exported[0].read_bytes(), app.log_path.read_bytes())
            app.log_action(copy=True)
            while app.action_busy and time.monotonic() < deadline:
                app.poll()
                time.sleep(.01)
            import base64
            self.assertEqual(len(base64.b64decode(app.clipboard)), 100000)
            self.assertIn("Last 100 KB", app.panels.message)

    def test_restart_requires_real_success_and_explicit_confirmation(self):
        from test_package_selection import terminal
        app = terminal.App(demo=True)
        app.finished = True
        app.progress.finish(0, "complete")
        with patch.object(terminal.subprocess, "run") as run:
            app.key("r")
            self.assertFalse(app.reboot_dialog)
            app.demo = False
            app.key("r")
            self.assertTrue(app.reboot_dialog)
            run.assert_not_called()
            app.key("n")
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
