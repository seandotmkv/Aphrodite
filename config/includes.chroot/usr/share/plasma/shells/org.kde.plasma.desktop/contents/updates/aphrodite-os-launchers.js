// Installer-generated, verified launchers. One application per desktop profile;
// later logins and system upgrades never reset the user's taskbar.
(function () {
    const state = new ConfigFile("aphrodite-os-taskbar-state", "State");
    if (String(state.readEntry("initialized", "false")) === "true") {
        return;
    }
    const policy = new ConfigFile("/etc/xdg/aphrodite-os-taskbar.conf", "Launchers");
    if (String(policy.readEntry("enabled", "false")) !== "true") {
        return; // Live session: no installed-user pin policy exists.
    }
    const urls = Array.from(new Set(String(policy.readEntry("urls", "")).split(",")
        .filter(url => /^applications:[A-Za-z0-9_.+\-]+\.desktop$/.test(url))));
    let applied = false;
    for (const panel of panels()) {
        for (const widget of panel.widgets()) {
            if (widget.type === "org.kde.plasma.icontasks" ||
                widget.type === "org.kde.plasma.taskmanager") {
                widget.currentConfigGroup = ["General"];
                widget.writeConfig("launchers", urls);
                widget.reloadConfig();
                applied = true;
            }
        }
    }
    if (applied) {
        state.writeEntry("initialized", "true");
    }
})();
