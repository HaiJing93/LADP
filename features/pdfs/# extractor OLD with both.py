# extractor.py
"""PDF text extraction utilities with multi‑PDF friendliness.

Key tweaks (v2)
---------------
* **Always** reset the buffer cursor to byte‑0 on entry – important when the
  same UploadedFile is reused downstream.
* Clearer file‑type detection – path‑string vs buffer.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import BinaryIO, Sequence

import pdfplumber
import PyPDF2
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="PyPDF2")

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _ensure_seek_start(f: BinaryIO | io.BufferedIOBase) -> None:
    """Rewind *f* to byte‑0 if possible."""
    try:
        f.seek(0)
    except Exception:  # noqa: BLE001
        pass  # some path‑like objects don’t support seek (e.g. str)


def _page_text_with_pypdf(reader: PyPDF2.PdfReader, page_index: int) -> str:
    """Best‑effort text extraction from a single page."""
    try:
        return reader.pages[page_index].extract_text() or ""
    except Exception as exc:  # noqa: BLE001
        logger.debug("PyPDF2 failed on page %s: %s", page_index, exc)
        return ""


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

def extract_text_from_pdf(file: BinaryIO | str | Path) -> Sequence[str]:
    """Return *page‑level* texts – gracefully falling back to PyPDF2.
    Accepts multiple consecutive calls against the **same** buffer.
    """
    # If file is a buffer make sure we start at byte‑0 for pdfplumber.
    if not isinstance(file, (str, Path)):
        _ensure_seek_start(file)

    pages: list[str] = []

    try:
        with pdfplumber.open(file) as pdf:
            pyp_reader: PyPDF2.PdfReader | None = None

            for idx, page in enumerate(pdf.pages):
                text = page.extract_text() or ""

                if not text:
                    if pyp_reader is None:
                        # pdfplumber gave empty; try PyPDF2 only once per file.
                        if not isinstance(file, (str, Path)):
                            _ensure_seek_start(file)
                        pyp_reader = PyPDF2.PdfReader(file)
                    text = _page_text_with_pypdf(pyp_reader, idx)

                pages.append(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdfplumber failed (%s); pure PyPDF2 fallback: %s", file, exc)
        if not isinstance(file, (str, Path)):
            _ensure_seek_start(file)
        reader = PyPDF2.PdfReader(file)
        pages = [p.extract_text() or "" for p in reader.pages]

    return pages
