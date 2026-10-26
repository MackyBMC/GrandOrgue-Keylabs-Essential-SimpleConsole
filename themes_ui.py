"""Appearance dialog: theme family, mode, accent, shape, density, text size, Qt style, icons and toolbar layout.

Opens from the console (Appearance button) and the stave editor (View > Appearance...). Every change applies live to all windows.

CHANGELOG
2026-10-25  New.
"""
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QColorDialog, QComboBox, QDialog, QFormLayout, QGridLayout,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSlider, QSpinBox,
                               QStyleFactory, QTabWidget, QToolBar, QVBoxLayout, QWidget)

import themes

TB_STYLES = {"Icons only": Qt.ToolButtonStyle.ToolButtonIconOnly, "Text beside icon": Qt.ToolButtonStyle.ToolButtonTextBesideIcon,
             "Text under icon": Qt.ToolButtonStyle.ToolButtonTextUnderIcon}


def _bars(window):
    return [b for b in window.findChildren(QToolBar) if b.parent() is window]


def _key(bar):
    return bar.objectName() or bar.windowTitle()


def apply_toolbars(window):
    """Per-toolbar icon sizes and the text-under-icon style from the saved settings."""
    s = themes._settings()
    style = TB_STYLES.get(str(s.value("tb_style", "Icons only")), Qt.ToolButtonStyle.ToolButtonIconOnly)
    for bar in _bars(window):
        size = s.value("tb_size/" + _key(bar))
        if size:
            bar.setIconSize(QSize(int(size), int(size)))
        bar.setToolButtonStyle(style)


class AppearanceDialog(QDialog):
    def __init__(self, parent=None, stave=None):
        super().__init__(parent)
        self.setWindowTitle("Appearance")
        self.stave = stave
        self.resize(560, 520)
        tabs = QTabWidget()
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        st = themes.state()

        # ---- theme
        page = QWidget()
        form = QFormLayout(page)
        self.family = QComboBox()
        self.family.addItems(list(themes.FAMILIES))
        self.family.setCurrentText(st["family"])
        self.mode = QComboBox()
        for label, key in (("Light", "light"), ("Dark", "dark"), ("High contrast", "contrast")):
            self.mode.addItem(label, key)
        self.mode.setCurrentIndex(max(0, self.mode.findData(st["mode"])))
        form.addRow("Theme", self.family)
        form.addRow("Mode", self.mode)
        grid = QGridLayout()
        self.swatches = []
        reset = QPushButton("Theme default")
        reset.clicked.connect(lambda: self._set_accent(""))
        grid.addWidget(reset, 0, 0, 1, 2)
        for i, (name, colour) in enumerate(themes.ACCENTS.items()):
            b = QPushButton()
            b.setFixedSize(30, 24)
            b.setToolTip(name)
            b.setStyleSheet(f"QPushButton {{ background: {colour}; border: 2px solid transparent; border-radius: 6px; }}"
                            f"QPushButton:hover {{ border-color: white; }}")
            b.clicked.connect(lambda _=False, c=colour: self._set_accent(c))
            grid.addWidget(b, 0 if i < 5 else 1, 2 + i % 5)
        custom = QPushButton("Custom...")
        custom.clicked.connect(self._pick_accent)
        grid.addWidget(custom, 1, 0, 1, 2)
        form.addRow("Accent colour", grid)
        self.style_box = QComboBox()
        self.style_box.addItems(QStyleFactory.keys())
        self.style_box.setCurrentText(st["style"] if st["style"] in QStyleFactory.keys() else "Fusion")
        form.addRow("Qt style engine", self.style_box)
        self.detailed = QCheckBox("Apply the full theme (turn off for the plain native look of the style engine)")
        self.detailed.setChecked(st["detailed"])
        form.addRow(self.detailed)
        self.radius = QSlider(Qt.Orientation.Horizontal)
        self.radius.setRange(0, 14)
        self.radius.setValue(st["radius"])
        form.addRow("Corner radius", self.radius)
        self.density = QComboBox()
        for label, v in (("Compact", 0), ("Comfortable", 1), ("Spacious", 2)):
            self.density.addItem(label, v)
        self.density.setCurrentIndex(max(0, self.density.findData(st["density"])))
        form.addRow("Density", self.density)
        self.font = QSlider(Qt.Orientation.Horizontal)
        self.font.setRange(80, 160)
        self.font.setValue(st["font"])
        form.addRow("Text size %", self.font)
        tabs.addTab(page, "Theme")

        # ---- icons & toolbars
        page = QWidget()
        form = QFormLayout(page)
        try:
            from midi_stave import chrome
        except ImportError:
            import chrome
        self.chrome = chrome
        s = chrome.STYLE
        self.pack = QComboBox()
        for key, label in chrome.PACK_LABELS.items():
            self.pack.addItem(label, key)
        self.look = QComboBox()
        for key, label in chrome.LOOK_LABELS.items():
            self.look.addItem(label, key)
        self.size = QComboBox()
        for px in chrome.SIZES:
            self.size.addItem(f"{px} px", px)
        for box, key in ((self.pack, "pack"), (self.look, "look"), (self.size, "size")):
            box.setCurrentIndex(max(0, box.findData(s[key])))
        form.addRow("Icon pack", self.pack)
        form.addRow("Icon look", self.look)
        form.addRow("Default icon size", self.size)
        self.tbstyle = QComboBox()
        self.tbstyle.addItems(list(TB_STYLES))
        self.tbstyle.setCurrentText(str(themes._settings().value("tb_style", "Icons only")))
        form.addRow("Toolbar buttons", self.tbstyle)
        form.addRow(QLabel("Toolbars (tick to show, drag to reorder, pick a size per toolbar):"))
        self.bar_list = QListWidget()
        self.bar_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.bar_list.model().rowsMoved.connect(self._reorder)
        self.bar_list.currentRowChanged.connect(self._bar_selected)
        self.bar_list.itemChanged.connect(self._bar_toggled)
        form.addRow(self.bar_list)
        row = QHBoxLayout()
        self.bar_size = QSpinBox()
        self.bar_size.setRange(16, 96)
        self.bar_size.setSuffix(" px")
        self.bar_size.valueChanged.connect(self._bar_resized)
        row.addWidget(QLabel("Selected toolbar icon size"))
        row.addWidget(self.bar_size)
        row.addStretch(1)
        rb = QPushButton("Reset layout")
        rb.clicked.connect(self._reset_layout)
        row.addWidget(rb)
        form.addRow(row)
        tabs.addTab(page, "Icons && toolbars")
        self._fill_bars()

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        lay.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

        for w in (self.family, self.mode, self.style_box, self.density):
            w.currentIndexChanged.connect(self._theme_changed)
        self.detailed.toggled.connect(self._theme_changed)
        self.radius.valueChanged.connect(self._theme_changed)
        self.font.sliderReleased.connect(self._theme_changed)
        self.font.valueChanged.connect(lambda _v: (not self.font.isSliderDown()) and self._theme_changed())
        for w, k in ((self.pack, "pack"), (self.look, "look"), (self.size, "size")):
            w.currentIndexChanged.connect(lambda _i, w=w, k=k: self._icon_changed(k, w.currentData()))
        self.tbstyle.currentTextChanged.connect(self._tb_style)

    # ---- theme
    def _set_accent(self, colour):
        themes.save(accent=colour)
        themes.apply()

    def _pick_accent(self):
        c = QColorDialog.getColor(QColor(themes.tokens()["accent"]), self, "Accent colour")
        if c.isValid():
            self._set_accent(c.name())

    def _theme_changed(self, *_):
        themes.save(family=self.family.currentText(), mode=self.mode.currentData(), style=self.style_box.currentText(),
                    density=self.density.currentData(), radius=self.radius.value(), font=self.font.value(),
                    detailed=self.detailed.isChecked())
        themes.apply()

    # ---- icons
    def _icon_changed(self, key, value):
        if self.stave is not None:
            self.chrome.set_icon_style(self.stave, key, value)
            if key == "size":
                for bar in _bars(self.stave):
                    bar.setIconSize(QSize(value, value))
                themes._settings().remove("tb_size")
            apply_toolbars(self.stave)
            self._fill_bars()
        else:
            self.chrome.STYLE[key] = value
            self.chrome.QSettings("KeyLabGrandOrgue", "MidiStave").setValue("icon_" + key, value)

    def _tb_style(self, text):
        themes.save(tb_style=text)
        if self.stave is not None:
            apply_toolbars(self.stave)

    # ---- toolbars
    def _fill_bars(self):
        self.bar_list.blockSignals(True)
        self.bar_list.clear()
        if self.stave is not None:
            bars = sorted(_bars(self.stave), key=lambda b: (self.stave.toolBarArea(b).value, b.y(), b.x()))
            for bar in bars:
                item = QListWidgetItem(bar.windowTitle() or _key(bar))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if bar.isVisibleTo(self.stave) else Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, bar)
                self.bar_list.addItem(item)
        self.bar_list.blockSignals(False)

    def _bar_selected(self, row):
        item = self.bar_list.item(row)
        if item is not None:
            self.bar_size.blockSignals(True)
            self.bar_size.setValue(item.data(Qt.ItemDataRole.UserRole).iconSize().width())
            self.bar_size.blockSignals(False)

    def _bar_toggled(self, item):
        item.data(Qt.ItemDataRole.UserRole).setVisible(item.checkState() == Qt.CheckState.Checked)

    def _bar_resized(self, px):
        item = self.bar_list.currentItem()
        if item is not None:
            bar = item.data(Qt.ItemDataRole.UserRole)
            bar.setIconSize(QSize(px, px))
            themes._settings().setValue("tb_size/" + _key(bar), px)

    def _reorder(self, *_):
        """Rebuild the toolbar order in the main window to match the list (toolbars of the same area keep their area)."""
        if self.stave is None:
            return
        bars = [self.bar_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.bar_list.count())]
        for bar in bars:
            area = self.stave.toolBarArea(bar)
            if area == Qt.ToolBarArea.NoToolBarArea:
                continue
        for first, second in zip(bars, bars[1:]):
            if self.stave.toolBarArea(first) == self.stave.toolBarArea(second):
                self.stave.insertToolBar(second, first)

    def _reset_layout(self):
        themes._settings().remove("tb_size")
        themes._settings().remove("tb_style")
        if self.stave is not None:
            self.chrome.reset_layout(self.stave)
            for bar in _bars(self.stave):
                bar.setIconSize(QSize(self.chrome.STYLE["size"], self.chrome.STYLE["size"]))
                bar.setVisible(True)
            apply_toolbars(self.stave)
            self._fill_bars()
        self.tbstyle.setCurrentText("Icons only")
