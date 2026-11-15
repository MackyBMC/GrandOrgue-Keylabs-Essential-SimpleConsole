"""Fluid table / tree columns, everywhere in the app.

Every QTreeView / QTableView (QTreeWidget, QTableWidget, ...) gets columns that keep their share of the width when the window or a dock is resized,
so the layout rearranges itself instead of leaving dead space or cutting text. You can still drag a column edge: the new shares are kept.
A view that already stretches a column by itself (resize mode Stretch) or sets the property "fluidSkip" is left alone.

CHANGELOG
2026-11-15  New.
"""
from typing import Dict, List, Optional

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractItemView, QApplication, QHeaderView, QTableView, QTreeView

MIN_SECTION = 28


def header_of(view: QAbstractItemView) -> Optional[QHeaderView]:
    if isinstance(view, QTreeView):
        return view.header()
    if isinstance(view, QTableView):
        return view.horizontalHeader()
    return None


class _Fluid(QObject):
    """Keeps one view's columns proportional to its width."""

    def __init__(self, view: QAbstractItemView, header: QHeaderView) -> None:
        super().__init__(view)
        self.view, self.header = view, header
        self.shares: Dict[int, float] = {}
        self.busy = False
        self.user_set = False
        header.setStretchLastSection(False)
        for i in range(header.count()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        header.sectionResized.connect(self._section_resized)
        view.viewport().installEventFilter(self)
        model = view.model()
        if model is not None:
            model.rowsInserted.connect(self._content_changed)
            model.modelReset.connect(self._content_changed)
        self._fit_to_content()

    def _visible(self) -> List[int]:
        return [i for i in range(self.header.count()) if not self.header.isSectionHidden(i)]

    def _fit_to_content(self) -> None:
        """Start from what each column needs, then spread to the width. Skipped once the user has dragged an edge."""
        if self.user_set:
            return
        view = self.view
        sizes = {}
        for i in self._visible():
            if isinstance(view, QTreeView):
                view.resizeColumnToContents(i)
            elif isinstance(view, QTableView):
                view.resizeColumnToContents(i)
            sizes[i] = max(MIN_SECTION, self.header.sectionSize(i))
        total = sum(sizes.values()) or 1
        self.shares = {i: s / total for i, s in sizes.items()}
        self._apply()

    def _content_changed(self, *_args) -> None:
        try:
            self._fit_to_content()
        except RuntimeError:                                    # the view was deleted meanwhile
            pass

    def _apply(self) -> None:
        width = self.view.viewport().width()
        visible = self._visible()
        if width < 50 or not visible or not self.shares:
            return
        self.busy = True
        try:
            used = 0
            for n, i in enumerate(visible):
                size = width - used if n == len(visible) - 1 else max(MIN_SECTION, round(self.shares.get(i, 1.0 / len(visible)) * width))
                self.header.resizeSection(i, max(MIN_SECTION, size))
                used += self.header.sectionSize(i)
        finally:
            self.busy = False

    def _section_resized(self, _index: int, _old: int, _new: int) -> None:
        if self.busy or not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            return                                              # only a real drag of a column edge changes the shares
        visible = self._visible()
        total = sum(self.header.sectionSize(i) for i in visible) or 1
        self.shares = {i: self.header.sectionSize(i) / total for i in visible}
        self.user_set = True

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        try:
            if event.type() == QEvent.Type.Resize and obj is self.view.viewport():
                self._apply()
        except RuntimeError:                                    # the view was deleted meanwhile
            pass
        return False


class FluidColumns(QObject):
    """Application-wide: attaches _Fluid to every table / tree the first time it is shown."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Show and isinstance(obj, (QTreeView, QTableView)) and not obj.property("fluidDone"):
            obj.setProperty("fluidDone", True)
            header = header_of(obj)
            if header is not None and header.count() > 0 and not obj.property("fluidSkip"):
                modes = [header.sectionResizeMode(i) for i in range(header.count())]
                if not any(m == QHeaderView.ResizeMode.Stretch for m in modes):
                    _Fluid(obj, header)
        return False


def install(app: QApplication) -> FluidColumns:
    filt = FluidColumns(app)
    app.installEventFilter(filt)
    return filt
