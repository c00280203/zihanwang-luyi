"""Courseware storage service.

Provides one interface for saving and deleting files. The backing store is
selected by STORAGE_MODE: either the local filesystem or Supabase Storage.
"""
import os
import uuid
from pathlib import Path

from app.config import Config


def _safe_filename(original):
    """Build a collision-free storage path for an uploaded file."""
    suffix = Path(original or "").suffix.lower()
    if suffix not in (".pdf", ".pptx"):
        suffix = ".bin"
    return f"{uuid.uuid4().hex}{suffix}"


def save_file(file_storage, original_filename):
    """Persist an uploaded file and return its public URL.

    Returns:
        A URL/path string usable as Resource.file_url.
    """
    filename = _safe_filename(original_filename)
    mode = Config.STORAGE_MODE

    if mode == "supabase":
        return _save_to_supabase(file_storage, filename)
    return _save_to_local(file_storage, filename)


def delete_file(file_url):
    """Delete a previously stored file, ignoring missing files."""
    mode = Config.STORAGE_MODE
    if mode == "supabase":
        return _delete_from_supabase(file_url)
    return _delete_from_local(file_url)


def fetch_bytes(resource):
    """Return the raw bytes of a stored resource for AI text extraction.

    Seeded courseware keeps a local /static/courseware/... URL even when the
    app runs on Vercel with Supabase storage, so local URLs are always read
    from disk and only absolute URLs are downloaded over HTTP.
    """
    url = resource.file_url or ""
    if url.startswith("/static/"):
        return Path(_local_path(url)).read_bytes()
    if Config.STORAGE_MODE == "supabase":
        return _fetch_from_supabase(url)
    return Path(_local_path(url)).read_bytes()


# --- Local filesystem backend ------------------------------------------------

def _local_path(file_url):
    """Resolve a stored /uploads/... URL to an absolute local path."""
    name = Path(file_url).name
    return os.path.join(Config.UPLOAD_FOLDER, name)


def _save_to_local(file_storage, filename):
    """Write the upload into the local uploads directory."""
    folder = Path(Config.UPLOAD_FOLDER)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / filename
    file_storage.save(str(destination))
    return f"/static/courseware/{filename}"


def _delete_from_local(file_url):
    """Remove a file from the local uploads directory if present."""
    path = Path(_local_path(file_url))
    if path.exists():
        path.unlink()
    return True


# --- Supabase Storage backend ------------------------------------------------

def _supabase_headers():
    """Build authorization headers for Supabase Storage REST calls."""
    return {"apikey": Config.SUPABASE_KEY, "Authorization": f"Bearer {Config.SUPABASE_KEY}"}


def _save_to_supabase(file_storage, filename):
    """Upload the file to the configured Supabase bucket."""
    import requests

    url = (
        f"{Config.SUPABASE_URL}/storage/v1/object/"
        f"{Config.SUPABASE_BUCKET}/{filename}"
    )
    file_storage.stream.seek(0)
    response = requests.post(
        url,
        headers=_supabase_headers(),
        data=file_storage.read(),
        timeout=60,
    )
    response.raise_for_status()
    return (
        f"{Config.SUPABASE_URL}/storage/v1/object/public/"
        f"{Config.SUPABASE_BUCKET}/{filename}"
    )


def _delete_from_supabase(file_url):
    """Delete an object from the Supabase bucket given its public URL."""
    import requests

    prefix = f"/storage/v1/object/public/{Config.SUPABASE_BUCKET}/"
    if prefix not in (file_url or ""):
        return False
    filename = file_url.split(prefix, 1)[1]
    url = (
        f"{Config.SUPABASE_URL}/storage/v1/object/"
        f"{Config.SUPABASE_BUCKET}/{filename}"
    )
    response = requests.delete(url, headers=_supabase_headers(), timeout=30)
    return response.ok


def _fetch_from_supabase(file_url):
    """Download a stored object's bytes through its public URL."""
    import requests

    response = requests.get(file_url, timeout=60)
    response.raise_for_status()
    return response.content
