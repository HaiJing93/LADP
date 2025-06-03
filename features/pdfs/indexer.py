# --------------------------------------------------------------------------- #
# indexer.py – de-dupes identical uploads & merges with existing FAISS store  #
# --------------------------------------------------------------------------- #
from __future__ import annotations

import logging
from pathlib import Path
from typing import BinaryIO, Iterable, Tuple

from langchain.docstore.document import Document
from langchain.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings

from config.settings import settings
from utils.helpers import file_hash
from .extractor import extract_text_from_pdf
from .splitter import (
    split_texts,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_OVERLAP,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _get_embedder() -> AzureOpenAIEmbeddings:
    """Return a configured Azure-OpenAI embeddings client (singleton-ish)."""
    return AzureOpenAIEmbeddings(
        api_key=settings.EMBED_KEY,
        api_version=settings.EMBED_API_VERSION,
        azure_endpoint=settings.EMBED_BASE,
        deployment=settings.EMBED_DEPLOYMENT,
    )


def _known_hashes(vs: FAISS) -> set[str]:
    """Harvest SHA-256 hashes already stored in *vs* (private FAISS API)."""
    return {
        meta.metadata.get("sha256", "")
        for meta in vs.docstore._dict.values()  # type: ignore[attr-defined]
    }


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #

def index_pdfs(  # noqa: D401
    files: Iterable[BinaryIO],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_OVERLAP,
    existing_vs: FAISS | None = None,
) -> Tuple[FAISS, int]:
    """Embed **one or more** PDFs and return `(vectorstore, new_chunk_count)`.

    • Reuses *existing_vs* if supplied (incremental indexing).
    • Skips files already present in the index (content-hash match).
    """

    # --------------------------------------------------------------------- #
    # 1. Figure out which hashes we already know so we can skip duplicates   #
    # --------------------------------------------------------------------- #
    known_hashes: set[str] = _known_hashes(existing_vs) if existing_vs else set()

    # --------------------------------------------------------------------- #
    # 2. Extract & chunk any genuinely new PDFs                              #
    # --------------------------------------------------------------------- #
    new_docs: list[Document] = []

    for f in files:
        sha256 = file_hash(f)
        if sha256 in known_hashes:
            logger.info("Skipping duplicate PDF: %s", getattr(f, "name", "<upload>"))
            continue

        try:
            texts = extract_text_from_pdf(f)
        except Exception:
            # extractor already logged the error – move on to the next file
            continue

        if not any(texts):
            logger.info("No readable text in %s", getattr(f, "name", "<upload>"))
            continue

        fname = Path(getattr(f, "name", "upload")).stem
        for page_num, text in enumerate(texts, start=1):
            for chunk in split_texts(
                [text],
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            ):
                if chunk.strip():
                    new_docs.append(
                        Document(
                            page_content=chunk,
                            metadata={
                                "source": fname,
                                "page": page_num,
                                "sha256": sha256,
                            },
                        )
                    )

    # --------------------------------------------------------------------- #
    # 3. Nothing new? Just return what we started with                       #
    # --------------------------------------------------------------------- #
    if not new_docs:
        if existing_vs is None:
            raise ValueError("No new PDF content to index and no existing vectorstore supplied.")
        logger.info("No new chunks to add – returning existing vectorstore.")
        return existing_vs, 0

    # --------------------------------------------------------------------- #
    # 4. Embed the new chunks and update / create the FAISS store            #
    # --------------------------------------------------------------------- #
    logger.info("Embedding %s new chunks …", len(new_docs))
    embeddings = _get_embedder()

    if existing_vs is None:
        vectorstore = FAISS.from_documents(new_docs, embeddings)
    else:
        # API change in LangChain ≥ 0.1 – embeddings already stored inside *existing_vs*
        existing_vs.add_documents(new_docs)                 # ← **fixed**
        vectorstore = existing_vs

    return vectorstore, len(new_docs)