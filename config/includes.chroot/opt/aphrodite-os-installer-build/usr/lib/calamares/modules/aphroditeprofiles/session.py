"""Install the dedicated SDDM session and keep its login order independent of autologin."""

from configparser import ConfigParser
import os
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
GAMING = "/usr/local/share/wayland-sessions/aphrodite-os-gaming.desktop"
PLASMA = "/usr/share/wayland-sessions/plasma.desktop"
INSTALL_PATHS = {
    "aphrodite-os-gaming": "/usr/local/bin/",
    "aphrodite-os-switch-gaming": "/usr/local/bin/",
    "aphrodite-os-gaming.desktop": "/usr/local/share/wayland-sessions/",
    "aphrodite-os-switch-gaming.desktop": "/usr/local/share/applications/",
    "steamos-session-select": "/usr/local/lib/aphrodite-os/gaming/",
}


def gpu_drivers():
    return {node.resolve().name for node in
            Path("/sys/class/drm").glob("renderD*/device/driver")}


def set_preference(root, preference, only_if_gaming=False):
    accounts = (root / "etc/passwd").read_text().splitlines()
    sddm = next(row.split(":") for row in accounts if row.startswith("sddm:"))
    state = root / sddm[5].lstrip("/") / "state.conf"
    settings = ConfigParser(interpolation=None)
    settings.optionxform = str
    settings.read(state)
    if only_if_gaming and settings.get("Last", "Session", fallback=None) != GAMING:
        return
    if not settings.has_section("Last"):
        settings.add_section("Last")
    settings.set("Last", "Session", GAMING if preference == "gaming" else PLASMA)
    state.parent.mkdir(parents=True, exist_ok=True)
    temporary = state.with_suffix(".sean-tmp")
    with temporary.open("w") as stream:
        settings.write(stream, space_around_delimiters=False)
    os.chown(temporary, int(sddm[2]), int(sddm[3]))
    temporary.chmod(0o644)
    temporary.replace(state)


def install_session(root, preference):
    for name, directory in INSTALL_PATHS.items():
        target = root / directory.lstrip("/") / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / "gaming" / name, target)
        target.chmod(0o644 if name.endswith(".desktop") else 0o755)
    set_preference(root, preference)


def disable_session(root):
    if not (root / GAMING.lstrip("/")).exists():
        return
    set_preference(root, "desktop", only_if_gaming=True)
    for name, directory in INSTALL_PATHS.items():
        (root / directory.lstrip("/") / name).unlink(missing_ok=True)
