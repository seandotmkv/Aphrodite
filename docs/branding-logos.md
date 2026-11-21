# Supplied Aphrodite and Mnemosyne logos

The uploaded PNGs are used unchanged, including their original transparency.
`aphrodite.png` is white artwork on transparency and can appear blank on white.
The current dark desktop and rose installer header provide contrast.

Base-image assets, retained in an installed system:

- `config/includes.chroot/usr/share/pixmaps/aphrodite.png` (937x950)
- `config/includes.chroot/usr/share/pixmaps/mnemosyne.png` (1004x1027)

`config/hooks/normal/0650-branding-logos.hook.chroot` must be executable (0755).
It verifies both exact SHA-256 checksums, sets only `LOGO=aphrodite` in the
generated `/usr/lib/os-release`, and changes only the General/icon default in
the Plasma Kickoff schema. It does not change release names, IDs, package
selection or other desktop defaults. The icon assets and configuration files
are ordinary 0644 files.

`config/includes.chroot/etc/xdg/kcm-about-distrorc` points KDE's distribution
information page to `/usr/share/pixmaps/aphrodite.png`. The Plasma update script
`usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/aphrodite-logo.js`
sets the Kickoff button icon without changing panels, favourites or pinned apps.

Within `config/includes.chroot/opt/aphrodite-os-installer-build/`:

- `usr/share/applications/install-aphrodite-os.desktop` uses the Aphrodite PNG.
  The live desktop shortcut is copied from that entry in a fresh live session.
- `etc/calamares/branding/aphrodite-os/branding.desc` and `InstallerHeader.qml`
  reference the same PNG. The existing preserve-aspect-fit rule remains intact.
- `usr/lib/calamares/modules/aphroditeprofiles/sourceapps.py` writes the selected
  Mnemosyne app's desktop entry with `Icon=/usr/share/pixmaps/mnemosyne.png`.
- `usr/lib/calamares/modules/aphroditeprofiles/catalog.json` gives Mnemosyne the icon
  name `mnemosyne` for the graphical package catalog. `/usr/share/pixmaps` is
  the standard unthemed icon fallback. The app remains optional.

The PNG is an application launcher icon. Mnemosyne's browser-based interface
can still have a browser-owned taskbar window; this change does not convert
it into a native application or change its upstream web interface.

No terminal escape protocol for displaying PNGs is introduced into the ASCII
installer. This change does not rename the distribution, replace boot artwork,
change the wallpaper or implement an immutable system. It is the logo update
only; these other projects can be handled separately.

The release verifier checks that both assets exist inside the final SquashFS.
Development validation checked both PNGs decode, preserved their byte hashes,
ran the build-hook Python against Debian's real Plasma 6.3.6 Kickoff schema,
and checked that unrelated schema entries and release fields were preserved.
The Plasma script was exercised with fixture panels and unrelated widgets.
Actual fresh live/installed sessions and the next ISO rebuild remain untested.

After the next build, check in a fresh live session:

```bash
grep '^LOGO=' /etc/os-release
ls -l /usr/share/pixmaps/aphrodite.png /usr/share/pixmaps/mnemosyne.png
grep '^Icon=' /usr/share/applications/install-aphrodite-os.desktop
```

Choose Mnemosyne during a disposable installation, then verify its entry in
the installed system and launch it from the application menu:

```bash
grep '^Icon=' /usr/local/share/applications/mnemosyne.desktop
```

Sources for the existing desktop integration:

- [Icon-theme fallback locations](https://specifications.freedesktop.org/icon-theme/)
- [KDE's distribution-logo configuration](https://github.com/KDE/kinfocenter/blob/master/kcms/about-distro/example/kcm-about-distrorc.ex)
