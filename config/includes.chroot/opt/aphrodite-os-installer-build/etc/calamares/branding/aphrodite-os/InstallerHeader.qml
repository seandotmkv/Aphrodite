import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "Translations.js" as Translations

Rectangle {
    id: header
    property string localeName: Qt.locale().name
    property bool compact: false
    implicitHeight: Math.max(70, headerContent.implicitHeight + 24)
    color: "#893a60"
    RowLayout {
        id: headerContent
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10
        Image {
            source: "file:///usr/share/pixmaps/aphrodite.png"
            sourceSize.width: 34
            sourceSize.height: 34
            Layout.preferredWidth: 34
            Layout.preferredHeight: 34
            Layout.alignment: Qt.AlignVCenter
            fillMode: Image.PreserveAspectFit
        }
        Label {
            Layout.fillWidth: true
            color: "#f5f5f5"
            font.pixelSize: header.compact ? 18 : 21
            font.bold: true
            text: header.compact ? "Aphrodite OS" : Translations.text("Aphrodite OS installation", header.localeName)
            wrapMode: Text.WordWrap
        }
    }
}
