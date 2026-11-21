# aphrodite-os 0 (infant) installer

This image keeps Debian 13 Trixie, amd64, `live-build`, and the existing
Plasma Wayland session. The ISO boot menu still offers Debian Installer.
The live desktop and application menu offer **Install aphrodite-os**.

## Terminal installation

The terminal progress screen, panel controls, real package accounting and
validation limits are documented in [Installation progress](installation-progress.md).

Open **Install aphrodite-os** in the live desktop or run `install-aphrodite-os` from
a terminal. The menu and live desktop shortcut share the same launcher.
Use the existing tabs to configure the system. On Review, select **Install**
or press F2. Check the model, capacity and device path, then type the
displayed `ERASE /dev/…` confirmation. This removes all partitions and
operating systems on the selected drive.

The terminal installer uses the live SquashFS and requires a writable,
unused whole disk of at least 16 GiB. It creates GPT storage with a BIOS boot
partition or a 512 MiB EFI system partition, an ext4 or Btrfs root, and an
optional 2 GiB swap file. It sets up Plasma, the sudo user with a locked
root account, the selected locale, XKB layout and variant, timezone and
NTP settings. Manual time changes the system and hardware clock at the
end of installation. The 12-hour setting changes the preview only.
Manual partitioning, alongside installation, partition replacement, disk
encryption, Secure Boot and 32-bit EFI are unavailable in the terminal flow.

The terminal displays extraction progress, actual setup and package commands,
and results for selected applications and sessions. Healthy targets can
finish with skipped optional selections. Fatal storage, configuration or
package-manager errors stop the installation. Root-only logs go to
`/var/log/aphrodite-os/install-*.log` in the live session and
`/var/log/aphrodite-os-install.log` on the target once the target can store it.
Detailed package diagnostics are saved in the target's
`/var/log/aphrodite-os-selected-packages.log` and alongside the live installer log.
Copy live diagnostics before rebooting if the live system has no persistence.
The password goes to `chpasswd` over stdin and is excluded from logs.

## Source layout

- `config/package-lists/installer.list.chroot_live` installs the Debian
  Calamares packages and live tools. `installation-support.list.chroot`
  supplies target GRUB platform binaries, cryptsetup, filesystem tools,
  Systemd time synchronisation, CJK fonts, and Fcitx 5.
- `config/includes.chroot/opt/aphrodite-os-installer-build` is the source
  of the local live-only Debian package. It contains the launcher, policy,
  Calamares branding, QML pages and catalog, profile jobs and session files.
- `0700-aphrodite-os-installer.hook.chroot` composes the Calamares job sequence
  from Debian’s settings, builds the local package, and checks its dependencies.
  It checks upstream versions 3.3.14-1 and 13.0.13-1 before transforming them.
  Review the module APIs and Debian job sequence before updating these checks.
- `0800-installed-manifest.hook.binary` keeps the existing late-installed
  libdvdcss and installer packages and records live package removals. Calamares
  purges the live installer from the copied target before rebuilding the
  initramfs. Debian Installer uses its package-removal manifest and preseed.
- `scripts/build-release` and `scripts/verify-release` build, inspect,
  checksum, and export the release.

The terminal installer opens through a restricted live-only Polkit action.
A one-time autostart task copies the shortcut for the live user. The
privileged installer uses a
private mount namespace to hide the live disk’s block device nodes while
keeping its mounted SquashFS readable. When the live medium is a loop-mounted
ISO file, the installer traces the file back to its physical disk. If it
cannot identify that disk, the installer stops and reports the failure.

Device IDs are resolved using `lsblk`'s normal block-device paths, without
requiring optional `/dev/block/MAJ:MIN` udev aliases. This supports optical
live media such as `/dev/sr0` (`11:0`) even when those aliases are absent.
USB and NVMe media still protect their whole backing disk and partitions;
loop-backed ISO files still trace their backing filesystem recursively.
Unresolved, ambiguous, or non-block sources still stop the installer before
masking any device or enabling a target. The terminal worker checks the
reviewed device number, kernel disk generation, and size again before writes.
It checks for mounts, active swap, holders and exclusive kernel access.
The live disk and its descendants are masked before partitioning.

### Ventoy and directly flashed USB media

Directly flashed USBs, optical ISO boots and ordinary loop mounts retain
the existing `lsblk` ancestry checks. When those checks cannot resolve a
Ventoy ISO mapping, `aphrodite-os-ventoy-device` reads Ventoy's boot metadata.
It accepts only the current `/run/live/medium` mount with source
`/dev/mapper/ventoy` and type `iso9660` or `udf`, and verifies its kernel
device ID before using this fallback.

The helper validates the 512-byte signature and checksum, then matches
both the Ventoy disk GUID and MBR disk signature against physical disks.
It supports saved initramfs metadata, UEFI variables, the VTOY ACPI table,
and bounded legacy BIOS memory data when the kernel permits that read.
Missing, invalid, conflicting or ambiguous identities stop installation.
No disk is guessed from its label, size, USB ordering or `/dev/sdX` name.
The matched disk and every partition are hidden in the installer's private
mount namespace using the same protection as a normal USB boot.

The implementation follows the [Ventoy information format](https://www.ventoy.net/en/doc_compatible_format.html)
and [firmware handoff](https://www.ventoy.net/en/doc_compatible_pass.html).
It does not depend on the hidden mapping being visible to `dmsetup`, and
does not install or alter Ventoy on the USB. Unrecognised boot modes,
including virtual-link or RAM-boot arrangements without verifiable backing
metadata, are not certified and remain subject to the same stop-on-failure
checks.

Tests include the hidden `254:0` mapping reported on the ThinkPad,
normal USB partitions, optical media, NVMe, loop-backed ISOs, malformed
metadata, stale devices and cloned disk identities. The protection tests include actual shell control flow with
fixture-backed device commands. The integration tests also check that the
terminal write sequence stops when live-device resolution or target identity
verification fails. Run them without disk access:

```bash
python3 -m unittest discover -s tests -v
```

### Retained Calamares configuration

The image still carries the existing Calamares configuration and artwork.
The Install aphrodite-os launchers use the terminal backend. Calamares
3.3.14 constructs a Qt application, shows its window and exposes no headless
installation command in its entry point. The terminal backend invokes the
Linux storage and boot tools directly and shares the installed-target cleanup
script, Chinese input setup and package executor. [Calamares 3.3.14 entry point](https://github.com/calamares/calamares/blob/v3.3.14/src/calamares/main.cpp)

### Installer layout and diagnostics

The custom navigation, sidebar and completion page import `io.calamares.ui`
for `ViewManager`; `io.calamares.core` supplies the separate global storage
API. Missing the UI import produced empty navigation labels and disconnected
actions. Navigation follows Calamares's readiness checks, so Next stays
disabled until required checks finish. These checks must not be bypassed to
hide a startup stall.

The sidebar uses a short aphrodite-os header, an aspect-preserving icon, wrapped
step labels and scrolling on short screens. Navigation fits the 64-pixel
height used by Calamares. The real execution progress text remains visible.
The installer process uses Qt Quick software rendering, the Basic controls
style, Fusion widgets and the Compose input context. These settings isolate
the privileged installer from desktop theme/input plugins and avoid reliance
on virtual GPU acceleration. They do not change Plasma's renderer or the
installed desktop. Maximise and fractional scaling still need a real live
session check on the target display and virtual GPU.

An optional Qt smoke check is included for development hosts with PySide6:

```bash
python3 tests/qml_smoke.py
```

This loads all six custom QML views with Calamares API test doubles, checks
Next-label and enabled-state bindings, clicks Next, and checks resize geometry.
It reproduced 11 missing-ViewManager binding errors before the fix and no
QML errors after it on Qt 6.12. It does not run the real Calamares backend,
requirements workers, Linux input plugins or disk installer. The ordinary
standard-library tests do not require PySide6. `scripts/build-release` runs
those ordinary tests before its privileged build.
The numbered sidebar groups keyboard with Welcome, and partitioning with
encryption. Four progress stages track the actual job queue, with task text
and logs from Calamares. Work still pending includes a separate encryption
page, a root-account opt-in UI, complete backend message translations, and a
consolidated review of all optional selections.

Encryption uses Calamares LUKS1 for the GRUB-readable encrypted root layout.
LUKS2 with Argon2 requires a different, validated boot arrangement. The
installed initramfs is generated with restricted permissions. The graphical
path uses GRUB platform binaries staged in the SquashFS, and preserves any
existing EFI fallback file. Graphical Secure Boot installation and boot
have not been validated. Use the fallback tool if signed-boot support is
needed, and test that path on the intended firmware.

The account page uses a nonempty password requirement, without a strength
requirement. Root starts locked and the local user joins Debian’s sudo
group. Verify login, sudo, and root status with a disposable VM before
release. Do not enable Calamares debug dumps during real installations
using personal passwords or encryption keys.

### Localization and time

Calamares supplies its language selector, locale and timezone configuration,
and keyboard preview and variants. The aphrodite-os QML catalog has English
fallback plus French, Dutch, Irish, Simplified Chinese, and Traditional
Chinese for its custom views. Translations are pending human review.
Coverage of the stock Calamares pages and Python job errors varies by
language. In particular, the full Irish UI is unverified. Verify six locale
variants before advertising complete localization.

Pinyin or Chewing is set up for the installed Plasma user based on the
target Chinese locale. KWin starts Fcitx 5 using Debian's Wayland launcher.
Test Qt and GTK input after login using `fcitx5-diagnose` and a text editor.
The live password fields use the keyboard layout selected in Calamares
through Xwayland. The bundled Fcitx engines can also be configured in the
live session.

Automatic time continues through Debian systemd-timesyncd. Optional NTP
hosts go in a target-only timesyncd drop-in. Manual time sets the hardware
clock during installation using the selected timezone and disables target
NTP. Timezone selection is manual. The wizard offers no automatic location
lookup.

## Target packages

The terminal installer and Calamares pass a versioned selection to the shared executor.
The catalog is `usr/lib/calamares/modules/aphroditeprofiles/catalog.json` inside the
installer payload. The live build generates the graphical catalog and the APT
size snapshot from the same data the terminal picker and job validate. Debian
Installer continues to install the base image.

- **Minimal** starts with the essential desktop and Firefox ESR.
- **Recommended** adds KeePassXC and PDF Arranger. Either can be deselected.
- **Full** selects curated open-source Debian apps with a complete estimate of
  at most 50 MiB download and 200 MiB candidate package footprint each. It
  excludes browsers beyond Firefox, proprietary apps, large or unmeasured
  packages, Flatpaks, pinned source apps and the gaming session. The ceiling is
  per app with its simulated dependencies, so the total can exceed either value.

The chooser shows a build-dated APT estimate using package metadata and
deduplicates identical dependency versions. The estimate is relative to the
base used at build time. It sums candidate package footprints, including
upgrades, before removals. Flatpak app sizes, shared runtimes and the current
transaction size can differ and are displayed as unknown where no estimate is
available. The snapshot expires after 90 days. The chooser works offline and
the install job validates against refreshed repository metadata.

APT uses signed Trixie, security and updates indexes. Gamescope uses Debian
backports. Flatpak uses system deployments from Flathub. APT simulates with
recommends disabled, rejects removals and unselected catalog apps in the solver
plan, downloads the transaction, then applies it. A browser replacement needs
an installed launcher before Firefox can be removed. If APT proposes removing
anything else along with Firefox, both browsers remain and the installer
reports the failed removal.

The two dedicated session orders both select native Steam and Gamescope.
Desktop first preselects Plasma and Gaming mode first preselects the DRM
session. Both require a supported AMD or Intel render device. SDDM prompts for
login in either mode. GameMode is a separate performance tool. Legacy
`off`, `games`, `desktop`, and `gaming` choices still load, including
`-resolve`. Legacy `games` retains the gaming tools without the session.
Legacy Resolve support can install compatible compute dependencies. Installing
the licensed application requires a separate Blackmagic installer and verified
hardware. GOG Galaxy and Timeshift remain unavailable pending validated
installation and recovery designs, respectively. Extension Manager requires
GNOME Shell.

Torrentula and Mnemosyne deploy their reviewed Linux application files from
GitHub archives pinned by commit and SHA-256 in the catalog. The installer
does not invoke upstream scripts or use pip as root. Torrentula provides the
`torrentula` and `torrentula-gui` commands and uses Debian's Requests and
Pyperclip packages. The upstream revision has no license file.
Mnemosyne stores its portable app files and downloads in the user's data
directory. It starts with Debian yt-dlp and FFmpeg wrappers under its own
tool directory. For full YouTube support it also needs Node.js 22 or newer, or
Deno 2.3 or newer. The installer leaves that runtime and compatibility check
to the user.

The executor saves `/var/log/aphrodite-os-selected-packages.log` on the target.
The terminal saves a second copy next to its live installer log. Healthy
targets can finish with optional apps skipped and retry
them from the live terminal once connectivity is restored. A broken dpkg
state stops the job and requires repair before retry. No maintainer-script
rollback is attempted. Once a separately installed aphrodite-os root is mounted at
`/mnt/aphrodite-os-target`, with its normal package-script mounts available:

```bash
sudo aphrodite-os-apply-packages /mnt/aphrodite-os-target
sudo aphrodite-os-apply-packages /mnt/aphrodite-os-target /path/to/selection.json
```

Omitting the plan retries the versioned selection saved on the target. The
executor reads only application methods, default browser and session choices
from a terminal plan. It does not partition, install an OS, create accounts,
or consume the plan's storage and account fields. To skip a failed choice on retry, supply a selection JSON that omits it. Packages already installed are preserved, except for a successful Firefox
replacement. A successful retry does not imply a full disk installation test.

SDDM remembers the last successful session selection. To switch from Plasma,
open **Switch to Gaming Mode**, sign out, and select **aphrodite-os Gaming Mode** in
SDDM. To return, exit Steam and select Plasma. Inspect
`~/.local/share/sddm/wayland-session.log` for session failures. Test controller
behavior and hardware acceleration on the intended hardware.

## VM tests

Install the VM tools on a Linux machine where a graphical QEMU session is
available. WSL can use its graphical display bridge where available.

```bash
sudo apt-get install qemu-system-x86 qemu-utils ovmf
cd /home/sean/mydistro
vm=$(mktemp -d "${TMPDIR:-/tmp}/aphrodite-os-vm.XXXXXX")
qemu-img create -f qcow2 "$vm/bios.qcow2" 48G
qemu-system-x86_64 -m 4096 -smp 4 -nic none \
  -drive "file=$vm/bios.qcow2,format=qcow2,if=virtio" \
  -cdrom "$PWD/aphrodite-os-0-amd64.iso" -boot d
# After installation and shutdown, boot the same VM without the ISO.
qemu-system-x86_64 -m 4096 -smp 4 -nic none \
  -drive "file=$vm/bios.qcow2,format=qcow2,if=virtio" -boot c

cp /usr/share/OVMF/OVMF_VARS_4M.fd "$vm/uefi-vars.fd"
qemu-img create -f qcow2 "$vm/uefi.qcow2" 48G
qemu-system-x86_64 -machine q35 -m 4096 -smp 4 -nic none \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive "if=pflash,format=raw,file=$vm/uefi-vars.fd" \
  -drive "file=$vm/uefi.qcow2,format=qcow2,if=virtio" \
  -cdrom "$PWD/aphrodite-os-0-amd64.iso" -boot d
# Boot the installed UEFI disk without the ISO.
qemu-system-x86_64 -machine q35 -m 4096 -smp 4 -nic none \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive "if=pflash,format=raw,file=$vm/uefi-vars.fd" \
  -drive "file=$vm/uefi.qcow2,format=qcow2,if=virtio" -boot c
```

Use a fresh disk per storage case. Test offline BIOS and UEFI erase
installs with ext4 and Btrfs. Confirm the live medium is absent from writable
choices. Compare the review with `lsblk -f`, `findmnt` and `/etc/fstab`
on the installed system. For online package tests use
`-nic user,model=virtio-net-pci` and a fresh disposable disk. Choose Chromium,
KeePassXC, a Flatpak, and one Sean app. Check the installed package manifests,
default HTTP/HTTPS handlers, and `flatpak info --system APP_ID`. Repeat with
`-nic none` and confirm Firefox remains the default after a failed
replacement. Verify that a VM without a supported DRM render device reports
the session limitation. Test desktop shortcut and
menu activation, one-character password, root lock, sudo, manual date and
timezone, keyboard layout and CJK text on both Qt and GTK. After detach, confirm the live-only package and entry are absent.

On return from a physical validation run, record the GPU, driver, firmware
mode, controller, display and installed packages. Test native Vulkan amd64
and i386, GameMode, MangoHud, Steam and Proton, session switching, Wi-Fi,
Bluetooth, VA-API, Resolve compute and export, then authored DVD and Blu-ray
menus. Keep protected discs and UHD checks separate. See the README for
Firefox ESR updates, libdvdcss source and rebuild procedure, and
commercial disc limitations.

## Terminal validation

The standard-library suite covers terminal confirmation, disk generation
changes, protection failures, password handling, and package handoff and
recovery. QEMU tests used disposable virtual disks and loaded the terminal
installer files into the existing live ISO at boot. They completed an
offline BIOS/ext4 installation and an online UEFI/Btrfs installation with
KeePassXC. Both disks booted to SDDM with the ISO detached.

The live desktop test verified terminal activation from the application
entry and checked the copied shortcut. An emulated optical drive and an
emulated directly flashed USB were protected. Ventoy was tested with
fixtures for hidden mappings and boot metadata. Physical-media boots,
manual clock changes, interactive account login and GPU gaming sessions
remain unverified.
The full release image still needs its privileged rebuild.

## Earlier package validation

The package overhaul passed the 49-test Python suite, the offscreen Qt 6.8.2
QML smoke test, and a curses PTY run through package selection and Review.
The native live and base package lists resolved against the clean Debian
bootstrap package state. Both solver plans excluded optional catalog apps.

Real package transactions used a disposable overlay of the existing
SquashFS. The Minimal target passed manifest checks. A customized target
installed Chromium, KeePassXC, qBittorrent, PDF Arranger, Torrentula and
Mnemosyne. Chromium became the HTTP/HTTPS default and Firefox ESR was
removed. Both pinned apps started their loopback interfaces. The executor
rejected an unsupported GOG Galaxy selection. Steam and Gamescope passed
APT simulation. The three session choices were tested through the picker
and SDDM configuration tests.

The first Flatseal transaction ran out of scratch space and was reported as
incomplete. The retry in a larger disposable target completed a real
system deployment. With networking isolated, an attempted Chromium
replacement reported the index failure and kept Firefox as the working
default. The target passed `apt-get check` after that failure.

That validation used an earlier ISO and a disposable overlay. It covered
package transactions. The release build uses sudo in the regular Debian
terminal.

Upstream references for updates and compatibility checks:

- [Calamares v3.3.14](https://github.com/calamares/calamares/tree/v3.3.14)
  and [Debian’s live settings package](https://packages.debian.org/trixie/calamares-settings-debian)
- [Gamescope in Trixie Backports](https://packages.debian.org/trixie-backports/gamescope)
  and [Valve Gamescope](https://github.com/ValveSoftware/gamescope)
- [Bazzite’s Gaming Mode overview](https://github.com/ublue-os/docs.bazzite.gg/blob/main/src/Handheld_and_HTPC_edition/Steam_Gaming_Mode.md)
  and [ChimeraOS’s Steam session conventions](https://github.com/ChimeraOS/gamescope-session-steam)
- [Debian Steam installer](https://packages.debian.org/trixie/steam-installer)
  and [Valve Proton](https://github.com/ValveSoftware/Proton)
- [Fcitx Wayland setup](https://fcitx-im.org/wiki/Using_Fcitx_5_on_Wayland)
