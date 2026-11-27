"""Sheet music window (score + setter lists).

Split out of qt_gui.py.

CHANGELOG
2026-11-28  Changelog labels of the module split now use the v2.0.9 patch numbers (comments only, no code change).
2026-11-27  Moved from qt_gui.py (modularisation, v2.0.9-68). isinstance(parent, BridgeWindow) became isinstance(parent, SheetMusicHost) (a runtime Protocol, same single parent in practice); window memory comes from gui.window_memory.current().
"""

from typing import Protocol, runtime_checkable
import threading
import gui_metrics
import os
import time
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
)
from PySide6.QtCore import (
    QEvent,
    QPointF,
    QSettings,
    QSize,
    QTimer,
    Qt,
)
from PySide6.QtPdf import (
    QPdfDocument,
)
from PySide6.QtPdfWidgets import (
    QPdfView,
)
from gui import window_memory
from gui import window_memory


@runtime_checkable
class SheetMusicBridge(Protocol):
    """What the sheet music window needs from the bridge (keylab_bridge.application.BridgeApp provides it)."""
    sustain_sheet_nav: bool
    sheet_music_navigation_enabled: threading.Event

    def set_sheet_zone(self, zone: str, announce: bool = True) -> None: ...

    def post_ui_event(self, event: str, value: object = None) -> None: ...


@runtime_checkable
class SheetMusicHost(Protocol):
    """A parent window that owns a bridge (BridgeWindow). Replaces isinstance(parent, BridgeWindow) so gui/ does not import qt_gui."""
    bridge: SheetMusicBridge


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
        self.pedal_pages = QCheckBox("Pedal turns pages")
        self.pedal_pages.setToolTip("Sustain pedal: tap = next page / screen, double tap = back. Then only the Jog press loads a setter.")
        self.pedal_pages.setChecked(str(QSettings("KeyLabGrandOrgue", "SheetMusic").value("pedal_pages", "false")) == "true")
        self.pedal_pages.toggled.connect(self._pedal_pages_changed)
        toolbar.addWidget(self.pedal_pages)
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
        memory = window_memory.current()
        saved_width = memory.value("SheetMusicSideWidth") if memory is not None else None
        self.side_panel.setMinimumWidth(220)
        self.main_split.setSizes([int(saved_width) if isinstance(saved_width, (int, float)) and saved_width >= 220 else int(gui_metrics.get("side_column_width")), 900, 900])
        self.main_split.splitterMoved.connect(
            lambda *_: (m := window_memory.current()) and m.store("SheetMusicSideWidth", self.side_panel.width()))
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

    IMAGES_ROLE = Qt.ItemDataRole.UserRole + 1                # set on a row that stands for a folder of page images

    def _load_file_list(self):
        if not os.path.isdir(self.FOLDER):
            self.status_label.setText(f"Folder not found: {self.FOLDER}")
            return
        import sheet_images
        entries = []                                          # (display name, path of the pdf, image folder or "")
        for root, _, filenames in os.walk(self.FOLDER):
            for name in filenames:
                if name.lower().endswith(".pdf"):
                    entries.append((os.path.relpath(os.path.join(root, name), self.FOLDER), os.path.join(root, name), ""))
            pictures = sheet_images.image_files(root)
            if pictures and not sheet_images.is_current(root):   # an up-to-date converted pdf is listed as a normal pdf above
                label = os.path.relpath(root, self.FOLDER)
                label = "(pictures)" if label == "." else label
                entries.append((f"{label}  [{len(pictures)} images]", sheet_images.pdf_path_for(root), root))
        entries.sort(key=lambda e: e[0].casefold())
        for display_name, path, folder in entries:
            self.file_list.addItem(display_name)
            item = self.file_list.item(self.file_list.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setData(self.IMAGES_ROLE, folder)
        if entries:
            self.file_list.setCurrentRow(0)
        else:
            self.status_label.setText("No PDF files or image folders found")

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
        folder = item.data(self.IMAGES_ROLE)
        if isinstance(folder, str) and folder:                # a folder of page images: make (or reuse) its pdf, then open that
            import sheet_images
            self.status_label.setText(f"Converting {item.text()} to a PDF...")
            QApplication.processEvents()
            made = sheet_images.ensure_pdf(folder)
            if made is None:
                self.status_label.setText("Could not convert these images to a PDF (is the folder writable?)")
                return
            path = made
            item.setData(Qt.ItemDataRole.UserRole, path)
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
                QTimer.singleShot(100, self._render_spread)
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
        self._publish_zone()

    def _pedal_pages_changed(self, on=None):
        on = self.pedal_pages.isChecked() if on is None else on
        QSettings("KeyLabGrandOrgue", "SheetMusic").setValue("pedal_pages", "true" if on else "false")
        parent = self.parentWidget()
        if isinstance(parent, SheetMusicHost):
            parent.bridge.sustain_sheet_nav = bool(on)

    def _publish_zone(self, closed=False):
        """Tell the bridge which list the jog drives, so every LCD (keyboard, window, floating) shows it."""
        parent = self.parentWidget()
        if isinstance(parent, SheetMusicHost):
            parent.bridge.set_sheet_zone("" if closed else self.jog_zone, announce=not closed)

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
        if index is not None and isinstance(parent, SheetMusicHost):
            self._hold_cursor_until = time.time() + 1.5
            parent.bridge.post_ui_event("cue_setter", int(index))

    def jog_press(self):
        had_pending = self._pending is not None
        self._apply_pending()
        if self.jog_zone == "setters":
            parent = self.parentWidget()
            if isinstance(parent, SheetMusicHost):
                parent.bridge.post_ui_event("transport", "load")      # load the cued setter onto the organ
        elif not had_pending and self.file_list.currentRow() >= 0:
            self._load_file_at(self.file_list.currentRow())           # re-open the current file from page one

    def _setter_clicked(self, item):
        index = item.data(Qt.ItemDataRole.UserRole)
        parent = self.parentWidget()
        if index is not None and isinstance(parent, SheetMusicHost):
            parent.bridge.post_ui_event("combination", int(index))

    def update_setters(self, combinations, selected_index, active_index):
        """Mirror the main window's setter list (called from its refresh); only rebuilds when the list changes."""
        signature = tuple((c["filename"], c["internal_id"], c["name"]) for c in combinations)
        if signature != self._setter_signature:
            self._setter_signature = signature
            self.setter_list.blockSignals(True)
            self.setter_list.clear()
            for index, c in enumerate(combinations):
                item = QListWidgetItem(f"{(c.get('file_names') or {}).get('default') or c['filename'].rsplit('.', 1)[0]}  |  {c['name']}")
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
        bar = self.pdf_view.verticalScrollBar()
        step = max(1, int(self.pdf_view.viewport().height() * 0.9))      # one screenful, a little overlap so no staff is lost
        if delta > 0 and bar.value() < bar.maximum() - 2:                # zoomed: more of this page below
            bar.setValue(min(bar.maximum(), bar.value() + step))
            return
        if delta < 0 and bar.value() > bar.minimum() + 2:
            bar.setValue(max(bar.minimum(), bar.value() - step))
            return
        page = self.pdf_view.pageNavigator().currentPage()
        target_page = page + delta
        if 0 <= target_page < self.document.pageCount():
            self.pdf_view.pageNavigator().jump(target_page, QPointF(0, 0))
            # same zoom on the next page: forward starts at its top, backward at its bottom
            QTimer.singleShot(40, lambda b=bar, up=delta < 0: b.setValue(b.maximum() if up else b.minimum()))

    def _select_zoom_mode(self, index):
        if self._two_page_mode:
            return
        mode = self.zoom_box.itemData(index)
        self.pdf_view.setZoomMode(mode)
        if mode == QPdfView.ZoomMode.Custom:
            self.pdf_view.setZoomFactor(1.0)                  # "Actual size"

    def _effective_zoom(self):
        """The zoom factor really on screen (zoomFactor() is stale in the Fit modes)."""
        view = self.pdf_view
        mode = view.zoomMode()
        if mode == QPdfView.ZoomMode.Custom:
            return view.zoomFactor()
        page = max(0, view.pageNavigator().currentPage())
        size = self.document.pagePointSize(page)
        if size.width() <= 0 or size.height() <= 0:
            return 1.0
        dpi = view.logicalDpiX() / 72.0
        port = view.viewport()
        fit_w = (port.width() - 8) / (size.width() * dpi)
        fit_h = (port.height() - 8) / (size.height() * dpi)
        return max(0.1, fit_w if mode == QPdfView.ZoomMode.FitToWidth else min(fit_w, fit_h))

    def _change_zoom(self, factor):
        if self._two_page_mode:
            return
        base = self._effective_zoom()
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.pdf_view.setZoomFactor(max(0.25, min(5.0, base * factor)))
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
            self.spread_label.setMinimumSize(1, 1)
            self.spread_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
            QTimer.singleShot(0, self._render_spread)          # the label has no size until the layout has run
            QTimer.singleShot(150, self._render_spread)
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
        if isinstance(parent, SheetMusicHost):
            parent.bridge.sheet_music_navigation_enabled.set()
        self._publish_zone()
        self._pedal_pages_changed()
        super().showEvent(event)

    def hideEvent(self, event):
        # Esc / reject() hides the dialog without closeEvent: the jog and arrows must go back to the main window.
        parent = self.parentWidget()
        if isinstance(parent, SheetMusicHost):
            parent.bridge.sheet_music_navigation_enabled.clear()
        self._publish_zone(closed=True)
        super().hideEvent(event)

    def closeEvent(self, event):
        parent = self.parentWidget()
        if isinstance(parent, SheetMusicHost):
            parent.bridge.sheet_music_navigation_enabled.clear()
        self._publish_zone(closed=True)
        event.accept()
