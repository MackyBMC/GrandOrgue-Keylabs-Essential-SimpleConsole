"""Remembers every window position and size across restarts.

Split out of qt_gui.py without behaviour change.

CHANGELOG
2026-11-28  Changelog labels of the module split now use the v2.0.9 patch numbers (comments only, no code change).
2026-11-27  Moved verbatim from qt_gui.py (modularisation, v2.0.9-65).
"""

import json
import os
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QMainWindow,
    QWidget,
)
from PySide6.QtCore import (
    QEvent,
    QObject,
    QRect,
    QTimer,
)


class WindowMemory(QObject):
    """Remembers position, size and maximised state of the console, the sheet music window and every popup dialog,
    in window_layout.json next to config.yaml, and puts each back the next time it is shown. Message boxes and
    file pickers are left alone (they centre on their parent)."""

    FILE = "window_layout.json"
    SKIP = {"QMessageBox", "QFileDialog", "QColorDialog", "QInputDialog", "QFontDialog", "QProgressDialog"}

    def __init__(self, folder):
        super().__init__()
        self._path = os.path.join(folder, self.FILE)
        self._data = {}
        self._restored = set()
        self._waiting = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.flush)
        try:
            with open(self._path, encoding="utf-8") as stream:
                loaded = json.load(stream)
            if isinstance(loaded, dict):
                self._data = loaded
        except (OSError, ValueError):
            pass

    def value(self, name):
        return self._data.get(name)

    def store(self, name, value):
        self._data[name] = value
        self._timer.start(500)

    @staticmethod
    def key(widget):
        name = type(widget).__name__
        if isinstance(widget, QDialog):                 # dialogs differ by title ("Channels - take.mid" and "Channels - other.mid" share one place)
            title = widget.windowTitle().split(" - ")[0].strip()
            return f"{name}:{title}" if title else name
        return name

    def saved_rect(self, key):
        entry = self._data.get(key)
        if not isinstance(entry, dict):
            return None
        try:
            return self._fit(QRect(int(entry["x"]), int(entry["y"]), int(entry["w"]), int(entry["h"])))
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _fit(rect):
        """Keep a remembered window on a screen that still exists (monitor unplugged, resolution changed)."""
        for screen in QApplication.screens():
            area = screen.availableGeometry()
            overlap = area.intersected(rect)
            if overlap.width() >= 120 and overlap.height() >= 60:
                w, h = min(rect.width(), area.width()), min(rect.height(), area.height())
                x = max(area.left(), min(rect.x(), area.right() - w + 1))
                y = max(area.top(), min(rect.y(), area.bottom() - h + 1))
                return QRect(x, y, w, h)
        return None

    def _tracked(self, obj):
        if not isinstance(obj, QWidget) or not obj.isWindow() or not isinstance(obj, (QMainWindow, QDialog)):
            return False
        return not any(cls.__name__ in self.SKIP for cls in type(obj).__mro__)

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind not in (QEvent.Type.Show, QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.Hide, QEvent.Type.Close):
            return False
        if not self._tracked(obj):
            return False
        key = self.key(obj)
        if kind == QEvent.Type.Show:
            if (id(obj) not in self._restored and not hasattr(obj, "_target_geometry")
                    and not obj.isFullScreen() and not obj.isMaximized()):
                self._restored.add(id(obj))
                rect = self.saved_rect(key)
                if rect is not None:
                    obj.setGeometry(rect)
                    if self._data[key].get("max"):
                        obj.showMaximized()
            self._restored.add(id(obj))
        elif kind in (QEvent.Type.Hide, QEvent.Type.Close):
            self._capture(obj)
            self.flush()
        elif obj.isVisible():
            self._waiting[key] = obj                       # moving / resizing: save shortly after it stops
            self._timer.start(500)
        return False

    def _capture(self, obj):
        if obj.isMinimized() or obj.isFullScreen() or getattr(obj, "_animation", None) is not None:
            return
        geometry = obj.normalGeometry() if obj.isMaximized() else obj.geometry()
        good = getattr(obj, "_last_good", None)         # windows that shrink away when closing: keep their last real size
        if good is not None and not obj.isMaximized():
            geometry = good
        if hasattr(obj, "_target_geometry"):
            obj._target_geometry = QRect(geometry)          # next open animates to where the user left it
        self._data[self.key(obj)] = {"x": geometry.x(), "y": geometry.y(), "w": geometry.width(),
                                     "h": geometry.height(), "max": obj.isMaximized()}

    def flush(self):
        for obj in list(self._waiting.values()):
            try:
                if obj.isVisible():
                    self._capture(obj)
            except RuntimeError:                           # widget already deleted
                pass
        self._waiting.clear()
        try:
            temporary = self._path + ".tmp"
            with open(temporary, "w", encoding="utf-8") as stream:
                json.dump(self._data, stream, indent=1)
            os.replace(temporary, self._path)
        except OSError:
            pass


_current: "WindowMemory | None" = None   # set by qt_gui.run_qt_ui through install()


def install(memory: "WindowMemory | None") -> None:
    """Register the application-wide WindowMemory (qt_gui keeps its own WINDOW_MEMORY alias)."""
    global _current
    _current = memory


def current() -> "WindowMemory | None":
    return _current
