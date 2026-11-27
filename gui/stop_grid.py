"""Stop selection grid widget and dialog.

Split out of qt_gui.py without behaviour change.

CHANGELOG
2026-11-28  Changelog labels of the module split now use the v2.0.9 patch numbers (comments only, no code change).
2026-11-27  Moved verbatim from qt_gui.py (modularisation, v2.0.9-65).
"""

from gui import window_memory
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    Qt,
    Signal,
)


class StopGridWidget(QWidget):
    toggle_requested = Signal(str, bool)

    def __init__(self, draft=False, parent=None):
        super().__init__(parent)
        self.draft = draft
        self._stops = []
        self._selected_paths = set()
        self._mapped_paths = []
        self._buttons = {}
        self._content_signature = None
        self._preview_signature = None

        layout = QVBoxLayout(self)
        self.mapping_label = QLabel()
        self.mapping_label.setWordWrap(True)
        layout.addWidget(self.mapping_label)
        self.preview_box = QWidget()
        self.preview_grid = QGridLayout(self.preview_box)
        self.preview_grid.setContentsMargins(0, 0, 0, 0)
        self.preview_grid.setSpacing(4)
        layout.addWidget(self.preview_box)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.content = QWidget()
        self.groups_layout = QVBoxLayout(self.content)
        self.groups_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.content)
        layout.addWidget(self.scroll_area, 1)

    def set_grid_data(self, stops, mapped_paths, active_paths, window_rows, draft_paths=None):
        self._stops = list(stops)
        self._mapped_paths = list(mapped_paths)
        self._window_rows = list(window_rows)
        if self.draft:
            if draft_paths is not None:
                self._selected_paths = set(draft_paths)
        else:
            self._selected_paths = set(active_paths)
        signature = tuple((item["path"], item["division"], item["name"]) for item in self._stops)
        if signature != self._content_signature:
            self._build_groups()
            self._content_signature = signature
        self._update_preview()
        self._update_buttons()

    def _build_groups(self):
        while self.groups_layout.count():
            child = self.groups_layout.takeAt(0)
            if child is None:
                continue
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        self._buttons.clear()
        groups = {}
        for item in self._stops:
            groups.setdefault(item["division"] or "Other", []).append(item)
        for division, items in groups.items():
            group_box = QGroupBox(f"{division} · {len(items)}")
            cells = QGridLayout(group_box)
            cells.setSpacing(4)
            for index, item in enumerate(items):
                button = QPushButton()
                button.setCheckable(True)
                button.setMinimumHeight(48)
                button.clicked.connect(
                    lambda checked, path=item["path"]: self._cell_clicked(path, checked))
                cells.addWidget(button, index // 8, index % 8)
                self._buttons[item["path"]] = button
            self.groups_layout.addWidget(group_box)

    def _cell_clicked(self, path, checked):
        if self.draft:
            if checked:
                self._selected_paths.add(path)
            else:
                self._selected_paths.discard(path)
        self.toggle_requested.emit(path, checked)

    def set_pad_map_visible(self, visible):
        """The PAD MAP strip (which stops sit on the KeyLab pads) only means something beside the live pads."""
        self.mapping_label.setVisible(visible)
        self.preview_box.setVisible(visible)

    def selected_paths(self):
        return set(self._selected_paths)

    def set_selected_paths(self, paths):
        self._selected_paths = set(paths)
        self._update_buttons()

    def toggle_path(self, path):
        if path not in self._buttons:
            return
        selected = path not in self._selected_paths
        if selected:
            self._selected_paths.add(path)
        else:
            self._selected_paths.remove(path)
        self._update_buttons()
        self.toggle_requested.emit(path, selected)

    def _update_preview(self):
        signature = (
            tuple(self._mapped_paths),
            tuple((row["division"], row["grid_row"], row["focus_x"],
                   tuple((item["path"], item["name"]) if item is not None else None
                         for item in row["cells"]))
                  for row in self._window_rows),
        )
        if signature == self._preview_signature:
            return
        self._preview_signature = signature
        while self.preview_grid.count():
            child = self.preview_grid.takeAt(0)
            if child is None:
                continue
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        mapped = {path: index + 1 for index, path in enumerate(self._mapped_paths) if path is not None}
        divisions = list(dict.fromkeys(row["division"] for row in self._window_rows if row["division"]))
        focused_division = " / ".join(divisions) or "No stops"
        focus_x = self._window_rows[0]["focus_x"] if self._window_rows else 0
        self.mapping_label.setText(
            f"PAD MAP  ·  {focused_division}  ·  "
            f"columns {focus_x + 1}–{focus_x + 4}  ·  pads 1–8")
        for row_index in range(2):
            row = self._window_rows[row_index] if row_index < len(self._window_rows) else None
            division_label = QLabel(
                f"{row['division']} · {row['grid_row'] + 1}" if row and row["division"] else "")
            division_label.setMinimumWidth(115)
            division_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
            self.preview_grid.addWidget(division_label, row_index, 0)
            cells = row["cells"] if row else []
            start = row["focus_x"] if row else focus_x
            for column in range(4):
                index = start + column
                item = cells[index] if index < len(cells) else None
                cell = QLabel()
                cell.setMinimumHeight(46)
                cell.setWordWrap(True)
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if item is not None:
                    pad_number = mapped.get(item["path"])
                    cell.setText((f"PAD {pad_number}  ·  " if pad_number else "") + item["name"])
                    if pad_number:
                        cell.setStyleSheet("border: 3px solid #d58b2a; background: #9a6b24; color: white; font-weight: 600;")
                    else:
                        cell.setStyleSheet("border: 1px solid #707780; padding: 3px;")
                else:
                    cell.setStyleSheet("border: 1px dashed #707780; padding: 3px;")
                self.preview_grid.addWidget(cell, row_index, column + 1)

    def _update_buttons(self):
        mapped = {path: index + 1 for index, path in enumerate(self._mapped_paths) if path is not None}
        for item in self._stops:
            button = self._buttons.get(item["path"])
            if button is None:
                continue
            active = item["path"] in self._selected_paths
            pad_number = mapped.get(item["path"])
            button.blockSignals(True)
            button.setChecked(active)
            button.setText(f"{'PAD ' + str(pad_number) + '  ·  ' if pad_number else ''}{item['name']}\n"
                           f"{'ON' if active else 'off'}  ·  CC {item.get('cc', '?')}")
            button.setToolTip(f"{item['division']} · {item['name']} · {'active' if active else 'inactive'}"
                              + (f" · KeyLab pad {pad_number}" if pad_number else ""))
            button.setStyleSheet(
                f"QPushButton {{ text-align: left; border: {3 if pad_number else 1}px solid "
                f"{'#d58b2a' if pad_number else '#707780'}; min-height: 42px; }} "
                "QPushButton:checked { background-color: #367f6b; color: white; font-weight: 600; }")
            button.blockSignals(False)


class StopGridDialog(QDialog):
    closed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Stop Selection Grid")
        self.setMinimumSize(560, 380)
        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else QRect(0, 0, 1120, 720)
        width = max(560, min(1120, available.width() - 40))
        height = max(380, min(720, available.height() - 64))
        center = available.center()
        self._target_geometry = QRect(center.x() - width // 2, center.y() - height // 2, width, height)
        memory = window_memory.current()
        remembered = memory.saved_rect("StopGridDialog:Stop Selection Grid") if memory is not None else None
        if remembered is not None:
            self._target_geometry = remembered              # reopen where the user last left the grid
        self._target_geometry = self._inside(self._target_geometry, available)
        self._animation = None
        self._closing = False
        self._preserve_mode_on_close = False
        self._allow_close = False
        self._closed_emitted = False
        layout = QVBoxLayout(self)
        self.grid = StopGridWidget()
        layout.addWidget(self.grid)

    @staticmethod
    def _inside(rect, area):
        """The window including its frame (8 px sides / bottom, 31 px title bar) stays on the screen, so Windows never has to refuse the size."""
        w = max(560, min(rect.width(), area.width() - 16))
        h = max(380, min(rect.height(), area.height() - 39))
        x = max(area.left() + 8, min(rect.x(), area.right() - w - 7))
        y = max(area.top() + 31, min(rect.y(), area.bottom() - h - 7))
        return QRect(x, y, w, h)

    @property
    def is_closing(self):
        return self._closing

    def _note_geometry(self):
        if self._animation is None and not self._closing and self.isVisible() and not self.isMinimized():
            self._last_good = QRect(self.geometry())

    def moveEvent(self, event):
        super().moveEvent(event)
        self._note_geometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._note_geometry()

    def _collapsed_geometry(self):
        center = self._target_geometry.center()
        return QRect(center.x() - 24, center.y() - 18, 48, 36)

    def _animate(self, target_geometry, target_opacity, duration, easing, closing):
        if self._animation is not None:
            self._animation.stop()
            self._animation.deleteLater()
        self._closing = closing
        group = QParallelAnimationGroup(self)
        geometry = QPropertyAnimation(self, b"geometry", group)
        geometry.setDuration(duration)
        geometry.setStartValue(self.geometry())
        geometry.setEndValue(target_geometry)
        geometry.setEasingCurve(easing)
        opacity = QPropertyAnimation(self, b"windowOpacity", group)
        opacity.setDuration(duration)
        opacity.setStartValue(self.windowOpacity())
        opacity.setEndValue(target_opacity)
        opacity.setEasingCurve(easing)
        group.finished.connect(lambda: self._animation_finished(closing, group))
        self._animation = group
        group.start()

    def _animation_finished(self, closing, group):
        if self._animation is not group:
            return
        self._animation = None
        group.deleteLater()
        if closing:
            self._allow_close = True
            self.close()
        else:
            self._closing = False
            self.setGeometry(self._target_geometry)
            self.setWindowOpacity(1.0)

    def animate_open(self):
        self._allow_close = False
        self._preserve_mode_on_close = False
        if not self.isVisible():
            self.setGeometry(self._collapsed_geometry())
            self.setWindowOpacity(0.0)
            self.show()
            self.raise_()
        self._animate(self._target_geometry, 1.0, 260, QEasingCurve.Type.OutCubic, False)

    def animate_close(self, preserve_mode=False):
        if self._closing:
            return
        self._preserve_mode_on_close = preserve_mode
        if not self.isVisible():
            self._allow_close = True
            self.close()
            return
        self._animate(self._collapsed_geometry(), 0.0, 200, QEasingCurve.Type.InCubic, True)

    def close_immediately(self):
        if self._animation is not None:
            self._animation.stop()
            self._animation.deleteLater()
            self._animation = None
        self._allow_close = True
        self.close()

    def closeEvent(self, event):
        if not self._allow_close:
            event.ignore()
            self.animate_close()
            return
        if not self._closed_emitted:
            self._closed_emitted = True
            self.closed.emit(self._preserve_mode_on_close)
        super().closeEvent(event)
