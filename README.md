# Aphrodite OS 0 (infant)

A Debian 13 Trixie amd64 desktop built around choice, simplicity and the
software you love. The current desktop is KDE Plasma with the existing dark
appearance, supplied forest wallpaper and Aphrodite branding.

## Build and current status

This source includes the integrated rebrand, package verification and recovery,
browser/pinning policy, terminal progress interface and a **development-stage**
Btrfs transactional installation. Mutable installation remains the release
default until the transactional installation/update/rollback VM scenario passes.
The Windows-side editing session has not rebuilt or boot-tested this version.

Installed systems check `seandotmkv/Aphrodite` GitHub releases after login and
every 30 minutes, notifying when release files change. `aphrodite-update check`
checks manually; `sudo aphrodite-update install` applies published package
updates. See [release publishing and login policy](docs/github-releases-and-login.md)
for the required release assets and current qualification limits.

Live boots enter Plasma automatically. The terminal installer's Account tab
offers **Log in automatically** for the installed system; it is off by default.

```bash
cd /home/sean/mydistro
python3 -m unittest discover -s tests -v
./scripts/build-release
```

`build-release` also runs tests before sudo. A successful build exports
`aphrodite-os-0-amd64.iso`, manifests and checksums to Windows Downloads. It
preserves a previous working image where available. The build directory and
user home paths stay intact. Applying the migration does not start a build.
It also writes the package/manifest for GitHub Releases under `release-assets/`.

## Applications and recovery

**Install Aphrodite OS** opens the existing terminal installer. Desktop Only
does not require Steam/Gamescope. Gaming sessions require explicit selection.
Firefox ESR is live-only and enters the target only when selected. Browser
failure is reported without silently substituting Firefox. No browser is also
an explicit option with a warning. Brave offers its official signed AMD64 APT
repository first, with Flatpak retained as an alternative.

Steam's launcher and graphics dependencies are verified by architecture.
The client still downloads/initializes on first launch; its manifest status is
`first-run-required`, and the bootstrapper is not pinned as an initialized client.
Gamescope installation and dedicated SDDM session setup are separate operations.
Hardware compatibility and actual package transactions need VM/hardware tests.

Verified browser/core tools are pinned on first login. Additional app pins
are selectable. Failed apps are excluded; later logins and updates do not reset
the user's taskbar. Selections and verification results persist after reboot.

```bash
aphrodite-apps status
sudo aphrodite-apps retry
sudo aphrodite-apps export
```

The tools belong to `aphrodite-base`, independently of the removed live
installer. The application menu includes an Installation Report. Logs survive
in `/var/log/aphrodite-os-install.log` and
`/var/log/aphrodite-os-selected-packages.log`. Diagnostic exports are private
compressed archives of logs, selections and OS/kernel/storage information,
excluding authentication and home configuration files.

## Transactional development variant

Only in a disposable VM during qualification:

```bash
install-aphrodite-os --experimental-immutable
```

Storage exposes an explicit development option requiring Erase disk, Btrfs and
32+ GiB. Typed erase confirmation and boot-medium/target identity guards remain.
There is no automatic in-place conversion. The layout has a separate `/boot`,
read-only root deployments, versioned writable `/etc` and `/var`, and shared
homes, Flatpaks, containers, logs and caches. APT changes run in an inactive
snapshot. Checked boot configuration selects the prepared deployment on reboot;
older entries remain available for manual rollback. Flatpak apps are writable
independently of the protected base.

```bash
aphrodite-system status
sudo aphrodite-system update
sudo aphrodite-system layer PACKAGE
sudo aphrodite-system rollback
```

The transactional variant directs APT/dpkg changes through staging and removes
the Debian backend from Software while retaining Flatpak. Mutable installations
continue using normal APT. There is no automatic failed-boot fallback, automatic
deployment pruning, Secure Boot qualification or protection against root tampering.

Read [the implementation and qualification checklist](docs/release-overhaul.md)
before changing release defaults. Historical notes/results elsewhere concern
earlier revisions and do not qualify this overhaul.

Custom app sources are [Torrentula](https://github.com/seandotmkv/torrentula)
and [Mnemosyne](https://github.com/seandotmkv/Mnemosyne), retaining reviewed
commit/checksum pins. Earlier media, firmware and project notes are retained
in [pre-overhaul notes](docs/pre-overhaul-notes.md).

## Repository upload and releases

See [upload, build and release instructions](docs/github-upload.md).
