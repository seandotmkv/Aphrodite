# Release updates and login policy

## Users

The installed desktop checks the public stable releases at
https://github.com/seandotmkv/Aphrodite after login (about 2–4 minutes) and then
every 30–32 minutes. It uses GitHub's conditional HTTP requests and stores its
metadata in `~/.cache/aphrodite-updates`. A new release or changed release asset
set triggers one desktop notification. No GitHub token is needed for a public
repository. Offline, rate-limit and download failures appear in the user journal;
the next timer invocation retries. This is polling, not an instant webhook.

```bash
aphrodite-update check
sudo aphrodite-update install
systemctl --user status aphrodite-update.timer
journalctl --user -u aphrodite-update.service -n 80
sudo tail -n 100 /var/log/aphrodite-update.log
```

The notifier does not install anything or interrupt an installation. It is
disabled in live sessions. Drafts and prereleases are excluded. Editing a branch,
committing source or creating a plain Git tag does not publish a release update.

The updater downloads only assets of this fixed GitHub repository. It verifies
GitHub's SHA256 digest, then manifest checksums and actual Debian package
name/version/architecture. Only `aphrodite-*` packages, OS series 0 and amd64/all
are supported. Package downgrades and APT removals are rejected. Source archives,
release descriptions, ISO files and arbitrary remote scripts are never executed.
The trust anchor is the configured owner's GitHub account over HTTPS; SHA256
is an integrity check, not an independent signing key. Debian dependencies still
come from the existing signature-verified APT sources.

Mutable systems install with APT and verify package versions before recording
success. If APT fails, no successful-release marker is written: inspect the log
and repair any reported dpkg failure before retrying. Transactional development
systems stage verified packages in a new deployment, write its receipt there,
and require a reboot. The active root is not upgraded in place. This path remains
unqualified until the disposable VM update/rollback test passes.

## Publishing

An installed system cannot apply an ISO or a GitHub source ZIP as a package
update. Each installable release must have the generated package and manifest.
The build produces `aphrodite-base`, containing the distribution's updater,
runtime/application modules, transaction support, supplied icons and wallpaper.
It does not mirror all source files over `/` or replace user preferences. Changes
to other system files require an appropriate maintained Debian package; boot/live
installer changes require a new ISO. Adding another `aphrodite-*` package is
supported by the manifest, but that package must be built and tested first.

For every changed package, increase its Debian version in
`config/includes.chroot/usr/share/aphrodite/package-version` **before rebuilding**.
The starting package version is 0.2; it is distinct from the OS release label
0 (infant). Do not replace a package's bytes while keeping the same version.

```bash
cd /home/sean/mydistro
./scripts/build-release
# Also available separately after a completed build:
./scripts/export-update-release
```

For version 0.2 upload these together to a new published stable GitHub Release:

- `release-assets/0.2/aphrodite-base_0.2_all.deb`
- `release-assets/0.2/aphrodite-update.json`
- `release-assets/0.2/SHA256SUMS`

The ISO can be another release asset for fresh installations. Upload all assets
while the release is a draft, then publish it and mark it latest. GitHub must
report SHA256 digests for the downloadable assets; missing digests stop the
installation. Package filenames must use letters, numbers, dots, underscores,
plus signs or hyphens. Source code belongs in Git; generated ISOs, caches,
chroots, package artifacts and credentials do not. No GitHub upload is performed
by the local build/export scripts.

## Login

`usr/lib/live/config/0086-aphrodite-os-sddm` runs after live-config has created
the `live` account. It calls `/usr/lib/aphrodite/login.py --live` to set SDDM's
autologin user, Plasma Wayland session and relogin. It disables idle/resume
locking only in the ephemeral live user's home, without changing `/etc/skel`.

The terminal installer's Account tab adds **Log in automatically**, disabled
by default. The Review page and exported plan record the choice. After live-only
cleanup and gaming-session setup, the backend writes the chosen user's SDDM
policy. Password login clears the live autologin user; automatic login selects
the created account and a successfully configured gaming session where selected.
The account password remains required for sudo and normal unlocking. No password
is written to SDDM configuration. Only the Autologin section is changed; unrelated
SDDM settings and panel configuration are preserved.

## Validation

`tests/test_github_updates_login.py` tests changed-asset fingerprints, conditional
metadata caching, notifications, malformed/digest-corrupt releases, package
allowlists, mutable/staged routing, downgrade refusal and login policy isolation.
Storage and APT operations are mocked. Source-policy regression checks also pass.
Windows cannot run the real WSL build, user systemd session or firmware boot here.

Before a release, use a disposable VM: verify the live desktop appears without
a login/idle password prompt; test installed password and automatic-login choices;
publish a tested higher-version package to a stable release, observe notification,
install it and verify version/log/receipt. Test offline behavior and changed assets.
Repeat boot/update/rollback separately for the transactional development option.
