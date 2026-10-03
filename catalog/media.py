"""Reading uploaded files: size, type, image dimensions and thumbnails."""

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

THUMBNAIL_SIZE = (640, 640)

# Raster formats a browser can show. SVG is deliberately absent: it can carry
# scripts, so it is only ever offered as a download.
IMAGE_FORMATS = {
    "JPEG": "image/jpeg",
    "MPO": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "WEBP": "image/webp",
    "BMP": "image/bmp",
}

EXTENSION_KINDS = {
    "document": {"pdf", "doc", "docx", "odt", "rtf", "txt", "md", "epub", "djvu"},
    "spreadsheet": {"xls", "xlsx", "ods", "csv"},
    "presentation": {"ppt", "pptx", "odp", "key"},
    "audio": {"mp3", "wav", "flac", "ogg", "m4a", "aac"},
    "video": {"mp4", "mov", "avi", "mkv", "webm"},
    "archive": {"zip", "rar", "7z", "tar", "gz"},
}


@dataclass
class FileInfo:
    size: int
    kind: str
    width: int | None = None
    height: int | None = None
    thumbnail: ContentFile | None = None


def kind_for_extension(name: str) -> str:
    extension = PurePath(name).suffix.lstrip(".").lower()
    for kind, extensions in EXTENSION_KINDS.items():
        if extension in extensions:
            return kind
    return "other"


def inspect(file) -> FileInfo:
    """Describe an uploaded file. Images are recognised by content, not by extension."""
    info = FileInfo(size=file.size, kind=kind_for_extension(file.name))
    try:
        file.seek(0)
        with Image.open(file) as image:
            if image.format not in IMAGE_FORMATS:
                return info
            image.load()
            info.kind = "image"
            info.width, info.height = image.size
            info.thumbnail = _thumbnail(image)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        logger.debug("%s is not a supported image", file.name)
    finally:
        file.seek(0)
    return info


def image_content_type(file) -> str | None:
    """MIME type of a stored image, read from its content."""
    try:
        with file.open("rb"), Image.open(file) as image:
            return IMAGE_FORMATS.get(image.format)
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _thumbnail(image: Image.Image) -> ContentFile:
    image = ImageOps.exif_transpose(image)
    image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "transparency" in image.info else "RGB")
    buffer = BytesIO()
    image.save(buffer, "WEBP", quality=82, method=6)
    return ContentFile(buffer.getvalue())


def delete_files(names) -> None:
    for name in names:
        try:
            default_storage.delete(name)
        except OSError:
            logger.warning("Could not delete %s", name, exc_info=True)
