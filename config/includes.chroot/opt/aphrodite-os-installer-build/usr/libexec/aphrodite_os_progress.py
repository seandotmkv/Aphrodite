"""Terminal installation state and panels, fed only by backend events."""

from collections import deque
from datetime import datetime, timezone
import math
import queue
import textwrap
import time


STAGES = (("preflight", "Checking the installation target"),
          ("storage", "Partitioning and formatting"),
          ("extract", "Copying the base system"),
          ("account", "Configuring your account"),
          ("filesystem", "Configuring filesystems"),
          ("packages", "Installing additional applications"),
          ("boot", "Installing the bootloader"),
          ("services", "Configuring system services"),
          ("verify", "Final verification and cleanup"))
PANELS = ("Installation Details", "Package Installation", "Live Installation Logs", "System Configuration")


def duration(seconds):
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02}m" if hours else f"{minutes}m {seconds:02}s"


class Inbox:
    """Keep telemetry reliable while bounding noisy display logs independently."""
    def __init__(self):
        self.events = queue.SimpleQueue()
        self.logs = queue.Queue(maxsize=2048)
        self.dropped = 0

    def put(self, event):
        if isinstance(event, str):
            event = {"kind": "log", "text": event}
        event = dict(event, timestamp=event.get("timestamp") or datetime.now(timezone.utc).isoformat())
        if event["kind"] == "log":
            try:
                self.logs.put_nowait(event)
            except queue.Full:
                self.dropped += 1
                try:
                    self.logs.get_nowait()
                    self.logs.put_nowait(event)
                except (queue.Full, queue.Empty):
                    pass
        else:
            self.events.put(event)

    def drain(self, limit=256):
        result = []
        for source in (self.events, self.logs):
            while len(result) < limit:
                try:
                    result.append(source.get_nowait())
                except queue.Empty:
                    break
        return result


class Progress:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.started = self.ended = None
        self.changed = clock()
        self.status = "waiting"
        self.stage = "preflight"
        self.states = {key: "waiting" for key, _ in STAGES}
        self.fractions = {key: 0.0 for key, _ in STAGES}
        self.stage_started = None
        self.operation = "Waiting for backend"
        self.command = ""
        self.command_elapsed = 0
        self.logs = deque(maxlen=1200)
        self.history = deque(maxlen=2000)
        self.packages = {}
        self.apps = {}
        self.app_fractions = {}
        self.error = ""
        self.warning = ""
        self.revision = 0

    def begin(self, selections):
        self.started = self.clock()
        self.status = "active"
        self.apps = {key: {"name": name, "state": "waiting"} for key, name in selections.items()}

    def consume(self, event):
        self.changed = self.clock()
        self.revision += 1
        kind = event.get("kind")
        if kind == "log":
            text = event.get("text", "")
            stamp = event.get("timestamp", "")[11:19]
            self.logs.append(f"{stamp}  {text}")
        elif kind == "stage":
            key = event["id"]
            if key not in self.states:
                return
            if event.get("state") == "complete":
                self.states[key], self.fractions[key] = "complete", 1.0
            else:
                self.stage, self.stage_started = key, self.clock()
                self.states[key] = "active"
                self.operation = event.get("text", dict(STAGES)[key])
                self.command = ""
        elif kind == "fraction":
            value = event.get("value")
            key = event.get("id", self.stage)
            if key in self.fractions and isinstance(value, (int, float)) and math.isfinite(value):
                self.fractions[key] = max(self.fractions[key], min(.99, max(0, value)))
        elif kind == "command":
            self.command = event["text"]
            self.operation = self.command
            self.command_elapsed = 0
        elif kind == "heartbeat":
            self.command_elapsed = event["elapsed"]
        elif kind == "apt_plan":
            for name in event["packages"]:
                self.packages.setdefault(name, "waiting")
        elif kind == "apt_state":
            name = event["id"]
            # APT simulation sometimes omits the native architecture, while
            # dpkg status includes it. Only count solver-planned identities.
            if name not in self.packages:
                matches = [key for key in self.packages if key.split(":")[0] == name.split(":")[0]]
                name = matches[0] if len(matches) == 1 else None
            if name in self.packages:
                if self.packages[name] != event["state"]:
                    self.history.append(f"{event.get('timestamp', '')[11:19]} [{event['state']}] APT: {name}")
                self.packages[name] = event["state"]
            if event["state"] == "installing":
                self.operation = "Installing: " + event["id"]
        elif kind == "app":
            key = event["id"]
            if self.apps.get(key, {}).get("state") != event["state"]:
                self.history.append(f"{event.get('timestamp', '')[11:19]} [{event['state']}] {event['name']}")
            self.apps[key] = {"name": event["name"], "state": event["state"]}
            if event["state"] == "installing":
                self.operation = "Installing: " + event["name"]
            self.update_packages()
        elif kind == "app_fraction":
            value = event.get("value")
            if isinstance(value, (int, float)) and math.isfinite(value) and event["id"] in self.apps:
                self.app_fractions[event["id"]] = min(.99, max(0, value))
                self.update_packages()
        elif kind == "warning":
            self.warning = event["text"]
        elif kind == "error":
            self.error = event["text"]
            self.states[self.stage] = "error"

    def update_packages(self):
        units = sum(1 if row["state"] in {"complete", "already installed", "failed", "skipped", "first-run-required"}
                    else self.app_fractions.get(key, 0) for key, row in self.apps.items())
        self.fractions["packages"] = units / max(1, len(self.apps)) * .99

    def finish(self, status, message, warnings=()):
        self.ended = self.clock()
        self.status = "error" if status else "complete"
        if status:
            self.error = message
            self.states[self.stage] = "error"
        elif warnings:
            self.warning = "; ".join(warnings)
        self.operation = message
        self.revision += 1

    @property
    def elapsed(self):
        if self.started is None:
            return 0
        return (self.ended if self.ended is not None else self.clock()) - self.started

    @property
    def percentage(self):
        if self.status == "complete":
            return 100
        return min(99, int(100 * sum(self.fractions.values()) / len(STAGES)))

    def eta(self):
        # A changing package denominator and uneven installation stages make
        # extrapolating an overall ETA dishonest. Report only a measured stage ETA.
        fraction = self.fractions[self.stage]
        if self.stage == "extract" and self.stage_started is not None and .05 < fraction < .99:
            elapsed = self.clock() - self.stage_started
            if elapsed >= 5:
                return "Copy stage: about " + duration(elapsed * (1 - fraction) / fraction) + " left"
        return "Time remaining: estimating" if self.status == "active" else "Total time: " + duration(self.elapsed)

    def package_counter(self):
        installed = sum(value in {"complete", "configured"} for value in self.packages.values())
        suffix = "known" if self.states["packages"] != "complete" else "planned"
        return f"APT packages: {installed} / {len(self.packages)} {suffix}"


class Panels:
    def __init__(self, model, reduced_motion=True):
        self.model = model
        self.open = set()
        self.focus = self.scroll = 0
        self.follow = True
        self.frozen_logs = None
        self.search = ""
        self.searching = False
        self.message = ""
        self.reduced_motion = reduced_motion
        self.hits = {}
        self.copy = self.save = self.restart = False
        self.last_error = self.last_warning = ""
        self.transition = None

    def update(self):
        if self.transition and self.model.clock() - self.transition[1] >= .12:
            if not self.transition[2]:
                self.open.discard(self.transition[0])
            self.transition = None
        if self.model.error and self.model.error != self.last_error:
            self.last_error = self.model.error
            self.open.update({0, 2})
            self.focus = 2
            self.scroll = 0
        elif self.model.warning and self.model.warning != self.last_warning:
            self.last_warning = self.model.warning
            self.open.add(1)
            self.focus = 1

    def key(self, key):
        if self.searching:
            if key in ("ENTER", "ESC"):
                self.searching = False
            elif key == "BACKSPACE":
                self.search = self.search[:-1]
            elif key == "CLEAR":
                self.search = ""
            elif len(key) == 1 and key.isprintable() and len(self.search) < 80:
                self.search += key
            self.scroll = 0
            return
        if key in ("TAB", "DOWN", "BTAB", "UP"):
            self.focus = (self.focus + (1 if key in ("TAB", "DOWN") else -1)) % 4
            self.scroll = 0
        elif key in ("1", "2", "3", "4"):
            self.focus = int(key) - 1
            self.toggle()
        elif key in ("ENTER", " "):
            self.toggle()
        elif key in ("LEFT", "RIGHT"):
            (self.open.add if key == "RIGHT" else self.open.discard)(self.focus)
        elif key in ("PGUP", "PGDN"):
            self.scroll = max(0, self.scroll + (-5 if key == "PGUP" else 5))
            if key == "PGUP" and self.focus == 2:
                self.pause()
        elif key in ("HOME", "END"):
            self.scroll = 0 if key == "HOME" else 10**9
        elif key == "/":
            self.focus = 1
            self.open.add(1)
            self.searching = True
            self.scroll = 0
        elif key in ("p", "P"):
            if self.follow:
                self.pause()
            else:
                self.follow, self.frozen_logs, self.scroll = True, None, 0
        elif key in ("c", "C"):
            self.copy = True
        elif key in ("s", "S"):
            self.save = True
        elif key == "F6":
            self.reduced_motion = not self.reduced_motion
        elif key in ("r", "R") and self.model.status == "complete":
            self.restart = True

    def pause(self):
        if self.follow:
            self.frozen_logs = list(self.model.logs)
        self.follow = False

    def toggle(self):
        opening = self.focus not in self.open
        if self.reduced_motion:
            (self.open.add if opening else self.open.discard)(self.focus)
            self.transition = None
        else:
            self.transition = (self.focus, self.model.clock(), opening)
            self.open.add(self.focus)
        self.scroll = 0

    def content(self, index):
        m = self.model
        if index == 0:
            completed = [label for key, label in STAGES if m.states[key] == "complete"]
            return ["Current stage: " + dict(STAGES)[m.stage],
                    "Completed: " + (", ".join(completed) or "None yet"),
                    m.package_counter(), "Elapsed: " + duration(m.elapsed),
                    "Stage progress: " + str(int(m.fractions[m.stage] * 100)) + "%",
                    "Package speed: " + (f"{sum(v in {'complete', 'configured'} for v in m.packages.values()) / (m.elapsed / 60):.1f}/min (session average)"
                                           if m.elapsed >= 10 and m.packages else "measuring"),
                    "Overall percentage estimates completed stages, not download bytes.",
                    "The base system is copied from SquashFS; it is not counted as new APT packages."]
        if index == 1:
            lines = ["Search: " + self.search + ("_" if self.searching else "  (/ to search)"),
                     "Selected applications (APT dependencies are listed separately):"]
            if m.warning:
                lines.insert(1, "WARNING: " + m.warning)
            for key, row in m.apps.items():
                text = f"[{row['state']}] {row['name']} ({key})"
                if self.search.casefold() in text.casefold():
                    lines.append(text)
            lines.append("APT packages, including dependencies:")
            for name, state in sorted(m.packages.items()):
                text = f"[{state}] {name}"
                if self.search.casefold() in text.casefold():
                    lines.append(text)
            history = [line for line in m.history if self.search.casefold() in line.casefold()]
            if history:
                lines.append("Recent package events (bounded display history):")
                lines.extend(history[-250:])
            return lines
        if index == 2:
            lines = ["[Copy Logs: c]  [Save Logs: s]  [" + ("Pause: p" if self.follow else "Resume: p") + "]",
                     "Display is a bounded tail; Save Logs exports the complete diagnostic file."]
            if m.error:
                lines.append("ERROR: " + m.error)
            lines.extend(list(m.logs)[-250:] if self.follow else (self.frozen_logs or [])[-250:])
            return lines
        return [f"[{m.states[key]}] {label}" for key, label in STAGES
                if key in {"storage", "filesystem", "account", "boot", "services", "verify"}]

    def rows(self, width):
        result = []
        for index, title in enumerate(PANELS):
            result.append((index, ("v " if index in self.open else "> ") + title, True))
            if index in self.open:
                body = []
                for text in self.content(index):
                    for line in textwrap.wrap(text, max(1, width - 4), replace_whitespace=True) or [""]:
                        body.append((index, "  " + line, False))
                if self.transition and self.transition[0] == index:
                    fraction = min(1, max(0, (self.model.clock() - self.transition[1]) / .12))
                    if not self.transition[2]:
                        fraction = 1 - fraction
                    body = body[:int(len(body) * fraction)]
                result.extend(body)
        return result


def draw(view, canvas, log_path, demo=False):
    """Render within the existing terminal frame; the progress header never scrolls."""
    m = view.model
    width, height = canvas.width, canvas.height
    view.hits = {}
    if width < 60 or height < 18:
        canvas.put(0, 0, f"aphrodite-os: {m.status} {m.percentage}% | enlarge terminal", 4)
        canvas.put(1, 0, m.operation, 0, width)
        return
    canvas.put(3, 3, " Installation " + ("(DEMO)" if demo else ""), 3, width - 6)
    if m.status == "complete":
        title = "Aphrodite OS installed with warnings" if m.warning else "Aphrodite OS has been installed successfully!"
        canvas.put(5, 3, title, 5, width - 6)
        additional = sum(row["state"] == "complete" for row in m.apps.values())
        canvas.put(7, 3, f"Total time: {duration(m.elapsed)} | Additional applications installed: {additional}", 0, width - 6)
        canvas.put(8, 3, "[ Restart System: r ]   View logs: 3   Summary: 1   Close: q", 1, width - 6)
        view.hits[8] = "r"
        top = 10
    else:
        title = "Installation stopped" if m.status == "error" else "Installing Aphrodite OS"
        canvas.put(5, 3, title, 4 if m.status == "error" else 1, width - 6)
        canvas.put(6, 3, dict(STAGES)[m.stage], 0, width - 6)
        bar_width = width - 15
        filled = bar_width * m.percentage // 100
        canvas.put(7, 3, "[" + "#" * filled + "-" * (bar_width - filled) + f"] {m.percentage:3}%", 1)
        canvas.put(8, 3, m.package_counter() + " | overall: stage estimate", 2, width - 6)
        canvas.put(9, 3, "Current: " + m.operation, 0, width - 6)
        canvas.put(10, 3, m.eta() + " | elapsed " + duration(m.elapsed), 2, width - 6)
        state = "ERROR: " + m.error if m.error else f"Status: {m.status}"
        if m.command_elapsed >= 5 and m.status == "active":
            state += f" | command running {duration(m.command_elapsed)}"
        canvas.put(11, 3, state, 4 if m.error else 5, width - 6)
        top = 13
    rows = view.rows(width - 6)
    capacity = max(1, height - top - 4)
    # Focused panel headers remain reachable. Its body scrolls independently of
    # the fixed progress header. Other headers return immediately on Up/Down.
    anchor = next(i for i, row in enumerate(rows) if row[0] == view.focus and row[2])
    end = next((i for i in range(anchor + 1, len(rows)) if rows[i][2]), len(rows))
    if len(rows) <= capacity:
        view.scroll = 0
        visible = rows
    elif view.focus in view.open:
        section = rows[anchor:end]
        if view.focus == 2 and view.follow:
            # Keep log actions and the latest output visible, without losing the header.
            pinned = section[:3]
            rest = section[3:]
            section = pinned + rest[-max(1, capacity - len(pinned)):]
        view.scroll = min(view.scroll, max(0, len(section) - capacity))
        visible = section[view.scroll:view.scroll + capacity]
        if view.scroll and visible and not visible[0][2]:
            visible = [section[0]] + section[view.scroll + 1:view.scroll + capacity]
    else:
        view.scroll = 0
        visible = [row for row in rows if row[2]][:capacity]
    for offset, (index, text, header) in enumerate(visible):
        row = top + offset
        style = 3 if header and index == view.focus else 1 if header else 0
        if text.lstrip().startswith(("ERROR:", "WARNING:", "[failed]", "[skipped]")):
            style = 4
        canvas.put(row, 3, text.ljust(width - 6) if header else text, style, width - 6)
        if header:
            view.hits[row] = str(index + 1)
        elif text.lstrip().startswith("[Copy Logs:"):
            view.hits[row] = [(3, 20, "c"), (20, 36, "s"), (36, width - 3, "p")]
    message = view.message or ("Log: " + str(log_path) if log_path else "")
    canvas.put(height - 3, 3, message, 4 if view.message else 2, width - 6)
    canvas.put(height - 2, 3, "1-4 panels | Enter toggle | PgUp/Dn scroll | / search | c/s logs", 2, width - 6)
