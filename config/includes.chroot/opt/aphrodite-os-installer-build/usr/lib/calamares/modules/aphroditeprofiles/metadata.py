"""Generate an offline size snapshot from a clean live build's APT indexes."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from selection import APPS, CATALOG, HERE

INSTALL = re.compile(r"^Inst (\S+)(?: \[[^]]+\])? \((\S+)", re.MULTILINE)
FULL_DOWNLOAD_MAX = 50 * 1024**2
FULL_INSTALLED_MAX = 200 * 1024**2


def command(*args):
    return subprocess.check_output(
        args, stderr=subprocess.DEVNULL, text=True,
        env=dict(os.environ, LC_ALL="C"), timeout=8,
    )


def native(app):
    spec = app["methods"].get("apt")
    if not spec or spec["suite"] != "trixie" or not all(":" not in p for p in spec["packages"]):
        return app["id"], {}
    try:
        plan = command("apt-get", "-s", "--no-remove", "--no-install-recommends",
                       "install", *spec["packages"])
        requested = {f"{name}={version}" for name, version in INSTALL.findall(plan)}
        package_sizes = {}
        if requested:
            stanzas = command("apt-cache", "show", *sorted(requested)).split("\n\n")
        else:
            stanzas = []
        for stanza in stanzas:
            fields = dict(line.split(": ", 1) for line in stanza.splitlines() if ": " in line)
            if "Size" not in fields or "Installed-Size" not in fields:
                continue
            name, arch, version = fields["Package"], fields["Architecture"], fields["Version"]
            native = f"{name}={version}"
            qualified = f"{name}:{arch}={version}"
            key = qualified if qualified in requested else native
            if key in requested:
                package_sizes[key] = [int(fields["Size"]), int(fields["Installed-Size"]) * 1024]
        if package_sizes.keys() != requested:
            raise ValueError("Incomplete candidate metadata")
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        return app["id"], {"apt": {"error": "No complete clean-image APT size estimate."}}
    # A deployment can add both initially installed size and upgrades. These
    # totals describe the candidate package footprint, before removals.
    download = sum(size[0] for size in package_sizes.values())
    installed = sum(size[1] for size in package_sizes.values())
    return app["id"], {"apt": {"packages": package_sizes,
                               "full": download <= FULL_DOWNLOAD_MAX and installed <= FULL_INSTALLED_MAX}}


def generate(branding, snapshot):
    with ThreadPoolExecutor(max_workers=4) as workers:
        entries = dict(workers.map(native, (app for app in APPS.values() if app["desktop"] != "gnome")))
    metadata = {"source": "Debian Trixie live build APT indexes (amd64)",
                "created": datetime.now(timezone.utc).isoformat(),
                "version": CATALOG["version"], "entries": entries}
    snapshot.write_text(json.dumps(metadata) + "\n")
    # Qt 6's JavaScript import is a local resource, so no file XMLHttpRequest
    # privileges or network access are needed to open the chooser.
    branding.write_text(
        ".pragma library\nvar catalog = " + json.dumps(CATALOG) +
        "\nvar metadata = " + json.dumps(metadata) + "\n"
    )


if __name__ == "__main__":
    generate(Path(sys.argv[1]), HERE / "metadata.json")
