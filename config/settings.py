from urllib.parse import urlsplit
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Centralised environment & endpoint configuration."""

    # --- Core chat deployment ---
    API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
    API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview").strip('"')
    RAW_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")

    BASE_ENDPOINT = (
        f"{urlsplit(RAW_ENDPOINT).scheme}://{urlsplit(RAW_ENDPOINT).netloc}"
        if RAW_ENDPOINT
        else None
    )

    # --- Embeddings deployment ---
    EMBED_KEY = os.getenv("AZURE_OPENAI_EMBEDDING_API_KEY", API_KEY)
    EMBED_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    EMBED_API_VERSION = os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION", API_VERSION).strip('"')
    EMBED_ENDPOINT = os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT", RAW_ENDPOINT)
    EMBED_BASE = (
        f"{urlsplit(EMBED_ENDPOINT).scheme}://{urlsplit(EMBED_ENDPOINT).netloc}"
        if EMBED_ENDPOINT
        else None
    )

    # --- Basic validation ---
    required = [API_KEY, CHAT_DEPLOYMENT, RAW_ENDPOINT, EMBED_DEPLOYMENT]
    if not all(required):
        raise RuntimeError("Missing one or more required AZURE_OPENAI_* environment variables.")

settings = Settings()