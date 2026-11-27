"""Config editor dialog and its choice / range tables.

Split out of qt_gui.py without behaviour change.

CHANGELOG
2026-11-28  Changelog labels of the module split now use the v2.0.9 patch numbers (comments only, no code change).
2026-11-27  Moved verbatim from qt_gui.py (modularisation, v2.0.9-65).
"""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import (
    Qt,
)
from keylab_bridge.preset_store import set_config_value


CONFIG_CHOICES = {
    ("language",): ["en", "de", "fr", "es"],
    ("ui",): ["textual", "simple", "gui", "both", "none"],
    ("theme",): ["light", "dark", "contrast"],
    ("preset_activation",): ["staged", "direct"],
}


ENCODER_TARGETS = ["pedal", "hw", "sw", "sl", "swell", "noises", "master"]


CONFIG_RANGES = {("pads", "verbosity"): (1, 3), ("pads", "off_grey"): (0, 127),
                 ("testing", "note_pad_channel"): (1, 16), ("testing", "note_pad_first"): (0, 120)}


LIVE_CONFIG_SECTIONS = ("pads", "testing")       # applied at once on save; everything else needs a restart (F5)


def read_config_comments(path):
    """{key path tuple: comment text} from a commented YAML file: a trailing '# note' or the comment lines above."""
    import re
    comments, stack, pending = {}, [], []
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return comments
    for line in lines:
        stripped = line.strip()
        if not stripped:
            pending = []
            continue
        if stripped.startswith("#"):
            pending.append(stripped.lstrip("# ").strip())
            continue
        match = re.match(r"^(\s*)(['\"]?)([^:'\"]+)\2:\s*(.*)$", line)
        if not match:
            pending = []
            continue
        indent, key = len(match.group(1)), match.group(3).strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, key))
        rest, trailing = match.group(4), ""
        if " #" in rest:
            trailing = rest.split(" #", 1)[1].strip()
        text = " ".join(part for part in ([*pending] + ([trailing] if trailing else [])) if part)
        if text:
            comments[tuple(k for _, k in stack)] = text
        pending = []
    return comments


class ConfigEditor(QWidget):
    """Every option in config.yaml as an editable field. Saving rewrites only the changed values in place (the
    file's comments are kept). Pad display settings apply immediately; the rest take effect after a restart."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self._fields = {}          # key path -> (widget, original value)
        outer = QVBoxLayout(self)
        self.path_label = QLabel(bridge.cfg_path)
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(self.path_label)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        outer.addWidget(self.scroll_area, 1)
        row = QHBoxLayout()
        self.status = QLabel("")
        row.addWidget(self.status, 1)
        reload_button = QPushButton("Reload from file")
        reload_button.clicked.connect(self.load)
        save_button = QPushButton("Save changes")
        save_button.clicked.connect(self.save)
        row.addWidget(reload_button)
        row.addWidget(save_button)
        outer.addLayout(row)
        self.load()

    def _make_editor(self, path, value):
        if isinstance(value, bool):
            widget = QCheckBox()
            widget.setChecked(value)
            return widget
        choices = CONFIG_CHOICES.get(path)
        if path[:2] == ("controls", "encoders"):
            choices = ENCODER_TARGETS
        if choices:
            widget = QComboBox()
            widget.addItems([str(c) for c in choices])
            if str(value) not in [str(c) for c in choices]:
                widget.addItem(str(value))
            widget.setCurrentText(str(value))
            return widget
        if isinstance(value, int):
            widget = QSpinBox()
            low, high = CONFIG_RANGES.get(path, (-1000000, 1000000))
            widget.setRange(low, high)
            widget.setValue(value)
            return widget
        if isinstance(value, float):
            widget = QDoubleSpinBox()
            widget.setDecimals(3)
            widget.setSingleStep(0.01)
            widget.setRange(-1000000.0, 1000000.0)
            widget.setValue(value)
            return widget
        if isinstance(value, list):
            return QLineEdit(", ".join(str(v) for v in value))
        return QLineEdit("" if value is None else str(value))

    @staticmethod
    def _read_editor(widget, original):
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QComboBox):
            text = widget.currentText()
            return type(original)(text) if isinstance(original, int) and not isinstance(original, bool) else text
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            return widget.value()
        text = widget.text().strip()
        if isinstance(original, list):
            items = [part.strip() for part in text.split(",") if part.strip()]
            converted = []
            for part in items:
                try:
                    converted.append(int(part))
                except ValueError:
                    try:
                        converted.append(float(part))
                    except ValueError:
                        converted.append(part)
            return converted
        return text

    def load(self):
        import yaml
        try:
            with open(self.bridge.cfg_path, encoding="utf-8") as stream:
                data = yaml.safe_load(stream) or {}
        except (OSError, yaml.YAMLError) as exc:
            self.status.setText(f"Could not read config.yaml: {exc}")
            return
        comments = read_config_comments(self.bridge.cfg_path)
        self._fields.clear()
        page = QWidget()
        layout = QVBoxLayout(page)

        def leaves(node, prefix=()):
            for key, value in node.items():
                path = prefix + (str(key),)
                if isinstance(value, dict) and value:
                    yield from leaves(value, path)
                elif isinstance(value, dict):
                    yield path, None, True               # empty mapping: edit in the file
                else:
                    yield path, value, False

        groups = {}
        for path, value, is_empty_map in leaves(data):
            title = path[0] if len(path) > 1 else "general"
            form = groups.get(title)
            if form is None:
                box = QGroupBox(title)
                form = QFormLayout(box)
                groups[title] = form
                layout.addWidget(box)
            label = ".".join(path[1:] if len(path) > 1 else path)
            if is_empty_map:
                note = QLabel("(empty - edit in the file)")
                note.setToolTip(comments.get(path, ""))
                form.addRow(label, note)
                continue
            # config.yaml keys such as encoders use integer keys; the original types decide the editor
            original = value
            widget = self._make_editor(path, original)
            tip = comments.get(path, "")
            if tip:
                widget.setToolTip(tip)
                widget.setWhatsThis(tip)
            live = path[0] in LIVE_CONFIG_SECTIONS
            caption = label + ("" if live else "  *")
            form.addRow(caption, widget)
            if tip:
                hint = QLabel(tip)
                hint.setWordWrap(True)
                hint.setStyleSheet("color: gray; font-size: 11px;")
                form.addRow("", hint)
            self._fields[path] = (widget, original)
        layout.addStretch(1)
        self.scroll_area.setWidget(page)
        self.status.setText("* needs a restart (F5); pad settings apply immediately.")

    def save(self):
        changed = live = 0
        failed = []
        for path, (widget, original) in self._fields.items():
            value = self._read_editor(widget, original)
            if value == original:
                continue
            key_path = tuple(path)
            if set_config_value(self.bridge.cfg_path, key_path, value):
                changed += 1
                live += path[0] in LIVE_CONFIG_SECTIONS
            else:
                failed.append(".".join(path))
        if changed:
            self.bridge.post_ui_event("reload_config", True)
        self.load()
        message = f"Saved {changed} change(s)" + (f"; {live} applied now" if live else "")
        if changed - live:
            message += f"; {changed - live} need a restart (F5)"
        if failed:
            message += f". Not written (key not found in the file): {', '.join(failed)}"
        self.status.setText(message)
