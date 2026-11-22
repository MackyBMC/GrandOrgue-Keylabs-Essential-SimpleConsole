"""One way to put a panel into a window as a dock that can be dragged, floated, resized and closed (View menu entry brings it back).
The window's dock layout is remembered per key. Use this for every new panel in a QMainWindow.

Look: a slim title bar (small text, float and close buttons, double-click floats / docks) in the theme's colours, and a floating dock can be made
translucent from its right-click menu (remembered per dock), like the floating LCD.

CHANGELOG
2026-11-23  Grip sits 3 px further in from the corner.
2026-11-23  The corner grip is our own widget placed in the real bottom-right corner (QSizeGrip placed itself wrongly inside the dock).
2026-11-23  DockFrame: the floating LCD's layered frame (grey, accent line, darker panel, small margin) and a corner grip while floating.
2026-11-23  Slim title bar with float / close buttons and an opacity menu for the floating dock.
2026-11-22  New.
"""
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QDockWidget, QHBoxLayout, QLabel, QMainWindow, QMenu, QToolButton, QVBoxLayout,
                               QWidget)

OPACITIES = (100, 90, 80, 70, 55, 40)


class Grip(QWidget):
    """The dotted corner that resizes a floating dock (drawn and placed by us, so it always sits in the real bottom-right corner)."""
    SIZE = 14

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self._start: tuple[QPointF, QSize] | None = None

    def paintEvent(self, event) -> None:
        try:
            import themes
            colour = QColor(themes.tokens()["accent"])
        except Exception:
            colour = QColor("#3daee9")
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour)
        for row in range(3):
            for column in range(3 - row):
                painter.drawEllipse(QPointF(self.SIZE - 3 - column * 4, self.SIZE - 3 - row * 4), 1.0, 1.0)
        painter.end()

    def mousePressEvent(self, event) -> None:
        self._start = (event.globalPosition(), self.window().size())

    def mouseMoveEvent(self, event) -> None:
        if self._start is not None:
            delta = event.globalPosition() - self._start[0]
            size = self._start[1]
            self.window().resize(max(160, size.width() + int(delta.x())), max(80, size.height() + int(delta.y())))

    def mouseReleaseEvent(self, event) -> None:
        self._start = None


class DockFrame(QWidget):
    """The floating LCD's frame around a dock's content: window grey, a thin accent line, a darker panel, a small margin, and (floating)
    the dotted corner grip that shows it can be resized."""

    def __init__(self, inner: QWidget, dock: QDockWidget):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 5, 6, 6)
        layout.setSpacing(0)
        layout.addWidget(inner)
        self.grip = Grip(self)
        self.grip.setVisible(dock.isFloating())
        dock.topLevelChanged.connect(self.grip.setVisible)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.grip.move(self.width() - Grip.SIZE - 4, self.height() - Grip.SIZE - 4)
        self.grip.raise_()

    def paintEvent(self, event) -> None:
        try:
            import themes
            tokens = themes.tokens()
            window, base, accent = QColor(tokens["window"]), QColor(tokens["base"]), QColor(tokens["accent"])
        except Exception:
            window, base, accent = QColor("#31363b"), QColor("#232629"), QColor("#3daee9")
        painter = QPainter(self)
        painter.fillRect(self.rect(), window)
        panel = QRectF(self.rect()).adjusted(2.5, 1.5, -2.5, -2.5)
        painter.setPen(QPen(accent, 1))
        painter.setBrush(base.darker(125))
        painter.drawRoundedRect(panel, 2, 2)
        painter.end()


class SlimTitle(QWidget):
    """Thin title bar for a QDockWidget: name, float, close. Right-click: opacity of the floating window."""

    def __init__(self, dock: QDockWidget):
        super().__init__(dock)
        self.dock = dock
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 1, 2, 1)
        row.setSpacing(2)
        self.label = QLabel(dock.windowTitle())
        font = self.label.font()
        font.setPointSizeF(max(7.0, font.pointSizeF() * 0.85))
        font.setBold(True)
        self.label.setFont(font)
        row.addWidget(self.label, 1)
        for text, tip, handler in (("⧉", "Float / dock", self._toggle_float), ("✕", "Close (View menu brings it back)", dock.close)):
            button = QToolButton()
            button.setText(text)
            button.setToolTip(tip)
            button.setAutoRaise(True)
            button.setFixedSize(18, 16)
            button.clicked.connect(lambda checked=False, h=handler: h())
            row.addWidget(button)
        dock.windowTitleChanged.connect(self.label.setText)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def _toggle_float(self) -> None:
        self.dock.setFloating(not self.dock.isFloating())

    def mouseDoubleClickEvent(self, event) -> None:
        self._toggle_float()

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        float_action = menu.addAction("Dock" if self.dock.isFloating() else "Float")
        opacity = menu.addMenu("Opacity (floating)")
        actions = {opacity.addAction(f"{pct} %"): pct for pct in OPACITIES}
        chosen = menu.exec(event.globalPos())
        if chosen is float_action:
            self._toggle_float()
        elif chosen in actions:
            set_opacity(self.dock, actions[chosen] / 100.0)


def _settings() -> QSettings:
    return QSettings("KeyLabGrandOrgue", "Docks")


def set_opacity(dock: QDockWidget, value: float) -> None:
    _settings().setValue("opacity/" + dock.objectName(), value)
    apply_opacity(dock)


def apply_opacity(dock: QDockWidget) -> None:
    try:
        value = float(_settings().value("opacity/" + dock.objectName(), 1.0))
    except (TypeError, ValueError):
        value = 1.0
    dock.setWindowOpacity(value if dock.isFloating() else 1.0)


def dock_in(window: QMainWindow, widget: QWidget, title: str, name: str,
            area: Qt.DockWidgetArea = Qt.DockWidgetArea.BottomDockWidgetArea, key: str = "") -> QDockWidget:
    """Dock `widget` in `window`. `name` must be unique and stable (it is how the saved layout finds the dock)."""
    dock = QDockWidget(title, window)
    dock.setObjectName(name)
    dock.setWidget(DockFrame(widget, dock))
    dock.setTitleBarWidget(SlimTitle(dock))
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
    dock.topLevelChanged.connect(lambda _floating=False: apply_opacity(dock))
    if key:
        settings = _settings()
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
    apply_opacity(dock)
    return dock
