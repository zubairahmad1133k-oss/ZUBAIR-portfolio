"""Safe image uploads. The stored name is random and the type is detected
from the file's actual bytes, so the original file name or extension can never
cause a file to be treated as code."""
import secrets
from pathlib import Path

from flask import current_app

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PDF_BYTES = 10 * 1024 * 1024
MIME_TYPES = {
    "png": "image/png", "jpg": "image/jpeg", "gif": "image/gif",
    "webp": "image/webp", "pdf": "application/pdf",
}


def _require_uploads() -> None:
    if not current_app.config.get("UPLOADS_ENABLED", True):
        raise ValueError("File uploads are turned off on this host because it has no permanent storage.")


def detect_image_type(head: bytes) -> str | None:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def public_folder() -> Path:
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / "public"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_public_image(file_storage) -> str:
    """Validate and store an uploaded image; return its stored file name."""
    _require_uploads()
    data = file_storage.read(MAX_IMAGE_BYTES + 1)
    if not data:
        raise ValueError("The uploaded file is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("The image is larger than 5 MB.")
    kind = detect_image_type(data[:16])
    if kind is None:
        raise ValueError("Only PNG, JPG, GIF or WebP images are allowed.")
    name = f"{secrets.token_hex(16)}.{kind}"
    (public_folder() / name).write_bytes(data)
    return name


def delete_public_file(filename: str | None) -> None:
    if not filename:
        return
    folder = public_folder().resolve()
    target = (folder / filename).resolve()
    if target.parent == folder and target.is_file():
        target.unlink()


def private_folder() -> Path:
    """Documents live here. This folder is never served by a public route."""
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / "private"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def detect_file_type(head: bytes) -> str | None:
    """Detect png/jpg/gif/webp/pdf from the file's real first bytes."""
    if head.startswith(b"%PDF-"):
        return "pdf"
    return detect_image_type(head)


def save_media_file(file_storage) -> dict:
    """Validate and store an image or PDF. Returns stored name, type, mime, size."""
    _require_uploads()
    data = file_storage.read(MAX_PDF_BYTES + 1)
    if not data:
        raise ValueError("The file is empty.")
    kind = detect_file_type(data[:16])
    if kind is None:
        raise ValueError("Only PNG, JPG, GIF, WebP images and PDF files are allowed.")
    limit = MAX_PDF_BYTES if kind == "pdf" else MAX_IMAGE_BYTES
    if len(data) > limit:
        raise ValueError(f"The file is larger than {limit // (1024 * 1024)} MB.")
    folder = private_folder() if kind == "pdf" else public_folder()
    name = f"{secrets.token_hex(16)}.{kind}"
    (folder / name).write_bytes(data)
    return {"filename": name, "type": kind, "mime": MIME_TYPES[kind], "size": len(data)}


def delete_media_file(filename: str | None, private: bool) -> None:
    if not filename:
        return
    folder = (private_folder() if private else public_folder()).resolve()
    target = (folder / filename).resolve()
    if target.parent == folder and target.is_file():
        target.unlink()
