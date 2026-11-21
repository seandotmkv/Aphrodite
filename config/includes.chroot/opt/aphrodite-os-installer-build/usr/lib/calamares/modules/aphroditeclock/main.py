"""Persist Calamares clock choices using Debian's systemd-timesyncd."""

import datetime
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote
from zoneinfo import ZoneInfo

def setup_input_method(root, locale, username):
    engine = {"zh_CN": "pinyin", "zh_TW": "chewing"}.get(locale.split(".")[0])
    if engine is None:
        return
    fields = next(row.split(":") for row in (root / "etc/passwd").read_text().splitlines()
                  if row.split(":", 1)[0] == username)
    uid, gid = int(fields[2]), int(fields[3])
    home = root / fields[5].lstrip("/")
    config = home / ".config"
    method = config / "fcitx5"
    for directory in (config, method):
        if not directory.exists():
            directory.mkdir()
            os.chown(directory, uid, gid)

    keyboard = (root / "etc/default/keyboard").read_text()
    match = re.search(r'^XKBLAYOUT="([a-z]+)"$', keyboard, re.MULTILINE)
    layout = match[1] if match else "us"
    files = {
        method / "profile": f"""[Groups/0]
Name=Default
Default Layout={layout}
DefaultIM={engine}

[Groups/0/Items/0]
Name=keyboard-{layout}

[Groups/0/Items/1]
Name={engine}

[GroupOrder]
0=Default
""",
        config / "kwinrc": """[Wayland]
InputMethod[$e]=/usr/share/applications/fcitx5-wayland-launcher.desktop
""",
        home / ".xinputrc": "run_im none\n",
    }
    for path, content in files.items():
        if not path.exists():
            path.write_text(content)
            os.chown(path, uid, gid)


def pretty_name():
    return "Configure date and time"


def run():
    import libcalamares

    storage = libcalamares.globalstorage
    root = Path(storage.value("rootMountPoint"))
    mode, _, value = (storage.value("packagechooser_aphroditeclock") or "auto:").partition(":")
    try:
        setup_input_method(root, (storage.value("localeConf") or {}).get("LANG", ""),
                           storage.value("username"))
        if mode == "auto":
            hosts = unquote(value).split()
            if any(not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.:-]*|:[0-9a-fA-F:]+", host)
                   for host in hosts):
                return ("Invalid time server", "Use hostnames or IP addresses separated by spaces.")
            if hosts:
                config = root / "etc/systemd/timesyncd.conf.d/50-aphrodite-os.conf"
                config.parent.mkdir(parents=True, exist_ok=True)
                config.write_text("[Time]\nNTP=" + " ".join(hosts) + "\n")
            subprocess.run(["systemctl", "--root", str(root), "enable", "systemd-timesyncd"],
                           check=True, timeout=20)
        elif mode == "manual":
            timezone_file = root / "etc/timezone"
            if timezone_file.is_file():
                timezone = timezone_file.read_text().strip()
            else:
                link = (root / "etc/localtime").readlink()
                timezone = str(link).split("/zoneinfo/", 1)[1]
            moment = datetime.datetime(*map(int, value.split("-")), tzinfo=ZoneInfo(timezone))
            subprocess.run(["timedatectl", "set-ntp", "false"], check=True, timeout=20)
            subprocess.run(["timedatectl", "set-time",
                            moment.astimezone().strftime("%Y-%m-%d %H:%M:%S")],
                           check=True, timeout=20)
            subprocess.run(["systemctl", "--root", str(root), "disable", "systemd-timesyncd"],
                           check=True, timeout=20)
        else:
            return ("Invalid clock configuration", "Select automatic or manual time.")
    except (OSError, ValueError, KeyError, IndexError, StopIteration, subprocess.SubprocessError) as error:
        return ("Could not configure the clock", str(error))
    return None
