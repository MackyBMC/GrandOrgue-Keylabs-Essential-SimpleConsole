"""Small reusable widgets: active-setter tick delegate, mini roll, star rating, organ picture label.

Split out of qt_gui.py without behaviour change.

CHANGELOG
2026-11-28  Changelog labels of the module split now use the v2.0.9 patch numbers (comments only, no code change).
2026-11-27  ActiveTickDelegate.paint clears HasCheckIndicator through the flag's integer value (same result; no Flag operator typing for pyright).
2026-11-27  Moved verbatim from qt_gui.py (modularisation, v2.0.9-65).
"""

from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QSizePolicy,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QWidget,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtCore import (
    QPointF,
    QRect,
    Qt,
    Signal,
)


class ActiveTickDelegate(QStyledItemDelegate):
    """Paints the Active column itself, so the tick looks the same on every row whatever the stylesheet or the
    selection colour does: active = solid amber box with a tick, inactive = empty box. Highlight never inverts it."""

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        features = QStyleOptionViewItem.ViewItemFeature
        opt.features = features(opt.features.value & ~features.HasCheckIndicator.value)
        opt.text = ""
        widget = opt.widget
        (widget.style() if widget else QApplication.style()).drawControl(
            QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)          # row background / selection only
        value = index.data(Qt.ItemDataRole.CheckStateRole)
        active = int(getattr(value, "value", value) or 0) == 2
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        size = 16
        box = QRect(option.rect.left() + 4, option.rect.center().y() - size // 2, size, size)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#202327"), 1.5))
        painter.setBrush(QColor("#f2a33a") if active else (QColor("#ffffff") if selected else QColor(0, 0, 0, 0)))
        painter.drawRoundedRect(box, 3, 3)
        if active:
            painter.setPen(QPen(QColor("#202327"), 2.2))
            painter.drawLine(box.left() + 3, box.center().y() + 1, box.left() + 6, box.bottom() - 4)
            painter.drawLine(box.left() + 6, box.bottom() - 4, box.right() - 3, box.top() + 4)
        painter.restore()


class _MiniRoll(QWidget):
    """Tiny piano roll: notes of one MIDI channel, time across, pitch up."""

    def __init__(self, notes, lo, hi, parent=None):
        super().__init__(parent)
        self.notes, self.lo, self.hi = notes, lo, hi
        self.setMinimumSize(260, 48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), self.palette().base())
        span = max(1, self.hi - self.lo)
        h, w = self.height() - 4, self.width() - 4
        p.setPen(QPen(self.palette().highlight().color(), 2))
        for frac, note in self.notes:
            x = 2 + int(frac * (w - 1))
            y = 2 + int((1 - (note - self.lo) / span) * (h - 1))
            p.drawPoint(x, y)
        p.end()


class StarRating(QWidget):
    """Five painted stars in the theme's accent colour; click star n for n stars, click the current rating again to clear."""
    valueChanged = Signal(int)
    _SIZE = 26

    def __init__(self):
        super().__init__()
        self._value = 0
        self.setFixedSize(self._SIZE * 5 + 4, self._SIZE + 2)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def value(self):
        return self._value

    def setValue(self, value, emit=False):
        value = max(0, min(5, int(value)))
        if value != self._value:
            self._value = value
            self.update()
        if emit:
            self.valueChanged.emit(value)

    def mousePressEvent(self, event):
        number = max(1, min(5, int(event.position().x() // self._SIZE) + 1))
        self.setValue(0 if number == self._value else number, True)
        self.setFocus()

    def paintEvent(self, event):
        import math
        import themes
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF
        accent = QColor(themes.tokens().get("accent", "#0b6f5c"))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        half = self._SIZE / 2
        for n in range(5):
            centre = QPointF(n * self._SIZE + half + 2, half + 1)
            points = QPolygonF()
            for k in range(10):
                radius = half - 2 if k % 2 == 0 else (half - 2) * 0.42
                angle = -math.pi / 2 + k * math.pi / 5
                points.append(QPointF(centre.x() + radius * math.cos(angle), centre.y() + radius * math.sin(angle)))
            painter.setPen(QPen(accent, 1.4))
            painter.setBrush(QBrush(accent) if n < self._value else Qt.BrushStyle.NoBrush)
            painter.drawPolygon(points)
        painter.end()

    def hasFocus(self):
        return super().hasFocus()


class OrganImageLabel(QLabel):
    """The organ's picture, scaled to the frame with its aspect kept."""

    def __init__(self):
        super().__init__("No picture of this organ found")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(160, 120)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self._pixmap = QPixmap()
        self._path = ""

    def set_image(self, path):
        if path == self._path:
            return
        self._path = path
        self._pixmap = QPixmap(path) if path else QPixmap()
        self._rescale()

    def _rescale(self):
        if self._pixmap.isNull():
            self.setPixmap(QPixmap())
            self.setText("No picture of this organ found")
        else:
            self.setPixmap(self._pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._pixmap.isNull():
            self._rescale()
