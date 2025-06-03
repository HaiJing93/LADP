"""PDF text extraction utilities – **PyPDF2‑only** edition.

Key tweaks (v3)
---------------
* Dropped *pdfplumber* – removes double‑parsing & stream‑rewind issues.
* Works with both path‑strings and seekable binary buffers.
* Supports repeated calls on the **same** buffer by always rewinding to
  byte‑0 on entry.
* Logs (not raises) on per‑page failures so callers still receive text
  for the rest of the document.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import BinaryIO, Sequence

import PyPDF2
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="PyPDF2")

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _ensure_seek_start(f: BinaryIO | io.BufferedIOBase) -> None:  # noqa: D401
    """Rewind *f* to byte‑0 if the object supports ``seek``."""
    try:
        f.seek(0)
    except Exception:  # noqa: BLE001
        pass  # some path‑like objects don’t support seek (e.g. str)


def _page_text(reader: PyPDF2.PdfReader, page_index: int) -> str:
    """Best‑effort text extraction from a single page using PyPDF2."""
    try:
        page = reader.pages[page_index]
        # Handle encrypted files transparently if possible.
        if reader.is_encrypted:  # noqa: WPS437
            try:
                reader.decrypt("")  # attempt empty‑password unlock
            except Exception:  # noqa: BLE001
                logger.debug("Encrypted PDF – failed to decrypt.")
                return ""
        return page.extract_text() or ""
    except Exception as exc:  # noqa: BLE001
        logger.debug("PyPDF2 failed on page %s: %s", page_index, exc)
        return ""


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #

def extract_text_from_pdf(file: BinaryIO | str | Path) -> Sequence[str]:  # noqa: D401
    """Return *page‑level* texts using **PyPDF2** only.

    The function accepts either a path‑string/``Path`` or an already‑open
    binary buffer (e.g. :class:`io.BytesIO`). When the same buffer is
    reused across consecutive calls, we rewind it for you.
    """

    # Prepare a reader – deal with both path and live buffer cases.

    if isinstance(file, (str, Path)):
        # Open path *once* – the handle is closed automatically.
        with open(file, "rb") as fp:  # noqa: WPS515
            reader = PyPDF2.PdfReader(fp)
            pages = [_page_text(reader, idx) for idx in range(len(reader.pages))]
        return pages

    # For buffers: rewind to start so PyPDF2 can parse from byte‑0.
    _ensure_seek_start(file)
    reader = PyPDF2.PdfReader(file)
    return [_page_text(reader, idx) for idx in range(len(reader.pages))]