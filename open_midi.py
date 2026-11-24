"""One "Open MIDI / take" picker for the main window, the Stave Station and the Piano Roll.

CHANGELOG
2026-11-25  New: recordings and MIDI files of the takes folder, newest first (double-click opens), plus Browse... for any other file.
"""
from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout, QWidget)

MIDI_EXT = (".mid", ".midi", ".kar")


def list_midi(folder: str) -> list[str]:
    """MIDI files of a folder, newest first (the _preview.mid scratch file and the _trash folder are left out)."""
    if not folder or not os.path.isdir(folder):
        return []
    out = [os.path.join(folder, n) for n in os.listdir(folder)
           if n.lower().endswith(MIDI_EXT) and not n.startswith("_preview")]
    return sorted(out, key=lambda p: os.path.getmtime(p), reverse=True)


def pick_midi(parent: QWidget | None, folder: str, browse_filter: str = "MIDI files (*.mid *.midi *.kar)",
              title: str = "Open MIDI / take") -> str:
    """Return the chosen file path, or "" when cancelled."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(520, 420)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Recordings and MIDI files in " + (folder or "(no folder)")))
    box = QListWidget()
    for path in list_midi(folder):
        item = QListWidgetItem(f"{os.path.basename(path)}    {time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(path)))}")
        item.setData(Qt.ItemDataRole.UserRole, path)
        box.addItem(item)
    layout.addWidget(box, 1)
    chosen = {"path": ""}

    def accept_current(*_):
        item = box.currentItem()
        if item is not None:
            chosen["path"] = str(item.data(Qt.ItemDataRole.UserRole))
            dialog.accept()

    def browse():
        path, _ = QFileDialog.getOpenFileName(dialog, title, folder or "", browse_filter)
        if path:
            chosen["path"] = path
            dialog.accept()

    box.itemDoubleClicked.connect(accept_current)
    row = QHBoxLayout()
    open_button, browse_button, cancel = QPushButton("Open"), QPushButton("Browse..."), QPushButton("Cancel")
    open_button.setDefault(True)
    open_button.clicked.connect(accept_current)
    browse_button.clicked.connect(browse)
    cancel.clicked.connect(dialog.reject)
    row.addStretch(1)
    for button in (open_button, browse_button, cancel):
        row.addWidget(button)
    layout.addLayout(row)
    if box.count():
        box.setCurrentRow(0)
    dialog.exec()
    return chosen["path"]
