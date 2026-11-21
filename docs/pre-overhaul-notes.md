# aphrodite-os 0 (infant)

An amd64 Debian 13 Trixie image with Plasma 6, SDDM, Wayland, and Debian
Installer. The live hostname is `aphrodite-os`. The same desktop defaults apply to
the live session and a fresh installation. **Install aphrodite-os** opens the
terminal installer from the live desktop and application menu. Thanks to
Debian Live and KDE.

## Clean, build and export

Run in your regular Debian WSL terminal after any earlier build has stopped.

```bash
cd /home/sean/mydistro
sudo apt-get install live-build xorriso squashfs-tools
./scripts/build-release
```

The release script checks for active builds and build-tree mounts, preserves
`~/aphrodite-os-0-known-working.iso`, and uses `lb clean --all` to refresh the build
while retaining the cache. It verifies the ISO contents and exports the ISO,
the live and base target package manifests, and their SHA-256 checksums to
`/mnt/c/Users/sean/Downloads`. The target manifest describes the base before
optional downloads. Override the export location with `APHRODITE_OS_EXPORT_DIR`.

See [installer architecture and tests](docs/installer.md) for the current
implementation, exact virtual machine commands, package profiles, recovery,
and the remaining physical tests.

## Minimal desktop and optional apps

| Role | Default |
| --- | --- |
| Desktop and settings | Plasma Wayland, SDDM and System Settings |
| Browser | Firefox ESR |
| Files and terminal | Nautilus and Black Box |
| Software and updates | GNOME Software, Debian plugin, PackageKit and APT |
| Text, archives and screenshots | GNOME Text Editor, File Roller and Spectacle |
| Images and media | Loupe and VLC |
| Disks and processes | GNOME Disks and GNOME System Monitor |
| Network | NetworkManager and the Plasma network applet |

Nano remains available for terminal recovery. The base also keeps accessibility,
firmware, drivers, codecs, audio, archive and filesystem tools, and optical disc
support. The default panel uses the existing empty application-pin list.

Minimal is the terminal installer default. Recommended adds KeePassXC and PDF Arranger.
Full adds a broader curated set of Debian applications with measured package
sizes. All three presets allow individual changes. A replacement browser is
installed and its launcher checked before its MIME handler is set and Firefox
ESR is removed. Firefox ESR also provides the offline live browser.

Floorp, Fragments, Transmission's system daemon, mpv, Papers and GNOME
Calculator were in the prior image and are outside the new base. mpv, Papers,
GNOME Calculator and Transmission's graphical client can be selected independently.
See [package installation, sources and recovery](docs/installer.md#target-packages).

## Optical discs

VLC handles DVD and Blu-ray actions in Plasma's Disks & Devices widget.
Debian ships these actions with VLC. Logind grants the active local session
optical-device access through udev, and UDisks2 handles mounting and
unmounting. If Solid identifies a disc as a generic data disc, use VLC's
**Media → Open Disc** and select the relevant type and device.

The VLC base, Qt and video-output plugins supply disc access, menus and video
output. FFmpeg's Trixie runtime provides common MPEG-2, H.264, HEVC, VC-1,
AC-3, DTS, AAC and file-format support. DVD menus use libdvdnav and
libdvdread. Blu-ray titles and HDMV navigation use libbluray, and BD-J uses
`libbluray-bdj` and Debian's OpenJDK 21 headless runtime. [VLC package contents](https://packages.debian.org/trixie/amd64/vlc-plugin-base/filelist) · [Debian BD-J runtime](https://packages.debian.org/trixie/libbluray-bdj)

The build uses `libdvd-pkg` to verify and compile the VideoLAN source
(Trixie's helper packages libdvdcss 1.4.3). Debian's helper injects a
dependency on itself. The build repackages only the runtime to remove that
dependency, retains its other package relationships, and verifies
`libdvdcss.so.2` after purging the build packages. Source, packaging inputs,
licence and versions are under `/usr/share/doc/aphrodite-os` and
`/usr/share/doc/libdvdcss2`. [Debian helper source](https://sources.debian.org/src/libdvd-pkg/1.4.3-1-1.1/debian/b-i_libdvdcss.sh)

VLC is the default for ordinary media and interactive disc menus. The AACS and BD+ libraries provide components of encrypted
Blu-ray playback. Commercial discs may need matching keys and supported
protection revisions. The image ships no key database and makes no
compatibility guarantee for commercial Blu-ray or UHD media. [VideoLAN libbluray](https://www.videolan.org/developers/libbluray.html)

## Release checks

Run these checks on both a live boot and a newly installed VM using the
terminal installer. Check the boot menu in BIOS and UEFI and confirm
`hostname` in the live session and `cat /etc/os-release` in both systems.

- Boot offline and open a local HTML file in Firefox ESR. Verify
  `xdg-mime query default text/html`, `xdg-mime query default x-scheme-handler/http`
  and `xdg-mime query default x-scheme-handler/https` return `firefox-esr.desktop`.
  Confirm the default taskbar has no application pins.
- Open GNOME Software from the application menu and load the package catalogue. Test the
  Polkit prompt by initiating installation of a small Debian package.
  Open a Qt and a GTK file picker in the Plasma session. Open ZIP, RAR,
  7z and tar.zst samples in File Roller, and verify USB mounting plus
  image and video previews in Nautilus.
- Open an H.264/AAC MP4, an HEVC MKV and an audio file from Files. Verify VLC launches and
  `xdg-mime query default video/mp4` prints `vlc.desktop`. Check `ldconfig -p | grep libdvdcss.so.2`
  and `java -version`.
- **VM with a suitable authored image or folder** — Use VLC to play a DVD
  title and select chapters in its DVD menu. Test a Blu-ray title with
  **No disc menus**, an HDMV menu with menus enabled, then a known BD-J sample
  with a Java menu.
- **Physical optical drive required** — Insert a known CSS-protected DVD
  and open it from Disks & Devices. Play a title offline and navigate the
  menu. Repeat with a known-compatible Blu-ray for title playback, HDMV,
  and BD-J navigation. Check `lsblk -f`, `udisksctl info -b /dev/sr0`
  and `test -r /dev/sr0` as the logged-in user. Check data-disc mounting in
  Files. A regular VM without physical drive passthrough cannot verify
  these device, permission, or commercial-disc cases.
- **Physical AMD GPU or GPU passthrough required** — Run `vainfo`, look for
  Mesa's AMD driver and the codec decode profiles. In VLC, play a supported clip with **Hardware-accelerated decoding →
  Automatic** and check verbose playback logs. A VM's virtual GPU cannot
  verify the host AMD decoder.
