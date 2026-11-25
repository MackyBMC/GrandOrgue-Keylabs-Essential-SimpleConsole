"""Appearance > Studio: every GUI metric as a slider / tick box / drop-down, applied live to the whole program, with a miniature preview
(tabs, tool bar, group box, table, docked and floating dock frame) beside the controls and the GPU / performance profile.

The values are the ones of gui_metrics.py and are saved to gui_metrics.yaml (next to config.yaml) a moment after each change.

CHANGELOG
2026-11-25  New.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDockWidget, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QScrollArea,
                               QSizePolicy, QSlider, QSpinBox, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem,
                               QTabWidget, QToolBar, QToolButton, QVBoxLayout, QWidget)

import gui_metrics as gm
import themes


class PreviewPanel(QWidget):
    """A small console that uses the real style sheet, so every change shows here at once as well as in the program itself."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from dock_helper import DockFrame, SlimTitle
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        page = QWidget()
        lay = QVBoxLayout(page)
        bar = QToolBar()
        for text in ("Play", "Stop", "Loop", "Save"):
            bar.addAction(text)
        bar.addSeparator()
        combo = QComboBox()
        combo.addItems(["Quarter note", "Eighth note"])
        bar.addWidget(combo)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedWidth(80)
        slider.setValue(40)
        bar.addWidget(slider)
        lay.addWidget(bar)
        row = QHBoxLayout()
        box = QGroupBox("Registrations")
        box_lay = QVBoxLayout(box)
        for text in ("Adventus", "Ferialis", "Tutti"):
            box_lay.addWidget(QPushButton(text))
        box_lay.addWidget(QCheckBox("Great to Pedal"))
        spin = QSpinBox()
        spin.setSuffix(" BPM")
        spin.setValue(80)
        box_lay.addWidget(spin)
        box_lay.addWidget(QLineEdit("Name of the setter"))
        row.addWidget(box)
        table = QTableWidget(5, 4)
        table.setHorizontalHeaderLabels(["Show", "Track name", "Ch", "Notes"])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for r in range(5):
            for c, text in enumerate(("", f"Track {r + 1}", str(r + 1), str(10 * r + 8))):
                table.setItem(r, c, QTableWidgetItem(text))
        table.selectRow(1)
        row.addWidget(table, 1)
        lay.addLayout(row, 1)
        tabs.addTab(page, "Bridge")
        tabs.addTab(QWidget(), "Stave Station")
        tabs.addTab(QWidget(), "Piano Roll")
        root.addWidget(tabs, 1)
        cards = QHBoxLayout()
        for title, note in (("Record center (docked)", "Docked dock frame"), ("LCD (floating)", "Floating: grip and shadow")):
            dock = QDockWidget(title, self)
            dock.hide()
            inner = QLabel(note)
            inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner.setMinimumHeight(44)
            card = QWidget()
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(0, 0, 0, 0)
            card_lay.setSpacing(0)
            card_lay.addWidget(SlimTitle(dock))
            card_lay.addWidget(DockFrame(inner, dock, preview=title.endswith("(floating)")))
            cards.addWidget(card)
        root.addLayout(cards)


class StudioPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: dict[str, tuple[QLabel, Callable[[], None]]] = {}
        self._snapshot = dict(gm.values())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        top = QHBoxLayout()
        self.looks = QComboBox()
        self.looks.addItems(list(gm.LOOKS))
        look_button = QPushButton("Apply look")
        look_button.setToolTip("Sets the frame, spacing and table metrics of this look (fonts, shadows and performance stay as they are).")
        look_button.clicked.connect(self._apply_look)
        revert = QPushButton("Revert")
        revert.setToolTip("Back to the values this dialog opened with")
        revert.clicked.connect(self._revert)
        reset = QPushButton("Reset all")
        reset.clicked.connect(self._reset_all)
        export = QPushButton("Export...")
        export.clicked.connect(self._export)
        load = QPushButton("Import...")
        load.clicked.connect(self._import)
        for widget in (QLabel("Look"), self.looks, look_button, revert, reset, export, load):
            top.addWidget(widget)
        top.addStretch(1)
        outer.addLayout(top)
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_lay = QHBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        self.nav = QListWidget()
        self.nav.setMaximumWidth(150)
        self.stack = QStackedWidget()
        for group in gm.GROUPS:
            self.nav.addItem(group)
            self.stack.addWidget(self._build_group(group))
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        left_lay.addWidget(self.nav)
        left_lay.addWidget(self.stack, 1)
        split.addWidget(left)
        self.preview = PreviewPanel()
        box = QGroupBox("Live preview")
        box_lay = QVBoxLayout(box)
        box_lay.addWidget(self.preview)
        split.addWidget(box)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        outer.addWidget(split, 1)
        self.status = QLabel()
        outer.addWidget(self.status)
        self._apply_timer = QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.timeout.connect(themes.apply)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save)
        self._show_path()
        self._sync_all()

    # ---- building
    def _build_group(self, group: str) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        if group == gm.G_PERF:
            lay.addWidget(self._hardware_box())
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for metric in (m for m in gm.SCHEMA if m.group == group):
            form.addRow(*self._row(metric))
        lay.addLayout(form)
        lay.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(page)
        return scroll

    def _hardware_box(self) -> QWidget:
        box = QGroupBox("This computer")
        lay = QVBoxLayout(box)
        self.hw_label = QLabel()
        self.hw_label.setWordWrap(True)
        lay.addWidget(self.hw_label)
        button = QPushButton("Detect and use the recommended profile")
        button.clicked.connect(self._use_recommended)
        lay.addWidget(button)
        self._refresh_hardware()
        return box

    def _refresh_hardware(self) -> None:
        info = gm.hardware()
        gpus = ", ".join(info["gpus"]) or "unknown"
        ram = f"{info['ram_gb']:.1f} GB" if info["ram_gb"] else "unknown"
        self.hw_label.setText(f"{info['cores']} CPU threads, memory {ram}, graphics: {gpus}.\n"
                              f"Recommended profile: <b>{gm.recommend(info)}</b> (class of graphics: {gm.gpu_class(info['gpus'])}). "
                              f"Active now: <b>{gm.effective_profile()}</b>.")

    def _row(self, metric: gm.Metric) -> tuple[QLabel, QWidget]:
        label = QLabel(metric.label + (f"  ({metric.restart})" if metric.restart else ""))
        label.setToolTip(metric.tip or metric.label)
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        key = metric.key
        if metric.kind == "int":
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(int(metric.lo), int(metric.hi))
            spin = QSpinBox()
            spin.setRange(int(metric.lo), int(metric.hi))
            spin.setSuffix(f" {metric.unit}" if metric.unit else "")
            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)
            spin.valueChanged.connect(lambda v, k=key: self._changed(k, v))
            row.addWidget(slider, 1)
            row.addWidget(spin)

            def set_int(value: Any, s=spin, sl=slider) -> None:
                s.blockSignals(True)
                sl.blockSignals(True)
                s.setValue(int(value))
                sl.setValue(int(value))
                s.blockSignals(False)
                sl.blockSignals(False)
            setter = set_int
        elif metric.kind == "float":
            dspin = QDoubleSpinBox()
            dspin.setRange(metric.lo, metric.hi)
            dspin.setSingleStep(0.5)
            dspin.setSuffix(f" {metric.unit}" if metric.unit else "")
            dspin.valueChanged.connect(lambda v, k=key: self._changed(k, v))
            row.addWidget(dspin)

            def set_float(value: Any, d=dspin) -> None:
                d.blockSignals(True)
                d.setValue(float(value))
                d.blockSignals(False)
            setter = set_float
        elif metric.kind == "bool":
            check = QCheckBox("on")
            check.toggled.connect(lambda v, k=key: self._changed(k, v))
            row.addWidget(check)

            def set_bool(value: Any, c=check) -> None:
                c.blockSignals(True)
                c.setChecked(bool(value))
                c.blockSignals(False)
            setter = set_bool
        elif metric.kind == "choice":
            combo = QComboBox()
            combo.addItems(list(metric.choices))
            combo.currentTextChanged.connect(lambda v, k=key: self._changed(k, v))
            row.addWidget(combo, 1)

            def set_choice(value: Any, c=combo) -> None:
                c.blockSignals(True)
                c.setCurrentText(str(value))
                c.blockSignals(False)
            setter = set_choice
        else:
            fonts = QComboBox()
            fonts.addItem("(system default)", "")
            fonts.addItems(QFontDatabase.families())
            fonts.currentIndexChanged.connect(lambda _i, k=key, f=fonts: self._changed(k, f.currentData() or f.currentText() if f.currentIndex() else ""))
            row.addWidget(fonts, 1)

            def set_font(value: Any, f=fonts) -> None:
                f.blockSignals(True)
                f.setCurrentIndex(max(0, f.findText(str(value))) if value else 0)
                f.blockSignals(False)
            setter = set_font
        reset = QToolButton()
        reset.setText("↺")
        reset.setToolTip("Back to the default")
        reset.clicked.connect(lambda _=False, k=key: self._changed(k, gm.BY_KEY[k].default))
        row.addWidget(reset)
        self._rows[key] = (label, lambda s=setter, k=key: s(gm.get(k)))
        return label, holder

    # ---- state
    def _sync_all(self) -> None:
        for key, (label, push) in self._rows.items():
            push()
            font = label.font()
            font.setBold(gm.modified(key))
            label.setFont(font)
        if hasattr(self, "hw_label"):
            self._refresh_hardware()

    def _changed(self, key: str, value: Any) -> None:
        if key == "perf_preset":
            gm.set_profile(str(value))
        else:
            gm.set_value(key, value)
        self._sync_all()
        self._apply_timer.start(40)
        self._save_timer.start(700)

    def _use_recommended(self) -> None:
        gm.hardware.__dict__.pop("_cache", None)
        gm.set_profile("Auto")
        self._sync_all()
        self._changed("perf_preset", "Auto")

    def _apply_look(self) -> None:
        gm.apply_look(self.looks.currentText())
        self._sync_all()
        self._apply_timer.start(40)
        self._save_timer.start(700)

    def _revert(self) -> None:
        gm.values().clear()
        gm.values().update(self._snapshot)
        self._sync_all()
        self._apply_timer.start(40)
        self._save_timer.start(700)

    def _reset_all(self) -> None:
        gm.reset_all()
        self._sync_all()
        self._apply_timer.start(40)
        self._save_timer.start(700)

    def _export(self) -> None:
        name, _ = QFileDialog.getSaveFileName(self, "Export GUI metrics", "gui_metrics.yaml", "YAML (*.yaml *.yml)")
        if name:
            gm.save(name)

    def _import(self) -> None:
        name, _ = QFileDialog.getOpenFileName(self, "Import GUI metrics", "", "YAML (*.yaml *.yml)")
        if name and gm.load(name):
            self._sync_all()
            self._apply_timer.start(40)
            self._save_timer.start(700)

    def _save(self) -> None:
        self.status.setText(("Saved to " + gm.path()) if gm.save() else "Not saved: no config folder (changes last for this session).")

    def _show_path(self) -> None:
        self.status.setText(("Changes are saved to " + gm.path()) if gm.path() else "No config folder: changes last for this session.")
