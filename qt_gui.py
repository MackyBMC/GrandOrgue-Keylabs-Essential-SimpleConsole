"""Optional PySide6 dashboard for the KeyLab bridge.

CHANGELOG
2026-10-24  The MIDI timeline can be clicked / dragged to move to a position (playback restarts there, registration restored).
2026-10-24  Polished look (polish.py): slim rounded scroll bars, rounded flat buttons, soft focus rings, tidy tool bars / docks.
2026-10-24  Theme (light / dark / contrast) now also applies to the stave editor and sheet music windows, live.
2026-10-24  File dialogs (MIDI, YAML, organ, save) remember their last folder between sessions (lastdir.py).
2026-10-23  Stave editor: step sequence + interactive printed score hooks (chord event, KeyLab >> / << in step mode).
2026-10-21  Stave editor opened from here gets the playback position (red playhead on the roll, current bar red in the score).
2026-10-24  Transport tempo is a session-wide BPM target with synchronized controls and shared undo / redo.
2026-10-21  Transport frame: "Channels..." remaps each channel of the active MIDI file to a GrandOrgue channel (sidecar file).
2026-10-20  Transport frame: Previous/Next file = MIDI files in the midi folder, Save = Save As, new "Open MIDI..." button,
            active MIDI file shown under the buttons.
2026-10-20  "Stave editor" toolbar button opens the MIDI to Stave editor (midi_stave folder) as a remembered window.
2026-10-17  Sheet music jog is now a quick-switch: the highlight follows the jog instantly in either list, but the
            file opens / setter cues only after the jog has been still for SETTLE_MS (0.9 s). Jog press applies at
            once. Setter switching uses the new "cue_setter" event, so it ignores the unsaved-registration prompt and
            does not depend on << / >> (which keep stepping inside one combination). The setter highlight is no longer
            snapped back by the periodic refresh while the jog is moving.
2026-10-18  Large PDFs: opening is deferred 30 ms and superseded requests are skipped (fast jogging never opens the
            files it passes), the status line shows page count and open time, and the two-page view keeps an 8-image
            cache and pre-renders the next spread while idle. Setter jog calls the same backend entry as the main GUI
            (request_navigate), so selection and activation logic are shared.
2026-10-18  Sheet music: the Files / Setters panel is now in a horizontal splitter - drag its right edge to stretch it
            (up to 1200 px); the width is remembered in window_layout.json.
2026-10-18  Window memory: WindowMemory remembers position, size and maximised state of the console, the sheet music
            window, the stop grid and every popup dialog (setter editor etc.) in window_layout.json next to config.yaml,
            and restores them on show; windows that would land off-screen (monitor removed) are pulled back on. Message
            boxes and file pickers are excluded. Delete window_layout.json to reset all positions.
2026-10-18  Active tick is now painted by ActiveTickDelegate (not the stylesheet): amber box + tick = active, empty
            box = inactive, identical on highlighted rows, in every theme.
2026-10-18  Active tick (setter tree): checked = solid amber box, unchecked = empty box, on EVERY row including the
            highlighted one. Before, a highlighted active row drew the tick in the selection's contrast colour, so it
            looked inverted / off.
2026-10-17  Sheet music lists now show state clearly: the ACTIVE setter (what the organ is playing, incl. after the
            pedal / jog press) and the OPEN score are bold with a teal tint; the plain highlight is only the cursor.
            After a jog cue the setter cursor is held for 1.5 s so the organ's step-by-step feedback cannot pull it
            around, then it follows the real selection again.
"""

import importlib
import lastdir
import polish
import json
import os
import shutil
import sys
import threading
import time

from PySide6.QtCore import (
    QEvent, QEasingCurve, QObject, QParallelAnimationGroup, QPoint, QPointF, QPropertyAnimation, QRect, QSize, Qt, QTimer, Signal,
)
from PySide6.QtGui import QBrush, QColor, QImage, QPen, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTabWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QSplitter,
    QSizeGrip,
    QStyleFactory,
)

from keylab_bridge.midi_protocol import UNASSIGNED_PAD_COLOR, VOLS
from keylab_bridge.preset_store import set_config_value
from tempo_control import TempoControl
from translations import LANGUAGE_NAMES, THEME_PALETTES, contrast_text, translate
TRANSPORT_ACTIONS = (
    ("gui_previous_step", "previous_step"),
    ("gui_next_step", "next_step"),
    ("gui_previous_file", "previous_file"),
    ("gui_next_file", "next_file"),
    ("gui_load", "load"),
    ("gui_save", "save"),
    ("gui_play", "play"),
    ("gui_loop", "loop"),
    ("gui_metro", "metro"),
    ("gui_panic", "stop"),
)
COMMAND_OPTIONS = (
    "help", "status", "debug on", "debug off", "reconnect", "recover", "resync", "restart",
    "panic", "clear", "language en", "language de", "language fr", "language es",
    "theme light", "theme dark", "theme contrast", "preset-mode staged", "preset-mode direct", "quit",
    "config", "combinations reload", "organ-apply", "organ-routes on", "organ-routes off",
)


class SheetMusicWindow(QDialog):
    FOLDER = r"C:\Audio\sheet music"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sheet music")
        self.resize(1200, 820)
        self.setMinimumSize(900, 600)
        self.document = QPdfDocument(self)
        self.document.statusChanged.connect(self._document_status_changed)
        self.document.pageCountChanged.connect(self._page_count_changed)
        self._pdf_path = ""
        self._pending_page_direction = 1
        self._two_page_mode = False
        self._spread_first_page = 0

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.page_number = QSpinBox()
        self.page_number.setPrefix("Page ")
        self.page_number.setRange(1, 1)
        self.page_number.setEnabled(False)
        self.page_number.valueChanged.connect(self._goto_page)
        toolbar.addWidget(self.page_number)
        self.page_count_label = QLabel("of 0")
        toolbar.addWidget(self.page_count_label)
        toolbar.addSpacing(16)
        self.zoom_box = QComboBox()
        self.zoom_box.addItem("Fit page", QPdfView.ZoomMode.FitInView)
        self.zoom_box.addItem("Fit width", QPdfView.ZoomMode.FitToWidth)
        self.zoom_box.addItem("Actual size", QPdfView.ZoomMode.Custom)
        self.zoom_box.currentIndexChanged.connect(self._select_zoom_mode)
        toolbar.addWidget(self.zoom_box)
        self.zoom_out_button = QPushButton("-")
        self.zoom_out_button.setToolTip("Zoom out")
        self.zoom_out_button.clicked.connect(lambda: self._change_zoom(1 / 1.2))
        toolbar.addWidget(self.zoom_out_button)
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setToolTip("Zoom in")
        self.zoom_in_button.clicked.connect(lambda: self._change_zoom(1.2))
        toolbar.addWidget(self.zoom_in_button)
        toolbar.addSpacing(16)
        self.two_page_button = QPushButton("Two-page view")
        self.two_page_button.setCheckable(True)
        self.two_page_button.setToolTip(
            "Show two pages side by side, so you can read ahead without turning as often"
        )
        self.two_page_button.toggled.connect(self._toggle_two_page)
        toolbar.addWidget(self.two_page_button)
        toolbar.addStretch(1)
        self.files_button = QPushButton("Hide files")
        self.files_button.setToolTip("Collapse the file list for maximum viewing width")
        self.files_button.clicked.connect(self._toggle_file_list)
        toolbar.addWidget(self.files_button)
        self.fullscreen_button = QPushButton("Full screen")
        self.fullscreen_button.clicked.connect(self._toggle_fullscreen)
        toolbar.addWidget(self.fullscreen_button)
        layout.addLayout(toolbar)

        content = QHBoxLayout()
        self.file_list = QListWidget()
        self.file_list.currentRowChanged.connect(self._load_file_at)
        self.setter_list = QListWidget()                  # the setter steps, so a service can be driven from here
        self.setter_list.itemClicked.connect(self._setter_clicked)
        self._setter_signature = None
        self._setter_indices = []
        self.files_title = QLabel()
        self.setters_title = QLabel()
        files_box, setters_box = QWidget(), QWidget()
        for box, title, widget in ((files_box, self.files_title, self.file_list),
                                   (setters_box, self.setters_title, self.setter_list)):
            column = QVBoxLayout(box)
            column.setContentsMargins(0, 0, 0, 0)
            column.addWidget(title)
            column.addWidget(widget, 1)
        self.side_panel = QSplitter(Qt.Orientation.Vertical)     # drag the handle to give either list more room
        self.side_panel.setChildrenCollapsible(False)
        self.side_panel.addWidget(files_box)
        self.side_panel.addWidget(setters_box)
        self.side_panel.setMinimumWidth(220)
        self.side_panel.setMaximumWidth(1200)
        self.jog_zone = "files"                           # which list the jog wheel drives: "files" or "setters"
        self._hold_cursor_until = 0.0
        self._load_token = 0                              # newest file request wins; older ones are skipped
        self._load_started = 0.0
        self._spread_cache = {}                           # (path, page, w, h) -> QImage, small LRU for two-page view
        self._pending = None                              # ("files"|"setters", row) waiting for the jog to settle
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.timeout.connect(self._apply_pending)
        self._update_zone_titles()
        self.main_split = QSplitter(Qt.Orientation.Horizontal)     # drag the handle to stretch the file / setter lists
        self.main_split.setChildrenCollapsible(False)
        self.main_split.addWidget(self.side_panel)
        self.pdf_view = QPdfView()
        self.pdf_view.setDocument(self.document)
        self.pdf_view.setPageMode(QPdfView.PageMode.SinglePage)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self.pdf_view.pageNavigator().currentPageChanged.connect(self._page_navigated)
        self.main_split.addWidget(self.pdf_view)
        self.spread_label = QLabel()
        self.spread_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spread_label.setStyleSheet("background: white;")
        self.spread_label.setVisible(False)
        self.main_split.addWidget(self.spread_label)
        self.main_split.setStretchFactor(0, 0)
        self.main_split.setStretchFactor(1, 1)
        self.main_split.setStretchFactor(2, 1)
        saved_width = WINDOW_MEMORY.value("SheetMusicSideWidth") if WINDOW_MEMORY is not None else None
        self.side_panel.setMinimumWidth(220)
        self.main_split.setSizes([int(saved_width) if isinstance(saved_width, (int, float)) and saved_width >= 220 else 320, 900, 900])
        self.main_split.splitterMoved.connect(
            lambda *_: WINDOW_MEMORY and WINDOW_MEMORY.store("SheetMusicSideWidth", self.side_panel.width()))
        layout.addWidget(self.main_split, 1)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        self._load_file_list()
        self._page_shortcuts = []
        escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape.setContext(Qt.ShortcutContext.WindowShortcut)
        escape.activated.connect(self._leave_fullscreen)
        self._page_shortcuts.append(escape)
        # QShortcut alone isn't enough for Left/Right: QListWidget (the file
        # list) and other child widgets claim those keys for their own item
        # navigation via Qt's ShortcutOverride mechanism, which silently
        # swallows the shortcut before it ever fires. Installing an
        # application-wide filter lets us catch Left/Right regardless of
        # which child widget currently has focus, as long as this window is
        # the active one.
        application = QApplication.instance()
        if application is None:
            raise RuntimeError("Sheet music window requires a QApplication instance")
        application.installEventFilter(self)

    def eventFilter(self, obj, event):
        if self.isVisible() and self.isActiveWindow():
            event_type = event.type()
            if event_type in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
                if (event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right)
                        and event.modifiers() == Qt.KeyboardModifier.NoModifier):
                    if event_type == QEvent.Type.ShortcutOverride:
                        event.accept()
                    else:
                        self.navigate_score(-1 if event.key() == Qt.Key.Key_Left else 1)
                    return True
        return super().eventFilter(obj, event)

    def _load_file_list(self):
        if not os.path.isdir(self.FOLDER):
            self.status_label.setText(f"Folder not found: {self.FOLDER}")
            return
        paths = []
        for root, _, filenames in os.walk(self.FOLDER):
            paths.extend(os.path.join(root, name) for name in filenames if name.lower().endswith(".pdf"))
        paths.sort(key=lambda path: os.path.relpath(path, self.FOLDER).casefold())
        for path in paths:
            display_name = os.path.relpath(path, self.FOLDER)
            self.file_list.addItem(display_name)
            self.file_list.item(self.file_list.count() - 1).setData(Qt.ItemDataRole.UserRole, path)
        if paths:
            self.file_list.setCurrentRow(0)
        else:
            self.status_label.setText("No PDF files found")

    def _load_file_at(self, row):
        if row < 0:
            return
        item = self.file_list.item(row)
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(path, str):
            return
        self._mark_active(self.file_list, row)
        self._load_token += 1
        token = self._load_token
        self.status_label.setText(f"Loading {item.text()}...")
        self.setWindowTitle(f"Sheet music - {os.path.basename(path)}")
        QTimer.singleShot(30, lambda: self._open_pdf(path, token))   # let the highlight paint; skip superseded requests

    def _open_pdf(self, path, token):
        if token != self._load_token:
            return                                          # the jog has already moved on: never open this one
        self._pdf_path = path
        self._spread_first_page = 0
        self._spread_cache.clear()
        self._load_started = time.time()
        self.document.close()
        self.document.load(path)

    _TINT = QColor(79, 209, 197, 70)

    def _mark_active(self, widget, active_row):
        """Bold + tint exactly one row of a list: the one that is really open / playing (not just the cursor)."""
        for r in range(widget.count()):
            it = widget.item(r)
            on = r == active_row
            font = it.font()
            if font.bold() != on:
                font.setBold(on)
                it.setFont(font)
            it.setBackground(QBrush(self._TINT) if on else QBrush())

    def _document_status_changed(self, status):
        if status == QPdfDocument.Status.Error:
            self.status_label.setText("Could not open this PDF")
        elif status == QPdfDocument.Status.Ready:
            self._page_count_changed(self.document.pageCount())
            self.pdf_view.pageNavigator().jump(0, QPointF(0, 0))     # every newly chosen file starts on page one
            self._current_page_changed(0)
            if self._two_page_mode:
                self._spread_first_page = 0
                self._render_spread()
            else:
                item = self.file_list.currentItem()
                self.status_label.setText(f"{item.text() if item else ''} - {self.document.pageCount()} pages "
                                          f"({time.time() - self._load_started:.1f} s)")

    def _page_count_changed(self, count):
        self.page_count_label.setText(f"of {count}")
        self.page_number.setEnabled(count > 0)
        if count and not self._two_page_mode:
            self._current_page_changed(self.pdf_view.pageNavigator().currentPage())
            self.status_label.setText(self.file_list.currentItem().text() if self.file_list.currentItem() else "")

    def _current_page_changed(self, page):
        count = self.document.pageCount()
        if not count:
            return
        self.page_number.blockSignals(True)
        self.page_number.setRange(1, count)
        self.page_number.setValue(max(1, min(count, page + 1)))
        self.page_number.blockSignals(False)

    def _page_navigated(self, page):
        self._current_page_changed(page)

    def _goto_page(self, page):
        if not self.document.pageCount():
            return
        if self._two_page_mode:
            self._spread_first_page = max(0, page - 1)
            self._render_spread()
        else:
            self.pdf_view.pageNavigator().jump(page - 1, QPointF(0, 0))

    def _update_zone_titles(self):
        on, off = "color: #4fd1c5; font-weight: bold;", "color: gray;"
        self.files_title.setText("Files  (jog)" if self.jog_zone == "files" else "Files")
        self.setters_title.setText("Setters  (jog)" if self.jog_zone == "setters" else "Setters")
        self.files_title.setStyleSheet(on if self.jog_zone == "files" else off)
        self.setters_title.setStyleSheet(on if self.jog_zone == "setters" else off)

    SETTLE_MS = 900                                        # jog must be still this long before the list acts

    def toggle_jog_zone(self):
        self._apply_pending()
        self.jog_zone = "setters" if self.jog_zone == "files" else "files"
        self._update_zone_titles()

    def jog_move(self, direction):
        """Jog wheel while the score is open: the highlight moves at once, the action waits for the jog to settle."""
        widget = self.file_list if self.jog_zone == "files" else self.setter_list
        count = widget.count()
        if not count:
            return
        if self._pending is not None and self._pending[0] == self.jog_zone:
            row = self._pending[1]
        else:
            self._apply_pending()
            row = widget.currentRow()
        row = max(0, min(count - 1, row + direction))
        widget.blockSignals(True)                          # highlight only: no file load / no click handler yet
        widget.setCurrentRow(row)
        widget.scrollToItem(widget.item(row))
        widget.blockSignals(False)
        self._pending = (self.jog_zone, row)
        self._settle_timer.start(self.SETTLE_MS)

    def _apply_pending(self):
        self._settle_timer.stop()
        pending, self._pending = self._pending, None
        if pending is None:
            return
        zone, row = pending
        if zone == "files":
            self._load_file_at(row)                        # opens it, back on page one
            return
        item = self.setter_list.item(row)
        index = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        parent = self.parentWidget()
        if index is not None and isinstance(parent, BridgeWindow):
            self._hold_cursor_until = time.time() + 1.5
            parent.bridge.post_ui_event("cue_setter", int(index))

    def jog_press(self):
        had_pending = self._pending is not None
        self._apply_pending()
        if self.jog_zone == "setters":
            parent = self.parentWidget()
            if isinstance(parent, BridgeWindow):
                parent.bridge.post_ui_event("transport", "load")      # load the cued setter onto the organ
        elif not had_pending and self.file_list.currentRow() >= 0:
            self._load_file_at(self.file_list.currentRow())           # re-open the current file from page one

    def _setter_clicked(self, item):
        index = item.data(Qt.ItemDataRole.UserRole)
        parent = self.parentWidget()
        if index is not None and isinstance(parent, BridgeWindow):
            parent.bridge.post_ui_event("combination", int(index))

    def update_setters(self, combinations, selected_index, active_index):
        """Mirror the main window's setter list (called from its refresh); only rebuilds when the list changes."""
        signature = tuple((c["filename"], c["internal_id"], c["name"]) for c in combinations)
        if signature != self._setter_signature:
            self._setter_signature = signature
            self.setter_list.blockSignals(True)
            self.setter_list.clear()
            for index, c in enumerate(combinations):
                item = QListWidgetItem(f"{c['filename'].rsplit('.', 1)[0]}  |  {c['name']}")
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.setter_list.addItem(item)
            self.setter_list.blockSignals(False)
        self.setter_list.blockSignals(True)
        hold = (self._pending is not None and self._pending[0] == "setters") or time.time() < self._hold_cursor_until
        for row in range(self.setter_list.count()):
            item = self.setter_list.item(row)
            index = item.data(Qt.ItemDataRole.UserRole)
            on = index == active_index                        # what the organ is playing now (pedal / jog press too)
            font = item.font()
            if font.bold() != on:
                font.setBold(on)
                item.setFont(font)
            item.setBackground(QBrush(self._TINT) if on else QBrush())
            if index == selected_index and self.setter_list.currentRow() != row and not hold:
                self.setter_list.setCurrentRow(row)
                self.setter_list.scrollToItem(item)
        self.setter_list.blockSignals(False)

    def navigate_score(self, delta):
        if not self.isVisible() or not self.document.pageCount():
            return
        if self._two_page_mode:
            count = self.document.pageCount()
            target = self._spread_first_page + 2 * delta
            if target < 0 or target >= count:
                return
            self._spread_first_page = target
            self._render_spread()
            return
        page = self.pdf_view.pageNavigator().currentPage()
        target_page = page + delta
        if 0 <= target_page < self.document.pageCount():
            target_y = self.document.pagePointSize(target_page).height() if delta < 0 else 0
            self.pdf_view.pageNavigator().jump(target_page, QPointF(0, target_y))

    def _select_zoom_mode(self, index):
        if self._two_page_mode:
            return
        mode = self.zoom_box.itemData(index)
        self.pdf_view.setZoomMode(mode)
        if mode == QPdfView.ZoomMode.Custom:
            self.pdf_view.setZoomFactor(1.0)

    def _change_zoom(self, factor):
        if self._two_page_mode:
            return
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.pdf_view.setZoomFactor(max(0.25, min(5.0, self.pdf_view.zoomFactor() * factor)))
        self.zoom_box.blockSignals(True)
        self.zoom_box.setCurrentIndex(2)
        self.zoom_box.blockSignals(False)

    def _toggle_two_page(self, checked):
        self._two_page_mode = checked
        self.pdf_view.setVisible(not checked)
        self.spread_label.setVisible(checked)
        self.zoom_box.setEnabled(not checked)
        self.zoom_out_button.setEnabled(not checked)
        self.zoom_in_button.setEnabled(not checked)
        self.two_page_button.setText("Single page" if checked else "Two-page view")
        if checked and self.document.pageCount():
            page = self.pdf_view.pageNavigator().currentPage()
            self._spread_first_page = page - (page % 2)
            self._render_spread()
        elif not checked and self.document.pageCount():
            self.pdf_view.pageNavigator().jump(self._spread_first_page, QPointF(0, 0))

    def _page_image(self, index, half_width, height):
        size = self.document.pagePointSize(index)
        if size.width() <= 0 or size.height() <= 0:
            return None
        scale = min(half_width / size.width(), height / size.height())
        target = QSize(max(1, int(size.width() * scale)), max(1, int(size.height() * scale)))
        key = (self._pdf_path, index, target.width(), target.height())
        image = self._spread_cache.pop(key, None)
        if image is None:
            image = self.document.render(index, target)
        self._spread_cache[key] = image                     # most recently used goes last
        while len(self._spread_cache) > 8:
            self._spread_cache.pop(next(iter(self._spread_cache)))
        return image

    def _prefetch_next_spread(self, token):
        """Idle time after a spread is shown: render the next one so turning the page is instant on huge scores."""
        if token != self._load_token or not self._two_page_mode or self.document.status() != QPdfDocument.Status.Ready:
            return
        viewport = self.spread_label.size()
        count = self.document.pageCount()
        for index in (self._spread_first_page + 2, self._spread_first_page + 3):
            if index < count:
                self._page_image(index, (viewport.width() - 8) // 2, viewport.height())

    def _render_spread(self):
        if not self._two_page_mode or self.document.status() != QPdfDocument.Status.Ready:
            return
        count = self.document.pageCount()
        if not count:
            return
        self._spread_first_page = max(0, min(self._spread_first_page, count - 1))
        left = self._spread_first_page
        right = left + 1 if left + 1 < count else None
        viewport = self.spread_label.size()
        if viewport.width() < 20 or viewport.height() < 20:
            return
        gap = 8
        half_width = (viewport.width() - gap) // (2 if right is not None else 1)
        images = []
        for index in (left, right):
            if index is None:
                continue
            image = self._page_image(index, half_width, viewport.height())
            if image is not None:
                images.append(image)
        if not images:
            return
        total_width = sum(image.width() for image in images) + (gap if len(images) > 1 else 0)
        max_height = max(image.height() for image in images)
        canvas = QImage(total_width, max_height, QImage.Format.Format_ARGB32)
        canvas.fill(Qt.GlobalColor.white)
        painter = QPainter(canvas)
        x = 0
        for image in images:
            painter.drawImage(x, (max_height - image.height()) // 2, image)
            x += image.width() + gap
        painter.end()
        self.spread_label.setPixmap(QPixmap.fromImage(canvas))
        QTimer.singleShot(250, lambda t=self._load_token: self._prefetch_next_spread(t))
        pages_text = f"{left + 1}" + (f"-{right + 1}" if right is not None else "")
        item = self.file_list.currentItem()
        self.status_label.setText(f"{item.text() if item else ''} - pages {pages_text} of {count}")
        self.page_number.blockSignals(True)
        self.page_number.setValue(left + 1)
        self.page_number.blockSignals(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._two_page_mode:
            self._render_spread()

    def _toggle_file_list(self):
        visible = not self.side_panel.isVisible()
        self.side_panel.setVisible(visible)
        self.files_button.setText("Hide files" if visible else "Show files")
        if self._two_page_mode:
            QTimer.singleShot(0, self._render_spread)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self._leave_fullscreen()
        else:
            self.showFullScreen()
            self.fullscreen_button.setText("Windowed")

    def _leave_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_button.setText("Full screen")

    def showEvent(self, event):
        parent = self.parentWidget()
        if isinstance(parent, BridgeWindow):
            parent.bridge.sheet_music_navigation_enabled.set()
        super().showEvent(event)

    def hideEvent(self, event):
        # Esc / reject() hides the dialog without closeEvent: the jog and arrows must go back to the main window.
        parent = self.parentWidget()
        if isinstance(parent, BridgeWindow):
            parent.bridge.sheet_music_navigation_enabled.clear()
        super().hideEvent(event)

    def closeEvent(self, event):
        parent = self.parentWidget()
        if isinstance(parent, BridgeWindow):
            parent.bridge.sheet_music_navigation_enabled.clear()
        event.accept()

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
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        outer.addWidget(self.scroll, 1)
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
        self.scroll.setWidget(page)
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
        self.preview_grid = QGridLayout()
        self.preview_grid.setSpacing(4)
        layout.addLayout(self.preview_grid)
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
        remembered = WINDOW_MEMORY.saved_rect("StopGridDialog:Stop Selection Grid") if WINDOW_MEMORY is not None else None
        if remembered is not None:
            self._target_geometry = remembered              # reopen where the user last left the grid
        self._animation = None
        self._closing = False
        self._preserve_mode_on_close = False
        self._allow_close = False
        self._closed_emitted = False
        layout = QVBoxLayout(self)
        self.grid = StopGridWidget()
        layout.addWidget(self.grid)

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
        self._animate(self._target_geometry, 1.0, 420, QEasingCurve.Type.OutBack, False)

    def animate_close(self, preserve_mode=False):
        if self._closing:
            return
        self._preserve_mode_on_close = preserve_mode
        if not self.isVisible():
            self._allow_close = True
            self.close()
            return
        self._animate(self._collapsed_geometry(), 0.0, 260, QEasingCurve.Type.InBack, True)

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


WINDOW_MEMORY = None            # set by run_qt_ui: remembers every window's place and size across restarts


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


class ActiveTickDelegate(QStyledItemDelegate):
    """Paints the Active column itself, so the tick looks the same on every row whatever the stylesheet or the
    selection colour does: active = solid amber box with a tick, inactive = empty box. Highlight never inverts it."""

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
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


class BridgeWindow(QMainWindow):
    sheet_music_navigation_requested = Signal(int)
    sheet_jog_requested = Signal(int)
    sheet_press_requested = Signal()
    sheet_zone_requested = Signal()
    menu_jog_requested = Signal(int)
    menu_press_requested = Signal()
    modal_jog_requested = Signal(int)
    modal_press_requested = Signal()
    main_jog_requested = Signal(int)
    main_press_requested = Signal()
    stop_grid_pad_requested = Signal(str)

    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge
        self._language = None
        self._pad_buttons = []
        self._volume_sliders = {}
        self._volume_leds = {}
        self._volume_labels = {}
        self._transport_buttons = {}
        self._text_labels = {}
        self._metro_pressed = False
        self._metro_active = False
        self._active_stop_snapshot = None
        self._last_preset_event_index = None
        self._combination_tree_signature = None
        self._combination_snapshot = []
        self._available_stops = []
        self._active_stop_paths = []
        self._stop_grid_popup = None
        self._suppress_grid_close = False
        self._grid_close_pending = False
        self._active_editor_grid = None
        self._confirm_navigate_open = False
        self.sheet_music_window = None
        self.sheet_music_navigation_requested.connect(self._navigate_sheet_music)
        self.bridge.sheet_music_navigation_handler = self.sheet_music_navigation_requested.emit
        self.sheet_jog_requested.connect(lambda d: self.sheet_music_window and self.sheet_music_window.jog_move(d))
        self.sheet_press_requested.connect(lambda: self.sheet_music_window and self.sheet_music_window.jog_press())
        self.sheet_zone_requested.connect(lambda: self.sheet_music_window and self.sheet_music_window.toggle_jog_zone())
        self.bridge.sheet_jog_handler = self.sheet_jog_requested.emit
        self.bridge.sheet_press_handler = self.sheet_press_requested.emit
        self.bridge.sheet_zone_handler = self.sheet_zone_requested.emit
        self._menu_cursor = None
        self._main_cursor = None
        self.menu_jog_requested.connect(self._menu_move)
        self.menu_press_requested.connect(self._menu_press)
        self.main_jog_requested.connect(self._main_jog)
        self.main_press_requested.connect(self._main_press)
        self.modal_jog_requested.connect(self._modal_move)
        self.modal_press_requested.connect(self._modal_press)
        self.bridge.modal_jog_handler = self.modal_jog_requested.emit
        self.bridge.modal_press_handler = self.modal_press_requested.emit
        self.stop_grid_pad_requested.connect(self._toggle_editor_grid_path)
        self.bridge.menu_jog_handler = self.menu_jog_requested.emit
        self.bridge.menu_press_handler = self.menu_press_requested.emit
        self.bridge.main_jog_handler = self.main_jog_requested.emit
        self.bridge.main_press_handler = self.main_press_requested.emit
        self.bridge.br.stop_grid_ui_enabled = True
        self.bridge.br.stop_grid_pad_handler = self.stop_grid_pad_requested.emit
        self.bridge.stop_grid_pad_handler = self.stop_grid_pad_requested.emit

        self.resize(1120, 760)
        self.setMinimumSize(840, 600)
        root = QWidget()
        layout = QVBoxLayout(root)
        self.setCentralWidget(root)

        toolbar = QHBoxLayout()
        self._text_labels["title"] = QLabel()
        self._text_labels["title"].setObjectName("windowTitle")
        toolbar.addWidget(self._text_labels["title"])
        self.menu_status_label = QLabel("MENU OFF")
        toolbar.addWidget(self.menu_status_label)
        toolbar.addStretch(1)
        self._text_labels["language"] = QLabel()
        toolbar.addWidget(self._text_labels["language"])
        self.language_box = QComboBox()
        for code, name in LANGUAGE_NAMES.items():
            self.language_box.addItem(name, code)
        self.language_box.currentIndexChanged.connect(self._language_selected)
        toolbar.addWidget(self.language_box)
        self._text_labels["theme"] = QLabel()
        toolbar.addWidget(self._text_labels["theme"])
        self.theme_box = QComboBox()
        for theme in THEME_PALETTES:
            self.theme_box.addItem(theme.title(), theme)
        self.theme_box.currentIndexChanged.connect(self._theme_selected)
        toolbar.addWidget(self.theme_box)
        self.appearance_button = QPushButton("Appearance...")
        self.appearance_button.clicked.connect(self.show_appearance)
        toolbar.addWidget(self.appearance_button)
        import themes
        themes.bus.changed.connect(self._appearance_changed)
        self.licenses_button = QPushButton()
        self.licenses_button.clicked.connect(self.show_licenses)
        toolbar.addWidget(self.licenses_button)
        self.sheet_music_button = QPushButton("Show sheet music")
        self.sheet_music_button.clicked.connect(self.show_sheet_music)
        toolbar.addWidget(self.sheet_music_button)
        self.stave_button = QPushButton("Stave editor")
        self.stave_button.clicked.connect(self.show_stave_editor)
        toolbar.addWidget(self.stave_button)
        self.stop_grid_button = QPushButton("Stop grid")
        self.stop_grid_button.setCheckable(True)
        self.stop_grid_button.clicked.connect(self._stop_grid_button_changed)
        toolbar.addWidget(self.stop_grid_button)
        layout.addLayout(toolbar)

        self.lcd_box = QGroupBox()
        lcd_layout = QVBoxLayout(self.lcd_box)
        self.lcd_text = QLabel()
        self.lcd_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lcd_text.setFixedHeight(105)
        self.lcd_text.setObjectName("lcdText")
        lcd_layout.addWidget(self.lcd_text)
        layout.addWidget(self.lcd_box)

        self.main_tabs = QTabWidget()
        layout.addWidget(self.main_tabs, 1)
        live_page = QWidget()
        live_grid = QGridLayout(live_page)
        self.main_tabs.addTab(live_page, "Live / Main")

        self.setter_box = QGroupBox()
        setter_layout = QVBoxLayout(self.setter_box)
        self._text_labels["presets"] = QLabel()
        setter_layout.addWidget(self._text_labels["presets"])
        self.combination_list = QTreeWidget()
        self.combination_list.setColumnCount(3)
        self.combination_list.setHeaderLabels(["Setter combination / focused step", "ID", "Active"])
        self.combination_list.setWordWrap(False)
        self.combination_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.combination_list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.combination_list.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.combination_list.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.combination_list.setRootIsDecorated(True)
        self.combination_list.setItemDelegateForColumn(2, ActiveTickDelegate(self.combination_list))
        self.combination_list.setUniformRowHeights(True)
        self.combination_list.setMinimumHeight(260)
        self.combination_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.combination_list.itemSelectionChanged.connect(self._combination_selected)
        setter_layout.addWidget(self.combination_list, 1)
        setter_actions = QHBoxLayout()
        self.preset_direct_checkbox = QCheckBox()
        self.preset_direct_checkbox.toggled.connect(self._preset_mode_changed)
        setter_actions.addWidget(self.preset_direct_checkbox)
        self.edit_combination_button = QPushButton("Edit / save setter")
        self.edit_combination_button.clicked.connect(self._open_combination_editor)
        setter_layout.addLayout(setter_actions)

        self.bank_box = QGroupBox()
        bank_layout = QHBoxLayout(self.bank_box)
        self.bank_box_combo = QComboBox()
        self.bank_box_combo.currentIndexChanged.connect(self._bank_selected)
        bank_layout.addWidget(self.bank_box_combo, 1)
        self.marks_label = QLabel()
        bank_layout.addWidget(self.marks_label)
        stops_controls = QVBoxLayout()
        stops_controls.addWidget(self.bank_box)

        pads = QGridLayout()
        pads.setSpacing(8)
        for index in range(8):
            button = QPushButton()
            button.setMinimumHeight(58)
            button.setObjectName("padButton")
            button.clicked.connect(lambda checked=False, pad=index: self.bridge.post_ui_event("pad", pad))
            self._pad_buttons.append(button)
            pads.addWidget(button, index // 4, index % 4)
        stops_controls.addLayout(pads, 2)

        self.transport_box = QGroupBox()
        transport_layout = QGridLayout(self.transport_box)
        for index, (label_key, action) in enumerate(TRANSPORT_ACTIONS):
            button = QPushButton()
            if action == "metro":
                button.pressed.connect(self._metro_down)
                button.released.connect(self._metro_up)
                button.setCheckable(True)
                button.setAutoDefault(False)
            else:
                button.clicked.connect(lambda checked=False, name=action: self._transport_action(name))
            self._transport_buttons[label_key] = button
            transport_layout.addWidget(button, index // 2, index % 2)
        self.open_midi_button = QPushButton("Open MIDI...")
        self.open_midi_button.clicked.connect(self._open_midi_file)
        rows = (len(TRANSPORT_ACTIONS) + 1) // 2
        transport_layout.addWidget(self.open_midi_button, rows, 0, 1, 2)
        self.tempo_control = TempoControl(self.bridge.tempo)
        transport_layout.addWidget(self.tempo_control, rows + 1, 0, 1, 2)
        self.channels_button = QPushButton("Channels...")
        self.channels_button.setToolTip("Send each MIDI channel of the active file to another channel (manual) in GrandOrgue")
        self.channels_button.clicked.connect(self._midi_channels)
        transport_layout.addWidget(self.channels_button, rows + 2, 0, 1, 2)
        self.go_setup_button = QPushButton("GrandOrgue MIDI setup...")
        self.go_setup_button.setToolTip("Create / check the MIDI settings file that GrandOrgue must import")
        self.go_setup_button.clicked.connect(self._go_setup)
        transport_layout.addWidget(self.go_setup_button, rows + 4, 0, 1, 2)
        self.time_slider = polish.make_seek_slider()
        self.time_slider.setToolTip("Click or drag to move to a position in the MIDI file")
        self.time_slider.seek.connect(self._seek_file)
        self.time_slider.moved.connect(self._seek_preview)
        self.time_label = QLabel("0:00 / 0:00")
        transport_layout.addWidget(self.time_slider, rows + 5, 0, 1, 2)
        transport_layout.addWidget(self.time_label, rows + 6, 0, 1, 2)
        self.active_file_label = QLabel("MIDI: none")
        self.active_file_label.setWordWrap(True)
        transport_layout.addWidget(self.active_file_label, rows + 3, 0, 1, 2)
        self._file_timer = QTimer(self)
        self._file_timer.timeout.connect(self._refresh_active_file)
        self._file_timer.start(200)
        live_grid.addWidget(self.transport_box, 0, 2)

        self.volumes_box = QGroupBox()
        volumes_layout = QFormLayout(self.volumes_box)
        self._volumes_layout = volumes_layout
        for key in bridge.br.vol:
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 127)
            slider.setTracking(True)
            slider.sliderReleased.connect(lambda name=key, control=slider: self.bridge.post_ui_event(
                "volume", (name, control.value())))
            name_label = QLabel()
            self._volume_sliders[key] = slider
            self._volume_labels[key] = name_label
            volumes_layout.addRow(name_label, self._volume_field(key, slider))
        live_grid.addWidget(self.volumes_box, 1, 2)

        self.active_box = QGroupBox()
        active_layout = QVBoxLayout(self.active_box)
        self.active_list = QListWidget()
        self.active_list.setProperty("jogSkip", True)      # display-only; jog must not walk it
        self.active_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.active_list.setMinimumHeight(self.active_list.fontMetrics().height() * 8 + 28)
        active_layout.addWidget(self.active_list)
        self.mark_legend = QLabel()
        self.mark_legend.setWordWrap(False)
        self.mark_legend.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        active_layout.addWidget(self.mark_legend)
        stops_controls.addWidget(self.active_box, 1)
        live_grid.addWidget(self.setter_box, 0, 0, 2, 1)
        live_grid.addLayout(stops_controls, 0, 1, 2, 1)
        live_grid.setColumnStretch(0, 4)
        live_grid.setColumnStretch(1, 3)
        live_grid.setColumnStretch(2, 3)
        live_grid.setRowStretch(1, 1)

        setter_page = QWidget()
        setter_tools_layout = QVBoxLayout(setter_page)
        self.setter_edit_summary = QLabel()
        setter_tools_layout.addWidget(self.setter_edit_summary)
        setter_buttons = QGridLayout()
        for position, (label, action) in enumerate((
                ("Previous step", "previous_step"), ("Next step", "next_step"),
                ("Load", "load"), ("Save", "save"))):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, name=action: self._transport_action(name))
            setter_buttons.addWidget(button, position // 2, position % 2)
        setter_tools_layout.addLayout(setter_buttons)
        setter_tools_layout.addStretch(1)
        setter_tools_layout.addWidget(self.edit_combination_button)
        self.main_tabs.addTab(setter_page, "Setter Editing")

        files_page = QWidget()
        files_layout = QVBoxLayout(files_page)
        self.setter_files_list = QListWidget()
        self.setter_files_list.itemClicked.connect(self._edit_setter_file)
        files_layout.addWidget(self.setter_files_list, 1)
        file_actions = QHBoxLayout()
        self.import_combination_button = QPushButton("Import combination file...")
        self.import_combination_button.clicked.connect(self._import_combination_file)
        file_actions.addWidget(self.import_combination_button)
        self.open_combinations_button = QPushButton("Open combination folder")
        self.open_combinations_button.clicked.connect(self._open_combination_folder)
        file_actions.addWidget(self.open_combinations_button)
        files_layout.addLayout(file_actions)
        self.main_tabs.addTab(files_page, "Combination Files")

        couplings_page = QWidget()
        couplings_layout = QVBoxLayout(couplings_page)
        self.couplings_list = QListWidget()
        self.couplings_list.itemChanged.connect(self._coupling_changed)
        couplings_layout.addWidget(self.couplings_list)
        self.main_tabs.addTab(couplings_page, "Couplings")

        command_row = QHBoxLayout()
        self.command_box = QComboBox()
        self.command_box.setEditable(True)
        self.command_box.addItems(COMMAND_OPTIONS)
        command_line = self.command_box.lineEdit()
        if command_line is not None:
            command_line.returnPressed.connect(self._send_command)
        command_row.addWidget(self.command_box, 1)
        self.send_button = QPushButton()
        self.send_button.clicked.connect(self._send_command)
        command_row.addWidget(self.send_button)
        system_page = QWidget()
        system_page_layout = QVBoxLayout(system_page)
        system_page_layout.addLayout(command_row)

        self.diagnostics_box = QGroupBox()
        diagnostics_layout = QVBoxLayout(self.diagnostics_box)
        self.diagnostics_text = QTextEdit()
        self.diagnostics_text.setReadOnly(True)
        self.diagnostics_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        diagnostics_layout.addWidget(self.diagnostics_text)
        system_page_layout.addWidget(self.diagnostics_box, 1)
        system_actions = QHBoxLayout()
        for text, command in (("Recover", "recover"), ("Resync", "resync"), ("Panic", "panic"),
                              ("Clear log", "clear")):
            action_button = QPushButton(text)
            action_button.clicked.connect(lambda checked=False, value=command: self.bridge.post_ui_event("command", value))
            system_actions.addWidget(action_button)
        system_page_layout.addLayout(system_actions)
        config_actions = QHBoxLayout()
        config_path_label = QLabel(self.bridge.cfg_path)
        config_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        config_actions.addWidget(config_path_label, 1)
        open_config_button = QPushButton("Open config.yaml")
        open_config_button.clicked.connect(self._open_config_file)
        config_actions.addWidget(open_config_button)
        system_page_layout.addLayout(config_actions)
        self.main_tabs.addTab(system_page, "System Console")
        self.config_editor = ConfigEditor(self.bridge)
        self.main_tabs.addTab(self.config_editor, "Config")

        organ_page = QWidget()
        organ_layout = QVBoxLayout(organ_page)
        organ_path_row = QHBoxLayout()
        self.organ_path_edit = QLineEdit(self.bridge.organ_path)
        self.organ_path_edit.setPlaceholderText("GrandOrgue .organ file")
        self.organ_path_edit.textEdited.connect(
            lambda path: self.bridge.post_ui_event("organ_path", path)
        )
        organ_path_row.addWidget(self.organ_path_edit, 1)
        self.organ_browse_button = QPushButton("Browse...")
        self.organ_browse_button.clicked.connect(self._browse_organ)
        organ_path_row.addWidget(self.organ_browse_button)
        self.organ_import_button = QPushButton("Import organ")
        self.organ_import_button.clicked.connect(self._import_organ)
        organ_path_row.addWidget(self.organ_import_button)
        self.organ_cancel_button = QPushButton("Cancel import")
        self.organ_cancel_button.clicked.connect(lambda: self.bridge.post_ui_event("organ_cancel"))
        self.organ_cancel_button.setVisible(False)
        organ_path_row.addWidget(self.organ_cancel_button)
        organ_layout.addLayout(organ_path_row)
        self.organ_summary_label = QLabel()
        self.organ_summary_label.setWordWrap(True)
        organ_layout.addWidget(self.organ_summary_label)
        self.organ_settings_label = QLabel()
        self.organ_settings_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        organ_layout.addWidget(self.organ_settings_label)
        organ_layout.addStretch(1)
        self.main_tabs.addTab(organ_page, "Organ Selection")

        self.main_tabs.currentChanged.connect(self._on_main_tab_changed)

        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        live_grid.addWidget(self.status_label, 2, 0, 1, 2)

        self._apply_theme(self.bridge.theme)

        self.shortcuts = []
        for key in ("F1", "F2", "F3", "F4", "F5", "F8", "F9"):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(lambda name=key: self.bridge.post_ui_event("key", name))
            self.shortcuts.append(shortcut)

        space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)      # Space = play / stop (not while typing in a field)
        space.activated.connect(self._space_play)
        self.shortcuts.append(space)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_view)
        self.timer.start(150)
        self.modal_timer = QTimer(self)             # separate from refresh_view: Qt will not re-run a timer slot that
        self.modal_timer.timeout.connect(self._update_modal_flag)   # is itself blocked inside a popup's exec()
        self.modal_timer.start(40)
        self.refresh_view()
        # F10 is also Windows' "enter system menu" key; handle it ourselves so the window never gets stuck in
        # that mode, and leave through the normal close path.
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        if (event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress)
                and getattr(event, "key", lambda: None)() == Qt.Key.Key_F10 and self.isActiveWindow()):
            if event.type() == QEvent.Type.ShortcutOverride:
                event.accept()
            else:
                self.close()
            return True
        return super().eventFilter(obj, event)

    def _stop_grid_button_changed(self, checked):
        self._grid_close_pending = not checked
        self.bridge.post_ui_event("stop_grid_mode", bool(checked))

    def _stop_grid_popup_closed(self, preserve_mode):
        self._stop_grid_popup = None
        if not preserve_mode and not self._suppress_grid_close:
            self._grid_close_pending = True
            self.bridge.post_ui_event("stop_grid_mode", False)

    def _toggle_editor_grid_path(self, path):
        if self._active_editor_grid is not None:
            self._active_editor_grid.toggle_path(path)

    def _editor_grid_toggled(self, row, path, selected, table, grid):
        if row < 0 or row >= table.rowCount():
            return
        id_item = table.item(row, 0)
        if id_item is None:
            return
        paths = grid.selected_paths()
        if selected:
            paths.add(path)
        else:
            paths.discard(path)
        grid.set_selected_paths(paths)
        id_item.setData(Qt.ItemDataRole.UserRole, paths)
        self.bridge.post_ui_event("stop_grid_draft_paths", paths)

    def _toggle_live_grid_path(self, path, _checked):
        self.bridge.post_ui_event("toggle_grid_switch", path)

    def _sync_stop_grid_popup(self, snapshot):
        grid = snapshot["stop_grid"]
        stops = snapshot.get("available_stops", [])
        active_paths = snapshot.get("active_stop_paths", [])
        if not grid["mode"]:
            self._grid_close_pending = False
        should_show = (grid["available"] and grid["mode"] and grid["context"] == "live"
                       and not self._grid_close_pending)
        if should_show and self._stop_grid_popup is None:
            popup = StopGridDialog(self)
            popup.closed.connect(self._stop_grid_popup_closed)
            popup.grid.toggle_requested.connect(self._toggle_live_grid_path)
            self._stop_grid_popup = popup
            popup.animate_open()
        elif should_show and self._stop_grid_popup is not None and self._stop_grid_popup.is_closing:
            self._stop_grid_popup.animate_open()
        elif not should_show and self._stop_grid_popup is not None:
            self._stop_grid_popup.animate_close(preserve_mode=grid["mode"])
        if self._stop_grid_popup is not None:
            self._stop_grid_popup.grid.set_grid_data(
                stops, grid["mapped_paths"], active_paths, grid["rows"])
        if self._active_editor_grid is not None:
            self._active_editor_grid.set_grid_data(
                stops, grid["mapped_paths"], active_paths, grid["rows"])
        self.stop_grid_button.blockSignals(True)
        self.stop_grid_button.setChecked(grid["mode"])
        self.stop_grid_button.blockSignals(False)

    def _browse_organ(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, "Select GrandOrgue organ", lastdir.get("organ", os.path.dirname(self.organ_path_edit.text())),
            "GrandOrgue organ definitions (*.organ)",
        )
        if path:
            lastdir.put("organ", path)
            self.organ_path_edit.setText(path)
            self.bridge.post_ui_event("organ_path", path)

    def _import_organ(self):
        if getattr(self, "_organ_import_pending", False):
            export_path, _filter = QFileDialog.getOpenFileName(
                self, "Select GrandOrgue MIDI Settings export after importing the candidate",
                lastdir.get("yaml", os.path.dirname(self.bridge.cfg_path)), "YAML files (*.yaml *.yml)",
            )
            if export_path:
                lastdir.put("yaml", export_path)
                self.bridge.post_ui_event("organ_confirm", export_path)
            return
        organ_path = self.organ_path_edit.text().strip()
        if not organ_path:
            QMessageBox.warning(self, "Import organ", "Choose a GrandOrgue .organ file first.")
            return
        export_path, _filter = QFileDialog.getOpenFileName(
            self, "Select this organ's GrandOrgue MIDI Settings export",
            lastdir.get("yaml", os.path.dirname(self.bridge.cfg_path)), "YAML files (*.yaml *.yml)",
        )
        if export_path:
            lastdir.put("yaml", export_path)
            self.bridge.post_ui_event("organ_import", {
                "organ_path": organ_path,
                "midi_export": export_path,
            })

    def _import_combination_file(self):
        source, _filter = QFileDialog.getOpenFileName(
            self, "Import combination file", lastdir.get("yaml", os.path.dirname(self.bridge.cfg_path)),
            "GrandOrgue combination files (*.yaml *.yml)",
        )
        if not source:
            return
        lastdir.put("yaml", source)
        folder = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(self.bridge.cfg_path))),
            "Combinations", self.bridge.combination_set,
        )
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, os.path.basename(source))
        if os.path.exists(target):
            QMessageBox.warning(self, "Combination exists", f"A file named {os.path.basename(source)} already exists.")
            return
        try:
            shutil.copy2(source, target)
        except OSError as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        self.bridge.post_ui_event("reload_combinations")

    def _coupling_changed(self, row):
        if row is not None:
            cc = row.data(Qt.ItemDataRole.UserRole)
            if cc is not None:
                self.bridge.post_ui_event("toggle_switch", int(cc))

    def _open_combination_folder(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(self.bridge.cfg_path))),
            "Combinations", self.bridge.combination_set,
        )
        os.makedirs(path, exist_ok=True)
        os.startfile(path)

    def _open_config_file(self):
        if os.path.isfile(self.bridge.cfg_path):
            os.startfile(self.bridge.cfg_path)

    def _t(self, key, **values):
        return translate(self._language or "en", key, **values)

    def apply_language(self, language):
        self._language = language
        self.setWindowTitle(self._t("title"))
        self._text_labels["title"].setText(self._t("title"))
        self._text_labels["language"].setText(self._t("gui_language"))
        self._text_labels["theme"].setText(self._t("gui_theme"))
        self.licenses_button.setText(self._t("gui_licenses"))
        self.sheet_music_button.setText("Show sheet music")
        self.lcd_box.setTitle(self._t("lcd"))
        self.setter_box.setTitle(self._t("gui_presets"))
        self._text_labels["presets"].setText(self._t("gui_presets"))
        self.bank_box.setTitle(self._t("gui_bank"))
        self.transport_box.setTitle(self._t("gui_transport"))
        self.volumes_box.setTitle(self._t("gui_volumes"))
        self.active_box.setTitle(self._t("gui_active_stops"))
        self.diagnostics_box.setTitle(self._t("gui_diagnostics"))
        self.command_box.setPlaceholderText(self._t("gui_command"))
        self.send_button.setText(self._t("gui_send"))
        self.preset_direct_checkbox.setText(self._t("gui_preset_direct"))
        self.edit_combination_button.setText("Edit / save setter")
        for label_key, button in self._transport_buttons.items():
            button.setText(self._t(label_key))
        for key, label in self._volume_labels.items():
            label.setText(self._t(f"volume_{key}") if key in ("master", "pedal", "hw", "sw", "sl", "noises", "swell")
                          else VOLS[key][2])
        self.mark_legend.setText(self._t("gui_marks_legend"))
        metro_button = self._transport_buttons["gui_metro"]
        metro_button.setToolTip(self._t("gui_metro_tempo"))
        for index, theme in enumerate(THEME_PALETTES):
            self.theme_box.setItemText(index, self._t(f"theme_{theme}"))

    def _language_selected(self, index):
        code = self.language_box.itemData(index)
        if code and code != self._language:
            self.bridge.post_ui_event("command", f"language {code}")

    def _bank_selected(self, index):
        if index >= 0:
            self.bridge.post_ui_event("bank", index)

    def _combination_selected(self):
        items = self.combination_list.selectedItems()
        if not items:
            return
        item = items[0]
        index = item.data(0, Qt.ItemDataRole.UserRole)
        if index is None and item.childCount() > 0:
            # A parent row is the file name itself, not a step -- clicking it
            # should cue that file's first (000) step, not do nothing.
            index = item.child(0).data(0, Qt.ItemDataRole.UserRole)
        if index is not None and index != self._last_preset_event_index:
            self._last_preset_event_index = index
            self.bridge.post_ui_event("combination", int(index))

    def _show_navigate_confirm(self, pending):
        box = QMessageBox(QApplication.activeWindow() or self)       # on top of the sheet music window if it is open
        box.setWindowTitle("Unsaved registration")
        box.setText(
            f"The stops currently drawn don't match \"{pending['current_name']}\".\n"
            f"Save them before moving to \"{pending['target_name']}\"?"
        )
        update_button = box.addButton("Update existing", QMessageBox.ButtonRole.AcceptRole)
        save_new_button = box.addButton("Save as new...", QMessageBox.ButtonRole.ActionRole)
        discard_button = box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(cancel_button)
        self.bridge.modal_open.set()
        box.exec()
        clicked = box.clickedButton()
        self._confirm_navigate_open = False
        if clicked is update_button:
            self.bridge.post_ui_event("confirm_navigate", "update")
        elif clicked is save_new_button:
            # Cancel the pending move (stay put) and open the full editor so
            # they can name a file properly; it opens pre-loaded with the
            # currently-selected combination's steps, with a new step added
            # and pre-checked with exactly what's currently drawn.
            self.bridge.post_ui_event("confirm_navigate", "cancel")
            self._open_combination_editor(prefill_live_stops=True)
        elif clicked is discard_button:
            self.bridge.post_ui_event("confirm_navigate", "discard")
        else:
            self.bridge.post_ui_event("confirm_navigate", "cancel")

    def _open_combination_editor(self, prefill_live_stops=False):
        if prefill_live_stops:
            # "Save as new": a brand-new setter file holding ONE step with exactly the stops drawn now. It is not a
            # copy of whichever file happens to be selected, and it never touches an existing file.
            selected = {"internal_id": "000", "filename": ""}
            steps = []
            initial_filename = ""
            initial_signature = ()
            default_name = "New setter"
            taken = {item["filename"].rsplit(".", 1)[0].casefold() for item in self._combination_snapshot}
            counter = 1
            while default_name.casefold() in taken:
                counter += 1
                default_name = f"New setter {counter}"
        else:
            items = self.combination_list.selectedItems()
            if not items:
                return
            selected_index = items[0].data(0, Qt.ItemDataRole.UserRole)
            if selected_index is None:
                return
            selected_index = int(selected_index)
            selected = self._combination_snapshot[selected_index]
            filename = selected["filename"]
            steps = [item for item in self._combination_snapshot if item["filename"] == filename]
            initial_filename = filename.rsplit(".", 1)[0]
            default_name = initial_filename
            initial_signature = tuple(
                (step["internal_id"], step["name"], frozenset(step.get("switch_paths", [])))
                for step in steps
            )

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit setter combination")
        dialog.setMinimumSize(700, 420)
        avail = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        dialog.resize(min(1300, int(avail.width() * 0.9)), min(760, int(avail.height() * 0.9)))   # fluid, fits the screen
        layout = QVBoxLayout(dialog)
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Setter file"))
        filename_edit = QLineEdit(default_name)
        file_row.addWidget(filename_edit, 1)
        layout.addLayout(file_row)

        body = QSplitter(Qt.Orientation.Horizontal)   # drag the handle to rebalance the two panes
        body.setChildrenCollapsible(False)
        left_column = QVBoxLayout()
        table = QTableWidget(len(steps), 2)
        table.setHorizontalHeaderLabels(["Internal ID", "Focused name"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for row, step in enumerate(steps):
            id_item = QTableWidgetItem(step["internal_id"])
            # Each step's chosen stops travel with its ID cell as item data,
            # so they survive row insertion/removal/reordering without a
            # separate row-index-keyed lookup that could drift out of sync.
            id_item.setData(Qt.ItemDataRole.UserRole, set(step.get("switch_paths", [])))
            table.setItem(row, 0, id_item)
            table.setItem(row, 1, QTableWidgetItem(step["name"]))
        table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed
                              | QTableWidget.EditTrigger.SelectedClicked)   # steps edit inline
        table.setWordWrap(True)
        left_widget = QWidget()
        left_widget.setMinimumWidth(200)      # guided sizes: steps start narrow, grid is the focus, both resizable
        left_widget.setLayout(left_column)
        left_column.setContentsMargins(0, 0, 0, 0)
        left_column.addWidget(table, 1)
        row_actions = QHBoxLayout()
        add_button = QPushButton("Add internal step")
        remove_button = QPushButton("Remove selected")
        row_actions.addWidget(add_button)
        row_actions.addWidget(remove_button)
        row_actions.addStretch(1)
        left_column.addLayout(row_actions)
        body.addWidget(left_widget)

        right_column = QVBoxLayout()
        right_column.addWidget(QLabel("Stops for the selected step"))
        stop_grid = StopGridWidget(draft=True)
        grid_snapshot = self.bridge.get_snapshot().get("stop_grid", {})
        stop_grid.set_grid_data(
            self._available_stops, grid_snapshot.get("mapped_paths", []), self._active_stop_paths,
            grid_snapshot.get("rows", []), draft_paths=set())
        stop_grid.toggle_requested.connect(
            lambda path, selected: self._editor_grid_toggled(current_row[0], path, selected, table, stop_grid))
        right_column.addWidget(stop_grid, 1)
        right_widget = QWidget()
        right_widget.setMinimumWidth(420)
        right_widget.setLayout(right_column)
        right_column.setContentsMargins(0, 0, 0, 0)
        body.addWidget(right_widget)
        body.setStretchFactor(0, 1)           # on window resize the grid takes most of the change
        body.setStretchFactor(1, 4)
        body.setSizes([300, 1000])            # initial guide: about 1:3.3
        layout.addWidget(body, 1)
        layout.addWidget(QSizeGrip(dialog), 0, Qt.AlignmentFlag.AlignRight)

        current_row = [-1]  # mutable box so the nested closures below can update it

        def commit_current_row():
            row = current_row[0]
            if row < 0 or row >= table.rowCount():
                return
            id_item = table.item(row, 0)
            if id_item is None:
                return
            id_item.setData(Qt.ItemDataRole.UserRole, stop_grid.selected_paths())

        def load_row(row):
            id_item = table.item(row, 0) if 0 <= row < table.rowCount() else None
            chosen = id_item.data(Qt.ItemDataRole.UserRole) if id_item is not None else set()
            chosen = chosen or set()
            stop_grid.set_selected_paths(chosen)
            self.bridge.post_ui_event("stop_grid_draft_paths", chosen)
            current_row[0] = row

        def row_selected():
            commit_current_row()
            rows = {index.row() for index in table.selectedIndexes()}
            load_row(min(rows) if rows else -1)

        table.itemSelectionChanged.connect(row_selected)
        if steps:
            table.selectRow(0)

        if prefill_live_stops:
            commit_current_row()
            used = set()
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                if item is not None:
                    used.add(item.text())
            number = 0
            while f"{number:03d}" in used:
                number += 1
            row = table.rowCount()
            table.insertRow(row)
            id_item = QTableWidgetItem(f"{number:03d}")
            id_item.setData(Qt.ItemDataRole.UserRole, set(self._active_stop_paths))
            table.setItem(row, 0, id_item)
            table.setItem(row, 1, QTableWidgetItem("New combination"))
            table.selectRow(row)

        def add_step():
            commit_current_row()
            used = set()
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                if item is not None:
                    used.add(item.text())
            number = 0
            while f"{number:03d}" in used:
                number += 1
            # New steps default to a copy of whichever step was selected
            # before "Add" was pressed, since that's usually the closest
            # starting point -- pick the stops you actually want from there.
            selected_item = (table.item(current_row[0], 0)
                             if 0 <= current_row[0] < table.rowCount() else None)
            starting_stops = (set(selected_item.data(Qt.ItemDataRole.UserRole) or set())
                              if selected_item is not None else set())
            row = table.rowCount()
            table.insertRow(row)
            id_item = QTableWidgetItem(f"{number:03d}")
            id_item.setData(Qt.ItemDataRole.UserRole, starting_stops)
            table.setItem(row, 0, id_item)
            table.setItem(row, 1, QTableWidgetItem(f"Step {number:03d}"))
            table.selectRow(row)

        def remove_step():
            rows = sorted({index.row() for index in table.selectedIndexes()}, reverse=True)
            for row in rows:
                table.removeRow(row)
            current_row[0] = -1

        add_button.clicked.connect(add_step)
        remove_button.clicked.connect(remove_step)

        def is_dirty():
            commit_current_row()
            if filename_edit.text().strip() != initial_filename:
                return True
            signature_rows = []
            for row in range(table.rowCount()):
                id_item = table.item(row, 0)
                name_item = table.item(row, 1)
                if id_item is not None and name_item is not None:
                    signature_rows.append((
                        id_item.text(), name_item.text(),
                        frozenset(id_item.data(Qt.ItemDataRole.UserRole) or set()),
                    ))
            current_signature = tuple(signature_rows)
            return current_signature != initial_signature

        def handle_cancel():
            # Covers both the Cancel button and the window's own close (X)
            # button, since QDialog routes both through reject() by default.
            if is_dirty():
                choice = QMessageBox.question(
                    dialog, "Unsaved changes",
                    "This setter has unsaved changes. Save before closing?",
                    QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel,
                )
                if choice == QMessageBox.StandardButton.Save:
                    dialog.accept()
                    return
                if choice == QMessageBox.StandardButton.Cancel:
                    return  # stay in the dialog, nothing discarded
            QDialog.reject(dialog)  # the real Qt method; dialog.reject is overridden above

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(handle_cancel)
        dialog.reject = handle_cancel  # also catches the window's X close button
        layout.addWidget(buttons)
        self._active_editor_grid = stop_grid
        self.bridge.post_ui_event("stop_grid_context", "draft")
        self.bridge.post_ui_event("stop_grid_draft_paths", stop_grid.selected_paths())
        try:
            dialog_result = dialog.exec()
        finally:
            self._active_editor_grid = None
            self.bridge.post_ui_event("stop_grid_context", "live")
            self.bridge.post_ui_event("stop_grid_draft_paths", [])
        if dialog_result != QDialog.DialogCode.Accepted:
            return
        commit_current_row()
        if prefill_live_stops:
            taken = {item["filename"].rsplit(".", 1)[0].casefold() for item in self._combination_snapshot}
            base = filename_edit.text().strip() or "New setter"
            name, counter = base, 1
            while name.casefold() in taken:          # never overwrite an existing setter file
                counter += 1
                name = f"{base} {counter}"
            filename_edit.setText(name)
        edited_steps = []
        for row in range(table.rowCount()):
            id_item = table.item(row, 0)
            name_item = table.item(row, 1)
            if id_item is not None and name_item is not None:
                edited_steps.append({
                    "id": id_item.text(),
                    "name": name_item.text(),
                    "stops": sorted(id_item.data(Qt.ItemDataRole.UserRole) or set()),
                })
        self.bridge.post_ui_event("save_combination", {
            "filename": filename_edit.text().strip(),
            "selected_id": selected["internal_id"],
            "steps": edited_steps,
        })

    def _preset_mode_changed(self, checked):
        self.bridge.post_ui_event("preset_activation", "direct" if checked else "staged")

    def _theme_selected(self, index):
        theme = self.theme_box.itemData(index)
        if theme:
            self._apply_theme(theme)
            self.bridge.post_ui_event("theme", theme)

    def _apply_theme(self, theme):
        """Global theme: one palette + style sheet on the QApplication (themes.py) so every window and dialog follows."""
        self._theme_now = theme
        import themes
        themes.apply(theme)
        self._theme_children()

    def _theme_children(self):
        """Child windows only need their icons redrawn in the new text colour."""
        import themes
        palette = themes.tokens()
        palette = dict(palette, text=palette["text"])
        stave = getattr(self, "stave_window", None)
        if stave is not None and hasattr(stave, "apply_theme"):
            stave.apply_theme(palette, "")

    def _appearance_changed(self):
        import themes
        mode = themes.state()["mode"]
        index = self.theme_box.findData(mode)
        if index >= 0 and index != self.theme_box.currentIndex():
            self.theme_box.blockSignals(True)
            self.theme_box.setCurrentIndex(index)
            self.theme_box.blockSignals(False)
            self._theme_now = mode
            self.bridge.post_ui_event("theme", mode)
        self._theme_children()

    def show_appearance(self):
        from themes_ui import AppearanceDialog
        dialog = AppearanceDialog(self, getattr(self, "stave_window", None))
        dialog.exec()

    def _theme_css(self, palette):
        return (f"""
            QMainWindow, QWidget {{ background: {palette['background']}; color: {palette['text']}; }}
            QGroupBox {{ background: {palette['surface']}; border: 1px solid {palette['border']}; border-radius: 4px; margin-top: 9px; padding: 8px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {palette['accent']}; }}
            QCheckBox::indicator, QListView::indicator, QTreeView::indicator {{ width: 14px; height: 14px; border: 1px solid {palette['accent']}; background: {palette['input']}; border-radius: 3px; }}
            QCheckBox::indicator:checked, QListView::indicator:checked, QTreeView::indicator:checked {{ background: {palette['accent']}; }}
            QLabel#windowTitle {{ color: {palette['accent']}; font-size: 18px; font-weight: 600; }}
            QLabel#lcdText {{ background: {palette['surface']}; color: {palette['text']}; font-size: 17px; font-weight: 600; }}
            QPushButton, QComboBox, QLineEdit, QTreeWidget {{
                background: {palette['input']}; color: {palette['text']};
                border: 1px solid {palette['border']}; border-radius: 3px; padding: 6px;
            }}
            QPushButton:hover, QComboBox:hover, QLineEdit:hover {{ border-color: {palette['accent']}; }}
            QPushButton:pressed, QComboBox:on {{ background: {palette['surface']}; border-color: {palette['accent']}; }}
            QComboBox::drop-down {{
                subcontrol-origin: padding; subcontrol-position: top right;
                width: 24px; border-left: 1px solid {palette['border']};
                background: {palette['surface']};
            }}
            QComboBox::down-arrow {{
                image: none; width: 0; height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {palette['text']};
            }}
            QComboBox QAbstractItemView {{
                background: {palette['input']}; color: {palette['text']};
                border: 1px solid {palette['border']};
                selection-background-color: {palette['accent']};
                selection-color: {contrast_text(palette['accent'])};
                outline: 0;
            }}
            QTreeView::item:selected, QListView::item:selected, QTableView::item:selected,
            QTreeView::item:selected:!active, QListView::item:selected:!active, QTableView::item:selected:!active {{
                background: {palette['accent']}; color: {contrast_text(palette['accent'])};
            }}
            QTreeView::indicator:checked, QTreeView::indicator:checked:selected {{ background: #f2a33a; border: 1px solid #202327; }}
            QTreeView::indicator:unchecked:selected {{ background: #ffffff; border: 1px solid #202327; }}
            QTreeView::item:hover:!selected, QListView::item:hover:!selected, QTableView::item:hover:!selected {{
                background: {palette['border']};
            }}
            QPushButton#padButton {{ font-weight: 600; }}
            QSlider::groove:horizontal {{ height: 6px; background: {palette['border']}; border-radius: 3px; }}
            QSlider::handle:horizontal {{ width: 14px; margin: -5px 0; background: {palette['accent']}; border-radius: 7px; }}
            QTextEdit {{ background: {palette['input']}; border: 0; color: {palette['text']}; }}
            QLabel#statusLabel {{ background: {palette['surface']}; padding: 7px; color: {palette['text']}; }}
            QLabel, QCheckBox, QRadioButton {{ background: transparent; }}
            QToolBar {{ background: {palette['surface']}; border: none; }}
            QToolButton {{ color: {palette['text']}; }}
            QToolButton:hover {{ background: {palette['border']}; }}
            QScrollArea, QSplitter {{ background: {palette['background']}; }}
            QDockWidget {{ color: {palette['text']}; }}
            QDockWidget::title {{ background: {palette['surface']}; padding: 4px; }}
            QStatusBar, QMenu, QSpinBox, QDoubleSpinBox, QListWidget {{ background: {palette['input']}; color: {palette['text']}; }}
        """) + polish.extra_css(palette)

    def _metro_down(self):
        self._metro_pressed = True
        self.bridge.post_ui_event("metro_down")

    def _metro_up(self):
        self._metro_pressed = False
        self.bridge.post_ui_event("metro_up")

    def _seek_file(self, value):
        length = getattr(self.bridge, "take_length", 0.0) or 0.0
        if length > 0 and getattr(self.bridge, "take_to_play", None):
            self.bridge.post_ui_event("take_seek", value / 1000.0 * length)

    def _seek_preview(self, value):
        length = getattr(self.bridge, "take_length", 0.0) or 0.0
        t = value / 1000.0 * length
        self.time_label.setText(f"{int(t) // 60}:{int(t) % 60:02d} / {int(length) // 60}:{int(length) % 60:02d}")

    def _space_play(self):
        from PySide6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit, QTextEdit, QAbstractSpinBox
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QPlainTextEdit, QTextEdit, QAbstractSpinBox)):
            return
        self.bridge.post_ui_event("take_toggle")

    def _refresh_active_file(self):
        path = getattr(self.bridge, "take_to_play", None)
        playing = getattr(getattr(self.bridge, "take_player", None), "active", False)
        recording = getattr(self.bridge, "midi_rec", None) is not None
        text = "Recording..." if recording else ("Loaded: " + os.path.basename(path) if path else "MIDI: nothing loaded")
        self.active_file_label.setText(text + ("  [PLAYING]" if playing else ""))
        self.active_file_label.setToolTip((path or "") + "\n" + getattr(self.bridge, "take_info", ""))
        length = getattr(self.bridge, "take_length", 0.0) or 0.0
        pos = getattr(getattr(self.bridge, "take_player", None), "position", lambda: None)() if playing else None
        if pos is None:
            pos = 0.0 if not playing else 0.0
        if length > 0 and not self.time_slider.dragging:
            self.time_slider.setValue(int(min(1.0, pos / length) * 1000))
        fmt = lambda t: f"{int(t) // 60}:{int(t) % 60:02d}"
        self.time_label.setText(f"{fmt(pos)} / {fmt(length)}")

    def _open_midi_file(self):
        folder = lastdir.get("midi", getattr(self.bridge, "midi_dir", "") or "")
        path, _ = QFileDialog.getOpenFileName(self, "Open MIDI file", folder, "MIDI files (*.mid *.midi *.kar)")
        if path:
            lastdir.put("midi", path)
            self.bridge.post_ui_event("take_open", path)

    def _go_setup(self):
        """Check / create the GrandOrgue import file, open its folder, test the four manual channels."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout
        import go_midi_setup
        dlg = QDialog(self)
        dlg.setWindowTitle("GrandOrgue MIDI setup")
        lay = QVBoxLayout(dlg)
        info = QLabel()
        info.setWordWrap(True)
        lay.addWidget(info)
        lay.addWidget(QLabel("GrandOrgue only plays MIDI files / takes when it has the settings below imported.\n"
                             "1. Create the file here.   2. In GrandOrgue: Organ settings > MIDI > Import, choose it.\n"
                             "3. Press Test: you should hear Pedal, Hauptwerk, Schwellwerk, Solowerk in turn."))

        def refresh():
            kind, text = go_midi_setup.status()
            st = go_midi_setup._load()
            info.setText(f"{text}\nExport used: {st.get('source', '-')}\nImport file: {st.get('output', '-')}")

        def create():
            try:
                dst, _ = go_midi_setup.build()
                QMessageBox.information(dlg, "GrandOrgue", f"Created:\n{dst}\n\nNow import it in GrandOrgue.")
            except Exception as exc:
                QMessageBox.warning(dlg, "GrandOrgue", str(exc))
            refresh()

        def choose():
            f, _ = QFileDialog.getOpenFileName(dlg, "GrandOrgue MIDI settings export", lastdir.get("yaml", go_midi_setup.default_folder()),
                                               "YAML (*.yaml *.yml)")
            if f:
                lastdir.put("yaml", f)
                st = go_midi_setup._load()
                st["source"] = f
                go_midi_setup._save(st)
                create()

        row = QHBoxLayout()
        for text, fn in (("Choose export...", choose), ("Create import file now", create),
                         ("Open folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(go_midi_setup.default_folder()))),
                         ("Test manuals", lambda: self.bridge.post_ui_event("test_manuals"))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        refresh()
        dlg.exec()

    def _midi_channels(self):
        """Per-file channel remap (sidecar <file>.chmap.json): which GrandOrgue channel/manual each channel plays on."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QSpinBox
        path = getattr(self.bridge, "take_to_play", None)
        if not path:
            QMessageBox.information(self, "Channels", "No MIDI file is active.")
            return
        folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "midi_stave")
        if folder not in sys.path:
            sys.path.insert(0, folder)
        import sessionmeta
        channels = sessionmeta.channels_in(path)
        if not channels:
            QMessageBox.information(self, "Channels", "The file has no notes.")
            return
        current = sessionmeta.channel_map(path)
        dialog = QDialog(self)
        dialog.setWindowTitle("Channels - " + os.path.basename(path))
        form = QFormLayout(dialog)
        spins = {}
        from PySide6.QtWidgets import QComboBox
        manuals = sessionmeta.manual_channels()
        for ch in channels:
            box = QComboBox()
            box.addItem("as in the file", ch)
            for name, _path, mch in manuals:
                box.addItem(f"{name} (channel {mch})", mch - 1)
            index = box.findData(current.get(ch, ch))
            box.setCurrentIndex(index if index >= 0 else 0)
            spins[ch] = box
            form.addRow(f"File channel {ch + 1} plays on", box)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            sessionmeta.save_channel_map(path, {ch: box.currentData() for ch, box in spins.items()})

    def _save_midi_as(self):
        current = getattr(self.bridge, "take_to_play", None)
        if not current:
            QMessageBox.information(self, "Save", "No MIDI file is active.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save MIDI file as", lastdir.get("midi_save", os.path.dirname(current)) + os.sep + os.path.basename(current), "MIDI files (*.mid *.midi *.kar)")
        if path:
            lastdir.put("midi_save", path)
            self.bridge.post_ui_event("take_saveas", path)

    def _transport_action(self, name):
        if name in ("previous_file", "next_file") and self._metro_pressed:
            self.bridge.post_ui_event("metro_adjust", -1 if name == "previous_file" else 1)
        elif name in ("previous_file", "next_file"):
            self.bridge.post_ui_event("take_file", -1 if name == "previous_file" else 1)
        elif name == "save":
            self._save_midi_as()
        else:
            self.bridge.post_ui_event("transport", name)

    # ------------------------------------------------- hardware jog traversal
    # The jog walks every enabled, visible control on the active tab in creation order:
    # buttons, checkboxes, combo boxes, and each row of every list. Anything added to a
    # tab later is picked up automatically. Jog press activates the focused control.
    def _edit_setter_file(self, item):
        """Open the editor on a setter file. Selects its first step WITHOUT signalling the backend,
        so merely opening the editor never cues or loads anything on the organ."""
        filename = item.text()
        for index, combination in enumerate(self._combination_snapshot):
            if combination["filename"] == filename:
                self.combination_list.blockSignals(True)
                self._select_combination_row(index)
                self.combination_list.blockSignals(False)
                self._open_combination_editor()
                return

    def _select_combination_row(self, index):
        for parent_index in range(self.combination_list.topLevelItemCount()):
            parent = self.combination_list.topLevelItem(parent_index)
            if parent is None:
                continue
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                if child.data(0, Qt.ItemDataRole.UserRole) == index:
                    self.combination_list.setCurrentItem(child)
                    self.combination_list.scrollToItem(child)
                    return

    def _on_main_tab_changed(self, index):
        self._menu_cursor = None
        self._main_cursor = None
        self.bridge.post_ui_event("menu_tab", index)

    def _main_jog(self, direction):
        tab = self.main_tabs.currentIndex()
        if tab == 0:
            self.bridge.post_ui_event("navigate_combination", direction)
            return
        if tab == 2:
            widget = self.setter_files_list
        elif tab == 3:
            widget = self.couplings_list
        elif tab == 4:
            widget = self.command_box
        else:
            page = self.main_tabs.widget(tab)
            widgets = page.findChildren(QPushButton) if page is not None else []
            if not widgets:
                return
            if self._main_cursor is None or self._main_cursor >= len(widgets):
                self._main_cursor = 0 if direction > 0 else len(widgets) - 1
            else:
                self._main_cursor = (self._main_cursor + direction) % len(widgets)
            widgets[self._main_cursor].setFocus()
            self.bridge.post_ui_event("menu_focus", widgets[self._main_cursor].text())
            return
        if isinstance(widget, QListWidget):
            count = widget.count()
            if not count:
                return
            current = widget.currentRow()
            self._main_cursor = (current + direction) % count if current >= 0 else (0 if direction > 0 else count - 1)
            widget.setCurrentRow(self._main_cursor)
            item = widget.item(self._main_cursor)
            self.bridge.post_ui_event("menu_focus", item.text() if item else "")
        elif isinstance(widget, QComboBox) and widget.count():
            self._main_cursor = (widget.currentIndex() + direction) % widget.count()
            widget.setCurrentIndex(self._main_cursor)
            self.bridge.post_ui_event("menu_focus", widget.currentText())

    def _main_press(self):
        tab = self.main_tabs.currentIndex()
        if tab == 0:
            self.bridge.post_ui_event("transport", "load")
        elif tab == 2:
            item = self.setter_files_list.currentItem()
            if item is not None:
                self._edit_setter_file(item)
        elif tab == 3:
            item = self.couplings_list.currentItem()
            if item is not None:
                item.setCheckState(
                    Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )
        elif tab == 4:
            self._send_command()
        else:
            page = self.main_tabs.widget(tab)
            widgets = page.findChildren(QPushButton) if page is not None else []
            if widgets:
                index = self._main_cursor or 0
                if index < len(widgets):
                    widgets[index].click()

    def _menu_targets(self):
        page = self.main_tabs.currentWidget()
        targets = []
        if page is None:
            return targets
        for widget in page.findChildren(QWidget):
            if not widget.isEnabled() or not widget.isVisibleTo(page) or widget.property("jogSkip"):
                continue
            if isinstance(widget, QListWidget):
                targets.extend((widget, row) for row in range(widget.count()))
            elif isinstance(widget, (QPushButton, QCheckBox, QComboBox)):
                targets.append((widget, None))
        return targets

    @staticmethod
    def _menu_is_tickbox(item):
        # Qt's default list-item flags always include "user checkable"; only rows that were
        # actually given a check state (e.g. the Couplings rows) are real tickboxes.
        return bool(item.flags() & Qt.ItemFlag.ItemIsUserCheckable) and \
            item.data(Qt.ItemDataRole.CheckStateRole) is not None

    @staticmethod
    def _menu_describe(target):
        widget, row = target
        if row is not None:
            item = widget.item(row)
            if BridgeWindow._menu_is_tickbox(item):
                return ("[x] " if item.checkState() == Qt.CheckState.Checked else "[ ] ") + item.text()
            return "> " + item.text()
        if isinstance(widget, QCheckBox):
            return ("[x] " if widget.isChecked() else "[ ] ") + widget.text()
        if isinstance(widget, QComboBox):
            return "< " + widget.currentText() + " >"
        return "> " + widget.text()

    def _menu_focus(self, target):
        widget, row = target
        if row is not None:
            widget.setCurrentRow(row)
        widget.setFocus()
        self.bridge.post_ui_event("menu_focus", self._menu_describe(target))

    def _menu_move(self, direction):
        targets = self._menu_targets()
        if not targets:
            self.bridge.post_ui_event("menu_focus", "(nothing here)")
            return
        if self._menu_cursor is None or self._menu_cursor >= len(targets):
            cursor = 0 if direction > 0 else len(targets) - 1
        else:
            cursor = (self._menu_cursor + direction) % len(targets)
        self._menu_cursor = cursor
        self._menu_focus(targets[cursor])

    def _menu_press(self):
        targets = self._menu_targets()
        if self._menu_cursor is None or self._menu_cursor >= len(targets):
            return
        target = targets[self._menu_cursor]
        widget, row = target
        if row is not None:
            item = widget.item(row)
            if self._menu_is_tickbox(item):
                item.setCheckState(
                    Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked
                )
            else:
                widget.itemClicked.emit(item)
        elif isinstance(widget, QCheckBox):
            widget.toggle()
        elif isinstance(widget, QComboBox):
            widget.setCurrentIndex((widget.currentIndex() + 1) % max(1, widget.count()))
        else:
            widget.click()
        self._menu_focus(target)

    def _send_command(self):
        text = self.command_box.currentText().strip()
        if text:
            self.bridge.post_ui_event("command", text)
            self.command_box.setCurrentText("")

    def show_licenses(self):
        QMessageBox.information(self, self._t("gui_licenses"), self._t("gui_license_notice"))

    def show_stave_editor(self):
        """MIDI to Stave editor (midi_stave folder next to this file), opened like the sheet music viewer."""
        try:
            if getattr(self, "stave_window", None) is None:
                folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "midi_stave")
                if folder not in sys.path:
                    sys.path.insert(0, folder)
                import midi_stave as stave_module           # midi_stave/midi_stave.py
                if not hasattr(stave_module, "Stave"):
                    stave_module = importlib.import_module("midi_stave.midi_stave")
                stave_module.render.init_verovio()
                self.stave_window = stave_module.Stave()
                self.stave_window.set_tempo_controller(self.bridge.tempo)
                self.stave_window.play_hook = lambda path, offset=0.0: self.bridge.post_ui_event("preview_play", f"{path}|@{offset}")
                self.stave_window.seek_hook = lambda t: self.bridge.post_ui_event("take_seek", t)
                self.stave_window.stop_hook = lambda: self.bridge.post_ui_event("preview_stop")
                self.stave_window.pos_hook = lambda: self.bridge.take_player.position()
                self.stave_window.chord_hook = lambda items, hold: self.bridge.post_ui_event("chord", (items, hold))
                self.stave_window.gate_hook = lambda on, items: self.bridge.post_ui_event("gate", (on, items))
                self.bridge.stave_step_hook = self.stave_window.hw_step
                midi_dir = getattr(self.bridge, "midi_dir", "")
                if midi_dir and hasattr(self.stave_window, "default_dir"):
                    self.stave_window.default_dir = midi_dir
            self._theme_children()
            self.stave_window.show()
            self.stave_window.raise_()
            self.stave_window.activateWindow()
        except Exception as exc:
            QMessageBox.warning(self, "Stave editor", f"Could not open the stave editor: {exc}\n"
                                "Install its libraries: pip install music21 verovio mido")

    def show_sheet_music(self):
        if self.sheet_music_window is None:
            self.sheet_music_window = SheetMusicWindow(self)
            self._theme_children()
        self.bridge.sheet_music_navigation_enabled.set()
        self.sheet_music_window.show()
        self.sheet_music_window.raise_()
        self.sheet_music_window.activateWindow()

    def _navigate_sheet_music(self, direction):
        if self.sheet_music_window is not None:
            self.sheet_music_window.navigate_score(direction)

    def _volume_field(self, key, slider):
        """The slider with a small status light beside it: bright green when the division this volume belongs to
        has stops drawn, dim red when it has none, grey when the volume has no stops at all (noises)."""
        led = QLabel()
        led.setFixedSize(14, 14)
        led.setToolTip("Bright green: this volume's stops are in use. Dim red: none are drawn.")
        self._volume_leds[key] = led
        self._set_volume_led(led, None)
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(led)
        row.addWidget(slider, 1)
        return holder

    @staticmethod
    def _set_volume_led(led, active):
        colour = "#2bff6a" if active else ("#6b1d1d" if active is False else "#6a6f76")
        led.setStyleSheet(f"background-color: {colour}; border-radius: 7px; border: 1px solid #202327;")

    def _sync_volume_controls(self, volume_keys):
        if tuple(self._volume_sliders) == tuple(volume_keys):
            return
        while self._volumes_layout.rowCount():
            self._volumes_layout.removeRow(0)
        self._volume_sliders.clear()
        self._volume_labels.clear()
        self._volume_leds.clear()
        for key in volume_keys:
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 127)
            slider.setTracking(True)
            slider.sliderReleased.connect(lambda name=key, control=slider: self.bridge.post_ui_event(
                "volume", (name, control.value())))
            label = QLabel(VOLS[key][2])
            self._volume_sliders[key] = slider
            self._volume_labels[key] = label
            self._volumes_layout.addRow(label, self._volume_field(key, slider))

    def _update_modal_flag(self):
        if QApplication.activeModalWidget() is not None:
            self.bridge.modal_open.set()
        else:
            self.bridge.modal_open.clear()

    def _modal_buttons(self, modal):
        found = [b for b in modal.findChildren(QAbstractButton)
                 if b.isEnabled() and b.isVisible() and b.focusPolicy() != Qt.FocusPolicy.NoFocus]
        found.sort(key=lambda b: (b.mapTo(modal, QPoint(0, 0)).y() // 12, b.mapTo(modal, QPoint(0, 0)).x()))
        return found

    def _modal_move(self, direction):
        """A popup (unsaved-registration prompt, setter editor, ...) is open: the jog walks its buttons."""
        modal = QApplication.activeModalWidget()
        if modal is None:
            return
        buttons = self._modal_buttons(modal)
        if not buttons:
            return
        if "jogfocus" not in (modal.styleSheet() or ""):
            modal.setStyleSheet((modal.styleSheet() or "") +
                                " /*jogfocus*/ QAbstractButton:focus { border: 2px solid #4fd1c5; }")
        current = modal.focusWidget()
        index = buttons.index(current) if current in buttons else -1
        index = (index + direction) % len(buttons) if index >= 0 else (0 if direction > 0 else len(buttons) - 1)
        buttons[index].setFocus(Qt.FocusReason.OtherFocusReason)

    def _modal_press(self):
        modal = QApplication.activeModalWidget()
        if modal is None:
            return
        current = modal.focusWidget()
        if isinstance(current, QAbstractButton) and current.isEnabled():
            current.animateClick()
        else:
            default = next((b for b in modal.findChildren(QPushButton) if b.isDefault()), None)
            if default is not None:
                default.animateClick()

    def refresh_view(self):
        snapshot = self.bridge.get_snapshot()
        if not snapshot:
            return
        menu = snapshot["menu"]
        # Follow the backend only when ITS tab changed (e.g. Cat/Char pressed), so a GUI click
        # is never snapped back by a snapshot that predates the click.
        if menu["tab"] != getattr(self, "_last_backend_tab", None):
            self._last_backend_tab = menu["tab"]
            if self.main_tabs.currentIndex() != menu["tab"]:
                self.main_tabs.setCurrentIndex(menu["tab"])
        self.menu_status_label.setText(
            f"MENU {'ON' if menu['active'] else 'OFF'}  |  {menu['pages'][menu['tab']]['name']}"
        )
        couplings = snapshot.get("couplings", [])
        self.couplings_list.blockSignals(True)
        if self.couplings_list.count() != len(couplings):
            self.couplings_list.clear()
            for _control in couplings:
                row = QListWidgetItem()
                row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                self.couplings_list.addItem(row)
        for index, control in enumerate(couplings):
            row = self.couplings_list.item(index)
            row.setText(control["name"])
            row.setData(Qt.ItemDataRole.UserRole, control["cc"])
            row.setCheckState(Qt.CheckState.Checked if control["active"] else Qt.CheckState.Unchecked)
        self.couplings_list.blockSignals(False)
        self.couplings_list.setEnabled(snapshot.get("organ_routes_ready", True))
        if self.organ_path_edit.text() != snapshot.get("organ_path", "") and not self.organ_path_edit.hasFocus():
            self.organ_path_edit.setText(snapshot.get("organ_path", ""))
        self.organ_summary_label.setText(snapshot.get("organ_summary", "No organ profile loaded"))
        self.organ_settings_label.setText(snapshot.get("organ_settings_path", ""))
        self._organ_import_pending = bool(snapshot.get("organ_import_pending"))
        self.organ_path_edit.setEnabled(not self._organ_import_pending)
        self.organ_browse_button.setEnabled(not self._organ_import_pending)
        self.organ_cancel_button.setVisible(self._organ_import_pending)
        self.organ_import_button.setText(
            "Confirm MIDI import" if self._organ_import_pending else "Import organ"
        )
        self.organ_import_button.setEnabled(bool(self.organ_path_edit.text().strip()) or self._organ_import_pending)
        setter_files = snapshot.get("combination_files", [])
        current_files = [self.setter_files_list.item(index).text() for index in range(self.setter_files_list.count())]
        if current_files != setter_files:
            self.setter_files_list.clear()
            self.setter_files_list.addItems(setter_files)
        selected_index = snapshot.get("combination_index")
        selected = (snapshot["combinations"][selected_index]
                    if selected_index is not None and selected_index < len(snapshot["combinations"]) else None)
        self.setter_edit_summary.setText(
            f"{selected['filename']}  |  {selected['name']}" if selected else "No combination selected"
        )
        self.status_label.setText(snapshot.get("live_status", snapshot["status"]))
        if snapshot["language"] != self._language:
            self.apply_language(snapshot["language"])
        self.preset_direct_checkbox.blockSignals(True)
        self.preset_direct_checkbox.setChecked(snapshot["preset_activation"] == "direct")
        self.preset_direct_checkbox.blockSignals(False)
        self._sync_volume_controls(snapshot["volumes"])
        index = self.language_box.findData(snapshot["language"])
        if index >= 0 and index != self.language_box.currentIndex():
            self.language_box.blockSignals(True)
            self.language_box.setCurrentIndex(index)
            self.language_box.blockSignals(False)
        theme_index = self.theme_box.findData(snapshot["theme"])
        if theme_index >= 0 and theme_index != self.theme_box.currentIndex():
            self.theme_box.blockSignals(True)
            self.theme_box.setCurrentIndex(theme_index)
            self.theme_box.blockSignals(False)
            self._apply_theme(snapshot["theme"])
        self._metro_active = snapshot["metro_lit"]
        metro_button = self._transport_buttons["gui_metro"]
        if not self._metro_pressed and metro_button.isChecked() != self._metro_active:
            metro_button.blockSignals(True)
            metro_button.setChecked(self._metro_active)
            metro_button.blockSignals(False)
        if snapshot["metro_bpm"]:
            metro_button.setText(f"{self._t('gui_metro')}  {snapshot['metro_bpm']}")

        self.lcd_text.setText(f"{snapshot['lcd'][0][:16].ljust(16)}\n{snapshot['lcd'][1][:16].ljust(16)}")
        self.bank_box_combo.blockSignals(True)
        if self.bank_box_combo.count() != len(snapshot["banks"]):
            self.bank_box_combo.clear()
            self.bank_box_combo.addItems(snapshot["banks"])
        self.bank_box_combo.setCurrentIndex(snapshot["bank_index"])
        self.bank_box_combo.blockSignals(False)
        self.marks_label.setText(f"{self._t('marks')}: {snapshot['marks']}")
        self.marks_label.setToolTip(snapshot["mark_legend"])
        signature = tuple((item["filename"], item["internal_id"], item["name"])
                          for item in snapshot["combinations"])
        self._combination_snapshot = list(snapshot["combinations"])
        self._available_stops = list(snapshot.get("available_stops", []))
        self._active_stop_paths = list(snapshot.get("active_stop_paths", []))
        self._sync_stop_grid_popup(snapshot)
        if self.sheet_music_window is not None and self.sheet_music_window.isVisible():
            self.sheet_music_window.update_setters(
                snapshot["combinations"], snapshot.get("combination_index"), snapshot.get("active_combination_index"))
        self.combination_list.blockSignals(True)
        if signature != self._combination_tree_signature:
            self.combination_list.clear()
            parents = {}
            for index, item in enumerate(snapshot["combinations"]):
                parent = parents.get(item["filename"])
                if parent is None:
                    parent_name = item["filename"].rsplit(".", 1)[0]
                    parent = QTreeWidgetItem([parent_name, "", ""])
                    self.combination_list.addTopLevelItem(parent)
                    parents[item["filename"]] = parent
                child = QTreeWidgetItem([item["name"], item["internal_id"], ""])
                child.setData(0, Qt.ItemDataRole.UserRole, index)
                parent.addChild(child)
            self.combination_list.expandAll()
            self._combination_tree_signature = signature
            self._last_selected_combo = -2              # tree rebuilt: re-apply the selection below
        active_index = snapshot["active_combination_index"]
        for parent_index in range(self.combination_list.topLevelItemCount()):
            parent = self.combination_list.topLevelItem(parent_index)
            if parent is None:
                continue
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                if child is None:
                    continue
                index = child.data(0, Qt.ItemDataRole.UserRole)
                child.setCheckState(2, Qt.CheckState.Checked if index == active_index
                                    else Qt.CheckState.Unchecked)
                # Note: we deliberately do NOT force the tree's selection
                # cursor to follow `selected_index` here. This runs on every
                # periodic refresh, and forcing selection would snap the
                # user's mouse/controller click back to whatever the backend
                # last reported as active -- especially while not playing,
                # if the backend hasn't (yet) updated its own "selected"
                # state to match. The checkmark uses confirmed feedback; the
                # selection cursor is left for the user.
        # Follow the backend's selection (jog / hardware navigation) so the setter list shows where
        # the cue is. Only when the backend's index CHANGED, so a mouse click is never snapped back.
        selected_index = snapshot.get("combination_index")
        if selected_index != getattr(self, "_last_selected_combo", -2):
            self._last_selected_combo = selected_index
            self._select_combination_row(selected_index)
        self.combination_list.blockSignals(False)

        if snapshot["active_stops"] != self._active_stop_snapshot:
            self.active_list.clear()
            for registration in snapshot["active_stops"]:
                self.active_list.addItem(registration)
            self._active_stop_snapshot = list(snapshot["active_stops"])

        for button, pad in zip(self._pad_buttons, snapshot["pads"]):
            if pad["cc"] is None:               # nothing assigned: flat grey, no text, not clickable
                button.setEnabled(False)
                button.setText("")
                button.setStyleSheet(
                    f"QPushButton#padButton {{ background-color: {UNASSIGNED_PAD_COLOR}; border: 1px dashed #6a6f76; }}")
                continue
            button.setEnabled(snapshot.get("organ_routes_ready", True))
            button.setText("\n".join(pad["lines"]))
            button.setStyleSheet(f"QPushButton#padButton {{ background-color: {pad['color']}; color: {contrast_text(pad['color'])}; }}")

        for key, led in self._volume_leds.items():
            self._set_volume_led(led, snapshot.get("volume_active", {}).get(key))
        for key, slider in self._volume_sliders.items():
            slider.setEnabled(snapshot.get("organ_routes_ready", True))
            if not slider.isSliderDown():
                slider.blockSignals(True)
                slider.setValue(snapshot["volumes"].get(key, 0))
                slider.blockSignals(False)
            self.combination_list.setEnabled(snapshot.get("organ_routes_ready", True))
            self.preset_direct_checkbox.setEnabled(snapshot.get("organ_routes_ready", True))
            for button in self._transport_buttons.values():
                button.setEnabled(snapshot.get("organ_routes_ready", True))
        diagnostics = snapshot["debug_text"]
        if diagnostics != getattr(self, "_last_diagnostics", None):
            scroll = self.diagnostics_text.verticalScrollBar()
            position = scroll.value()
            self.diagnostics_text.setPlainText(diagnostics)
            scroll.setValue(position)
            self._last_diagnostics = diagnostics
        pending = snapshot.get("confirm_navigate")
        if pending and not self._confirm_navigate_open:
            self._confirm_navigate_open = True
            QTimer.singleShot(0, lambda: self._show_navigate_confirm(pending))   # leave refresh_view first: it keeps ticking
        if not self.bridge.running:
            self.close()

    def closeEvent(self, event):
        self.timer.stop()                      # no more snapshot refreshes while the bridge shuts down
        self.modal_timer.stop()
        self.bridge.modal_open.clear()
        if self._stop_grid_popup is not None:
            self._suppress_grid_close = True
            self._stop_grid_popup.close_immediately()
            self._stop_grid_popup = None
            self._suppress_grid_close = False
        self.bridge.post_ui_event("command", "quit")
        event.accept()


def run_qt_ui(bridge, ui):
    existing_application = QApplication.instance()
    application = existing_application if isinstance(existing_application, QApplication) else QApplication(sys.argv)
    # Fusion avoids platform-native combo-box arrows/popup colours leaking
    # through the theme stylesheet, especially in Windows Light mode.
    import themes                                    # global theme: Fusion engine + palette + style sheet, applied by the window
    themes.apply(bridge.theme, application)
    bridge.gui_hosted = True
    global WINDOW_MEMORY
    WINDOW_MEMORY = WindowMemory(os.path.dirname(os.path.abspath(bridge.cfg_path)))
    application.installEventFilter(WINDOW_MEMORY)
    application.aboutToQuit.connect(WINDOW_MEMORY.flush)
    window = BridgeWindow(bridge)
    engine_thread = threading.Thread(target=bridge.run, name="bridge-engine", daemon=True)
    engine_thread.start()
    window.show()
    try:
        exit_code = application.exec()
    finally:
        bridge.running = False
        window.hide()                     # the window disappears at once; the bridge finishes closing MIDI behind it
        deadline = time.time() + 6.0
        while engine_thread.is_alive() and time.time() < deadline:
            application.processEvents()   # keep the event loop alive instead of blocking in join()
            engine_thread.join(timeout=0.05)
        ui.close()
    return 1 if bridge.fatal else exit_code