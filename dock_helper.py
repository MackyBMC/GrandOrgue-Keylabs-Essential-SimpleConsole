"""One way to put a panel into a window as a dock that can be dragged, floated, resized and closed (View menu entry brings it back).
The window's dock layout is remembered per key. Use this for every new panel in a QMainWindow.

CHANGELOG
2026-11-22  New.
"""
from typing import Any

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtWidgets import QDockWidget, QMainWindow, QWidget


def dock_in(window: QMainWindow, widget: QWidget, title: str, name: str,
            area: Qt.DockWidgetArea = Qt.DockWidgetArea.BottomDockWidgetArea, key: str = "") -> QDockWidget:
    """Dock `widget` in `window`. `name` must be unique and stable (it is how the saved layout finds the dock)."""
    dock = QDockWidget(title, window)
    dock.setObjectName(name)
    dock.setWidget(widget)
    dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetMovable
                     | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
    window.addDockWidget(area, dock)
    for action in window.menuBar().actions():
        menu = action.menu()
        if menu is not None and action.text().replace("&", "") == "View":
            menu.addSeparator()
            menu.addAction(dock.toggleViewAction())
            break
    if key:
        settings = QSettings("KeyLabGrandOrgue", "Docks")
        saved = settings.value(key)
        if saved:
            try:
                window.restoreState(saved)
            except Exception:
                pass
        pending: list[Any] = []

        def save() -> None:
            pending.clear()
            settings.setValue(key, window.saveState())

        def later(*_args: Any) -> None:
            if not pending:
                pending.append(1)
                QTimer.singleShot(400, save)

        dock.dockLocationChanged.connect(later)
        dock.topLevelChanged.connect(later)
        dock.visibilityChanged.connect(later)
    return dock
