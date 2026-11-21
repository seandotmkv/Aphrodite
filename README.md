<div align="center">

# Aphrodite OS

### Your computer. Your choices.

**A Debian-based Linux distribution built for everyday computing, gaming, and creativity.**

[**Download Aphrodite OS**](https://github.com/seandotmkv/Aphrodite/releases) · [**Report an Issue**](https://github.com/seandotmkv/Aphrodite/issues) · [**View Source**](https://github.com/seandotmkv/Aphrodite)

![GitHub release](https://img.shields.io/github/v/release/seandotmkv/Aphrodite?display_name=tag&label=release)
![GitHub issues](https://img.shields.io/github/issues/seandotmkv/Aphrodite)
![GitHub stars](https://img.shields.io/github/stars/seandotmkv/Aphrodite)

</div>

---

## Meet Aphrodite

Aphrodite OS is a Linux distribution based on Debian, designed to make setting up a computer more personal and straightforward. Choose the software you want during installation, keep the desktop uncluttered, and add gaming and creative tools when you need them.

Rather than making everyone use the same collection of applications, Aphrodite aims to let you build a system that fits you from the beginning.

> **Project status:** Aphrodite OS is under active development. Features described below are project goals and may not all be available or fully tested in the current build. Check the release notes before installing.

## What makes Aphrodite different?

| Feature | What it means |
|---|---|
| **An installer built around choice** | Pick browsers, applications, and optional components during setup. |
| **A familiar desktop** | A clean everyday environment without an oversized default app collection. |
| **Gaming when you want it** | Optional Steam, gaming utilities, and Gamescope-based sessions. |
| **Emulation options** | Select emulator packages for classic and modern systems where available. |
| **Debian foundation** | Built on Debian's package ecosystem and familiar Linux tools. |
| **Project-managed updates** | A planned Aphrodite update workflow with releases hosted on GitHub. |
| **Open development** | Source code, changes, and issue tracking in one public repository. |

## Choose your experience

### Everyday desktop

Aphrodite is intended to work as a normal desktop Linux system first. Use it to browse, study, work, create, or play. The goal is a useful default installation without filling the applications menu with tools you never asked for.

### Gaming

Gaming tools are optional rather than mandatory. The installer is being designed to offer Steam and other launchers, compatibility tools, and gaming utilities through clearly separated selections.

**Planned gaming-session choices:**

1. **Desktop only** — no dedicated Gamescope gaming session.
2. **Desktop + Game Mode** — boot to the desktop, with a separate gaming session available when wanted.
3. **Game Mode first** — a console-like session as the main experience, with the desktop available separately.

Gaming-mode availability and compatibility depend on the selected packages and hardware. Not all configurations are guaranteed to work in early builds.

### Emulation

The optional emulator selection is intended to cover systems such as Game Boy Advance, Nintendo DS and 3DS, Wii, Wii U, and other supported platforms. Individual emulators depend on upstream availability and compatibility.

**Aphrodite does not include commercial game ROMs, BIOS files, or encryption keys.** Users must obtain any required files lawfully.

### Applications you choose

The installer is intended to group software by purpose, including browsers, recommended applications, gaming, multimedia, and additional utilities. Applications such as OBS Studio, Heroic Games Launcher, EasyEffects, and Obsidian can be offered as optional selections rather than being installed on every machine.

## Download and install

**[Visit the Releases page](https://github.com/seandotmkv/Aphrodite/releases)**

When an ISO release is available:

1. Download the ISO and read its release notes.
2. Back up important files before making changes to partitions.
3. Write the ISO to a USB drive using a suitable imaging tool.
4. Boot from the USB drive and test the live environment, if included.
5. Start the Aphrodite installer, choose your preferences, and review disk changes carefully.
6. Complete installation and restart into your new system.

> **Important:** Do not assume Secure Boot, Ventoy, every GPU driver, or every installation option is supported until confirmed in the relevant release notes. Early releases should be tested in a virtual machine or on non-critical hardware first.

## Updates

Aphrodite is being developed with a GitHub-based release workflow. The goal is to publish versioned updates and provide a straightforward way for installed systems to receive project-specific improvements.

The exact update and rollback behavior depends on the implementation shipped in each release. **GitHub hosting alone does not make the system immutable or provide atomic upgrades.** Debian security and package updates also need to be handled correctly alongside Aphrodite's own releases.

Follow [Releases](https://github.com/seandotmkv/Aphrodite/releases) for published versions and release notes.

## For developers and contributors

Aphrodite's source is hosted here so others can inspect the project, report problems, suggest improvements, and contribute changes.

```bash
git clone https://github.com/seandotmkv/Aphrodite.git
cd Aphrodite
```

Build prerequisites and the exact ISO build command will be documented alongside the published build configuration. Avoid running unverified build scripts as root.

### Reporting bugs

Use [GitHub Issues](https://github.com/seandotmkv/Aphrodite/issues) and include:

- The Aphrodite version or ISO filename.
- Your hardware or virtual machine configuration.
- What you expected to happen and what actually happened.
- Steps to reproduce the issue.
- Relevant installer or system logs, with personal information removed.

Issues involving package selection, installer progress, gaming-session setup, and updates are particularly useful during early development.

## Frequently asked questions

**Is Aphrodite based on Debian?**  
Yes. Aphrodite is a Debian-based distribution, with its own intended installation experience, branding, and software choices.

**Do I have to install Steam or emulators?**  
No. The installer is designed around optional software selections.

**Is Aphrodite the same as Bazzite or SteamOS?**  
No. Aphrodite is a separate Debian-based project. Bazzite is Fedora Atomic-based, and SteamOS has its own architecture. Aphrodite's planned gaming options do not imply identical compatibility or update behavior.

**Is Aphrodite immutable?**  
An immutable or image-based design has been considered, but its availability must be confirmed against the actual release implementation. Do not assume it is present in an ISO unless the release notes say so.

**Can I help?**  
Yes. Open an issue with a reproducible bug or a clear suggestion. Contributions are welcome as the repository develops.

## Acknowledgements

Aphrodite builds on the work of Debian and the wider free and open-source software community. The project's presentation takes inspiration from approachable Linux distributions such as [Bazzite](https://github.com/ublue-os/bazzite), while following its own direction.

## License

See the repository's `LICENSE` file once published for the licensing terms of Aphrodite's original code. Included third-party software retains its own licenses.

---

<div align="center">

**Aphrodite OS — made to be yours.**

[Releases](https://github.com/seandotmkv/Aphrodite/releases) · [Issues](https://github.com/seandotmkv/Aphrodite/issues) · [Source Code](https://github.com/seandotmkv/Aphrodite)

</div>
