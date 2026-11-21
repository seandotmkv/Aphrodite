"""Deploy reviewed source payloads without running upstream installers."""

import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import zipfile


SOURCE_LAYOUT = 1


def deploy(target, key, app):
    root = target.root
    spec = app["methods"]["source"]
    target.install(spec["packages"])
    destination = root / "usr/local/share/aphrodite-os" / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as directory:
        stage = Path(directory)
        archive = "/" + str((stage / "source.tar.gz").relative_to(root))
        # Use Debian's TLS trust store. Bound download time and bytes in the child.
        target.command("python3", "-c", """
import sys
import urllib.request
with urllib.request.urlopen(sys.argv[1], timeout=20) as response:
    data = response.read(2_000_001)
if len(data) > 2_000_000:
    raise ValueError("Source archive exceeds the reviewed size limit")
with open(sys.argv[2], "xb") as f:
    f.write(data)
""", spec["url"], archive, timeout=60)
        downloaded = stage / "source.tar.gz"
        if hashlib.sha256(downloaded.read_bytes()).hexdigest() != spec["sha256"]:
            raise ValueError(f"{app['name']} source checksum did not match")
        payload = stage / "payload"
        payload.mkdir()
        with tarfile.open(downloaded, "r:gz") as outer:
            member = next(entry for entry in outer if entry.isfile()
                          and Path(entry.name).name == spec["archive"])
            with zipfile.ZipFile(io.BytesIO(outer.extractfile(member).read())) as inner:
                for name in spec["members"]:
                    (payload / Path(name).name).write_bytes(inner.read(name))
            if key == "mnemosyne":
                license_file = outer.extractfile(member.name.split("/", 1)[0] + "/LICENSE")
                (payload / "LICENSE").write_bytes(license_file.read())
        destination.mkdir(exist_ok=True)
        for file in payload.iterdir():
            file.replace(destination / file.name)
    # The source is immutable in /usr/local. Mnemosyne stores its portable
    # runtime, downloads and settings relative to a per-user copy.
    launcher = root / "usr/local/bin" / ("torrentula-gui" if key == "torrentula" else key)
    launcher.parent.mkdir(parents=True, exist_ok=True)
    if key == "mnemosyne":
        start = """home="${XDG_DATA_HOME:-$HOME/.local/share}/aphrodite-os/mnemosyne"
legacy="${XDG_DATA_HOME:-$HOME/.local/share}/sean-os/mnemosyne"
if [ ! -d "$home" ] && [ -d "$legacy" ]; then
    home="$legacy"
fi
mkdir -p "$home/files/app" "$home/files/bin"
install -m644 /usr/local/share/aphrodite-os/mnemosyne/mnemosyne.py "$home/files/app/"
install -m644 /usr/local/share/aphrodite-os/mnemosyne/mnemosyne.html "$home/files/app/"
for tool in yt-dlp ffmpeg ffprobe; do
    if [ ! -e "$home/files/bin/$tool" ]; then
        printf '#!/bin/sh\nexec /usr/bin/%s "$@"\n' "$tool" > "$home/files/bin/$tool"
        chmod 755 "$home/files/bin/$tool"
    fi
done
exec python3 "$home/files/app/mnemosyne.py" "$@"
"""
    else:
        start = """magnet_dir="${XDG_DATA_HOME:-$HOME/.local/share}/torrentula/magnetfiles"
mkdir -p "$magnet_dir"
export TORRENTULA_MAGNET_DIR="$magnet_dir"
exec python3 /usr/local/share/aphrodite-os/torrentula/torrentula_gui.py "$@"
"""
    temporary = launcher.with_suffix(".tmp")
    temporary.write_text("#!/bin/sh\nset -eu\n" + start)
    temporary.chmod(0o755)
    temporary.replace(launcher)
    if key == "torrentula":
        terminal = launcher.with_name("torrentula")
        temporary.write_text("#!/bin/sh\nset -eu\n" + start.replace("torrentula_gui.py", "torrentula.py"))
        temporary.chmod(0o755)
        temporary.replace(terminal)
    shortcuts = root / "usr/local/share/applications"
    shortcuts.mkdir(parents=True, exist_ok=True)
    icon = ("/usr/local/share/aphrodite-os/torrentula/torrentula.png"
            if key == "torrentula" else "/usr/share/pixmaps/mnemosyne.png")
    (shortcuts / (key + ".desktop")).write_text(
        f"[Desktop Entry]\nType=Application\nName={app['name']}\n"
        f"Exec=/usr/local/bin/{launcher.name}\nIcon={icon}\nTerminal=false\nCategories=Network;\n")
    target.command("python3", "-c",
                   "from pathlib import Path; import sys; p = Path(sys.argv[1]); compile(p.read_bytes(), str(p), 'exec')",
                   f"/usr/local/share/aphrodite-os/{key}/{spec['entry']}")
    (destination / ".installed-commit").write_text(f'{SOURCE_LAYOUT} {spec["commit"]}\n')
