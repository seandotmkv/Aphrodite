import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "Translations.js" as Translations
import io.calamares.core 1.0
import io.calamares.ui 1.0

ScrollView {
    id: page
    readonly property string localeName: {
        if (visible) return Qt.locale().name;
        return Qt.locale().name;
    }
    clip: true
    contentWidth: availableWidth
    palette.button: "#383838"
    palette.buttonText: "#f5f5f5"
    palette.highlight: "#f3a1c3"
    property string profileReport: ""

    function onActivate() {
        profileReport = Global.value("seanProfileReport") || ""
    }

    ColumnLayout {
        width: page.availableWidth
        spacing: 18
        InstallerHeader { Layout.fillWidth: true; localeName: page.localeName }
        Label {
            Layout.alignment: Qt.AlignHCenter
            color: "#8dd4a4"
            font.pixelSize: 36
            text: "✓"
        }
        Label {
            Layout.alignment: Qt.AlignHCenter
            color: "#f5f5f5"
            font.pixelSize: 27
            font.bold: true
            text: Translations.text("Installation Complete", page.localeName)
        }
        Label {
            Layout.fillWidth: true
            color: "#f5f5f5"
            text: Translations.text("Your operating system has been installed successfully.", page.localeName)
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }
        Label {
            Layout.fillWidth: true
            color: "#a8a8a8"
            text: Translations.text("Remove the installation medium when prompted during restart.", page.localeName)
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }
        Flow {
            Layout.alignment: Qt.AlignHCenter
            Layout.maximumWidth: page.availableWidth
            spacing: 12
            Button {
                text: Translations.text("Restart Now", page.localeName)
                highlighted: true
                onClicked: config.doRestart(true)
            }
            Button {
                text: Translations.text("Continue Using Live Environment", page.localeName)
                onClicked: ViewManager.quit()
            }
        }
        Label {
            Layout.fillWidth: true
            visible: page.profileReport !== ""
            color: "#f5f5f5"
            text: Translations.text("Optional package results", page.localeName)
            font.bold: true
        }
        Label {
            Layout.fillWidth: true
            visible: page.profileReport !== ""
            color: "#a8a8a8"
            text: page.profileReport
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
        }
        Label {
            Layout.fillWidth: true
            visible: /incomplete|skipped/.test(page.profileReport)
            color: "#f5f5f5"
            text: "See /var/log/aphrodite-os-selected-packages.log on the installed system. To retry from the live terminal, use aphrodite-os-apply-packages with the mounted target."
            wrapMode: Text.Wrap
        }
    }
}
