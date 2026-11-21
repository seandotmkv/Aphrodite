// Apply only the distribution menu-button logo. Preserve panel structure,
// application pins, favourites, and all unrelated widget configuration.
(function () {
    for (const panel of panels()) {
        for (const widget of panel.widgets()) {
            if (widget.type === "org.kde.plasma.kickoff") {
                widget.currentConfigGroup = ["General"];
                widget.writeConfig("icon", "/usr/share/pixmaps/aphrodite.png");
                widget.reloadConfig();
            }
        }
    }
})();
