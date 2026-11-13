"""DEV ONLY - answer the questions Claude leaves in docs/claude.chat/*.txt.

Run from the repo root:   python tools/claude_chat_answers.py
Options:                  --repo-root DIR  (default: parent of tools/)   --chat-dir DIR   (default <repo-root>/docs/claude.chat)
                          --out-dir DIR    (default <chat-dir>/answers)

What it does
- Lists every .txt in the chat folder; a file with a "Questions" section shows one card per numbered question.
- Each card: Yes / No / Discuss / Skip plus a free-text note. A "General note" box covers anything else.
- Saves <name>.answers.txt in the out folder (autosave on switching file and on close, Ctrl+S). Upload those files to Claude;
  Claude folds the answers into the docs/ADRs with the next .patch and retires the answered chat files.
- Reopening a file reloads its saved answers.
- File names and "ADR 0002-0008" style references in the header and in each question are links: click one and the file opens in the
  viewer pane on the right (Markdown is rendered; ADR ranges open all of them in one view; links inside a viewed file work; Back button).
Not packaged: lives in tools/, is not in the Nuitka include list and refuses to run frozen.

CHANGELOG
2026-11-13  Clickable file / ADR references open in a viewer pane (Markdown rendered), with Back and relative-link navigation.
2026-11-13  New (dev tool).
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QCloseEvent, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QTextBrowser, QVBoxLayout, QWidget,
)

CHOICES = ("YES", "NO", "DISCUSS", "SKIP")
QUESTION_RE = re.compile(r"^\s{0,3}(\d+)[.)]\s+(.*\S)\s*$")
FORMAT_VERSION = 1


@dataclass
class Question:
    number: int
    text: str
    choice: str = ""
    note: str = ""


@dataclass
class ChatFile:
    path: Path
    header: str = ""
    questions: list[Question] = field(default_factory=list)
    general: str = ""
    dirty: bool = False

    def answered(self) -> int:
        return sum(1 for q in self.questions if q.choice or q.note.strip())


def parse_questions(text: str) -> tuple[str, list[Question]]:
    """Split a chat file into (header text, questions). Only a section headed "Questions" is parsed."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if re.match(r"^\s*questions\b", ln, re.I)), -1)
    if start < 0:
        return text, []
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^\s*notes\b", lines[i], re.I)), len(lines))
    questions: list[Question] = []
    for ln in lines[start + 1:end]:
        m = QUESTION_RE.match(ln)
        if m:
            questions.append(Question(int(m.group(1)), m.group(2).strip()))
        elif ln.strip() and ln[0].isspace() and questions:
            questions[-1].text += " " + ln.strip()
    header = "\n".join(lines[:start] + lines[end:])
    return header, questions


def render_answers(source: str, questions: list[Question], general: str) -> str:
    out = [f"ANSWERS-FOR: {source}", f"SAVED: {datetime.now():%Y-%m-%d %H:%M}", f"FORMAT: {FORMAT_VERSION}", ""]
    for q in questions:
        out.append(f"Q{q.number}: {q.text}")
        out.append(f"A{q.number}: {q.choice or '(none)'}")
        if q.note.strip():
            note = q.note.strip().splitlines()
            out.append(f"N{q.number}: {note[0]}")
            out += [f"    {ln}" for ln in note[1:]]
        out.append("")
    if general.strip():
        gen = general.strip().splitlines()
        out.append(f"GENERAL: {gen[0]}")
        out += [f"    {ln}" for ln in gen[1:]]
        out.append("")
    return "\n".join(out)


def load_answers(text: str, questions: list[Question]) -> str:
    """Fill questions from a saved answers file; return the general note."""
    by_number = {q.number: q for q in questions}
    notes: dict[int, list[str]] = {}
    general: list[str] = []
    target: list[str] | None = None
    for ln in text.splitlines():
        if ln.startswith("    ") and target is not None:
            target.append(ln[4:])
            continue
        target = None
        m = re.match(r"^A(\d+):\s*(\w*)", ln)
        if m:
            q = by_number.get(int(m.group(1)))
            if q is not None and m.group(2).upper() in CHOICES:
                q.choice = m.group(2).upper()
            continue
        m = re.match(r"^N(\d+):\s?(.*)$", ln)
        if m:
            n = int(m.group(1))
            if n in by_number:
                notes[n] = [m.group(2)]
                target = notes[n]
            continue
        m = re.match(r"^GENERAL:\s?(.*)$", ln)
        if m:
            general = [m.group(1)]
            target = general
    for n, lines in notes.items():
        by_number[n].note = "\n".join(lines)
    return "\n".join(general)


TEXT_EXTS = (".md", ".py", ".yaml", ".yml", ".txt", ".json", ".patch", ".iss", ".ps1", ".sh", ".toml")
SKIP_DIRS = {".git", "__pycache__", "node_modules", "dist", "build", ".venv", "venv"}
LINK_RE = re.compile(
    r"(?P<adr>ADRs?\s+(?P<a>\d{4})(?:\s*(?:-|\u2013|to)\s*(?P<b>\d{4}))?)"
    r"|(?P<file>[\w./\\-]*\w\.(?:md|py|yaml|yml|txt|json|patch|iss|ps1|sh|toml))\b"
    r"|(?P<bare>\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*\b)"
)


class Resolver:
    """Turns file names and ADR references found in text into files under the repo root."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.by_name: dict[str, list[Path]] = {}
        for folder, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for n in names:
                if n.lower().endswith(TEXT_EXTS):
                    self.by_name.setdefault(n, []).append(Path(folder) / n)

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    def file(self, token: str) -> Path | None:
        token = token.replace("\\", "/")
        if token.startswith("./"):
            token = token[2:]
        direct = self.root / token
        if direct.is_file():
            return direct
        cands = self.by_name.get(token.rsplit("/", 1)[-1], [])
        tail = [c for c in cands if c.as_posix().endswith("/" + token)]
        if len(tail) == 1:
            return tail[0]
        if len(cands) == 1:
            return cands[0]
        docs = [c for c in cands if "docs" in c.relative_to(self.root).parts]
        pool = docs or cands
        return min(pool, key=lambda c: len(c.as_posix())) if pool else None

    def bare(self, token: str) -> Path | None:
        for base in (self.root / "docs", self.root):
            p = base / f"{token}.md"
            if p.is_file():
                return p
        return None

    def adr(self, number: str) -> Path | None:
        found = sorted((self.root / "docs" / "adr").glob(f"{number}-*.md"))
        return found[0] if found else None


def _anchor(href: str, label: str) -> str:
    return f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'


def linkify(text: str, res: Resolver) -> str:
    """HTML for text with file names, bare doc names (SCOPE, VISION...) and ADR references turned into links."""
    out: list[str] = []
    pos = 0
    for m in LINK_RE.finditer(text):
        piece: str | None = None
        if m.group("adr"):
            a, b = m.group("a"), m.group("b") or m.group("a")
            numbers = [f"{n:04d}" for n in range(int(a), int(b) + 1)] if int(b) >= int(a) else [a]
            paths = [p for p in (res.adr(n) for n in numbers) if p is not None]
            if len(paths) == 1:
                piece = _anchor("ref:" + res.rel(paths[0]), m.group("adr"))
            elif paths:
                piece = _anchor(f"adrs:{a}-{b}", m.group("adr")) + " " + " ".join(
                    _anchor("ref:" + res.rel(p), f"[{p.name[:4]}]") for p in paths)
        elif m.group("file"):
            p = res.file(m.group("file"))
            if p is not None:
                piece = _anchor("ref:" + res.rel(p), m.group("file"))
        elif m.group("bare"):
            p = res.bare(m.group("bare"))
            if p is not None:
                piece = _anchor("ref:" + res.rel(p), m.group("bare"))
        if piece is not None:
            out.append(html.escape(text[pos:m.start()]))
            out.append(piece)
            pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out).replace("\n", "<br>")


class Viewer(QWidget):
    """Right-hand file viewer: Markdown rendered, other text shown monospaced. Back button, relative links followed."""

    def __init__(self, res: Resolver) -> None:
        super().__init__()
        self.res = res
        self.history: list[str] = []
        self.current_path: Path | None = None
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self.back)
        self.back_btn.setEnabled(False)
        self.ext_btn = QPushButton("Open externally")
        self.ext_btn.clicked.connect(self._external)
        self.title = QLabel("")
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bar.addWidget(self.back_btn)
        bar.addWidget(self.ext_btn)
        bar.addWidget(self.title, 1)
        lay.addLayout(bar)
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self._anchor)
        lay.addWidget(self.browser, 1)
        self.browser.setMarkdown("*Click a highlighted file name or ADR reference in a question to read it here.*")

    def open_href(self, href: str, remember: bool = True) -> None:
        if href.startswith("adrs:"):
            a, b = href[5:].split("-", 1)
            paths = [p for p in (self.res.adr(f"{n:04d}") for n in range(int(a), int(b) + 1)) if p is not None]
            if not paths:
                return
            body = "\n\n---\n\n".join(p.read_text(encoding="utf-8", errors="replace") for p in paths)
            self._show(href, f"ADR {a}-{b} ({len(paths)} files)", body, markdown=True, path=None, remember=remember)
        elif href.startswith("ref:"):
            path = self.res.root / href[4:]
            if path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace")
                self._show(href, href[4:], text, markdown=path.suffix.lower() == ".md", path=path, remember=remember)

    def _show(self, href: str, title: str, text: str, markdown: bool, path: Path | None, remember: bool) -> None:
        if remember:
            self.history.append(href)
        self.current_path = path
        self.title.setText(title)
        if markdown:
            self.browser.setMarkdown(text)
        else:
            self.browser.setHtml(f'<pre style="white-space: pre-wrap">{html.escape(text)}</pre>')
        self.browser.verticalScrollBar().setValue(0)
        self.back_btn.setEnabled(len(self.history) > 1)
        self.ext_btn.setEnabled(path is not None)

    def back(self) -> None:
        if len(self.history) > 1:
            self.history.pop()
            self.open_href(self.history.pop(), remember=True)

    def _external(self) -> None:
        if self.current_path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.current_path)))

    def _anchor(self, url: QUrl) -> None:
        raw = url.toString()
        if raw.startswith(("ref:", "adrs:")):
            self.open_href(raw)
        elif url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)
        else:
            target = url.toLocalFile() if url.scheme() == "file" else url.path()
            if target and self.current_path is not None:
                p = (self.current_path.parent / target).resolve()
                if p.is_file() and p.suffix.lower() in TEXT_EXTS:
                    try:
                        self.open_href("ref:" + self.res.rel(p))
                    except ValueError:
                        pass


class QuestionCard(QFrame):
    def __init__(self, question: Question, on_change: Callable[[], None], res: Resolver, on_link: Callable[[str], None]) -> None:
        super().__init__()
        self.question = question
        self._on_change = on_change
        self.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QVBoxLayout(self)
        title = QLabel(f"<b>{question.number}.</b> {linkify(question.text, res)}")
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        title.linkActivated.connect(on_link)
        lay.addWidget(title)
        row = QHBoxLayout()
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        for name in CHOICES:
            b = QPushButton(name.capitalize())
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, n=name: self._choose(n))
            self.group.addButton(b)
            self.buttons[name] = b
            row.addWidget(b)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._clear)
        row.addWidget(clear)
        row.addStretch(1)
        lay.addLayout(row)
        self.note = QPlainTextEdit(question.note)
        self.note.setPlaceholderText("Note (optional)")
        self.note.setFixedHeight(56)
        self.note.textChanged.connect(self._note_changed)
        lay.addWidget(self.note)
        if question.choice in self.buttons:
            self.buttons[question.choice].setChecked(True)

    def _choose(self, name: str) -> None:
        self.question.choice = name
        self._on_change()

    def _clear(self) -> None:
        self.group.setExclusive(False)
        for b in self.buttons.values():
            b.setChecked(False)
        self.group.setExclusive(True)
        self.question.choice = ""
        self._on_change()

    def _note_changed(self) -> None:
        self.question.note = self.note.toPlainText()
        self._on_change()


class MainWindow(QMainWindow):
    def __init__(self, repo_root: Path, chat_dir: Path, out_dir: Path) -> None:
        super().__init__()
        self.res = Resolver(repo_root)
        self.chat_dir, self.out_dir = chat_dir, out_dir
        self.files: dict[Path, ChatFile] = {}
        self.current: ChatFile | None = None
        self.setWindowTitle("Claude chat answers (dev tool)")
        self.resize(1560, 800)

        split = QSplitter()
        self.setCentralWidget(split)
        self.listing = QListWidget()
        self.listing.setMinimumWidth(240)
        self.listing.currentItemChanged.connect(self._select)
        split.addWidget(self.listing)

        right = QWidget()
        rlay = QVBoxLayout(right)
        self.header = QTextBrowser()
        self.header.setOpenLinks(False)
        self.header.anchorClicked.connect(lambda url: self.viewer.open_href(url.toString()))
        self.header.setMaximumHeight(190)
        rlay.addWidget(self.header)
        self.cards_area = QScrollArea()
        self.cards_area.setWidgetResizable(True)
        rlay.addWidget(self.cards_area, 1)
        rlay.addWidget(QLabel("General note for this file"))
        self.general = QPlainTextEdit()
        self.general.setFixedHeight(70)
        self.general.textChanged.connect(self._general_changed)
        rlay.addWidget(self.general)
        bar = QHBoxLayout()
        save = QPushButton("Save (Ctrl+S)")
        save.clicked.connect(self.save_current)
        folder = QPushButton("Open answers folder")
        folder.clicked.connect(self._open_folder)
        self.status = QLabel("")
        bar.addWidget(save)
        bar.addWidget(folder)
        bar.addWidget(self.status, 1)
        rlay.addLayout(bar)
        split.addWidget(right)
        self.viewer = Viewer(self.res)
        split.addWidget(self.viewer)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 1)
        split.setSizes([260, 520, 640])
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_current)  # type: ignore[arg-type]
        self._scan()

    # ---- files
    def answers_path(self, cf: ChatFile) -> Path:
        return self.out_dir / f"{cf.path.stem}.answers.txt"

    def _scan(self) -> None:
        self.listing.clear()
        for p in sorted(self.chat_dir.glob("*.txt")):
            cf = ChatFile(p)
            text = p.read_text(encoding="utf-8", errors="replace")
            cf.header, cf.questions = parse_questions(text)
            ap = self.answers_path(cf)
            if ap.exists():
                cf.general = load_answers(ap.read_text(encoding="utf-8", errors="replace"), cf.questions)
            self.files[p] = cf
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, str(p))
            self.listing.addItem(item)
            self._refresh_item(item, cf)
        if self.listing.count():
            self.listing.setCurrentRow(0)
        else:
            self.status.setText(f"No .txt files in {self.chat_dir}")

    def _refresh_item(self, item: QListWidgetItem, cf: ChatFile) -> None:
        total = len(cf.questions)
        tag = f"{cf.answered()}/{total}" if total else "notes"
        item.setText(f"{cf.path.name}   [{tag}]")

    def _item_for(self, cf: ChatFile) -> QListWidgetItem | None:
        for i in range(self.listing.count()):
            it = self.listing.item(i)
            if it is not None and it.data(Qt.ItemDataRole.UserRole) == str(cf.path):
                return it
        return None

    def _select(self, item: QListWidgetItem | None, _prev: QListWidgetItem | None = None) -> None:
        self.save_current()
        if item is None:
            return
        cf = self.files[Path(str(item.data(Qt.ItemDataRole.UserRole)))]
        self.current = cf
        self.header.setHtml(linkify(cf.header.strip() or "(no header)", self.res))
        holder = QWidget()
        lay = QVBoxLayout(holder)
        if not cf.questions:
            lay.addWidget(QLabel("No questions in this file. Use the general note if you want to reply to it."))
        for q in cf.questions:
            lay.addWidget(QuestionCard(q, self._changed, self.res, self.viewer.open_href))
        lay.addStretch(1)
        self.cards_area.setWidget(holder)
        self.general.blockSignals(True)
        self.general.setPlainText(cf.general)
        self.general.blockSignals(False)
        self.status.setText("")

    # ---- state
    def _changed(self) -> None:
        if self.current:
            self.current.dirty = True
            it = self._item_for(self.current)
            if it is not None:
                self._refresh_item(it, self.current)

    def _general_changed(self) -> None:
        if self.current:
            self.current.general = self.general.toPlainText()
            self.current.dirty = True

    def save_current(self) -> None:
        cf = self.current
        if cf is None or not cf.dirty:
            return
        target = self.answers_path(cf)
        if not cf.answered() and not cf.general.strip():
            cf.dirty = False
            return
        self.out_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(render_answers(cf.path.name, cf.questions, cf.general), encoding="utf-8")
        cf.dirty = False
        self.status.setText(f"Saved {target}")

    def _open_folder(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.out_dir)))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.save_current()
        super().closeEvent(event)


def main() -> int:
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        print("claude_chat_answers is a dev tool and does not run in a packaged build.")
        return 2
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description="Answer docs/claude.chat questions (dev only).")
    ap.add_argument("--repo-root", type=Path, default=root)
    ap.add_argument("--chat-dir", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()
    repo_root: Path = args.repo_root
    chat_dir: Path = args.chat_dir or (repo_root / "docs" / "claude.chat")
    out_dir: Path = args.out_dir or (chat_dir / "answers")
    app = QApplication(sys.argv)
    win = MainWindow(repo_root, chat_dir, out_dir)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
