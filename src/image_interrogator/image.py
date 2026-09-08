"""Image loading: a path, raw bytes or a binary stream become an ImageInput"""

import base64
import io
from dataclasses import dataclass, field, replace
from pathlib import Path

from .errors import ImageError

# Anthropic rejects base64 images above 5 MB; other backends are more lenient
SIZE_WARNING_BYTES = 5 * 1024 * 1024

_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def detect_media_type(data):
    """MIME type from the file signature, or None when unsupported.
    imghdr was removed in Python 3.13, hence the hand-rolled check"""
    for signature, media_type in _SIGNATURES:
        if data.startswith(signature):
            return media_type
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@dataclass(frozen=True)
class ImageInput:
    data: bytes
    media_type: str
    path: Path | None = None
    warnings: tuple = field(default=(), compare=False)

    @property
    def base64(self):
        return base64.b64encode(self.data).decode("ascii")

    @property
    def data_uri(self):
        return f"data:{self.media_type};base64,{self.base64}"

    def describe(self):
        source = str(self.path) if self.path else "<bytes>"
        return f"{source} ({self.media_type}, {len(self.data)} bytes)"


def _read_path(value):
    path = Path(value).expanduser()
    if not path.exists():
        raise ImageError(f"image not found: {path}")
    if not path.is_file():
        raise ImageError(f"not a file: {path}")
    try:
        return path.resolve(), path.read_bytes()
    except OSError as e:
        raise ImageError(f"cannot read {path}: {e}") from e


def load_image(source):
    """Accept an ImageInput, a path (str or Path), bytes, or a binary
    stream with read(); the format is sniffed from the content"""
    if isinstance(source, ImageInput):
        return source
    path = None
    if isinstance(source, (str, Path)):
        path, data = _read_path(source)
    elif isinstance(source, (bytes, bytearray)):
        data = bytes(source)
    else:
        data = source.read()
    if not data:
        raise ImageError(f"empty image input: {path or '<bytes>'}")
    media_type = detect_media_type(data)
    if media_type is None:
        raise ImageError(f"unsupported image format: {path or '<bytes>'} "
                         "(PNG, JPEG, WebP and GIF are accepted; convert with "
                         '"sips -s format png <file> --out <file>.png" on macOS)')
    warnings = ()
    if len(data) > SIZE_WARNING_BYTES:
        warnings = (f"image is {len(data) / 1024 / 1024:.1f} MB, above the 5 MB "
                    "limit of some backends (Anthropic)",)
    return ImageInput(data=data, media_type=media_type, path=path, warnings=warnings)


_PIL_FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP",
                "image/gif": "GIF"}


def resize_image(image, max_side):
    """Return a copy scaled so that the longer side is at most `max_side`
    pixels, re-encoded in the original format; the image itself when it
    already fits. Needs the optional Pillow dependency"""
    try:
        from PIL import Image as PILImage
    except ImportError as e:
        raise ImageError("resizing needs Pillow: install "
                         '"image-to-text-interrogator[resize]"') from e
    try:
        with PILImage.open(io.BytesIO(image.data)) as source:
            width, height = source.size
            if max(width, height) <= max_side:
                return image
            scale = max_side / max(width, height)
            target = (max(1, round(width * scale)), max(1, round(height * scale)))
            resized = source.convert("RGB") if image.media_type == "image/jpeg" else source
            buffer = io.BytesIO()
            resized.resize(target, PILImage.LANCZOS).save(
                buffer, format=_PIL_FORMATS[image.media_type])
    except (OSError, ValueError) as e:
        raise ImageError(f"cannot decode image for resizing: {e}") from e
    data = buffer.getvalue()
    warnings = tuple(w for w in image.warnings if "5 MB" not in w)
    warnings += (f"resized from {width}x{height} to {target[0]}x{target[1]} "
                 f"({len(data)} bytes)",)
    return replace(image, data=data, warnings=warnings)
