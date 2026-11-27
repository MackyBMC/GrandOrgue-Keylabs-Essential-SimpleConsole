"""Organ FAQ (editable Markdown) dialog.

Split out of qt_gui.py without behaviour change.

CHANGELOG
2026-11-27  Moved verbatim from qt_gui.py (v3.0.0 modularisation, patch 06).
"""

import os
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import (
    QFontDatabase,
)
from PySide6.QtCore import (
    Qt,
)


class OrganFaqDialog(QDialog):
    """The Organ FAQ as a small Markdown editor: toolbar, source on the left, live preview on the right. Saved to the user's data folder
    (a copy of the shipped docs/ORGAN_FAQ.md); "Reset" goes back to the shipped text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QTextBrowser
        self.setWindowTitle("Organ FAQ (editable)")
        self.resize(1100, 720)
        self._saved = ""
        layout = QVBoxLayout(self)
        top_row = QHBoxLayout()
        self.edit_button = QPushButton("Edit")
        self.edit_button.setCheckable(True)
        self.edit_button.setToolTip("Show the Markdown editor beside the text")
        top_row.addWidget(self.edit_button)
        top_row.addStretch(1)
        layout.addLayout(top_row)
        self.toolbar = QWidget()
        bar = QHBoxLayout(self.toolbar)
        bar.setContentsMargins(0, 0, 0, 0)
        for label, tip, before, after in (
                ("B", "Bold", "**", "**"), ("I", "Italic", "*", "*"), ("H", "Heading", "## ", ""), ("\u2022", "Bullet", "- ", ""),
                ("1.", "Numbered", "1. ", ""), ("\u275d", "Quote", "> ", ""), ("</>", "Code", "`", "`"),
                ("\U0001F517", "Link", "[", "](https://)"), ("\u2014", "Rule", "\n---\n", "")):
            button = QPushButton(label)
            button.setToolTip(tip)
            button.setFixedWidth(40)
            button.clicked.connect(lambda checked=False, b=before, a=after: self._wrap(b, a))
            bar.addWidget(button)
        bar.addStretch(1)
        self.status = QLabel()
        bar.addWidget(self.status)
        layout.addWidget(self.toolbar)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        split.addWidget(self.editor)
        split.addWidget(self.preview)
        split.setSizes([550, 550])
        layout.addWidget(split, 1)
        self.action_bar = QWidget()
        row = QHBoxLayout(self.action_bar)
        row.setContentsMargins(0, 0, 0, 0)
        self.reset_button = QPushButton("Reset to shipped text")
        self.save_button = QPushButton("Save")
        self.close_button = QPushButton("Close")
        row.addWidget(self.reset_button)
        row.addWidget(self.save_button)
        layout.addWidget(self.action_bar)
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_row.addWidget(self.close_button)
        layout.addLayout(close_row)
        self._split = split
        self.editor.setPlainText(self._load(self._user_path()) or self._load(self._shipped_path()))
        self._saved = self.editor.toPlainText()
        self.editor.textChanged.connect(self._changed)
        self.save_button.clicked.connect(self._save)
        self.edit_button.toggled.connect(self._edit_toggled)
        self._edit_toggled(False)
        self.close_button.clicked.connect(self.close)
        self.reset_button.clicked.connect(self._reset)
        self._changed()

    def _edit_toggled(self, editing):
        self.edit_button.setText("Hide editor" if editing else "Edit")
        for widget in (self.toolbar, self.editor, self.action_bar):
            widget.setVisible(editing)
        if editing:
            self._split.setSizes([550, 550])

    @staticmethod
    def _user_path():
        from keylab_bridge import paths
        return os.path.join(paths.data_dir(), "docs", "ORGAN_FAQ.md")

    @staticmethod
    def _shipped_path():
        from keylab_bridge import paths
        for folder in (paths.app_dir(), os.path.dirname(os.path.abspath(__file__))):
            path = os.path.join(folder, "docs", "ORGAN_FAQ.md")
            if os.path.isfile(path):
                return path
        return ""

    @staticmethod
    def _load(path):
        try:
            with open(path, encoding="utf-8") as handle:
                return handle.read()
        except OSError:
            return ""

    def _wrap(self, before, after):
        cursor = self.editor.textCursor()
        text = cursor.selectedText()
        cursor.insertText(before + text + after)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def _changed(self):
        self.preview.setMarkdown(self.editor.toPlainText())
        self.status.setText("Unsaved changes" if self.editor.toPlainText() != self._saved else "Saved")

    def _save(self):
        path = self._user_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(self.editor.toPlainText())
            self._saved = self.editor.toPlainText()
            self._changed()
        except OSError as error:
            QMessageBox.warning(self, "Organ FAQ", f"Could not save: {error}")

    def _reset(self):
        if QMessageBox.question(self, "Organ FAQ", "Replace the text with the shipped version? Your edits stay in the saved copy until you Save.") \
                == QMessageBox.StandardButton.Yes:
            self.editor.setPlainText(self._load(self._shipped_path()))

    def closeEvent(self, event):
        if self.editor.toPlainText() != self._saved:
            choice = QMessageBox.question(self, "Organ FAQ", "Save your changes before closing?",
                                          QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                          QMessageBox.StandardButton.Save)
            if choice == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if choice == QMessageBox.StandardButton.Save:
                self._save()
        event.accept()
