import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import io.calamares.core 1.0
import io.calamares.ui 1.0

Rectangle {
    implicitHeight: 64
    height: implicitHeight
    color: "#262626"
    Rectangle {
        width: parent.width
        height: 1
        color: "#454545"
    }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        spacing: 12
        Button {
            id: back
            objectName: "backButton"
            Layout.minimumWidth: 110
            Layout.minimumHeight: 42
            text: ViewManager.backLabel
            enabled: ViewManager.backEnabled
            visible: ViewManager.backAndNextVisible
            onClicked: ViewManager.back()
            padding: 10
            horizontalPadding: 18
            palette.buttonText: enabled ? "#f3a1c3" : "#a8a8a8"
            background: Rectangle {
                color: back.hovered ? "#383139" : "transparent"
                border.color: back.enabled ? "#f3a1c3" : "#585858"
                border.width: back.visualFocus ? 2 : 1
                radius: 10
            }
        }
        Button {
            id: next
            objectName: "nextButton"
            Layout.minimumWidth: 110
            Layout.minimumHeight: 42
            text: ViewManager.nextLabel
            enabled: ViewManager.nextEnabled
            visible: ViewManager.backAndNextVisible
            onClicked: ViewManager.next()
            padding: 10
            horizontalPadding: 18
            palette.buttonText: enabled ? "#211219" : "#a8a8a8"
            background: Rectangle {
                color: !next.enabled ? "#383838" : next.hovered ? "#ffd6e7" : "#f3a1c3"
                border.color: next.visualFocus ? "#ffffff" : color
                border.width: 2
                radius: 10
            }
        }
        Button {
            id: quit
            text: ViewManager.quitLabel
            flat: true
            visible: ViewManager.quitVisible
            enabled: ViewManager.quitEnabled
            onClicked: ViewManager.quit()
            palette.buttonText: "#f5f5f5"
            palette.highlight: "#f3a1c3"
        }
        Item { Layout.fillWidth: true }
    }
}
