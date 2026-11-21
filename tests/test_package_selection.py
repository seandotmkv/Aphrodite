"""Catalog, recovery, and terminal package-selection regressions."""

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "config/includes.chroot/opt/aphrodite-os-installer-build"
MODULE = PAYLOAD / "usr/lib/calamares/modules/aphroditeprofiles"
sys.path.insert(0, str(MODULE))

import executor
from selection import APPS, CATALOG, available, preset, validate
import session

loader = SourceFileLoader("terminal_setup", str(PAYLOAD / "usr/bin/aphrodite-os-installer-tui"))
spec = spec_from_loader(loader.name, loader)
terminal = module_from_spec(spec)
sys.modules[loader.name] = terminal
loader.exec_module(terminal)


class CatalogTests(unittest.TestCase):
    def test_app_ids_and_install_identities_are_unique(self):
        self.assertEqual(len(APPS), len(CATALOG["apps"]))
        identities = []
        for app in APPS.values():
            for method, data in app["methods"].items():
                identities.append((method, data.get("ref") or data.get("url")
                                   or data["packages"][0]))
        self.assertEqual(len(identities), len(set(identities)))
        self.assertEqual({"torrentula", "mnemosyne"},
                         {app["id"] for app in APPS.values() if app["category"] == "sean"})

    def test_presets(self):
        self.assertEqual(preset("Minimal"), {"firefox": "apt"})
        self.assertEqual(set(preset("Recommended")), {"firefox", "keepassxc", "pdfarranger"})
        data = {key: {"apt": {"full": True}} for key in APPS if key != "git"}
        chosen = preset("Full", data)
        self.assertIn("gimp", chosen)
        self.assertTrue({"git", "chromium", "resolve", "steam", "timeshift", "extension-manager",
                         "torrentula", "mnemosyne", "obsidian"}.isdisjoint(chosen))
        self.assertEqual(preset("Full"), {"firefox": "apt"})

    def test_profile_migration_and_session_modes(self):
        for mode in ("off", "games", "desktop", "gaming"):
            for suffix in ("", "-resolve"):
                plan = validate(mode + suffix)
                self.assertEqual(plan["session"], mode if mode in {"desktop", "gaming"} else "off")
                self.assertEqual(plan["legacy_resolve"], bool(suffix))
                self.assertEqual("steam" in plan["apps"], mode != "off")
                self.assertEqual("gamescope" in plan["apps"], mode in {"desktop", "gaming"})
        self.assertTrue(available(APPS["extension-manager"], "gnome"))
        self.assertFalse(available(APPS["extension-manager"], "plasma"))

    def test_validates_only_catalog_methods_and_ids(self):
        plan = {"version": 1, "apps": {"brave": "flatpak", "gimp": "apt"},
                "browser": "brave", "session": "off"}
        self.assertEqual(validate({**plan, "command": "ignored"})["apps"], plan["apps"])
        for invalid in ({"apps": {"brave": "unsupported"}}, {"apps": {"unknown": "apt"}},
                        {"apps": {"extension-manager": "apt"}}, {"session": "gaming"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate({**plan, **invalid})


class TerminalTests(unittest.TestCase):
    def test_bulk_and_sessions(self):
        app = terminal.App(demo=True)
        app.page = 4
        app.set_value("category:utility", True)
        app.set_value("all:utility", True)
        self.assertIn("flatseal", app.settings.packages)
        self.assertNotIn("timeshift", app.settings.packages)
        self.assertNotIn("extension-manager", app.settings.packages)
        app.set_value("none:utility", True)
        app.set_value("game_mode", "desktop")
        self.assertEqual(app.plan()["packages"]["session"], "desktop")
        app.set_value("game_mode", "gaming")
        self.assertEqual(app.plan()["packages"]["session"], "gaming")
        app.set_value("game_mode", "off")
        self.assertNotIn("gamescope", app.settings.packages)
        self.assertNotIn("steam", app.settings.packages)
        app.set_value("browser", "chromium")
        self.assertEqual(app.plan()["packages"]["apps"], {"chromium": "apt"})
        app.set_value("app:firefox", "apt")
        self.assertEqual(set(app.plan()["packages"]["apps"]), {"chromium", "firefox"})
        self.assertFalse(app.plan()["installation_enabled"])

    def test_search_and_custom_method(self):
        app = terminal.App(demo=True)
        app.page = 4
        app.set_value("package_search", "raster image")
        self.assertIn("app:gimp", [field[0] for field in app.fields()])
        app.set_value("app:gimp", "flatpak")
        self.assertEqual(app.plan()["packages"]["apps"]["gimp"], "flatpak")


class SessionTests(unittest.TestCase):
    def test_session_helpers_and_sddm_order_leave_autologin_untouched(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(session.os, "chown"):
            root = Path(directory)
            (root / "etc").mkdir()
            (root / "etc/passwd").write_text("sddm:x:109:115:SDDM:/var/lib/sddm:/usr/sbin/nologin\n")
            sddm = root / "etc/sddm.conf"
            sddm.write_text("[Autologin]\nUser=\n")
            state = root / "var/lib/sddm/state.conf"
            state.parent.mkdir(parents=True)
            state.write_text("[Last]\nUser=sean\n")
            session.install_session(root, "desktop")
            self.assertIn(f"Session={session.PLASMA}", state.read_text())
            self.assertIn("User=sean", state.read_text())
            self.assertTrue((root / session.GAMING.lstrip("/")).is_file())
            session.install_session(root, "gaming")
            self.assertIn(f"Session={session.GAMING}", state.read_text())
            session.disable_session(root)
            self.assertIn(f"Session={session.PLASMA}", state.read_text())
            self.assertFalse((root / session.GAMING.lstrip("/")).exists())
            self.assertEqual(sddm.read_text(), "[Autologin]\nUser=\n")


class TransactionTests(unittest.TestCase):
    def test_simulation_blocks_removal_and_unsolicited_apps(self):
        target = object.__new__(executor.Target)
        for output in ("Remv plasma-desktop [1.0]", "Inst steam-installer (1 Debian)"):
            target.apt = Mock(return_value=output)
            with self.assertRaises(executor.TransactionError):
                target.install(["gimp"])
            target.apt.assert_called_once()

    def test_download_precedes_apply_and_failed_download_stops(self):
        target = object.__new__(executor.Target)
        target.check = Mock()
        target.apt = Mock(side_effect=["Inst gimp (1 Debian)", executor.TransactionError("offline")])
        with self.assertRaises(executor.TransactionError):
            target.install(["gimp"])
        self.assertEqual(target.apt.call_count, 2)
        self.assertIn("--download-only", target.apt.call_args.args)
        target.check.assert_not_called()

    def test_switch_only_updates_browser_mime_types(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mime = root / "etc/xdg/mimeapps.list"
            mime.parent.mkdir(parents=True)
            mime.write_text("[Default Applications]\ntext/html=firefox-esr.desktop;\ntext/plain=editor.desktop;\n")
            executor.set_browser(root, "chromium.desktop")
            self.assertIn("text/html=chromium.desktop;", mime.read_text())
            self.assertIn("text/plain=editor.desktop;", mime.read_text())

    def test_offline_replacement_reports_failure_without_substituting_firefox(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ("etc/apt", "etc/xdg", "var/log"):
                (root / folder).mkdir(parents=True)
            mime = root / "etc/xdg/mimeapps.list"
            mime.write_text("[Default Applications]\ntext/html=firefox-esr.desktop;\n")
            target = Mock()
            target.installed.side_effect = lambda package: package == "firefox-esr"
            target.apt.side_effect = executor.TransactionError("offline")
            plan = validate({"version": 1, "apps": {"chromium": "apt"},
                             "browser": "chromium", "session": "off"})
            with patch.object(executor, "Target", return_value=target):
                result = executor.apply_locked(root, plan, lambda _: None, root)
            self.assertIn("Chromium skipped after index failure.", result)
            self.assertTrue(any('Selected browser failed; no substitute' in line for line in result))
            self.assertNotIn('text/html=firefox-esr.desktop;', mime.read_text())
            target.remove_browser.assert_called_once_with('firefox-esr')

    def test_timed_out_command_is_reaped(self):
        target = object.__new__(executor.Target)
        with tempfile.TemporaryDirectory() as directory:
            target.root = Path(directory)
            target.output = Mock()
            chroot = target.root / "chroot"
            chroot.write_text('#!/bin/sh\nshift\nexec "$@"\n')
            chroot.chmod(0o755)
            with patch.dict(os.environ, {"PATH": directory + ":" + os.environ["PATH"]}):
                with self.assertRaisesRegex(executor.TransactionError, "timed out"):
                    target.command("/bin/sleep", "5", timeout=0.05)

    def test_browser_purge_requires_a_single_removal(self):
        target = object.__new__(executor.Target)
        target.apt = Mock(return_value="Purg firefox-esr [1]\nRemv plasma-desktop [1]")
        with self.assertRaises(executor.TransactionError):
            target.remove_browser("firefox-esr")
        target.apt.assert_called_once()


if __name__ == "__main__":
    unittest.main()
