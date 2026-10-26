"""Finishing touches for the Qt style sheet: slim rounded scroll bars, flat rounded buttons, soft focus rings, tidy tool
bars and docks - a calm, Breeze-like look on top of the Fusion style. Used by the console and the stave editor.

CHANGELOG
2026-10-24  New.
"""


def _mix(a, b, t):
    """Blend two #rrggbb colours (t = share of b)."""
    a, b = a.lstrip("#"), b.lstrip("#")
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def extra_css(p):
    bg, surf, text, border, accent, inp = p["background"], p["surface"], p["text"], p["border"], p["accent"], p["input"]
    soft = _mix(border, bg, 0.55)
    hover = _mix(surf, accent, 0.18)
    return f"""
        QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {_mix(border, bg, 0.2)}; border-radius: 4px; min-height: 28px; }}
        QScrollBar::handle:vertical:hover {{ background: {accent}; }}
        QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
        QScrollBar::handle:horizontal {{ background: {_mix(border, bg, 0.2)}; border-radius: 4px; min-width: 28px; }}
        QScrollBar::handle:horizontal:hover {{ background: {accent}; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        QToolTip {{ background: {surf}; color: {text}; border: 1px solid {accent}; padding: 4px 6px; border-radius: 4px; }}
        QPushButton {{ border-radius: 6px; padding: 5px 12px; }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:disabled, QToolButton:disabled {{ color: {_mix(text, bg, 0.6)}; }}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ border-radius: 6px; padding: 4px 8px; border: 1px solid {soft}; background: {inp}; color: {text}; }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {accent}; }}
        QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 16px; border: none; background: transparent; }}
        QGroupBox {{ border-radius: 8px; border: 1px solid {soft}; }}
        QToolBar {{ background: {surf}; border: 1px solid {soft}; border-radius: 8px; spacing: 3px; padding: 3px; }}
        QToolBar::handle {{ background: {soft}; width: 6px; height: 6px; margin: 4px; border-radius: 3px; }}
        QToolBar::separator {{ background: {soft}; width: 1px; height: 1px; margin: 4px; }}
        QToolButton {{ border-radius: 8px; padding: 5px; border: 1px solid transparent; }}
        QToolButton:hover {{ background: {hover}; border: 1px solid {_mix(accent, bg, 0.5)}; }}
        QToolButton:checked {{ background: {_mix(surf, accent, 0.35)}; border: 1px solid {accent}; }}
        QDockWidget {{ border: 1px solid {soft}; }}
        QDockWidget::title {{ background: {surf}; padding: 5px 8px; border-bottom: 1px solid {soft}; }}
        QMenuBar {{ background: {surf}; }}
        QMenuBar::item {{ padding: 4px 10px; border-radius: 5px; background: transparent; }}
        QMenuBar::item:selected {{ background: {hover}; }}
        QMenu {{ background: {surf}; border: 1px solid {soft}; border-radius: 6px; padding: 4px; }}
        QMenu::item {{ padding: 5px 22px; border-radius: 4px; }}
        QMenu::item:selected {{ background: {accent}; color: {bg}; }}
        QSplitter::handle {{ background: {soft}; }}
        QSplitter::handle:hover {{ background: {accent}; }}
        QStatusBar {{ background: {surf}; border-top: 1px solid {soft}; }}
        QTabBar::tab {{ padding: 6px 14px; border-top-left-radius: 6px; border-top-right-radius: 6px; background: {surf}; }}
        QTabBar::tab:selected {{ background: {_mix(surf, accent, 0.3)}; }}
        QListWidget, QTextBrowser, QTextEdit {{ border: 1px solid {soft}; border-radius: 6px; }}
    """


def full_css(p):
    """Complete style sheet for windows that run without the console (stave station): base colours + polish."""
    return f"""
        QMainWindow, QWidget {{ background: {p['background']}; color: {p['text']}; }}
        QGroupBox {{ background: {p['surface']}; margin-top: 9px; padding: 8px; }}
        QPushButton, QComboBox, QLineEdit {{ background: {p['input']}; color: {p['text']}; border: 1px solid {p['border']}; }}
        QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {p['accent']}; background: {p['input']}; border-radius: 3px; }}
        QCheckBox::indicator:checked {{ background: {p['accent']}; }}
        QLabel, QCheckBox {{ background: transparent; }}
    """ + extra_css(p)


def make_seek_slider(orientation=None):
    """A progress bar you can click or drag to move to a position; emits seek(value 0-1000) when released."""
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import QSlider, QStyle

    class SeekSlider(QSlider):
        seek = Signal(int)
        moved = Signal(int)

        def __init__(self):
            super().__init__(orientation or Qt.Orientation.Horizontal)
            self.setRange(0, 1000)
            self.dragging = False
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        def _value_at(self, x):
            return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), int(x), max(1, self.width()))

        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                self.dragging = True
                self.setValue(self._value_at(event.position().x()))
                self.moved.emit(self.value())
                event.accept()
            else:
                super().mousePressEvent(event)

        def mouseMoveEvent(self, event):
            if self.dragging:
                self.setValue(self._value_at(event.position().x()))
                self.moved.emit(self.value())
                event.accept()

        def mouseReleaseEvent(self, event):
            if self.dragging:
                self.dragging = False
                self.seek.emit(self.value())
                event.accept()

    return SeekSlider()
