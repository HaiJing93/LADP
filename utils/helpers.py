import hashlib


def file_hash(file_obj, chunk_size: int = 8192) -> str:
    """Return SHA‑256 hash for a file‑like object; resets pointer to start."""
    hasher = hashlib.sha256()
    while chunk := file_obj.read(chunk_size):
        hasher.update(chunk)
    file_obj.seek(0)
    return hasher.hexdigest()