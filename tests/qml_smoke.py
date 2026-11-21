"""Exercise branding with Qt Quick and a small Calamares API test double."""
import os
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import tempfile

BASE = Path(__file__).resolve().parents[1]
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl, QPoint, Qt, qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtQml import QQmlEngine, qmlRegisterSingletonInstance
from PySide6.QtTest import QTest


class Manager(QObject):
    changed = Signal()
    step = 0
    ready = False
    calls = 0
    currentStepIndex = Property(int, lambda self: self.step, notify=changed)
    backLabel = Property(str, lambda self: "Back", notify=changed)
    nextLabel = Property(str, lambda self: "Next", notify=changed)
    quitLabel = Property(str, lambda self: "Cancel", notify=changed)
    backEnabled = Property(bool, lambda self: self.step > 0, notify=changed)
    nextEnabled = Property(bool, lambda self: self.ready, notify=changed)
    quitEnabled = Property(bool, lambda self: True, notify=changed)
    quitVisible = Property(bool, lambda self: True, notify=changed)
    backAndNextVisible = Property(bool, lambda self: True, notify=changed)

    @Slot()
    def next(self):
        self.calls += 1
        self.step += 1
        self.changed.emit()

    @Slot()
    def back(self):
        self.step -= 1
        self.changed.emit()

    @Slot()
    def quit(self):
        pass


class Storage(QObject):
    changed = Signal()

    @Slot(str, result="QVariant")
    def value(self, key):
        return {"seanInstallPhase": 2, "seanProfileReport": ""}.get(key)


class Config(QObject):
    changed = Signal()
    choice = "off"

    @Slot(str)
    def set_selection(self, value):
        self.choice = value
        self.changed.emit()

    packageChoice = Property(str, lambda self: self.choice, set_selection, notify=changed)

    @Slot(bool)
    def doRestart(self, value):
        pass


app = QApplication([])
if os.name == "nt":
    QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\segoeui.ttf")
    app.setFont(QFont("Segoe UI", 10))
manager, storage, config = Manager(), Storage(), Config()
qmlRegisterSingletonInstance(Manager, "io.calamares.ui", 1, 0, "ViewManager", manager)
qmlRegisterSingletonInstance(Storage, "io.calamares.core", 1, 0, "Global", storage)
messages = []
qInstallMessageHandler(lambda kind, context, message: messages.append(message))
relative = Path("config/includes.chroot/opt/aphrodite-os-installer-build/etc/calamares/branding/aphrodite-os")
source = BASE / relative
svg = BASE / "config/includes.chroot/opt/aphrodite-os-installer-build/usr/share/icons/hicolor/scalable/apps/aphrodite-os-installer.svg"
with tempfile.TemporaryDirectory() as directory:
    directory = Path(directory)
    for path in source.iterdir():
        if path.suffix in (".qml", ".js"):
            text = path.read_text(encoding="utf-8").replace(
                "file:///usr/share/icons/hicolor/scalable/apps/aphrodite-os-installer.svg", QUrl.fromLocalFile(str(svg)).toString())
            (directory / path.name).write_text(text, encoding="utf-8")
    catalog_file = BASE / "config/includes.chroot/opt/aphrodite-os-installer-build/usr/lib/calamares/modules/aphroditeprofiles/catalog.json"
    (directory / "PackageCatalog.js").write_text(
        ".pragma library\nvar catalog = " + catalog_file.read_text() +
        '\nvar metadata = {"version": 1, "created": "' +
        datetime.now(timezone.utc).isoformat() +
        '", "entries": {"firefox": {"apt": {"packages": {}}}}}\n',
        encoding="utf-8",
    )
    widgets = []
    engine = QQmlEngine()
    for name in ("calamares-navigation.qml", "calamares-sidebar.qml", "installing.qml",
                 "finishedq.qml", "packagechooserq@aphroditeclock.qml", "packagechooserq@aphroditepackages.qml"):
        view = QQuickWidget(engine, None)
        widgets.append(view)
        view.rootContext().setContextProperty("config", config)
        view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        view.resize(190 if "sidebar" in name else 800, 620 if "navigation" not in name else 64)
        view.setSource(QUrl.fromLocalFile(str(directory / name)))
        view.show()
        QTest.qWait(50)
        print(name, "loaded:", view.status() == QQuickWidget.Ready)
        assert view.status() == QQuickWidget.Ready, [e.toString() for e in view.errors()]
        if "navigation" in name:
            button = view.rootObject().findChild(QObject, "nextButton")
            assert button is not None
            assert button.property("text") == "Next"
            assert not button.property("enabled")
            manager.ready = True
            manager.changed.emit()
            QTest.qWait(20)
            assert button.property("enabled")
            point = button.mapToItem(view.rootObject(), button.width() / 2, button.height() / 2)
            QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, QPoint(int(point.x()), int(point.y())))
            assert manager.calls == 1, manager.calls
            print("  Next label, readiness binding and click: passed")
        if name == "packagechooserq@aphroditepackages.qml":
            page = view.rootObject()
            page.preset("Recommended")
            assert json.loads(config.choice)["apps"] == {
                "firefox": "apt", "keepassxc": "apt", "pdfarranger": "apt",
            }
            page.bulk("utility", True)
            assert "extension-manager" not in json.loads(config.choice)["apps"]
            assert "timeshift" not in json.loads(config.choice)["apps"]
            page.bulk("utility", False)
            assert "keepassxc" not in json.loads(config.choice)["apps"]
            page.chooseSession("desktop")
            assert json.loads(config.choice)["session"] == "desktop"
            page.chooseSession("gaming")
            assert json.loads(config.choice)["session"] == "gaming"
            page.chooseSession("off")
            assert "steam" not in json.loads(config.choice)["apps"]
            page.preset("Minimal")
            QTest.qWait(100)
            assert "known download" in page.property("estimate")
            assert json.loads(config.choice)["apps"] == {"firefox": "apt"}
            print("  Presets, bulk eligibility, session transitions and async estimate: passed")
        for width, height in ((view.width(), 480), (view.width(), 900),
                              (view.width() if "sidebar" in name else 1200, 900)):
            view.resize(width, height)
            QTest.qWait(20)
            assert abs(view.rootObject().width() - width) < 1
            assert abs(view.rootObject().height() - height) < 1
        if name == "calamares-sidebar.qml":
            assert view.rootObject().property("current") == 0
            print("  Narrow sidebar and resize geometry: passed")
    # Destroy while the test-double singleton instances still exist.
    for view in widgets:
        view.close()
        view.deleteLater()
    app.processEvents()
errors = [message for message in messages if any(term in message for term in
          ("ReferenceError", "TypeError", "Error:", "Binding loop", "Unable to assign", "not a type"))]
print("QML errors:", len(errors))
for message in errors:
    print(message)
assert not errors, errors
print("QML interaction and resize smoke checks passed (Qt", __import__("PySide6").__version__, ")")
