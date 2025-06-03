
# --------------------------------------------------------------------------- #
# splitter.py (unchanged except docstring tweak)                               #
# --------------------------------------------------------------------------- #
from __future__ import annotations

from typing import Sequence

from langchain.text_splitter import RecursiveCharacterTextSplitter

DEFAULT_CHUNK_SIZE = 1500
DEFAULT_OVERLAP = 250


def split_texts(
    texts: Sequence[str],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """Flatten `texts` into overlapping chunks suitable for embeddings.
    Accepts the output of *many* PDFs stitched together.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return [chunk for t in texts for chunk in splitter.split_text(t)]