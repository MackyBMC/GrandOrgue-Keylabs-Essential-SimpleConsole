"""GUI metrics: one schema for every tweakable measure of the look (frames, bevels, spacing, tables, fonts, shadows, performance / GPU).

The values live in `gui_metrics.yaml` next to config.yaml (plain YAML, safe to edit by hand; the Appearance dialog > Studio tab edits the
same file live). A missing file or key means the default, and the defaults reproduce the look the program had before this module existed:
a rule is only added to the style sheet for a value that differs from its default.

CHANGELOG
2026-11-25  New. Replaces the seven loose "gui_layout" keys of config.yaml (still read once as defaults, see load_legacy).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QFont

FILE_NAME = "gui_metrics.yaml"


@dataclass(frozen=True)
class Metric:
    key: str
    group: str
    label: str
    kind: str                         # "int", "float", "bool", "choice", "font"
    default: Any
    lo: float = 0
    hi: float = 0
    choices: tuple[str, ...] = ()
    unit: str = ""
    tip: str = ""
    restart: str = ""                 # non-empty: when the change shows (e.g. "restart")


G_FRAME, G_SPACE, G_TABLE, G_FONT, G_SHADOW, G_PERF, G_LIVE = (
    "Frames & bevel", "Spacing", "Tables & columns", "Fonts", "Shadows", "Performance & GPU", "Live console")
GROUPS = (G_FRAME, G_SPACE, G_TABLE, G_FONT, G_SHADOW, G_PERF, G_LIVE)
STYLES = ("flat", "raised", "sunken", "groove", "ridge")
QSS_STYLE = {"flat": "solid", "raised": "outset", "sunken": "inset", "groove": "groove", "ridge": "ridge"}
PRESET_NAMES = ("Auto", "Low power", "Balanced", "High quality", "Custom")

SCHEMA: tuple[Metric, ...] = (
    Metric("frame_thickness", G_FRAME, "Frame thickness", "int", 1, 0, 8, unit="px",
           tip="Border width of group boxes, docks, tool bars, tab panes, buttons and input fields. Raised / sunken / groove look best at 2 px or more."),
    Metric("frame_style", G_FRAME, "Panel bevel", "choice", "flat", choices=STYLES,
           tip="Group boxes, docks, tool bars and tab panes: flat line, raised, sunken, groove (engraved) or ridge."),
    Metric("button_style", G_FRAME, "Button bevel", "choice", "flat", choices=("flat", "raised", "sunken")),
    Metric("input_style", G_FRAME, "Input field bevel", "choice", "flat", choices=("flat", "sunken", "raised", "groove"),
           tip="Text boxes, spin boxes, drop-downs and lists. Sunken is the classic look."),
    Metric("frame_contrast", G_FRAME, "Edge contrast", "int", 0, 0, 100, unit="%",
           tip="Moves the frame colour towards the text colour: a stronger bevel edge."),
    Metric("control_spacing", G_SPACE, "Tool bar spacing", "int", 3, 0, 32, unit="px"),
    Metric("control_padding", G_SPACE, "Control padding (vertical)", "int", 3, 1, 16, unit="px",
           tip="Space inside buttons and tool bars, above and below the text."),
    Metric("control_padding_h", G_SPACE, "Button padding (sides)", "int", 0, 0, 24, unit="px", tip="0 = automatic."),
    Metric("group_padding", G_SPACE, "Group box padding", "int", 0, 0, 20, unit="px", tip="0 = from the density setting."),
    Metric("outer_margin", G_SPACE, "Outer window margin", "int", 0, 0, 24, unit="px", tip="Space between the window edge and its content."),
    Metric("tab_padding_h", G_SPACE, "Tab padding (sides)", "int", 0, 0, 30, unit="px", tip="0 = automatic."),
    Metric("tab_gap", G_SPACE, "Gap between tabs", "int", 2, 0, 12, unit="px"),
    Metric("splitter_width", G_SPACE, "Dock separator width", "int", 3, 1, 12, unit="px"),
    Metric("scrollbar_width", G_SPACE, "Scroll bar width", "int", 12, 6, 28, unit="px"),
    Metric("row_height", G_TABLE, "Row height", "int", 0, 0, 48, unit="px", tip="Lists, trees and tables. 0 = automatic."),
    Metric("header_padding", G_TABLE, "Column header padding", "int", 0, 0, 16, unit="px", tip="0 = automatic."),
    Metric("column_offset", G_TABLE, "Cell text offset", "int", 0, 0, 24, unit="px", tip="Indent of the text inside list / table cells and headers."),
    Metric("alternate_rows", G_TABLE, "Alternating row colours", "bool", False, tip="Every other row of every list and table is tinted."),
    Metric("alternate_tint", G_TABLE, "Row tint strength", "int", 6, 1, 30, unit="%"),
    Metric("grid_lines", G_TABLE, "Grid lines in tables", "bool", False),
    Metric("ui_font_family", G_FONT, "Interface font", "font", ""),
    Metric("ui_font_pt", G_FONT, "Interface font size", "float", 0.0, 0, 24, unit="pt", tip="0 = the system size. 'Text size %' on the Theme tab scales it."),
    Metric("list_font_family", G_FONT, "List / table font", "font", ""),
    Metric("lcd_font_family", G_FONT, "LCD readout font", "font", ""),
    Metric("title_weight", G_FONT, "Title weight", "int", 600, 400, 900),
    Metric("font_hinting", G_FONT, "Font hinting", "choice", "default", choices=("default", "none", "vertical", "full")),
    Metric("font_smoothing", G_FONT, "Font smoothing", "choice", "default", choices=("default", "off", "on")),
    Metric("shadow_enabled", G_SHADOW, "Panel shadows", "bool", False,
           tip="A soft shadow inside the dock frame (docked and floating). Drawn by the frame itself: no cost for the content."),
    Metric("shadow_blur", G_SHADOW, "Shadow size", "int", 14, 0, 40, unit="px"),
    Metric("shadow_dx", G_SHADOW, "Shadow offset right", "int", 0, -12, 12, unit="px"),
    Metric("shadow_dy", G_SHADOW, "Shadow offset down", "int", 3, -12, 12, unit="px"),
    Metric("shadow_opacity", G_SHADOW, "Shadow strength", "int", 45, 0, 100, unit="%"),
    Metric("perf_preset", G_PERF, "Performance profile", "choice", "Auto", choices=PRESET_NAMES,
           tip="Auto picks Low power / Balanced / High quality from this computer's CPU, memory and graphics. Editing a switch below makes it Custom."),
    Metric("gl_backend", G_PERF, "Graphics backend", "choice", "Qt default",
           choices=("Qt default", "Desktop OpenGL", "OpenGL ES (ANGLE)", "Software"), restart="restart",
           tip="Chosen before the window opens. Use Software when the screen flickers or stays black with a graphics driver problem."),
    Metric("roll_gpu", G_PERF, "GPU-drawn piano roll", "bool", False, restart="reopen the roll",
           tip="The piano roll is drawn by OpenGL instead of the CPU: smoother scrolling and zoom on a real graphics card."),
    Metric("roll_antialias", G_PERF, "Smooth edges in the roll", "bool", True),
    Metric("roll_smooth", G_PERF, "Smooth scaling of pictures", "bool", True),
    Metric("ui_animations", G_PERF, "Menu / tooltip animations", "bool", True),
    Metric("live_ratio_1", G_LIVE, "Live console: column 1", "int", 4, 1, 10, tip="Registrations. The three numbers are the proportions of the first run (or a double-click on a column wall)."),
    Metric("live_ratio_2", G_LIVE, "Live console: column 2", "int", 3, 1, 10, tip="Active stops."),
    Metric("live_ratio_3", G_LIVE, "Live console: column 3", "int", 3, 1, 10, tip="Pads and volumes."),
    Metric("column_gap", G_LIVE, "Live console: column gap", "int", 7, 0, 32, unit="px"),
    Metric("side_column_width", G_LIVE, "Sheet music: file list width", "int", 320, 220, 1200, unit="px"),
)
BY_KEY = {m.key: m for m in SCHEMA}

PERF_KEYS = ("roll_gpu", "roll_antialias", "roll_smooth", "ui_animations", "shadow_enabled")
PERF_PRESETS: dict[str, dict[str, Any]] = {
    "Low power": dict(roll_gpu=False, roll_antialias=False, roll_smooth=False, ui_animations=False, shadow_enabled=False),
    "Balanced": dict(roll_gpu=False, roll_antialias=True, roll_smooth=True, ui_animations=True, shadow_enabled=False),
    "High quality": dict(roll_gpu=True, roll_antialias=True, roll_smooth=True, ui_animations=True, shadow_enabled=True),
}

LOOKS: dict[str, dict[str, Any]] = {
    "Flat (default)": {},
    "Raised (classic)": dict(frame_thickness=2, frame_style="raised", button_style="raised", input_style="sunken", frame_contrast=30),
    "Engraved": dict(frame_thickness=2, frame_style="groove", button_style="raised", input_style="sunken", frame_contrast=20),
    "Compact LCD": dict(control_padding=2, control_spacing=2, group_padding=3, row_height=18, header_padding=2, tab_padding_h=8,
                        scrollbar_width=9, splitter_width=2),
    "Spacious (touch)": dict(control_padding=7, control_spacing=10, group_padding=12, row_height=32, header_padding=6,
                             tab_padding_h=18, scrollbar_width=20, splitter_width=6),
}
LOOK_GROUPS = (G_FRAME, G_SPACE, G_TABLE)

_values: dict[str, Any] = {}
_path = ""
_filter: "_ViewFilter | None" = None


# ---------------------------------------------------------------- values and the file
def defaults() -> dict[str, Any]:
    return {m.key: m.default for m in SCHEMA}


def _clean(metric: Metric, value: Any) -> Any:
    """A value coerced to the metric's type and range (a wrong entry in the file falls back to the default)."""
    try:
        if metric.kind == "bool":
            return value if isinstance(value, bool) else str(value).strip().lower() in ("1", "true", "yes", "on")
        if metric.kind == "int":
            return int(max(metric.lo, min(metric.hi, int(round(float(value))))))
        if metric.kind == "float":
            return float(max(metric.lo, min(metric.hi, float(value))))
        if metric.kind == "choice":
            text = str(value)
            return text if text in metric.choices else metric.default
        return str(value or "")
    except (TypeError, ValueError):
        return metric.default


def values() -> dict[str, Any]:
    if not _values:
        _values.update(defaults())
    return _values


def get(key: str) -> Any:
    """The effective value. Performance switches follow the profile unless it is Custom."""
    vals = values()
    if key in PERF_KEYS:
        preset = effective_profile()
        if preset != "Custom":
            return PERF_PRESETS[preset][key]
    return vals.get(key, BY_KEY[key].default)


def effective_profile() -> str:
    preset = str(values().get("perf_preset", "Auto"))
    if preset == "Auto":
        return recommend(hardware())
    return preset if preset in PERF_PRESETS else "Custom"


def set_value(key: str, value: Any) -> None:
    metric = BY_KEY.get(key)
    if metric is None:
        return
    if key in PERF_KEYS and str(values().get("perf_preset")) != "Custom":
        for name in PERF_KEYS:                                # editing one switch turns the profile into Custom, keeping the others
            values()[name] = get(name)
        values()["perf_preset"] = "Custom"
    values()[key] = _clean(metric, value)


def set_profile(name: str) -> None:
    values()["perf_preset"] = name if name in PRESET_NAMES else "Auto"


def apply_look(name: str) -> None:
    """Reset the frame / spacing / table metrics, then set the ones the look defines."""
    vals = values()
    for metric in SCHEMA:
        if metric.group in LOOK_GROUPS:
            vals[metric.key] = metric.default
    for key, value in LOOKS.get(name, {}).items():
        vals[key] = _clean(BY_KEY[key], value)


def reset_all() -> None:
    values().clear()
    values().update(defaults())


def modified(key: str) -> bool:
    return values().get(key) != BY_KEY[key].default


def set_path(path: str) -> None:
    """The metrics file (normally next to config.yaml); loads it when it exists."""
    global _path
    _path = path
    load()


def path() -> str:
    return _path


def load(file: str = "") -> bool:
    target = file or _path
    if not target or not os.path.isfile(target):
        return False
    try:
        import yaml
        with open(target, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception:
        return False
    flat: dict[str, Any] = {}
    for key, value in data.items() if isinstance(data, dict) else ():
        if isinstance(value, dict):
            flat.update(value)
        else:
            flat[key] = value
    vals = values()
    for key, value in flat.items():
        if key in BY_KEY:
            vals[key] = _clean(BY_KEY[key], value)
    return True


def load_legacy(raw: Any) -> None:
    """config.yaml 'gui_layout' keys of the first layout patch: used as defaults for the keys they still mean."""
    section = raw.get("gui_layout") if isinstance(raw, dict) else None
    if not isinstance(section, dict) or (_path and os.path.isfile(_path)):
        return
    vals = values()
    for key in ("frame_thickness", "control_spacing", "control_padding", "side_column_width"):
        if key in section:
            vals[key] = _clean(BY_KEY[key], section[key])
    ratio = section.get("live_split_ratio")
    if isinstance(ratio, (list, tuple)) and len(ratio) == 3:
        for index, value in enumerate(ratio):
            vals[f"live_ratio_{index + 1}"] = _clean(BY_KEY[f"live_ratio_{index + 1}"], value)


def _yaml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    return json.dumps(str(value), ensure_ascii=False)


def to_text() -> str:
    lines = ["# GrandOrgue KeyLab console: GUI metrics. Edit here or live in Appearance > Studio (Studio saves this file).",
             "# A missing key means its default. Delete the file to go back to the stock look.", ""]
    for group in GROUPS:
        lines.append(group.lower().replace(" & ", "_").replace(" ", "_") + ":")
        for metric in (m for m in SCHEMA if m.group == group):
            rng = f"{metric.lo:g}..{metric.hi:g}" if metric.kind in ("int", "float") else ("/".join(metric.choices) if metric.choices else "")
            note = f"{metric.label}" + (f" ({rng}{(' ' + metric.unit) if metric.unit else ''})" if rng else "")
            lines.append(f"  {metric.key}: {_yaml_value(values().get(metric.key, metric.default))}   # {note}")
        lines.append("")
    return "\n".join(lines)


def save(file: str = "") -> bool:
    target = file or _path
    if not target:
        return False
    try:
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(to_text())
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- hardware and the performance profile
def hardware() -> dict[str, Any]:
    """CPU cores, memory and graphics adapter names of this computer (best effort; empty / 0 when unknown)."""
    info: dict[str, Any] = {"cores": os.cpu_count() or 1, "ram_gb": 0.0, "gpus": [], "gl": ""}
    cached = getattr(hardware, "_cache", None)
    if cached is not None:
        return cached
    try:
        if os.name == "nt":
            import ctypes

            class MemStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                            ("avail", ctypes.c_ulonglong), ("ptotal", ctypes.c_ulonglong), ("pavail", ctypes.c_ulonglong),
                            ("vtotal", ctypes.c_ulonglong), ("vavail", ctypes.c_ulonglong), ("ext", ctypes.c_ulonglong)]

            class Display(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_ulong), ("name", ctypes.c_wchar * 32), ("string", ctypes.c_wchar * 128),
                            ("flags", ctypes.c_ulong), ("id", ctypes.c_wchar * 128), ("key", ctypes.c_wchar * 128)]
            status = MemStatus()
            status.length = ctypes.sizeof(MemStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))     # type: ignore[attr-defined]
            info["ram_gb"] = round(status.total / 2 ** 30, 1)
            index = 0
            while index < 8:
                device = Display()
                device.cb = ctypes.sizeof(Display)
                if not ctypes.windll.user32.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):    # type: ignore[attr-defined]
                    break
                if device.string and device.string not in info["gpus"]:
                    info["gpus"].append(device.string)
                index += 1
        else:
            info["ram_gb"] = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30, 1)
    except Exception:
        pass
    info["gl"] = _gl_renderer()
    if info["gl"] and info["gl"] not in info["gpus"]:
        info["gpus"].append(info["gl"])
    setattr(hardware, "_cache", info)
    return info


def _gl_renderer() -> str:
    """The OpenGL renderer string Qt would use (needs a QGuiApplication)."""
    try:
        from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext
        if QGuiApplication.instance() is None:
            return ""
        context = QOpenGLContext()
        if not context.create():
            return ""
        surface = QOffscreenSurface()
        surface.setFormat(context.format())
        surface.create()
        if not context.makeCurrent(surface):
            return ""
        raw = context.functions().glGetString(0x1F01)                     # GL_RENDERER
        context.doneCurrent()
        return raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw or "")
    except Exception:
        return ""


def gpu_class(names: list[str]) -> str:
    text = " ".join(names)
    if not text.strip() or re.search(r"Basic Render|llvmpipe|SwiftShader|Software|Remote|Citrix", text, re.I):
        return "low"
    if re.search(r"NVIDIA|GeForce|RTX|GTX|Quadro|Radeon RX|Radeon Pro|Arc [AB]\d", text, re.I):
        return "high"
    return "mid"                                                          # Intel UHD / Iris, Radeon Graphics (integrated)


def recommend(info: dict[str, Any]) -> str:
    cores, ram, gpu = int(info.get("cores", 1)), float(info.get("ram_gb", 0.0)), gpu_class(list(info.get("gpus", [])))
    if gpu == "low" or (ram and ram <= 4) or cores <= 2:
        return "Low power"
    if gpu == "high" and cores >= 6 and (ram == 0 or ram >= 8):
        return "High quality"
    return "Balanced"


# ---------------------------------------------------------------- the style sheet fragment (only what differs from the default)
def _mix(a: str, b: str, t: float) -> str:
    a, b = a.lstrip("#"), b.lstrip("#")
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def qss(tokens: dict[str, str], scale: float = 1.0) -> str:
    """Extra style sheet rules, appended after the theme's, for every metric that is not at its default."""
    g = get
    out: list[str] = []
    soft = _mix(tokens["border"], tokens["window"], 0.45)
    edge = _mix(soft, tokens["text"], g("frame_contrast") / 100.0 * 0.7) if g("frame_contrast") else ""
    frame_sel = "QGroupBox, QToolBar, QDockWidget, QTabWidget::pane"
    rule = ""
    if g("frame_style") != "flat":
        rule += f"border-style: {QSS_STYLE[g('frame_style')]};"
    if edge:
        rule += f"border-color: {edge};"
    if rule:
        out.append(f"{frame_sel} {{ {rule} }}")
    if g("button_style") != "flat":
        out.append(f"QPushButton {{ border-style: {QSS_STYLE[g('button_style')]}; }}")
    if g("input_style") != "flat":
        out.append("QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit, QTextBrowser, QTreeWidget, QListWidget, "
                   f"QTableWidget {{ border-style: {QSS_STYLE[g('input_style')]}; }}")
    if g("group_padding"):
        n = int(g("group_padding"))
        out.append(f"QGroupBox {{ padding: {n}px {n}px {max(0, n - 1)}px {n}px; }}")
    if g("control_padding_h"):
        out.append(f"QPushButton {{ padding-left: {int(g('control_padding_h'))}px; padding-right: {int(g('control_padding_h'))}px; }}")
    if g("tab_padding_h"):
        out.append(f"QTabBar::tab {{ padding-left: {int(g('tab_padding_h'))}px; padding-right: {int(g('tab_padding_h'))}px; }}")
    if g("tab_gap") != 2:
        out.append(f"QTabBar::tab {{ margin-right: {int(g('tab_gap'))}px; }}")
    if g("splitter_width") != 3:
        n = max(1, round(int(g("splitter_width")) * scale))
        out.append(f"QMainWindow::separator {{ width: {n}px; height: {n}px; }}")
    if g("scrollbar_width") != 12:
        n = int(g("scrollbar_width"))
        out.append(f"QScrollBar:vertical {{ width: {n}px; }} QScrollBar:horizontal {{ height: {n}px; }}")
    if g("row_height"):
        out.append(f"QTableWidget::item, QTreeWidget::item, QListWidget::item {{ min-height: {int(g('row_height'))}px; }}")
    if g("header_padding"):
        n = int(g("header_padding"))
        out.append(f"QHeaderView::section {{ padding-top: {n}px; padding-bottom: {n}px; }}")
    if g("column_offset"):
        n = int(g("column_offset"))
        out.append(f"QHeaderView::section {{ padding-left: {n}px; }} QTableWidget::item, QTreeWidget::item {{ padding-left: {n}px; }}")
    if g("alternate_rows"):
        out.append("QAbstractItemView { alternate-background-color: "
                   f"{_mix(tokens['base'], tokens['accent'], int(g('alternate_tint')) / 100.0)}; }}")
    if g("list_font_family"):
        out.append(f'QTableWidget, QTreeWidget, QListWidget {{ font-family: "{g("list_font_family")}"; }}')
    if g("lcd_font_family"):
        out.append(f'QLabel#lcdText {{ font-family: "{g("lcd_font_family")}"; }}')
    if g("title_weight") != 600:
        out.append(f"QLabel#windowTitle, QGroupBox::title {{ font-weight: {int(g('title_weight'))}; }}")
    return "\n".join(out)


# ---------------------------------------------------------------- applying the rest (fonts, views, effects, roll)
def styled_font(font: QFont) -> QFont:
    """The application font with the family / size / hinting / smoothing metrics (the caller scales by 'Text size %')."""
    out = QFont(font)
    if g_family := str(get("ui_font_family")):
        out.setFamily(g_family)
    if float(get("ui_font_pt")) > 0:
        out.setPointSizeF(float(get("ui_font_pt")))
    hint = {"default": QFont.HintingPreference.PreferDefaultHinting, "none": QFont.HintingPreference.PreferNoHinting,
            "vertical": QFont.HintingPreference.PreferVerticalHinting, "full": QFont.HintingPreference.PreferFullHinting}
    out.setHintingPreference(hint.get(str(get("font_hinting")), QFont.HintingPreference.PreferDefaultHinting))
    smooth = str(get("font_smoothing"))
    out.setStyleStrategy(QFont.StyleStrategy.NoAntialias if smooth == "off"
                         else QFont.StyleStrategy.PreferAntialias if smooth == "on" else QFont.StyleStrategy.PreferDefault)
    return out


class _ViewFilter(QObject):
    """Applies alternating rows / grid lines to every list, tree and table as it is polished."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Polish:
            _style_view(obj)
        return False


def _style_view(obj: QObject) -> None:
    from PySide6.QtWidgets import QAbstractItemView, QTableView
    if isinstance(obj, QAbstractItemView):
        obj.setAlternatingRowColors(bool(get("alternate_rows")))
    if isinstance(obj, QTableView):
        obj.setShowGrid(bool(get("grid_lines")))


def startup() -> None:
    """Before the QApplication exists: the graphics backend (OpenGL flavour) the window system will use."""
    try:
        from PySide6.QtCore import QCoreApplication, Qt
        attribute = {"Desktop OpenGL": Qt.ApplicationAttribute.AA_UseDesktopOpenGL,
                     "OpenGL ES (ANGLE)": Qt.ApplicationAttribute.AA_UseOpenGLES,
                     "Software": Qt.ApplicationAttribute.AA_UseSoftwareOpenGL}.get(str(values().get("gl_backend")))
        if attribute is not None:
            QCoreApplication.setAttribute(attribute)
    except Exception:
        pass


def apply_runtime(app: Any) -> None:
    """After the style sheet: view options, UI effects. Safe to call again on every change."""
    global _filter
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    if _filter is None:
        _filter = _ViewFilter()
        app.installEventFilter(_filter)
    for widget in app.allWidgets():
        _style_view(widget)
    on = bool(get("ui_animations"))
    for effect in (Qt.UIEffect.UI_AnimateMenu, Qt.UIEffect.UI_FadeMenu, Qt.UIEffect.UI_AnimateCombo,
                   Qt.UIEffect.UI_AnimateTooltip, Qt.UIEffect.UI_FadeTooltip):
        QApplication.setEffectEnabled(effect, on)


def apply_roll(view: Any) -> None:
    """Rendering options of the piano roll's graphics view: edge smoothing, picture scaling, OpenGL viewport."""
    from PySide6.QtGui import QPainter
    view.setRenderHint(QPainter.RenderHint.Antialiasing, bool(get("roll_antialias")))
    view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, bool(get("roll_smooth")))
    try:
        from PySide6.QtGui import QSurfaceFormat
        from PySide6.QtOpenGLWidgets import QOpenGLWidget
        from PySide6.QtWidgets import QWidget
        is_gl = isinstance(view.viewport(), QOpenGLWidget)
        if bool(get("roll_gpu")) and not is_gl:
            gl = QOpenGLWidget()
            fmt = QSurfaceFormat()
            fmt.setSamples(4 if get("roll_antialias") else 0)
            gl.setFormat(fmt)
            view.setViewport(gl)
        elif not get("roll_gpu") and is_gl:
            view.setViewport(QWidget())
    except Exception:
        pass
