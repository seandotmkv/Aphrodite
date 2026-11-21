import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "PackageCatalog.js" as Data
import "Translations.js" as Translations

ScrollView {
    id: page
    clip: true
    contentWidth: availableWidth
    palette.windowText: "#f5f5f5"
    palette.text: "#f5f5f5"
    palette.buttonText: "#f5f5f5"
    palette.highlight: "#f3a1c3"
    palette.highlightedText: "#211219"
    property var apps: ({"firefox": "apt"})
    property string browser: "firefox"
    property string session: "off"
    property var sessionOwned: []
    property string activePreset: "Minimal"
    property bool legacy: false
    property bool initialized: false
    readonly property var catalog: Data.catalog
    readonly property var categories: Object.keys(catalog.categories)
    readonly property var browsers: catalog.apps.filter(app => app.category === "browser")
    readonly property bool fresh: Data.metadata.version === catalog.version &&
                                  Date.now() - Date.parse(Data.metadata.created) < 90 * 86400000
    readonly property var metadata: fresh ? Data.metadata.entries : ({})
    property int revision: 0
    property string estimate: ""
    property string estimateOrigin: fresh ? "Debian snapshot " + Data.metadata.created.slice(0, 10)
                                          : "Package size snapshot unavailable or expired"

    function available(app) {
        return app.desktop !== "gnome" && Object.keys(app.methods).length > 0
    }
    function matches(app) {
        const query = search.text.trim().toLowerCase()
        return (app.name + " " + app.description).toLowerCase().includes(query)
    }
    function save() {
        config.packageChoice = JSON.stringify({version: catalog.version, apps, browser, session})
        updateEstimate()
    }
    function updateEstimate() {
        revision++
        estimate = "Calculating package sizes…"
        calculator.sendMessage({revision, apps, metadata})
    }
    function preset(name) {
        let next = {"firefox": "apt"}
        for (const app of catalog.apps) {
            const info = metadata[app.id] && metadata[app.id].apt
            if (available(app) && (name === "Recommended" && app.recommended ||
                    name === "Full" && app.full && !app.large && app.license === "open-source" && info && info.full))
                next[app.id] = "apt"
        }
        apps = next
        browser = "firefox"
        session = "off"
        sessionOwned = []
        activePreset = name
        legacy = false
        save()
    }
    function update(next) {
        if (session !== "off" && (!next.steam || !next.gamescope)) {
            for (const id of sessionOwned) delete next[id]
            sessionOwned = []
            session = "off"
        }
        apps = next
        activePreset = "Custom"
        legacy = false
        save()
    }
    function toggle(app, method) {
        if (!available(app) || (!method && app.id === browser)) return
        const next = Object.assign({}, apps)
        if (method) next[app.id] = method
        else delete next[app.id]
        update(next)
    }
    function bulk(category, select) {
        const next = Object.assign({}, apps)
        for (const app of catalog.apps) {
            if (app.category !== category || !available(app) || app.id === browser) continue
            if (select) next[app.id] = next[app.id] || Object.keys(app.methods)[0]
            else delete next[app.id]
        }
        update(next)
    }
    function chooseBrowser(app) {
        const next = Object.assign({}, apps)
        if (!next[app.id]) {
            delete next[browser]
            next[app.id] = Object.keys(app.methods)[0]
        }
        browser = app.id
        update(next)
    }
    function chooseSession(mode) {
        const next = Object.assign({}, apps)
        if (mode === "off") {
            for (const id of sessionOwned) delete next[id]
            sessionOwned = []
        } else if (session === "off") {
            sessionOwned = ["steam", "gamescope"].filter(id => !next[id])
            next.steam = "apt"
            next.gamescope = "apt"
        }
        session = mode
        update(next)
    }
    function details(app, method) {
        const spec = app.methods[method]
        if (app.desktop === "gnome") return "Requires GNOME Shell. This image uses Plasma."
        if (!spec) return app.reason
        const requirements = (spec.packages || []).concat(app.extra)
        const estimateStatus = metadata[app.id] && metadata[app.id][method] && metadata[app.id][method].error
        return spec.source + (spec.ref ? " · " + spec.ref : "") +
               (spec.commit ? " · " + spec.commit.slice(0, 12) : "") +
               (requirements.length ? " · " + requirements.join(", ") : "") +
               " · " + app.license + (app.large ? " · Large download" : "") +
               (estimateStatus ? "\n" + estimateStatus : "")
    }

    function restore() {
        if (initialized) return
        initialized = true
        const old = config.packageChoice
        if (["off", "games", "desktop", "gaming", "off-resolve", "games-resolve",
             "desktop-resolve", "gaming-resolve"].includes(old)) {
            const mode = old.replace("-resolve", "")
            legacy = old !== "off"
            if (mode !== "off") {
                apps = {"firefox": "apt", "steam": "apt", "gamemode": "apt", "mangohud": "apt"}
                if (mode !== "games") {
                    apps = Object.assign({}, apps, {"gamescope": "apt"})
                    session = mode
                }
            }
            if (legacy) activePreset = "Custom"
            updateEstimate()
            return
        }
        try {
            const saved = JSON.parse(old)
            if (saved.version === catalog.version && saved.apps && saved.browser) {
                apps = saved.apps
                browser = saved.browser
                session = saved.session
                activePreset = "Custom"
            }
        } catch (error) {
            estimate = "Package selection could not be read."
        }
        updateEstimate()
    }

    Component.onCompleted: restore()
    onVisibleChanged: {
        if (visible && initialized) updateEstimate()
        else revision++
    }

    WorkerScript {
        id: calculator
        source: "PackageSizes.js"
        onMessage: function(reply) {
            if (reply.revision !== page.revision) return
            const size = value => (value / 1048576).toFixed(1) + " MiB"
            page.estimate = size(reply.download) + " known download · " +
                    size(reply.installed) + " known installed package footprint" +
                    (reply.unknown ? " · " + reply.unknown + " unknown" : "") +
                    (reply.runtimes ? " · Additional shared Flatpak runtimes unknown" : "")
        }
    }

    ColumnLayout {
        width: page.availableWidth
        spacing: 10
        Label {
            text: Translations.text("Additional Packages", Qt.locale().name)
            font.pixelSize: 26
            font.bold: true
        }
        RowLayout {
            Repeater {
                model: ["Minimal", "Recommended", "Full"]
                Button {
                    required property string modelData
                    text: modelData
                    highlighted: page.activePreset === text
                    onClicked: page.preset(text)
                }
            }
        }
        Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: page.activePreset === "Minimal" ? "Essential desktop and browser"
                 : page.activePreset === "Recommended" ? "Adds KeePassXC and PDF Arranger"
                 : page.activePreset === "Full" ? "Adds eligible open-source applications with known Debian sizes"
                 : "Custom selection"
        }
        Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: page.estimate + "\n" + page.estimateOrigin
        }
        Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            visible: page.legacy
            text: "Saved profile restored, including any requested legacy support. Editing choices switches to the application catalog."
        }
        Label { text: "Default browser" }
        ComboBox {
            id: browserChoice
            Layout.fillWidth: true
            model: page.browsers
            textRole: "name"
            currentIndex: page.browsers.findIndex(app => app.id === page.browser)
            onActivated: index => page.chooseBrowser(page.browsers[index])
        }
        Label { text: "Dedicated gaming session" }
        ComboBox {
            Layout.fillWidth: true
            model: ["No dedicated session", "Desktop first", "Gaming mode first"]
            currentIndex: ["off", "desktop", "gaming"].indexOf(page.session)
            onActivated: index => page.chooseSession(["off", "desktop", "gaming"][index])
        }
        Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: "Dedicated sessions select Steam and Gamescope and require a supported AMD or Intel render device. Optional packages require internet access."
        }
        TextField {
            id: search
            Layout.fillWidth: true
            placeholderText: "Search applications"
        }
        Repeater {
            model: page.categories
            delegate: ColumnLayout {
                id: group
                required property string modelData
                readonly property var category: page.catalog.categories[modelData]
                readonly property var entries: page.catalog.apps.filter(app => app.category === modelData && page.matches(app))
                property bool expanded: modelData === "browser"
                visible: entries.length > 0
                Layout.fillWidth: true
                Button {
                    Layout.fillWidth: true
                    icon.name: group.category.icon
                    text: (group.expanded || search.text ? "▾  " : "▸  ") + group.category.title
                    onClicked: group.expanded = !group.expanded
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: group.expanded || search.text.length > 0
                    RowLayout {
                        Button { text: "Select All"; onClicked: page.bulk(group.modelData, true) }
                        Button { text: "Deselect All"; onClicked: page.bulk(group.modelData, false) }
                    }
                    Repeater {
                        model: group.entries
                        delegate: ColumnLayout {
                            id: row
                            required property var modelData
                            readonly property var methods: Object.keys(modelData.methods)
                            readonly property string method: page.apps[modelData.id] || methods[0] || ""
                            Layout.fillWidth: true
                            RowLayout {
                                Layout.fillWidth: true
                                CheckBox {
                                    Layout.fillWidth: true
                                    text: row.modelData.name + (page.browser === row.modelData.id ? " (default)"
                                         : row.modelData.id === "firefox" ? " (Minimal preset)"
                                         : row.modelData.recommended ? " (Recommended preset)" : "")
                                    icon.name: row.modelData.icon
                                    checked: !!page.apps[row.modelData.id]
                                    enabled: page.available(row.modelData) && page.browser !== row.modelData.id
                                    onToggled: page.toggle(row.modelData, checked ? row.method : "")
                                }
                                ComboBox {
                                    visible: row.methods.length > 1
                                    enabled: !!page.apps[row.modelData.id]
                                    model: row.methods
                                    currentIndex: row.methods.indexOf(row.method)
                                    onActivated: index => page.toggle(row.modelData, row.methods[index])
                                }
                            }
                            Label {
                                Layout.fillWidth: true
                                Layout.leftMargin: 26
                                wrapMode: Text.Wrap
                                text: row.modelData.description + "\n" + page.details(row.modelData, row.method)
                                textFormat: Text.PlainText
                            }
                        }
                    }
                }
            }
        }
    }
}
