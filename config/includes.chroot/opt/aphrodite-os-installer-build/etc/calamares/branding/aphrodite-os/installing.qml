import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import io.calamares.core 1.0
import "Translations.js" as Translations

Item {
    id: progressView
    property int phase: 1
    Connections {
        target: Global
        function onChanged() {
            progressView.phase = Global.value("seanInstallPhase") || 1
        }
    }
    function onActivate() {}
    function onLeave() {}
    ColumnLayout {
        anchors.fill: parent
        spacing: 16
        InstallerHeader { Layout.fillWidth: true }
        Item { Layout.fillHeight: true }
        BusyIndicator {
            Layout.alignment: Qt.AlignHCenter
            palette.accent: "#f3a1c3"
            running: progressView.visible
        }
        Label {
            Layout.alignment: Qt.AlignHCenter
            text: Translations.text("Installing", Qt.locale().name)
            color: "#f5f5f5"
            font.pixelSize: 28
            font.bold: true
        }
        Flow {
            Layout.fillWidth: true
            Layout.margins: 12
            spacing: 14
            Repeater {
                model: ["Storage Configuration", "Software Installation",
                        "System Configuration", "Finalization"]
                delegate: ColumnLayout {
                    id: stage
                    required property int index
                    required property string modelData
                    readonly property bool active: progressView.phase === index + 1
                    readonly property bool complete: progressView.phase > index + 1
                    width: Math.max(132, (parent.width - 42) / 4)
                    Label {
                        Layout.alignment: Qt.AlignHCenter
                        text: stage.complete ? "✓" : stage.index + 1
                        color: stage.complete ? "#8dd4a4" : stage.active ? "#f3a1c3" : "#a8a8a8"
                        font.bold: true
                    }
                    Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: Translations.text(stage.modelData, Qt.locale().name)
                        color: stage.active ? "#f5f5f5" : "#a8a8a8"
                    }
                }
            }
        }
        Item { Layout.fillHeight: true }
    }
}
