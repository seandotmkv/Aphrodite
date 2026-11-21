# Changelog

## aphrodite-os 0 (infant) — pending rebuild

- Correct Calamares UI imports to reconnect custom navigation and completion
  actions. Fit the sidebar branding and wrap its labels; retain scrolling on
  short screens and visible execution progress. Use installer-only software
  Qt Quick rendering and preserve private launcher logs for startup diagnosis.
- Add an optional Qt interaction/resize smoke check and run the ordinary
  device-protection tests before release builds.
- Add a Ventoy fallback for live ISO mappings absent from `lsblk` and
  `dmsetup`: validate boot metadata and match the physical disk's Ventoy
  GUID and MBR signature. Retain directly flashed USB, optical and loop
  detection and whole-disk protection; reject absent or ambiguous matches.
- Check the new helper is present in the built SquashFS and declare its
  Python and util-linux runtime dependencies explicitly.
- Resolve live-medium block device IDs through `lsblk` rather than requiring
  `/dev/block/MAJ:MIN` aliases. Preserve whole-disk protection and recursive
  loop-backed ISO detection, and add non-destructive regression fixtures.
- Replace Firefox ESR with the official amd64 Floorp APT package and use the
  package's browser launcher for URL and HTML defaults and the taskbar.
- Add GNOME Software with the Debian backend and replace the stock Discover pin.
- Set Ant-Dark for Plasma and Qt and apply dark GTK and libadwaita defaults.
- Add VLC for discs and menus and retain MPV as the media-file default.
  Add DVD and Blu-ray navigation libraries, BD-J and OpenJDK. Build and
  retain the libdvdcss runtime and its licence and source.
- Add archive and removable-filesystem support, desktop accessibility,
  thumbnails and VA-API diagnostics.
- Remove the redundant terminal Vim installation and the temporary DVD
  toolchain. Disable the system Transmission service while retaining the
  binary used by Fragments.
- Check package relationships, desktop IDs, disc plugins and associations
  during the build. Use the full package manifest for both live and installed
  desktop systems.
- Preserve the previous ISO and document cache-preserving cleanup, export and
  release tests.

### Live graphical installer

- Add the live Calamares launcher and a pink aphrodite-os theme, with custom
  clock, optional software and completion views.
- Keep the boot-menu Debian Installer and separate live-only installer
  packages from the target package manifest.
- Add Debian APT profiles for desktop gaming, optional Gamescope sessions
  and hardware-selected Resolve dependencies.
- Stage offline GRUB binaries, CJK fonts and Fcitx input methods, and add
  a checked build and export command.
- Pin Ant-Dark to the revision recorded in the previous image.
- See `docs/installer.md` for the design limitations and unrun tests.
