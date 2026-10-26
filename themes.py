"""Global theming for the console, the stave editor and every dialog.

One design-token model (colours, accent, corner radius, density, font scale) is turned into a QPalette plus one application
wide style sheet on top of Qt's Fusion style, so every window - including pop-ups and dialogs - follows it at once.

Theme families (each has a light and a dark mode; "High contrast" is a third mode shared by all):
    Console (the original teal), Breeze (KDE), Adwaita (GNOME), Fusion (Qt), Nord, Dracula, Solarized, Catppuccin.
Your own themes: put a JSON file in a "themes" folder next to this file, e.g.
    {"name": "Harbour", "light": {"window": "#f4f6f8", "base": "#ffffff", "alt": "#e9edf1", "text": "#1c2733",
     "muted": "#5b6b7a", "border": "#c6d0da", "accent": "#0a7ea4"}, "dark": { ... same keys ... }}
Settings (family, accent override, radius, density, font size, Qt style, icons) are kept in QSettings
"KeyLabGrandOrgue / Appearance" and shared by all windows.

CHANGELOG
2026-10-25  New: replaces the per-window style sheets (polish.py still provides the seek slider).
"""
import json
import os

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtGui import QColor, QPalette

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = ("window", "base", "alt", "text", "muted", "border", "accent")

FAMILIES = {
    "Console": {
        "light": dict(window="#e9f0ed", base="#ffffff", alt="#fcfefc", text="#17312c", muted="#48615b", border="#96ada5", accent="#0b6f5c"),
        "dark": dict(window="#101820", base="#13212a", alt="#192832", text="#e6eef1", muted="#b0bec5", border="#52748a", accent="#67d4bd"),
    },
    "Breeze": {   # KDE Plasma
        "light": dict(window="#eff0f1", base="#fcfcfc", alt="#e4e6e8", text="#31363b", muted="#6f7b84", border="#bdc3c7", accent="#3daee9"),
        "dark": dict(window="#31363b", base="#232629", alt="#2a2e32", text="#eff0f1", muted="#a1a9b1", border="#4d5257", accent="#3daee9"),
    },
    "Adwaita": {   # GNOME / libadwaita
        "light": dict(window="#fafafb", base="#ffffff", alt="#f0eeec", text="#2e3436", muted="#77767b", border="#d5d0cc", accent="#3584e4"),
        "dark": dict(window="#242424", base="#1e1e1e", alt="#303030", text="#ffffff", muted="#9a9996", border="#454545", accent="#78aeed"),
    },
    "Fusion": {   # Qt's own
        "light": dict(window="#efefef", base="#ffffff", alt="#e4e4e4", text="#1b1b1b", muted="#6a6a6a", border="#bebebe", accent="#308cc6"),
        "dark": dict(window="#353535", base="#191919", alt="#2a2a2a", text="#f2f2f2", muted="#a0a0a0", border="#555555", accent="#2a82da"),
    },
    "Nord": {
        "light": dict(window="#eceff4", base="#ffffff", alt="#e5e9f0", text="#2e3440", muted="#4c566a", border="#d0d6e0", accent="#5e81ac"),
        "dark": dict(window="#2e3440", base="#3b4252", alt="#434c5e", text="#eceff4", muted="#a9b3c6", border="#4c566a", accent="#88c0d0"),
    },
    "Dracula": {
        "light": dict(window="#fbf8ec", base="#ffffff", alt="#f1ecd6", text="#1f1f1f", muted="#6c664b", border="#d7d3bf", accent="#644ac9"),
        "dark": dict(window="#282a36", base="#21222c", alt="#343746", text="#f8f8f2", muted="#a4a9c8", border="#44475a", accent="#bd93f9"),
    },
    "Solarized": {
        "light": dict(window="#fdf6e3", base="#fffdf5", alt="#eee8d5", text="#073642", muted="#657b83", border="#d3cbb6", accent="#268bd2"),
        "dark": dict(window="#002b36", base="#073642", alt="#0a4250", text="#eee8d5", muted="#93a1a1", border="#586e75", accent="#2aa198"),
    },
    "Catppuccin": {
        "light": dict(window="#eff1f5", base="#ffffff", alt="#e6e9ef", text="#4c4f69", muted="#6c6f85", border="#ccd0da", accent="#8839ef"),
        "dark": dict(window="#1e1e2e", base="#181825", alt="#313244", text="#cdd6f4", muted="#a6adc8", border="#45475a", accent="#cba6f7"),
    },
}
CONTRAST = dict(window="#ffffff", base="#ffffff", alt="#f0f0f0", text="#000000", muted="#1a1a1a", border="#000000", accent="#004c9a")
ACCENTS = {"Blue": "#3584e4", "Sky": "#3daee9", "Teal": "#14b8a6", "Green": "#30a46c", "Amber": "#e5a50a",
           "Orange": "#f97316", "Red": "#e5484d", "Pink": "#ec4899", "Purple": "#8b5cf6", "Slate": "#64748b"}
DEFAULTS = dict(family="Console", mode="dark", accent="", radius=6, density=1, font=100, style="Fusion", detailed=True)


class _Bus(QObject):
    changed = Signal()


bus = _Bus()                                   # windows connect to bus.changed to redraw their icons etc.


def _settings():
    return QSettings("KeyLabGrandOrgue", "Appearance")


def load_user_themes():
    folder = os.path.join(HERE, "themes")
    try:
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith(".json"):
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    data = json.load(handle)
                if data.get("name") and data.get("light") and data.get("dark"):
                    FAMILIES[str(data["name"])] = {"light": {**FAMILIES["Fusion"]["light"], **data["light"]},
                                                   "dark": {**FAMILIES["Fusion"]["dark"], **data["dark"]}}
    except (OSError, ValueError):
        pass


load_user_themes()


def state():
    s, out = _settings(), dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        value = s.value(key)
        if value is None or value == "":
            continue
        out[key] = (str(value).lower() in ("true", "1")) if isinstance(default, bool) else (type(default)(value) if not isinstance(default, str) else str(value))
    if out["family"] not in FAMILIES:
        out["family"] = DEFAULTS["family"]
    return out


def save(**changes):
    s = _settings()
    for key, value in changes.items():
        s.setValue(key, value)


def tokens(st=None, mode=None):
    st = st or state()
    mode = mode or st["mode"]
    if mode == "contrast":
        t = dict(CONTRAST)
    else:
        t = dict(FAMILIES[st["family"]]["dark" if mode == "dark" else "light"])
    if st["accent"] and mode != "contrast":
        t["accent"] = st["accent"]
    return t


def _mix(a, b, t):
    ca, cb = QColor(a), QColor(b)
    return QColor(round(ca.red() + (cb.red() - ca.red()) * t), round(ca.green() + (cb.green() - ca.green()) * t),
                  round(ca.blue() + (cb.blue() - ca.blue()) * t)).name()


def on_accent(t):
    return "#ffffff" if QColor(t["accent"]).lightnessF() < 0.58 else "#101010"


def palette(t):
    p = QPalette()
    roles = {QPalette.ColorRole.Window: t["window"], QPalette.ColorRole.WindowText: t["text"],
             QPalette.ColorRole.Base: t["base"], QPalette.ColorRole.AlternateBase: t["alt"],
             QPalette.ColorRole.Text: t["text"], QPalette.ColorRole.Button: t["alt"],
             QPalette.ColorRole.ButtonText: t["text"], QPalette.ColorRole.ToolTipBase: t["base"],
             QPalette.ColorRole.ToolTipText: t["text"], QPalette.ColorRole.Highlight: t["accent"],
             QPalette.ColorRole.HighlightedText: on_accent(t), QPalette.ColorRole.PlaceholderText: t["muted"],
             QPalette.ColorRole.Link: t["accent"], QPalette.ColorRole.BrightText: "#ffffff",
             QPalette.ColorRole.Mid: t["border"], QPalette.ColorRole.Dark: t["border"], QPalette.ColorRole.Light: t["base"]}
    for role, colour in roles.items():
        p.setColor(role, QColor(colour))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(_mix(t["text"], t["window"], 0.6)))
    return p


def stylesheet(st=None, mode=None):
    """The whole application style sheet from the tokens."""
    st = st or state()
    t = tokens(st, mode)
    r = int(st["radius"])
    pad = {0: 3, 1: 5, 2: 8}.get(int(st["density"]), 5)
    win, base, alt, text, muted, border, accent = (t[k] for k in KEYS)
    soft = _mix(border, win, 0.45)
    hover = _mix(alt, accent, 0.18)
    pressed = _mix(alt, accent, 0.32)
    sel_text = on_accent(t)
    tint = _mix(win, accent, 0.14)
    return f"""
        QWidget {{ color: {text}; }}
        QMainWindow, QDialog {{ background: {win}; }}
        QWidget:disabled {{ color: {_mix(text, win, 0.6)}; }}
        QLabel, QCheckBox, QRadioButton {{ background: transparent; }}
        QLabel#windowTitle {{ color: {accent}; font-size: 18px; font-weight: 600; }}
        QLabel#lcdText {{ background: {alt}; color: {text}; font-size: 17px; font-weight: 600; border-radius: {r}px; }}
        QLabel#statusLabel {{ background: {alt}; padding: 7px; color: {text}; border-radius: {r}px; }}
        QGroupBox {{ background: {alt}; border: 1px solid {soft}; border-radius: {r + 2}px; margin-top: 20px; padding: 12px 8px 8px 8px; }}
        QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 12px; top: 0px; padding: 0 5px; color: {accent}; font-weight: 600; }}
        QPushButton, QToolButton {{ background: {alt}; color: {text}; border: 1px solid {soft}; border-radius: {r}px; padding: {pad}px {pad * 2 + 2}px; }}
        QPushButton:hover, QToolButton:hover {{ background: {hover}; border-color: {_mix(accent, win, 0.35)}; }}
        QPushButton:pressed, QToolButton:pressed {{ background: {pressed}; border-color: {accent}; }}
        QPushButton:checked, QToolButton:checked {{ background: {_mix(alt, accent, 0.4)}; border: 1px solid {accent}; }}
        QPushButton:default {{ border: 1px solid {accent}; }}
        QPushButton:focus {{ border: 1px solid {accent}; }}
        QPushButton#padButton {{ font-weight: 600; }}
        QToolButton {{ padding: {max(2, pad - 1)}px; border: 1px solid transparent; background: transparent; }}
        QToolButton:hover {{ border: 1px solid {_mix(accent, win, 0.45)}; background: {hover}; }}
        QToolButton:checked {{ border: 1px solid {accent}; }}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit, QTextBrowser, QTreeWidget, QListWidget, QTableWidget {{
            background: {base}; color: {text}; border: 1px solid {soft}; border-radius: {r}px; padding: {max(2, pad - 1)}px 7px;
            selection-background-color: {accent}; selection-color: {sel_text}; }}
        QListWidget, QTreeWidget, QTableWidget, QTextEdit, QPlainTextEdit, QTextBrowser {{ padding: 2px; }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {accent}; }}
        QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{ border-color: {_mix(accent, win, 0.4)}; }}
        QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 16px; border: none; background: transparent; }}
        QComboBox QAbstractItemView {{ background: {base}; color: {text}; border: 1px solid {soft}; selection-background-color: {accent}; selection-color: {sel_text}; outline: 0; }}
        QCheckBox::indicator, QListView::indicator, QTreeView::indicator {{ width: 15px; height: 15px; border: 1px solid {_mix(border, accent, 0.4)}; background: {base}; border-radius: {max(2, r // 2)}px; }}
        QCheckBox::indicator:hover {{ border-color: {accent}; }}
        QCheckBox::indicator:checked, QListView::indicator:checked, QTreeView::indicator:checked {{ background: {accent}; border-color: {accent}; }}
        QRadioButton::indicator {{ width: 15px; height: 15px; border: 1px solid {border}; background: {base}; border-radius: 8px; }}
        QRadioButton::indicator:checked {{ background: {accent}; border-color: {accent}; }}
        QTreeView::item:selected, QListView::item:selected, QTableView::item:selected {{ background: {accent}; color: {sel_text}; }}
        QTreeView::item:hover:!selected, QListView::item:hover:!selected, QTableView::item:hover:!selected {{ background: {hover}; }}
        QHeaderView::section {{ background: {alt}; border: none; border-bottom: 1px solid {soft}; padding: 4px 8px; }}
        QSlider::groove:horizontal {{ height: 6px; background: {soft}; border-radius: 3px; }}
        QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 3px; }}
        QSlider::handle:horizontal {{ width: 14px; height: 14px; margin: -5px 0; background: {accent}; border-radius: 7px; }}
        QProgressBar {{ background: {soft}; border: none; border-radius: {r}px; text-align: center; }}
        QProgressBar::chunk {{ background: {accent}; border-radius: {r}px; }}
        QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {_mix(border, win, 0.1)}; border-radius: 4px; min-height: 28px; }}
        QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
        QScrollBar::handle:horizontal {{ background: {_mix(border, win, 0.1)}; border-radius: 4px; min-width: 28px; }}
        QScrollBar::handle:hover {{ background: {accent}; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        QScrollArea {{ background: transparent; border: none; }}
        QToolTip {{ background: {base}; color: {text}; border: 1px solid {accent}; border-radius: {max(3, r - 2)}px; padding: 4px 7px; }}
        QMenuBar {{ background: {win}; }}
        QMenuBar::item {{ padding: 5px 11px; border-radius: {max(3, r - 1)}px; background: transparent; }}
        QMenuBar::item:selected {{ background: {hover}; }}
        QMenu {{ background: {base}; border: 1px solid {soft}; border-radius: {r}px; padding: 5px; }}
        QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: {max(3, r - 2)}px; }}
        QMenu::item:selected {{ background: {accent}; color: {sel_text}; }}
        QMenu::separator {{ height: 1px; background: {soft}; margin: 4px 8px; }}
        QToolBar {{ background: {alt}; border: 1px solid {soft}; border-radius: {r + 2}px; spacing: 3px; padding: 3px; }}
        QToolBar::handle {{ background: {soft}; width: 6px; height: 6px; margin: 4px; border-radius: 3px; }}
        QToolBar::separator {{ background: {soft}; width: 1px; height: 1px; margin: 5px; }}
        QDockWidget {{ border: 1px solid {soft}; }}
        QDockWidget::title {{ background: {alt}; padding: 6px 8px; border-bottom: 1px solid {soft}; }}
        QStatusBar {{ background: {alt}; border-top: 1px solid {soft}; }}
        QSplitter::handle {{ background: {soft}; }}
        QSplitter::handle:hover {{ background: {accent}; }}
        QTabWidget::pane {{ border: 1px solid {soft}; border-radius: {r}px; top: -1px; }}
        QTabBar::tab {{ background: {alt}; padding: {pad + 1}px 14px; border: 1px solid {soft}; border-bottom: none; border-top-left-radius: {r}px; border-top-right-radius: {r}px; margin-right: 2px; }}
        QTabBar::tab:selected {{ background: {tint}; color: {accent}; border-color: {_mix(accent, win, 0.4)}; }}
        QTabBar::tab:hover:!selected {{ background: {hover}; }}
        QSvgWidget, QGraphicsView {{ border: none; }}
    """


def apply(mode=None, app=None):
    """Make the saved (or given) mode and settings the look of the whole application, right now."""
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QStyleFactory
    app = app or QApplication.instance()
    if app is None:
        return
    st = state()
    if mode in ("light", "dark", "contrast"):
        save(mode=mode)
        st["mode"] = mode
    style_name = st["style"] if st["style"] in QStyleFactory.keys() else "Fusion"
    if app.style().objectName().lower() != style_name.lower():
        app.setStyle(QStyleFactory.create(style_name))
    t = tokens(st)
    app.setPalette(palette(t))
    base_font = getattr(app, "_base_font", None) or QFont(app.font())
    app._base_font = base_font
    font = QFont(base_font)
    if base_font.pointSizeF() > 0:
        font.setPointSizeF(base_font.pointSizeF() * st["font"] / 100.0)
    app.setFont(font)
    app.setStyleSheet(stylesheet(st) if st["detailed"] else "")
    bus.changed.emit()


def mode_from_console(theme):
    return theme if theme in ("light", "dark", "contrast") else "dark"
