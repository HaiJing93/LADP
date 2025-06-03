from __future__ import annotations

import logging
from pathlib import Path
from typing import BinaryIO, Iterable, Tuple

import pandas as pd
from langchain.docstore.document import Document
from langchain.vectorstores import FAISS

from utils.helpers import file_hash
from features.pdfs.indexer import _get_embedder, _known_hashes
from features.pdfs.splitter import (
    split_texts,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_OVERLAP,
)

logger = logging.getLogger(__name__)


def _extract_sheets(file: BinaryIO | str | Path) -> dict[str, str]:
    """Return mapping of sheet name to CSV text."""
    try:
        if hasattr(file, "seek"):
            try:
                file.seek(0)
            except Exception:
                pass
        xls = pd.ExcelFile(file)
    except Exception as exc:
        logger.error("Failed to read Excel %s: %s", getattr(file, "name", "<upload>"), exc)
        return {}

    sheets: dict[str, str] = {}
    for name in xls.sheet_names:
        try:
            df = xls.parse(name)
            sheets[name] = df.to_csv(index=False)
        except Exception as exc:
            logger.debug("Failed parsing sheet %s: %s", name, exc)
    return sheets


def index_excels(
    files: Iterable[BinaryIO],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_OVERLAP,
    existing_vs: FAISS | None = None,
) -> Tuple[FAISS, int]:
    """Embed **one or more** Excel files and return ``(vectorstore, new_chunk_count)``."""

    known_hashes: set[str] = _known_hashes(existing_vs) if existing_vs else set()
    new_docs: list[Document] = []

    for f in files:
        sha256 = file_hash(f)
        if sha256 in known_hashes:
            logger.info("Skipping duplicate Excel: %s", getattr(f, "name", "<upload>"))
            continue

        texts = _extract_sheets(f)
        if not texts:
            logger.info("No readable data in %s", getattr(f, "name", "<upload>"))
            continue

        fname = Path(getattr(f, "name", "upload")).stem
        for sheet_name, text in texts.items():
            for chunk in split_texts([text], chunk_size=chunk_size, chunk_overlap=chunk_overlap):
                if chunk.strip():
                    new_docs.append(
                        Document(
                            page_content=chunk,
                            metadata={
                                "source": fname,
                                "sheet": sheet_name,
                                "sha256": sha256,
                            },
                        )
                    )

    if not new_docs:
        if existing_vs is None:
            raise ValueError(
                "No new Excel content to index and no existing vectorstore supplied."
            )
        logger.info("No new chunks to add – returning existing vectorstore.")
        return existing_vs, 0

    logger.info("Embedding %s new chunks …", len(new_docs))
    embeddings = _get_embedder()

    if existing_vs is None:
        vectorstore = FAISS.from_documents(new_docs, embeddings)
    else:
        existing_vs.add_documents(new_docs)
        vectorstore = existing_vs

    return vectorstore, len(new_docs)
