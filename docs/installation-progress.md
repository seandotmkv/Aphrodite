# Terminal installation progress

The existing `Install aphrodite-os` entry and terminal worker are unchanged entry
points. The progress view is part of that terminal application. No additional
installer window, service, package or graphical renderer is introduced.

## Interface

The fixed header shows the current stage, a stage-based overall percentage,
APT package counter, current operation, elapsed time and active/error status.
The four advanced sections start collapsed. On success, the same view changes
to a completion heading, duration, count of additional applications installed,
summary/log access and a **Restart System** action. Optional package failures
produce an installed-with-warnings heading; fatal failures never show success
or offer the restart action. Restart requires a separate confirmation.

- `1`–`4`: toggle Installation Details, Package Installation, Live Installation
  Logs or System Configuration.
- Up/Down or Tab/Shift-Tab: select a section. Enter/Space toggles it; Left closes
  and Right opens it. The progress header stays fixed while the section body
  scrolls with Page Up/Page Down, Home and End.
- `/`: search application/dependency history. Enter keeps the filter and returns
  to navigation; Ctrl-U clears it. Search includes names and status text.
  The model retains 2000 timestamped package state changes; the panel shows up
  to 250 matching recent events in addition to current application/package states.
- `p`: pause/resume the displayed log tail. The worker and full diagnostic log
  continue while the view is paused.
- `c`: request copying the diagnostic log through the terminal's OSC 52
  clipboard facility. The terminal must support and allow it. At most the last
  100 KB are sent; the UI explicitly reports this limit. It cannot confirm that
  the terminal accepted the clipboard request. No privileged Wayland socket
  access or extra clipboard package is required.
- `s`: save the full diagnostic file as a private, uniquely named
  `/var/log/aphrodite-os/saved-install-*.log`. The destination is shown on screen.
  Copy/export work runs in a background thread. The saved file is a snapshot
  through that moment; save again after completion for the final result.
- `r`: request restart after successful installation, then `y` to confirm or
  `n`/Esc to stay. Demo mode cannot restart the machine. `q` closes a completed
  or failed installer; it does not abort an active disk operation.
- Mouse clicks toggle section headings and activate displayed log actions on
  terminals supporting curses mouse events. Keyboard controls remain primary.
- Reduced motion is the default. `--motion` or F6 enables/disables brief,
  clock-driven 120 ms panel transitions. No sleep runs on the UI thread.

The view wraps panel content and works from 80x24 terminals upward. Terminal
resize preserves state; smaller dimensions show a compact status instead of
starting a second installer. The curses renderer updates changed rows rather
than repainting everything. Normal input polling is 250 ms; brief transitions
use 40 ms polling. Backend work never runs on the input/render thread.

## Honest progress accounting

The nine stages are preflight, storage, image extraction, account setup,
filesystem setup, selected applications, bootloader, services, and final cleanup.
The overall estimate gives these stages equal shares; it is **not** a measured
percentage of total bytes or total wall-clock time. Stage completion events,
real extraction percentages and application transaction events advance it.
It stays below 100% until the backend successfully returns after target
unmounting and synchronization. An elapsed timer alone never advances it.

The base operating system is copied from SquashFS, rather than installed as
hundreds of separate APT transactions. Its existing packages are not counted
as newly installed APT packages. Selected applications, including Flatpaks and
pinned source apps, have a separate list and completion count.

The APT denominator is the deduplicated solver plan, including dependencies,
from each actual transaction. It says **known** while further transactions
may still be resolved; it is not a promised final total. Native and qualified
architecture names are reconciled without double counting. The numerator
advances on APT's C-locale `Installed ...` status, then the whole transaction
is confirmed only after command success and package-manager checks. A global
`pmstatus` percentage alone does not mean that an individual package succeeded.
Failures or skipped application selections remain visible. Further transaction
checks may still fail after some packages were configured.

Extraction can show a measured **copy-stage** remaining-time estimate. Overall
remaining time says **estimating** where the backend has no defensible forecast;
it does not invent an ETA for downloads, maintainer scripts or bootloader work.
Package speed is a labelled session average. A running-command heartbeat says
the worker is alive, not that its underlying disk/network operation made progress.

Protocol reference: [APT install-progress reporting](https://github.com/Debian/apt/blob/main/doc/progress-reporting.md).

## Files and live-build integration

Within `config/includes.chroot/opt/aphrodite-os-installer-build/`:

- `usr/bin/aphrodite-os-installer-tui`: existing application; consumes queued events,
  handles panel/log/restart input and renders the in-place completion screen.
  Retains executable mode **0755**.
- `usr/libexec/aphrodite_os_progress.py`: view state, bounded display-log inbox,
  progress model and accordion renderer; mode **0644**.
- `usr/libexec/aphrodite_os_install.py`: existing backend, now emits stage, extraction,
  command and error events; mode **0644**.
- `usr/lib/calamares/modules/aphroditeprofiles/executor.py`: existing package
  executor, now emits actual solver/package/application events and streams
  command output; mode **0644**.
- `usr/lib/calamares/modules/aphroditeprofiles/processio.py`: shared worker-side
  command runner, streaming output, APT status descriptor and deadlines;
  mode **0644**.

`config/hooks/normal/0700-aphrodite-os-installer.hook.chroot` remains **0755** and
builds the existing live-only installer package. It checks the new modules and
executes a safe demo progress frame during the build. No `/etc/skel` or desktop
defaults are required for these per-process, initially collapsed panels.
`scripts/verify-release` checks both new runtime modules in the final SquashFS.

## Stalls addressed independently of rendering

Previously, package output was held in a temporary file until process exit;
long operations therefore appeared inactive. Also, the ordinary command path
could wait indefinitely on stdout lines or child process completion. The shared
worker now polls independently opened output files, streams CR/newline updates,
enforces a deadline and terminates/reaps the process group on timeout. It can
handle a silent command or a child emitting no final newline. APT keeps its
existing 120/1200/1800 second command limits; base extraction has a 7200 second
limit. The normal backend command default is 1800 seconds. Heartbeats are emitted
every five seconds and timeouts identify the failed command in diagnostics.

Timezone enumeration previously occurred synchronously in `fields()`, which
rendering and keyboard handling call. It now runs in a daemon worker and updates
the timezone chooser asynchronously. A missing/malformed/oversized cached
package metadata snapshot falls back to unknown sizes rather than crashing.
Disk scans remain background jobs using the unchanged fail-closed boot-medium
guard and target identity checks. Exceptions in that scan are saved to the log.
Panel input never invokes installation, repeats an operation, or alters storage
and package choices while the installation is active.

These are fixes for identified source-level blocking/visibility defects.
They do **not** establish the cause of every previously reported hardware or
Calamares startup freeze. The retained graphical Calamares interface was not
redesigned or certified here. A fresh live terminal run and runtime logs are
still required to confirm that the reported freeze is resolved.

## Validation

Run in the actual Debian source tree before rebuilding:

```bash
python3 -m unittest discover -s tests -v
python3 config/includes.chroot/opt/aphrodite-os-installer-build/usr/bin/aphrodite-os-installer-tui \
  --demo --progress-preview
```

The demo progress view is labelled DEMO and never invokes the installer. To
print one static frame, also add `--preview`. It deliberately shows no invented
package count or fake installation. Press `q` to leave the interactive preview;
active real installations require a completed worker before the normal quit
action is available.

Development checks performed on Windows: 18 platform-independent tests of the
state model, layout, input, stream runner, deadlines, output limits and secret
suppression passed. An additional 16 catalog/selection/interface checks passed
with an explicit import-only POSIX shim; these are not Linux system validation.
The new test file includes seven POSIX integration tests, skipped by the native
Windows runner. Python syntax was checked for all project Python sources.

Still required: the full Linux test suite; a real curses terminal/mouse/resize
check; the inherited APT status descriptor on Linux; clean live boot; privileged
ISO build; BIOS/UEFI disposable-disk install and installed-system boot; normal
USB and Ventoy boots; physical-hardware freeze reproduction. Previous VM test
claims elsewhere in this repository describe earlier revisions, not this change.
The Windows host also refused to launch Git Bash, so shell syntax checks for
the two changed shell scripts need to run in Debian as part of validation.

After applying the patch and passing the Linux suite:

```bash
./scripts/build-release
```

Test using the newly built ISO and a fresh nonpersistent live session. Open
`Install aphrodite-os`, verify four collapsed panels, then use only a disposable VM
disk for an installation. Exercise input/resize/log search while the worker
copies files and installs a chosen package with dependencies. Pause and resume
logs without interrupting work. Test an offline optional-app failure, a fatal
worker failure and a successful completion; check that a failure never shows
the success screen. Copy/save logs, then test confirmed restart only inside
the VM. Do not select a host or personal-data disk for this validation.
