# Uploading Aphrodite

Repository: https://github.com/seandotmkv/Aphrodite

For a command-by-command explanation of the existing apply/build block, see
`build-process.md`.

The supplied `aphrodite-repository.zip` is a complete source snapshot through
the corrected source-tree login import. It contains the build configuration,
installer, package catalog/backend, runtime updater, desktop defaults, image
assets, hooks, scripts, tests and documentation. It excludes build products,
logs, caches, VM screenshots, source-migration bundles and Git history.

## Upload the source

Extract the ZIP's **contents into the repository root**. `README.md`, `auto/`,
`config/`, `scripts/`, `tests/` and `docs/` belong at that level. Commit the
extracted files, not the ZIP file itself and not the contents of the whole
Windows Codex working directory. Hidden `.gitignore` and `.gitattributes` are
included and should also be committed.

Git is recommended because this snapshot exceeds the browser upload's 100-file
batch limit. These commands use a new publishing checkout, preserving the
existing `/home/sean/mydistro` build directory. If `Aphrodite-publish` already
exists, cloning stops: inspect that checkout instead of deleting it.

In Debian WSL, with Git, Python 3 and unzip installed:

```bash
(
    set -euo pipefail
    cd "$HOME"
    git clone https://github.com/seandotmkv/Aphrodite.git Aphrodite-publish
    cd Aphrodite-publish
    unzip /mnt/c/Users/sean/Documents/Codex/2026-11-19/help-me-do-this/outputs/aphrodite-repository.zip
    python3 scripts/prepare-source
    git add .
    git diff --cached --stat
)
```

Review the staged file list, then commit and push in that same checkout:

```bash
(
    set -euo pipefail
    cd "$HOME/Aphrodite-publish"
    git commit -m "Add Aphrodite OS source and release updater"
    git push
)
```

Use your own Git identity and GitHub authentication if prompted. No token,
password or private signing key is included. No push is performed by unpacking
the ZIP or running the preparation/build scripts.

## Build from another Debian system

Use Debian 13 amd64 or the existing Debian 13 WSL2 build host with working
privileged mounts. Clone the repository into the Linux filesystem. A full build
needs root privileges, network access and substantial free disk space. Exact
APT results can change with Debian mirrors; this source is not a bit-for-bit
frozen package snapshot. Existing build hooks pin some upstream tool versions
and custom source commits; review any unavailable pin instead of skipping checks.

```bash
(
    set -euo pipefail
    sudo apt-get update
    sudo apt-get install -y live-build debootstrap xorriso squashfs-tools \
        git ca-certificates python3 python3-yaml unzip
    git clone https://github.com/seandotmkv/Aphrodite.git
    cd Aphrodite
    python3 scripts/prepare-source
    mkdir -p "$HOME/Downloads"
    APHRODITE_OS_EXPORT_DIR="$HOME/Downloads" ./scripts/build-release
)
```

The export variable avoids assuming the original Windows Downloads path on a
different computer. On the existing Sean WSL build host, `./scripts/build-release`
continues to use `/mnt/c/Users/sean/Downloads` by default.

## Create the release after a successful build

The current OS label is 0 (infant); the updater's Debian package version is 0.2.
Keep that distinction in release notes. Use a release tag such as `v0.2` for
this package revision, targeting the source commit that produced the files.

In the original build directory the generated release files are:

| File | Purpose |
| --- | --- |
| `aphrodite-os-0-amd64.iso` | Bootable image for fresh installs |
| `aphrodite-os-0.sha256` | Checksums for ISO and both package inventories |
| `aphrodite-os-0-amd64.packages` | Live image package inventory |
| `aphrodite-os-0-amd64.target.packages` | Base installed-system inventory |
| `release-assets/0.2/aphrodite-base_0.2_all.deb` | Installed-system update package |
| `release-assets/0.2/aphrodite-update.json` | Required updater manifest |
| `release-assets/0.2/SHA256SUMS` | Update package checksum |

These are **release attachments**, not Git-tracked source. The `.deb` and update
manifest require a completed build; this repository ZIP cannot substitute for
them. The original build script exports the ISO and its inventories/checksum
to Windows Downloads; updater assets remain in `release-assets/0.2/` under the
build directory. Open that folder through
`\\wsl.localhost\Debian\home\sean\mydistro\release-assets\0.2` on Windows.

On GitHub, open Releases, draft a new release, choose/create the tag and attach
the files. Upload all assets before publishing. Mark the intended update release
latest. A prerelease is skipped by the stable-channel updater. Increase the
package version before every changed package build; do not replace a package's
contents while retaining its version. See `github-releases-and-login.md` for
the updater's trust model and supported file schema.

## Current validation

The last supplied WSL run executed 112 tests with one login-module import error.
That import has been corrected and its local import/handoff regression fixture
passes. A new source-import regression test is included. The full Linux suite
must pass on the build host before building. Real ISO boot, package upgrades,
automatic login and experimental immutable install/update/rollback still need
disposable VM testing. No ISO or update `.deb` was built by preparing this ZIP.

The repository does not yet contain a project-wide license chosen by the
maintainer. Existing upstream components retain their own licenses; add the
intended license for original project code before describing its license terms.

GitHub documentation:

- https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository
- https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
