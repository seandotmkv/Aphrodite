# What the apply and build commands do

The command block runs inside parentheses with `set -euo pipefail`. A failed
command, unset shell variable or failed pipeline stops that block before its
next command. Your interactive terminal remains open. The block does not resume
automatically after an error.

## Applying an existing source update

The source-migration archive is for an existing build directory. It is not
needed when building this complete repository snapshot from a fresh clone.

1. `cd /home/sean/mydistro` selects the existing build project.
2. `test -s ...tar.gz`, when included, checks that the update archive exists and
   is nonempty.
3. `tar -xzf ...tar.gz` extracts the migration program, payload and hash manifest
   into `aphrodite-consolidated-update/` inside that project.
4. `python3 aphrodite-consolidated-update/apply-release.py .` checks for an active
   build or mounted build filesystems, verifies the payload and recognized old
   source hashes, rejects unknown edits, backs up files being replaced and
   applies the source changes. The backup is
   `.aphrodite-source-backup-<timestamp>-<suffix>.tar.gz` in the build directory.
5. The migration assigns executable permissions, checks shell/Python syntax,
   runs the Linux unit-test suite and runs `lb config`. It does not build an ISO.
   Test output can describe simulated updates or installs: those are fixtures,
   not actual updates to the running computer.

## Building the release

`./scripts/build-release` performs these steps in order:

1. Locks the project so another copy cannot build it simultaneously. It also
   checks for an existing live-build process and mounted filesystems under
   `chroot/` or `binary/` before cleaning.
2. Runs the unit-test suite again. Failure stops before privileged rebuilding.
3. If no nonempty `~/aphrodite-os-0-known-working.iso` backup exists, copies and
   compares an available previous ISO. It also recognizes the earlier sean-os
   backup/image names. It keeps an existing backup rather than overwriting it.
4. Runs `sudo -v`, prompting for the Debian build-host password if required.
5. Copies existing downloaded APT archives from the old chroot into live-build's
   package cache, where available.
6. Runs `sudo lb clean --all` to remove prior build stages, then `lb config` to
   regenerate the build configuration from the source. Build intermediates are
   disposable; source configuration remains the input.
7. Runs `sudo lb build`, showing output and saving it in `build.log`. Live-build
   creates a Debian chroot, installs its package lists, runs the executable
   hooks, assembles the live filesystem and boot/installer files, and creates
   the hybrid ISO. The wrapper renames the result `aphrodite-os-0-amd64.iso`.
8. Runs `scripts/verify-release`: checks required files, live/target package
   inventories, live-only removal rules, absence of unselected optional apps,
   and expected ISO/SquashFS paths. These are artifact checks, not VM boots.
   The target inventory is written as `aphrodite-os-0-amd64.target.packages`.
9. Runs `scripts/export-update-release`, copying the built `aphrodite-base`
   package from the completed chroot and writing `aphrodite-update.json` plus
   `SHA256SUMS` under `release-assets/0.2/` for the current package version.
10. Writes `aphrodite-os-0.sha256`, covering the ISO, live package inventory and
    target package inventory.
11. Copies those four release files into the export directory using temporary
    files, checks each copy byte for byte, then replaces the destination file.
    The directory defaults to `/mnt/c/Users/sean/Downloads`; override it with
    `APHRODITE_OS_EXPORT_DIR` on another host. It must already exist.
12. Checks the exported files against the generated SHA256 list.

The final `test -s /mnt/c/Users/sean/Downloads/aphrodite-os-0-amd64.iso` checks
that the exported ISO is nonempty. `ls -lh` displays its size and timestamp.
Neither command boots or installs it.

The source includes the Aphrodite name/logos, wallpaper, terminal installer,
package selection/recovery, GitHub release checks and live/installed login policy.
Applying these sources does not change an already-running installed VM; those
changes must enter a newly built image or an appropriate installed-system package.
The immutable path remains explicitly experimental and off by default.

The build does not write an ISO to a USB, partition the host, install Aphrodite
onto the host, upload files to GitHub, publish a release or certify hardware.
The GitHub check/install commands belong inside installed Aphrodite OS, not
inside the Debian WSL build host.
