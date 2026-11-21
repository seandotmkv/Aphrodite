import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import io.calamares.core 1.0
import io.calamares.ui 1.0
import "Translations.js" as Translations

Rectangle {
    id: sidebar
    implicitWidth: 244
    color: "#252525"

    // Both the keyboard and language belong to Welcome. Clock and timezone
    // share the next stage. Calamares owns the validated forward/back actions.
    readonly property int current: [0, 0, 1, 1, 2, 3, 4, 5][ViewManager.currentStepIndex] ?? -1
    readonly property string localeName: {
        const step = ViewManager.currentStepIndex
        return step >= 0 ? Qt.locale().name : "en_US"
    }

    ScrollView {
        id: sidebarScroll
        anchors.fill: parent
        padding: 12
        contentWidth: availableWidth
        clip: true
        ColumnLayout {
            width: sidebarScroll.availableWidth
            spacing: 6
            visible: sidebar.current >= 0

            InstallerHeader {
                Layout.fillWidth: true
                Layout.bottomMargin: 10
                localeName: sidebar.localeName
                compact: true
            }
            Repeater {
                model: ["Welcome", "Date and Time", "Installation and Storage",
                        "Create Account", "Additional Packages", "Review and Install"]
                delegate: Rectangle {
                    id: row
                    required property int index
                    required property string modelData
                    readonly property bool active: index === sidebar.current
                    readonly property bool complete: index < sidebar.current
                    Layout.fillWidth: true
                    implicitHeight: Math.max(43, stepLabel.implicitHeight + 12)
                    radius: 8
                    color: active ? "#3b3036" : "transparent"
                    Accessible.role: Accessible.StaticText
                    Accessible.name: stepLabel.text
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 6
                        spacing: 9
                        Rectangle {
                            implicitWidth: 25
                            implicitHeight: 25
                            radius: width / 2
                            color: row.active ? "#f3a1c3" : "#373737"
                            Label {
                                anchors.centerIn: parent
                                font.bold: true
                                color: row.active ? "#211219" : row.complete ? "#8dd4a4" : "#a8a8a8"
                                text: row.complete ? "✓" : row.index + 1
                            }
                        }
                        Label {
                            id: stepLabel
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            color: row.active ? "#f5f5f5" : "#a8a8a8"
                            text: Translations.text(row.modelData, sidebar.localeName)
                        }
                    }
                }
            }
        }
    }
}
