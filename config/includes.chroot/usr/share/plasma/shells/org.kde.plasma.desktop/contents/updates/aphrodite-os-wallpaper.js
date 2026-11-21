// Apply the release wallpaper once per Plasma profile.
for (const desktop of desktops()) {
    desktop.wallpaperPlugin = "org.kde.image";
    desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    desktop.writeConfig("Image", "file:///usr/share/backgrounds/aphrodite-os/forest-3622519.jpg");
    desktop.writeConfig("FillMode", 2);
}
