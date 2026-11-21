# Aphrodite OS integrated development milestone

## Identity and integration

Factory identity: `NAME="Aphrodite OS"`, `PRETTY_NAME="Aphrodite OS"`,
`ID=aphrodite`, `ID_LIKE=debian`; version 0 / infant is preserved. Custom
namespaces, launchers, branding directories, manifests, logs, boot labels and
packages are renamed. Output is `aphrodite-os-0-amd64.iso`. The existing build
directory and user homes are preserved. Legacy-name reads are limited to
prior-image backups, the former export variable, old plan schemas and existing
Mnemosyne data directories. Historical generated
manifests/checksums are not rewritten; `lb config` refreshes generated settings.

Uploaded PNGs remain unchanged. OS metadata, KDE distribution info, Kickoff,
installer shortcut and graphical branding use Aphrodite's logo. Mnemosyne's
optional launcher/catalog use its supplied icon. The forest photo fills the
Plasma display with aspect ratio preserved. Build hooks validate the assets.

## Findings and implemented fixes

- The former `dpkg-query` verification concatenated architecture results with
  no newline and compared to `installed`. A multiarch package could become
  `installedinstalled`, producing a false Steam failure. New queries use
  Package/Architecture/Status rows and verify native amd64/all and explicit
  i386 requirements separately.
- Steam's Debian package is a launcher/bootstrapper. Package, executable,
  launcher and graphics checks are separate from client initialization. The
  manifest says `first-run-required`; no bootstrap placeholder is pinned.
- Desktop-only, desktop-default-plus-gaming and gaming-default choices have
  explicit labels. Off does not add or require Steam/Gamescope. Gamescope alone
  does not create an SDDM gaming session. Existing profiles are preserved.
- Brave now supports its official signed APT repository. Vendor HTTPS supplies
  the scoped key; Signed-By is repository-specific and architecture is amd64.
  Steam multiarch therefore does not request unsupported Brave i386 indexes.
  Only the selected vendor index is refreshed. No remote installer is executed.
  The Flatpak alternative verifies deployment and its desktop export.
- Firefox is live-only. Cleanup preserves it only for a selected target, and
  finalization removes an unselected Firefox. Browser failures are reported
  with no substitution; an explicit no-browser option is supported.
- Persistent results record selection, method, packages, source, status and
  reason. Executable/desktop checks supplement package checks where available.
  Optional failures remain visible/retriable; broken dpkg state is fatal.
- Package output streams and is saved in full, rather than only the last 80
  messages. `aphrodite-apps status/retry/export` survives live-package removal.
- Pin policy comes from verified outcomes, uses native Plasma configuration,
  applies once per profile and preserves later customization. Failed apps and
  first-run Steam bootstrappers are excluded. Individual additional pins are
  selected in the terminal application.
- Existing worker progress, command deadlines, paused/searchable logs,
  asynchronous timezone enumeration and drive guards are retained.
- Mutable fstab generation now writes all six fields, including dump/fsck.

The supplied missing-log result came from the WSL build host. The actual failed
installation logs were unavailable. These findings establish code defects and
changes, not proof of the exact observed ten-minute delay. The original Brave
Flatpak failure still needs its installed-system log.

## Source map

Live payload root is
`config/includes.chroot/opt/aphrodite-os-installer-build/`.

| Area | Main paths |
| --- | --- |
| Terminal and worker | `usr/bin/aphrodite-os-installer-tui`, `usr/libexec/aphrodite_os_install.py`, `aphrodite_os_progress.py` |
| Application logic | `usr/lib/calamares/modules/aphroditeprofiles/`: executor, selection, integration, repositories, sourceapps, session and catalog |
| Build identity | `auto/config`, `auto/build`, `0600-aphrodite-os-identity.hook.chroot` |
| Installed runtime | `0680-aphrodite-runtime.hook.chroot`; packages the tools/modules as `aphrodite-base` |
| Recovery and transactions | `config/includes.chroot/usr/bin/{aphrodite-apps,aphrodite-system}`, `usr/lib/aphrodite/transactional.py` |
| Boot integration | `etc/grub.d/09_aphrodite_deployments`, `usr/share/initramfs-tools/scripts/local-bottom/aphrodite-state` under includes.chroot |
| Pins | `usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/aphrodite-os-launchers.js` under includes.chroot |
| Verification | `scripts/verify-release`, `tests/test_release_contracts.py`, existing regression tests |

Hooks, CLI entry points, GRUB and initramfs scripts are 0755; modules,
configuration, desktop entries and images are 0644. Migration applies these
modes explicitly. The 0680 hook copies shared package modules to the installed
runtime before 0700 builds/removes the live staging directory.

## Transactional design and rollout gate

A simple read-only remount was rejected. OSTree/image A/B/systemd-sysupdate
would require a new composed-image publication/signing pipeline and replacing
much of the current APT installer. This development path instead uses Btrfs
deployments, staged Debian transactions, existing scoped signature-verified
repositories and versioned kernel/GRUB entries. No invented remote image server
or unsigned update feed is configured.

The filesystem has `@deployments/<id>/{root,etc,var}` and `@shared`. Initial
installation seals root read-only only after setup. The separate boot filesystem
contains a kernel/initramfs per deployment. An initramfs script binds the
matching etc/var before switch-root, then shared home/Flatpak/container/log/cache
data. Swap lives outside snapshots. Root/boot UUIDs and read-only state are
checked before updates. APT stages writable snapshots; package scripts cannot
start services. It does not bind the running boot filesystem into the staging
root. Checked GRUB configuration is published atomically after boot artifacts
are ready; prior entries remain available for manual rollback.

This is DEVELOPMENT, available only with `--experimental-immutable`. It does
not replace the working mutable default until VM scenario E passes, as required
by the supplied staged-conversion specification. There is no in-place conversion.

Limits: no automatic failed-boot fallback or pruning, no Secure Boot qualification,
no certification of arbitrary third-party maintainer scripts or service-data
schema rollback. etc/var snapshots capture staging-start state; later changes
are not merged automatically. Shared data are not rolled back and still need
backups. Flatpak retries can update shared app data before base activation.
NVIDIA/DKMS, physical firmware and gaming GPUs need separate qualification.

The local `aphrodite-base` Debian package owns custom runtime and branding files.
The subsequent GitHub update extension adds explicit installation of verified
release assets plus a desktop notification timer. See
`docs/github-releases-and-login.md` for its trust model, publishing commands and
required manifest/package files. No external publishing was performed here.

## Verification and release checklist

Windows checks cover Python syntax, progress/stream behavior, catalog/interface
policy with explicit import-only POSIX shims, manifests, pin filtering,
architecture-result parsing and generated Btrfs/GRUB configuration. These do
not execute Linux storage, APT, Flatpak or actual firmware boots. Historical VM
claims elsewhere describe earlier code. The bundle receipt records current checks.

WSL is inaccessible to this editing session and Git Bash launch was refused.
The migration runs shell syntax checks, the full Linux unittest suite and
`lb config` on the actual build host. It does not build an ISO. Stop on errors
and retain the output; an applied patch is not VM qualification.

Use fresh disposable VM disks and nonpersistent live sessions:

A. Desktop only, Firefox chosen: no Steam/Gamescope requirement; boot without
   ISO, verify default browser, manifest and core pins.
B. Brave/native APT plus Steam and standalone Gamescope: verify Brave/handler,
   absence of unselected Firefox, amd64/i386 graphics libraries, Steam executable
   and interactive first-run initialization. No gaming-session default.
C. Dedicated session on supported AMD/Intel rendering: check SDDM entry/order,
   actual gaming session, controllers and return to Plasma.
D. Offline optional failure: responsive progress panels, failure reason/logs,
   no substituted browser or failed-app pin; reconnect and retry after reboot.
E. Transactional development on a 48+ GiB disk, BIOS and UEFI: install, detach
   ISO, confirm root ro and persistent home/Flatpak data. Stage an update,
   reboot to it, select rollback and reboot again. Check old kernel/package DB,
   accounts and shared data. Interrupt staging before publication and confirm
   the old root stays selected. Test direct APT rejection, layering and app retry.
F. Normal USB/Ventoy: protect the live drive; a changed target identity must
   stop before any write. Physical media are not certified from fixture tests.
G. Customize the taskbar, reboot and update; ensure it is not reset.

Source tests never partition host disks. Do not recommend physical deployment
or enable immutable defaults until the VM checks actually pass.

Primary references: https://brave.com/linux/ ;
https://manpages.debian.org/trixie/dpkg/dpkg-query.1.en.html ;
https://btrfs.readthedocs.io/en/stable/btrfs-subvolume.html ;
https://specifications.freedesktop.org/icon-theme/
