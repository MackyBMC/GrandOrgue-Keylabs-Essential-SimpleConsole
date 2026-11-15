"""Score pages that are pictures (png / jpg / ...): a folder of page images becomes one PDF the sheet music viewer opens like any other.

One folder = one score, pages in natural file-name order (page2 before page10). The PDF is written next to the images as
"<folder name> (from images).pdf" and is rebuilt only when an image is newer or the set of images changed. Plain Qt (QPdfWriter), no extra library.

CHANGELOG
2026-11-15  New.
"""
import os
import re
from typing import List, Optional

from PySide6.QtCore import QMarginsF, QRect, QSizeF
from PySide6.QtGui import QImage, QPageLayout, QPageSize, QPainter, QPdfWriter

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif")
SUFFIX = " (from images).pdf"
DPI = 150                                   # page size = pixels / DPI; the picture is placed 1:1, nothing is resampled


def natural_key(name: str):
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", name)]


def image_files(folder: str) -> List[str]:
    """The page images directly inside a folder, in natural order."""
    try:
        names = [n for n in os.listdir(folder) if n.lower().endswith(IMAGE_EXT) and os.path.isfile(os.path.join(folder, n))]
    except OSError:
        return []
    return [os.path.join(folder, n) for n in sorted(names, key=natural_key)]


def pdf_path_for(folder: str) -> str:
    name = os.path.basename(os.path.normpath(folder)) or "pages"
    return os.path.join(folder, name + SUFFIX)


def is_current(folder: str) -> bool:
    """True when the converted PDF exists and is newer than every image in the folder."""
    pdf = pdf_path_for(folder)
    images = image_files(folder)
    if not images or not os.path.isfile(pdf):
        return False
    try:
        return os.path.getmtime(pdf) >= max(os.path.getmtime(p) for p in images)
    except OSError:
        return False


def images_to_pdf(files: List[str], out_path: str, dpi: int = DPI) -> Optional[str]:
    """Write the images as the pages of one PDF. Returns None on success or a message saying what failed."""
    pages = [(p, QImage(p)) for p in files]
    pages = [(p, img) for p, img in pages if not img.isNull()]
    if not pages:
        return "none of the images could be read"
    tmp = out_path + ".tmp"
    writer = QPdfWriter(tmp)
    writer.setResolution(dpi)
    writer.setTitle(os.path.basename(os.path.dirname(out_path)))
    painter = QPainter()
    try:
        for index, (_path, image) in enumerate(pages):
            size = QSizeF(image.width() * 25.4 / dpi, image.height() * 25.4 / dpi)
            writer.setPageLayout(QPageLayout(QPageSize(size, QPageSize.Unit.Millimeter), QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0)))
            if index == 0:
                if not painter.begin(writer):
                    return "the PDF could not be created"
            else:
                writer.newPage()
            painter.drawImage(QRect(0, 0, image.width(), image.height()), image)
    finally:
        if painter.isActive():
            painter.end()
    try:
        os.replace(tmp, out_path)
    except OSError as exc:
        return str(exc)
    return None


def ensure_pdf(folder: str) -> Optional[str]:
    """The up-to-date PDF of a folder of page images (converted now when needed), or None when it cannot be made."""
    if is_current(folder):
        return pdf_path_for(folder)
    files = image_files(folder)
    if not files:
        return None
    return pdf_path_for(folder) if images_to_pdf(files, pdf_path_for(folder)) is None else None
