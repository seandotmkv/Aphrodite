"""Apply catalog choices to a mounted Calamares target."""

from configparser import ConfigParser, Error as ConfigError
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shlex
import re
from datetime import datetime, timezone
import shutil

from processio import run as run_process, CommandTimeout
from integration import Manifest, launcher, desktop_file, write_pins
from repositories import configure_brave

from selection import APPS, DEFAULT, HERE, validate
from session import disable_session, GAMING, gpu_drivers, install_session
from sourceapps import deploy, SOURCE_LAYOUT

APT = ("apt-get", "-o", "DPkg::Lock::Timeout=45", "-o", "Acquire::Retries=1", "-o", "Acquire::http::Timeout=15",
       "-o", "Acquire::https::Timeout=15")
BACKPORTS = """Types: deb
URIs: https://deb.debian.org/debian
Suites: trixie-backports
Components: main contrib
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
"""
FLATHUB = "https://dl.flathub.org/repo/flathub.flatpakrepo"
TARGET_LOG = "var/log/aphrodite-os-selected-packages.log"


class TransactionError(RuntimeError):
    pass


class BrokenTarget(TransactionError):
    pass


def package_changes(output, verbs):
    return {line.split()[1].split(":")[0] for line in output.splitlines()
            if line.split()[:1] and line.split()[0] in verbs and len(line.split()) > 1}


class Target:
    def __init__(self, root, output, *, installed=False):
        self.root = Path(root).resolve(strict=True)
        if ((not installed and (self.root == Path("/") or not os.path.ismount(self.root)
                or self.root.stat().st_dev == Path("/").stat().st_dev))
                or (installed and self.root != Path('/'))
                or (self.root / "run/live/medium/live/filesystem.squashfs").exists()
                or not (self.root / "var/lib/dpkg/status").is_file()
                or "ID=aphrodite" not in (self.root / "etc/os-release").read_text().splitlines()):
            raise ValueError("Expected a separately mounted aphrodite-os installation target")
        self.output = output
        self.events = None

    def event(self, event):
        callback = getattr(self, "events", None)
        if callback:
            callback(event)

    def apt_status(self, line):
        # Architecture qualifiers can contain colons. Never split at fixed
        # colon offsets or infer completion merely from pmstatus's percentage.
        match = re.match(r"^pm(status|error):(.+?):([0-9]+(?:\.[0-9]+)?)%?:(.*)$", line)
        if match:
            kind, package, _fraction, text = match.groups()
            if package and package != "dpkg-exec":
                self.event({"kind": "apt_state", "id": package,
                            "state": "failed" if kind == "error" else
                                     "configured" if text.startswith("Installed ") else "installing"})
            if kind == "status" and getattr(self, "active_app", None):
                self.event({"kind": "app_fraction", "id": self.active_app,
                            "value": min(.99, float(_fraction) / 100)})
            if kind == "error":
                self.output("APT ERROR: " + text)

    def command(self, *args, timeout=120):
        self.output("$ " + shlex.join(args))
        self.event({"kind": "command", "text": shlex.join(args)})
        try:
            status, output, length = run_process(
                ["chroot", str(self.root), *args], output=self.output, timeout=timeout,
                env=dict(os.environ, LC_ALL="C", DEBIAN_FRONTEND="noninteractive"),
                apt_status=self.apt_status if args[0] == "apt-get" and "--no-download" in args
                           and "install" in args else None,
                heartbeat=lambda elapsed: self.event({"kind": "heartbeat", "elapsed": elapsed}))
        except CommandTimeout as error:
            raise TransactionError(str(error)) from None
        if status:
            raise TransactionError(f"{args[0]} exited with status {status}. {output.strip()[-450:]}")
        if length > 200_000 and "-s" in args:
            raise TransactionError("Solver output exceeded the validation limit")
        return output

    def apt(self, *args, timeout=120):
        return self.command(*APT, *args, timeout=timeout)

    def check(self):
        try:
            audit = self.command("dpkg", "--audit")
            if audit.strip():
                raise TransactionError("dpkg reports incomplete package configuration")
            self.apt("check")
        except TransactionError as error:
            raise BrokenTarget(f"Target package manager needs recovery. {error}") from error

    def install(self, packages, permitted=(), suite="trixie"):
        if suite == "trixie-backports":
            options = ("-t", suite)
        else:
            options = ()
        command = ("--no-remove", "--no-install-recommends", *options, "install", *packages)
        plan = self.apt("-s", *command)
        if package_changes(plan, {"Remv", "Purg"}):
            raise TransactionError("APT proposed removals")
        optional = {spec["packages"][0].split(":")[0]
                    for app in APPS.values() for name, spec in app["methods"].items()
                    if name == "apt"}
        allowed = set(permitted) | {name.split(":")[0] for name in packages}
        unsolicited = (package_changes(plan, {"Inst"}) & optional) - allowed
        if unsolicited:
            raise TransactionError("APT requires an additional catalog choice: " + ", ".join(sorted(unsolicited)))
        changes = sorted({line.split()[1] for line in plan.splitlines()
                          if line.startswith("Inst ") and len(line.split()) > 1})
        self.event({"kind": "apt_plan", "packages": changes})
        self.apt("-y", "--download-only", *command, timeout=1200)
        self.apt("-y", "--no-download", *command, timeout=1800)
        self.check()
        for package in changes:
            self.event({"kind": "apt_state", "id": package, "state": "complete"})

    def remove_browser(self, package):
        command = ("--no-auto-remove", "purge", package)
        plan = self.apt("-s", *command)
        if package_changes(plan, {"Remv", "Purg"}) != {package} or package_changes(plan, {"Inst"}):
            raise TransactionError(f"APT cannot remove only {package}")
        self.apt("-y", "--no-download", *command)
        self.check()

    def installed(self, package):
        try:
            output = self.command("dpkg-query", "-W", "-f=${Package}\t${Architecture}\t${db:Status-Status}\n", package)
        except TransactionError:
            return False
        name, separator, architecture = package.partition(":")
        # This image supports amd64; an unqualified package must not be
        # satisfied by its i386 edition alone. Architecture: all is valid.
        wanted = {architecture} if separator else {"amd64", "all"}
        return any(len(fields) == 3 and fields[0] == name and fields[1] in wanted
                   and fields[2] == "installed"
                   for line in output.splitlines() if (fields := line.split("\t")))


@contextmanager
def live_dns(root):
    resolver = root / "etc/resolv.conf"
    backup = resolver.with_name(".aphrodite-os-resolv.conf-original")
    # Restore the original first if a prior process was interrupted.
    if backup.exists() or backup.is_symlink():
        backup.replace(resolver)
    if resolver.exists() or resolver.is_symlink():
        resolver.rename(backup)
    try:
        resolver.write_bytes(Path("/etc/resolv.conf").read_bytes())
        yield
    finally:
        if backup.exists() or backup.is_symlink():
            backup.replace(resolver)
        else:
            resolver.unlink(missing_ok=True)


def set_browser(root, launcher):
    mime = root / "etc/xdg/mimeapps.list"
    associations = {"text/html", "application/xhtml+xml", "x-scheme-handler/http", "x-scheme-handler/https"}
    lines = [f"{line.split('=', 1)[0]}={launcher};"
             if line.split("=", 1)[0] in associations else line
             for line in mime.read_text().splitlines()]
    if launcher is None:
        lines = [line for line in lines if line.split('=', 1)[0] not in associations]
    temporary = mime.with_suffix(".sean-tmp")
    temporary.write_text("\n".join(lines) + "\n")
    temporary.replace(mime)


def apply(root, plan, notify=print, live_log=None, *, progress=None, events=None, installed=False):
    target = Target(root, lambda _: None, installed=installed)
    state = target.root / "var/lib/aphrodite-os"
    state.mkdir(mode=0o755, parents=True, exist_ok=True)
    with (state / "selected-packages.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise TransactionError("Another aphrodite-os package executor is running on this target") from error
        return apply_locked(target.root, plan, notify, state, live_log, progress, events, installed)


def apply_locked(root, plan, notify, state, live_log=None, progress=None, events=None, installed=False):
    root = Path(root)
    results = []
    log = []
    manifest = Manifest(root, plan)
    reasons = {}
    last_error = {'text': ''}
    diagnostic = root / TARGET_LOG
    diagnostic.parent.mkdir(parents=True, exist_ok=True)
    diagnostic_stream = diagnostic.open('a', encoding='utf-8', buffering=1)
    diagnostic.chmod(0o600)

    def output(message):
        print(datetime.now(timezone.utc).isoformat(), message, file=diagnostic_stream, flush=True)
        if progress:
            progress(message)
        log.append(message[-4000:])
        if len(log) > 80:
            del log[0]

    target = Target(root, output, installed=installed)
    target.events = events

    def app_event(key, status):
        manifest.result(key, status, reasons.get(key))
        if events:
            events({"kind": "app", "id": key, "name": APPS[key]["name"], "state": status})

    def record(message):
        results.append(message)
        print(datetime.now(timezone.utc).isoformat(), message, file=diagnostic_stream, flush=True)
        notify(message)
        if message.startswith('Dedicated session skipped'):
            manifest.value['gaming_session'].update(status='skipped', reason=message)
            manifest.save()
        elif message.startswith('Dedicated gaming session complete'):
            manifest.value['gaming_session'].update(status='configured', reason=None)
            manifest.save()
        elif message.startswith('Dedicated gaming session incomplete'):
            manifest.value['gaming_session'].update(status='failed', reason=message)
            manifest.save()

    def attempt(label, action):
        try:
            action()
        except BrokenTarget:
            raise
        except (TransactionError, OSError, StopIteration, ValueError, ConfigError) as error:
            last_error['text'] = str(error)
            reasons.update({key: str(error) for key, app in APPS.items() if app['name'] == label})
            record(f"{label} incomplete. {error}")
            target.check()
            return False
        record(f"{label} complete.")
        return True

    def install_app(key, method):
        target.active_app = key
        app = APPS[key]
        spec = app["methods"][method]
        for alternate in app["methods"]:
            if alternate != method and already_installed(key, alternate):
                raise TransactionError(f"The {alternate} edition is already installed. Remove it before switching methods.")
        if method == "apt":
            if key == 'brave':
                configure_brave(target)
            packages = spec["packages"]
            if key == "gamescope" and plan["session"] != "off":
                packages = packages + ["xwayland", "kdialog", "qdbus-qt6"]
            target.install(packages, permitted, spec["suite"])
            if not all(target.installed(package) for package in packages):
                missing = [package for package in packages if not target.installed(package)]
                raise TransactionError("Expected packages are missing: " + ", ".join(missing))
            executable = {"steam": "/usr/games/steam", "gamescope": "/usr/bin/gamescope",
                          "brave": "/usr/bin/brave-browser", "firefox": "/usr/bin/firefox-esr",
                          "chromium": "/usr/bin/chromium"}.get(key)
            if executable:
                target.command("test", "-x", executable)
            entry = launcher(key, method)
            if entry and not desktop_file(root, entry):
                raise TransactionError("Installed application desktop entry is missing: " + entry)
            return
        if method == "source":
            deploy(target, key, app)
            return
        if not target.installed("flatpak"):
            target.install(["flatpak"])
        target.command("flatpak", "remote-add", "--system", "--if-not-exists", "flathub", FLATHUB)
        config = ConfigParser(interpolation=None)
        config.read(root / "var/lib/flatpak/repo/config")
        remote = 'remote "flathub"'
        if (config.get(remote, "url", fallback="").rstrip("/") != "https://dl.flathub.org/repo"
                or not config.getboolean(remote, "gpg-verify", fallback=False)
                or not config.getboolean(remote, "gpg-verify-summary", fallback=False)):
            raise TransactionError("The target's Flathub remote does not use the expected URL and signature checks")
        ref = "app/" + spec["ref"] + "/x86_64/stable"
        transaction = ("flatpak", "install", "--system", "--noninteractive")
        target.command(*transaction, "--no-deploy", "flathub", ref, timeout=1200)
        target.command(*transaction, "--no-pull", "flathub", ref, timeout=1200)
        target.command("flatpak", "info", "--system", ref)
        if not desktop_file(root, spec['ref'] + '.desktop'):
            raise TransactionError("Flatpak desktop export is missing: " + spec['ref'])

    def browser_launcher(key, method):
        app = APPS[key]
        if method == "flatpak":
            launcher = app["methods"][method]["ref"] + ".desktop"
            folder = "var/lib/flatpak/exports/share/applications"
        else:
            launcher, folder = app["launcher"], "usr/share/applications"
        target.command("test", "-s", "/" + folder + "/" + launcher)
        return launcher

    def already_installed(key, method):
        spec = APPS[key]["methods"][method]
        if method == "apt":
            entry = launcher(key, method)
            return (all(target.installed(package) for package in spec["packages"])
                    and (not entry or desktop_file(root, entry) is not None))
        if method == "source":
            marker = root / "usr/local/share/aphrodite-os" / key / ".installed-commit"
            return (marker.is_file() and marker.read_text().strip() == f'{SOURCE_LAYOUT} {spec["commit"]}'
                    and (root / 'usr/local/share/aphrodite-os' / key / spec['entry']).is_file()
                    and desktop_file(root, key + '.desktop') is not None)
        if not target.installed("flatpak"):
            return False
        try:
            target.command("flatpak", "info", "--system", spec["ref"])
        except TransactionError:
            return False
        return desktop_file(root, spec['ref'] + '.desktop') is not None

    permitted = {APPS[key]["methods"][method]["packages"][0].split(":")[0]
                 for key, method in plan["apps"].items() if method == "apt"}
    installed = set()
    try:
        target.check()
        installed = {key for key, method in plan["apps"].items()
                     if already_installed(key, method)}
        # The live browser is not an implicit selection for the installed OS.
        for key in plan["apps"]:
            if key in installed:
                app_event(key, "first-run-required" if key == "steam" else "already installed")
            if key in installed and key != DEFAULT:
                record(f"{APPS[key]['name']} already installed.")
        pending_plan = {k: plan[k] for k in ("version", "apps", "browser", "session")}
        if "pins" in plan:
            pending_plan['pins'] = plan['pins']
        if plan["legacy_resolve"] or plan["legacy_gaming"]:
            mode = plan["session"] if plan["session"] != "off" else "games" if plan["legacy_gaming"] else "off"
            pending_plan = mode + ("-resolve" if plan["legacy_resolve"] else "")
        validate(pending_plan)
        retry = state / "selected-packages.json"
        temporary = retry.with_suffix(".tmp")
        temporary.write_text(json.dumps(pending_plan, indent=2) + "\n")
        temporary.replace(retry)
        (root / "etc/apt/sources.list").write_text((HERE / "debian.list").read_text())
        pending = [(key, method) for key, method in plan["apps"].items() if key not in installed]
        if plan["session"] != "off" and "gamescope" in installed and not all(
                target.installed(package) for package in ("xwayland", "kdialog", "qdbus-qt6")):
            installed.remove("gamescope")
            pending.append(("gamescope", "apt"))
        pending.sort(key=lambda entry: entry[0] != plan["browser"])
        if pending or plan["legacy_resolve"] or plan["legacy_gaming"]:
            with live_dns(root):
                if "steam" in plan["apps"]:
                    attempt("Steam architecture", lambda: target.command("dpkg", "--add-architecture", "i386"))
                if "gamescope" in plan["apps"]:
                    source = root / "etc/apt/sources.list.d/aphrodite-os-gamescope.sources"
                    source.write_text(BACKPORTS)
                ready = attempt("Debian indexes", lambda: target.apt(
                    "-o", "APT::Update::Error-Mode=any", "update", timeout=180))
                index_error = last_error['text'] if not ready else ''
                for key, method in pending:
                    if not ready and (method != "flatpak" or not target.installed("flatpak")):
                        reasons[key] = 'Debian index refresh failed: ' + index_error
                        record(f"{APPS[key]['name']} skipped after index failure.")
                        app_event(key, "skipped")
                        if events:
                            events({"kind": "warning", "text": f"{APPS[key]['name']} skipped after index failure."})
                    else:
                        app_event(key, "installing")
                        if attempt(APPS[key]["name"], lambda: install_app(key, method)):
                            installed.add(key)
                            app_event(key, "first-run-required" if key == "steam" else "complete")
                            if key == 'steam':
                                record('Steam launcher and graphics dependencies verified. First launch downloads and initializes the official client; no placeholder is pinned.')
                        else:
                            app_event(key, "failed")
                            if events:
                                events({"kind": "warning", "text": f"{APPS[key]['name']} was not installed. See package diagnostics."})
                if plan["legacy_gaming"] and ready and "steam" in installed:
                    profiles = json.loads((HERE / "profiles.json").read_text())
                    attempt("Legacy gaming libraries", lambda: target.install(profiles["gaming"]))
                if plan["legacy_resolve"]:
                    profiles = json.loads((HERE / "profiles.json").read_text())
                    drivers = gpu_drivers()
                    compute = profiles["resolve_amd"] if "amdgpu" in drivers else []
                    if drivers & {"i915", "xe"}:
                        compute += profiles["resolve_intel"]
                    if ready and compute:
                        attempt("Legacy Resolve dependencies",
                                lambda: target.install(profiles["resolve_common"] + compute))
                    else:
                        record("Legacy Resolve dependencies skipped. Repository indexes and an AMD or Intel DRM device are required.")
                    record("DaVinci Resolve requires a separate licensed vendor installer and compatible hardware.")
        preferred = plan["browser"]
        if preferred and preferred in installed and attempt(
                APPS[preferred]["name"] + " default handler",
                lambda: set_browser(root, browser_launcher(preferred, plan["apps"][preferred]))):
            record(APPS[preferred]['name'] + ' verified as the selected default browser.')
        else:
            set_browser(root, None)
            record((APPS[preferred]['name'] + ' incomplete. Selected browser failed; no substitute was installed.'
                    if preferred else 'No browser selected. Use the software manager to add one later.'))
        if 'firefox' not in plan['apps'] and target.installed('firefox-esr'):
            if not attempt('Remove unselected Firefox ESR', lambda: target.remove_browser('firefox-esr')):
                raise BrokenTarget('Could not remove unselected Firefox safely; do not report this installation as finalized.')
        if plan["session"] != "off":
            if not {"steam", "gamescope"} <= installed:
                record("Dedicated session skipped. Steam and Gamescope must both install successfully.")
            elif gpu_drivers().isdisjoint({"amdgpu", "i915", "xe"}):
                record("Dedicated session skipped. No supported AMD or Intel DRM device was detected.")
            else:
                attempt("Dedicated gaming session", lambda: install_session(root, plan["session"]))
        elif (root / GAMING.lstrip("/")).exists():
            attempt("Disable dedicated gaming session", lambda: disable_session(root))
        target.check()
        write_pins(root, plan, manifest)
    except (TransactionError, OSError) as error:
        for key, app in manifest.value['applications'].items():
            if app['status'] == 'installing':
                manifest.result(key, 'failed', str(error))
        record(f"Package finalization stopped. {error}")
        raise
    finally:
        diagnostic_stream.close()
        if live_log is not None:
            try:
                shutil.copyfile(diagnostic, live_log)
                Path(live_log).chmod(0o600)
            except OSError as error:
                notify(f"Could not write live package diagnostics. {error}")
    return results
