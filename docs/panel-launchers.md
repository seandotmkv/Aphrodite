# aphrodite-os panel application launchers

## Diagnosis and scope

The supplied `config/package-lists/plasma.list.chroot` installs KDE Plasma,
KWin Wayland, plasma-desktop and plasma-workspace. The panel is managed by
`plasmashell`; the stock panel template creates an Icons-Only Task Manager
(`org.kde.plasma.icontasks`). Debian's metadata makes that widget reuse the
configuration and code of `org.kde.plasma.taskmanager`.

Two independent sources supplied application pins:

1. `config/includes.chroot/usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/aphrodite-os-launchers.js`
   explicitly pinned System Settings, GNOME Software, Nautilus and Floorp.
2. The packaged task-manager KConfig schema had defaults for System Settings,
   Discover, the preferred file manager and the preferred browser. Discover
   is deliberately absent from this image, so its packaged default is a stale
   application reference. The old update script did not clear that schema.

The existence of these sources is verified. Which source produced each
previously observed broken icon cannot be established without that live
profile's panel configuration and session log. This update removes application
launchers rather than guessing replacement desktop IDs or adding applications.
It does not claim to repair a separate running-window icon or icon-theme issue
if one remains after the default launchers have been removed.

The panel, task-manager widgets, running-window buttons, application menu,
pager, separators, system tray, clock, input-method widget and show-desktop
widget are retained. Standalone `org.kde.plasma.icon` application shortcuts
are removed by the first-profile script. Ordinary document/folder shortcuts
and `.desktop` shortcuts explicitly marked Type=Link/Directory are retained.

## Exact files

All project paths below are relative to `/home/sean/mydistro`.

| Project file | Installed path or effect |
| --- | --- |
| `config/includes.chroot/usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/aphrodite-os-launchers.js` | `/usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/aphrodite-os-launchers.js`; clears General/launchers on both task-manager variants for a new profile and removes standalone application shortcut widgets. |
| `config/hooks/normal/0440-panel-launchers.hook.chroot` | Executable build hook, mode 0755; empties only the General/launchers default in the existing `/usr/share/plasma/plasmoids/org.kde.plasma.taskmanager/contents/config/main.xml`. It checks the installed icontasks metadata and schema before changing it. |
| `config/hooks/normal/0500-verify-desktop.hook.chroot` | Replaces the requirement to pin Floorp with a check for the explicit empty launcher list. The current build also verifies the Firefox ESR desktop ID and MIME defaults. |

The packaged default panel template is
`/usr/share/plasma/layout-templates/org.kde.plasma.desktop.defaultPanel/contents/layout.js`.
It remains unchanged. Its task-manager widget inherits the empty schema default,
so newly created stock panels also start with no application pins.

The active user profile is stored in
`~/.config/plasma-org.kde.plasma.desktop-appletsrc`.
Task-manager pins belong to
`[Containments][<panel-id>][Applets][<task-manager-id>][Configuration][General]`
under the `launchers` key. IDs are allocated by Plasma and must not be hardcoded.
An empty key can be omitted because the system schema default is now empty.

No pre-generated appletsrc is copied into `/etc/skel`, no whole profile is
deleted and no launcher policy is enforced continuously. First-profile setup
and system defaults apply to new live users and to new installed users because
these files are included in the copied root filesystem. Users may pin apps
later. Existing profiles which have already run this update script need an
explicit one-time application if they should also be cleared.

The schema is a package-owned file modified at build time. A later
plasma-desktop-data package upgrade may restore its packaged schema default.
Existing profiles retain their saved launcher choices; recheck new-panel
defaults after such an upgrade and rerun the same targeted hook when maintaining
the derivative. No upgrade service or package has been added by this change.

## Apply and build

Apply the supplied patch once in the normal Debian WSL terminal:

```bash
cd /home/sean/mydistro
patch=/mnt/c/Users/sean/Documents/Codex/2026-11-19/help-me-do-this/outputs/aphrodite-os-panel-launchers-fix.patch
git -c core.autocrlf=false apply --check "$patch" &&
git -c core.autocrlf=false apply "$patch" &&
chmod 0755 config/hooks/normal/0440-panel-launchers.hook.chroot
```

Inspect the complete deployed script and hook:

```bash
cat config/includes.chroot/usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/aphrodite-os-launchers.js
cat config/hooks/normal/0440-panel-launchers.hook.chroot
sh -n config/hooks/normal/0440-panel-launchers.hook.chroot
sh -n config/hooks/normal/0500-verify-desktop.hook.chroot
test -x config/hooks/normal/0440-panel-launchers.hook.chroot
```

Rebuild using the project's existing clean rebuild command:

```bash
./scripts/build-release
```

This update does not change that build script or any installer, repository,
kernel, bootloader, release identity or other desktop settings.

## Required clean live-session validation

This check MUST be performed on the rebuilt ISO. Boot it in a new VM, or boot
the live USB without persistent storage or an imported home directory. Do not
use an old saved Plasma profile as proof of the defaults. Do not delete the
entire configuration file as a workaround.

In a terminal inside that fresh live Plasma session:

```bash
printf 'Desktop: %s\n' "$XDG_CURRENT_DESKTOP"
plasmashell --version
python3 - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET
path = Path('/usr/share/plasma/plasmoids/org.kde.plasma.taskmanager/contents/config/main.xml')
ns = {'k': 'http://www.kde.org/standards/kcfg/1.0'}
entry = ET.parse(path).find("./k:group[@name='General']/k:entry[@name='launchers']/k:default", ns)
assert entry is not None and not (entry.text or '').strip(), 'Packaged application pins remain'
print('System task-manager launcher default is empty')
PY
```

Read the live panel configuration through Plasma's own scripting API. This
command does not change configuration:

```bash
gdbus call --session --dest org.kde.plasmashell \
  --object-path /PlasmaShell \
  --method org.kde.PlasmaShell.evaluateScript '
const report = [];
for (const panel of panels()) {
    for (const widget of panel.widgets()) {
        const row = {panel: panel.id, widget: widget.id, type: widget.type};
        if (widget.type === "org.kde.plasma.icontasks" || widget.type === "org.kde.plasma.taskmanager") {
            widget.currentConfigGroup = ["General"];
            row.launchers = widget.readConfig("launchers", []);
        } else if (widget.type === "org.kde.plasma.icon") {
            widget.currentConfigGroup = ["General"];
            row.url = widget.readConfig("url", "");
        }
        report.push(row);
    }
}
print(JSON.stringify(report));
'
```

Each task-manager entry must show an empty launchers list/string. No standalone
application shortcut should remain. Confirm visually that the panel, menu,
tray and clock work. Open an installed application from the menu, check its
running-window button, and close it: that button should disappear. A button
for a running application is expected; the requested removal concerns pins.
Log out and back in to confirm pins do not return. Repeat the checks on the
first login of a newly installed user.

If D-Bus evaluation is disabled on a particular build, retain the error and
inspect the per-user appletsrc plus the schema and the fresh-session visual
result instead. Do not enable extra D-Bus access or add packages for this check.

## Existing-profile repair, only when desired

To clear pins in an already running live profile, back up its configuration
and run the deployed script once through Plasma. This also clears user-added
pins, so it is separate from the clean-default validation:

```bash
cp -a ~/.config/plasma-org.kde.plasma.desktop-appletsrc \
  ~/.config/plasma-org.kde.plasma.desktop-appletsrc.before-aphrodite-os-panel-fix
gdbus call --session --dest org.kde.plasmashell \
  --object-path /PlasmaShell \
  --method org.kde.PlasmaShell.evaluateScript \
  "$(cat /usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/aphrodite-os-launchers.js)"
```

## Verification status

Inspected the supplied package list, project panel script, related build hooks,
and the actual Debian plasma-desktop-data 6.3.6-1 package metadata, default panel
template and task-manager schema. The metadata confirms the shared schema.

Executed the new script against multiple simulated panels and both task-manager
types, including standalone application/missing-desktop references and preserved
menu, tray, clock, pager, show-desktop, document/folder/Link shortcuts. Repeated
execution remained idempotent. Executed the hook's real Python body twice against
the Debian package data: only the launcher default changed; the other 29 schema
entries were preserved.

These are source/configuration checks, not a real Plasma session. This Windows
session cannot access the WSL build directory or perform a privileged rebuild.
Clean live boot, graphical icon interaction, logout/login, new-panel creation,
and installed-user validation are NOT VERIFIED on this revision. The commands
above are the remaining acceptance checks.

Primary references:

- https://develop.kde.org/docs/plasma/scripting/api/
- https://packages.debian.org/trixie/all/plasma-desktop-data/filelist
