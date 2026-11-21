import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Controls as Controls
import QtQuick.Layouts
import "Translations.js" as Translations

ScrollView {
    id: page
    readonly property string localeName: {
        if (visible) return Qt.locale().name;
        return Qt.locale().name;
    }
    clip: true
    contentWidth: availableWidth
    palette.windowText: "#f5f5f5"
    palette.text: "#f5f5f5"
    palette.buttonText: "#f5f5f5"
    palette.base: "#313131"
    palette.button: "#454545"
    palette.highlight: "#f3a1c3"
    palette.highlightedText: "#211219"
    property date now: new Date()
    readonly property int daysInMonth: new Date(year.value, month.value, 0).getDate()

    function save() {
        if (automatic.checked) {
            config.packageChoice = "auto:" + encodeURIComponent(servers.text.trim())
        } else {
            let parts = [year.value, month.value, day.value, hour.value, minute.value]
            config.packageChoice = "manual:" + parts.join("-")
        }
    }

    Timer {
        interval: 1000
        repeat: true
        running: page.visible
        onTriggered: page.now = new Date()
    }
    ColumnLayout {
        width: page.availableWidth
        spacing: 14

        Label {
            text: Translations.text("Date and Time", page.localeName)
            font.pixelSize: 26
            font.bold: true
        }
        CheckBox {
            id: automatic
            text: Translations.text("Automatically set date and time using time servers", page.localeName)
            checked: true
            onToggled: page.save()
        }
        Label {
            text: Qt.formatDateTime(page.now, twelveHour.checked ? "yyyy-MM-dd hh:mm AP" : "yyyy-MM-dd HH:mm")
        }
        CheckBox {
            id: twelveHour
            text: Translations.text("Show AM/PM in the clock preview", page.localeName)
        }
        Label {
            visible: automatic.checked
            text: Translations.text("NTP servers (optional, separated by spaces)", page.localeName)
        }
        TextField {
            id: servers
            visible: automatic.checked
            Layout.fillWidth: true
            Accessible.name: Translations.text("NTP servers", page.localeName)
            maximumLength: 253
            validator: RegularExpressionValidator { regularExpression: /[a-zA-Z0-9.: -]*/ }
            onTextEdited: page.save()
        }
        GridLayout {
            visible: !automatic.checked
            columns: 2
            Label { text: Translations.text("Year", page.localeName) }
            SpinBox {
                id: year
                from: 2000; to: 2099; value: new Date().getFullYear()
                editable: true
                Accessible.name: Translations.text("Year", page.localeName)
                onValueModified: page.save()
            }
            Label { text: Translations.text("Month", page.localeName) }
            SpinBox {
                id: month
                from: 1; to: 12; value: new Date().getMonth() + 1
                editable: true
                Accessible.name: Translations.text("Month", page.localeName)
                onValueModified: page.save()
            }
            Label { text: Translations.text("Day", page.localeName) }
            SpinBox {
                id: day
                from: 1; to: page.daysInMonth; value: Math.min(new Date().getDate(), to)
                editable: true
                Accessible.name: Translations.text("Day", page.localeName)
                onValueModified: page.save()
            }
            Label { text: Translations.text("Hour (24-hour)", page.localeName) }
            SpinBox {
                id: hour
                from: 0; to: 23; value: new Date().getHours()
                editable: true
                Accessible.name: Translations.text("Hour (24-hour)", page.localeName)
                onValueModified: page.save()
            }
            Label { text: Translations.text("Minute", page.localeName) }
            SpinBox {
                id: minute
                from: 0; to: 59; value: new Date().getMinutes()
                editable: true
                Accessible.name: Translations.text("Minute", page.localeName)
                onValueModified: page.save()
            }
        }
        Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            color: "#a8a8a8"
            text: Translations.text("Choose the timezone on the next page. Automatic time requires network access. Manual time is set when installation starts configuring the system.", page.localeName)
        }
    }
}
