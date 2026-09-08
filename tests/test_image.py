import base64
import io

import pytest

from image_interrogator import ImageError, ImageInput, load_image
from image_interrogator.image import SIZE_WARNING_BYTES, detect_media_type


def test_detect_media_type(png_bytes, jpeg_bytes):
    assert detect_media_type(png_bytes) == "image/png"
    assert detect_media_type(jpeg_bytes) == "image/jpeg"
    assert detect_media_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert detect_media_type(b"GIF89a" + b"\x00" * 10) == "image/gif"
    assert detect_media_type(b"\x00\x00\x00\x18ftypheic") is None
    assert detect_media_type(b"") is None


def test_load_from_path(png_file, png_bytes):
    image = load_image(png_file)
    assert isinstance(image, ImageInput)
    assert image.path == png_file.resolve()
    assert image.data == png_bytes
    assert image.media_type == "image/png"
    assert image.base64 == base64.b64encode(png_bytes).decode("ascii")
    assert image.data_uri == "data:image/png;base64," + image.base64


def test_load_from_str_and_expanduser(png_file, monkeypatch):
    monkeypatch.setenv("HOME", str(png_file.parent))
    assert load_image("~/sample.png").path == png_file.resolve()


def test_load_from_bytes_and_stream(png_bytes):
    image = load_image(png_bytes)
    assert image.path is None and image.media_type == "image/png"
    assert load_image(io.BytesIO(png_bytes)).data == png_bytes


def test_load_passthrough(png_bytes):
    image = load_image(png_bytes)
    assert load_image(image) is image


def test_missing_file(tmp_path):
    with pytest.raises(ImageError, match="not found"):
        load_image(tmp_path / "nope.png")


def test_directory(tmp_path):
    with pytest.raises(ImageError, match="not a file"):
        load_image(tmp_path)


def test_unsupported_format(tmp_path):
    path = tmp_path / "photo.heic"
    path.write_bytes(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 16)
    with pytest.raises(ImageError, match="sips"):
        load_image(path)


def test_empty_input():
    with pytest.raises(ImageError, match="empty"):
        load_image(b"")


def test_unreadable_file(tmp_path, monkeypatch):
    path = tmp_path / "a.png"
    path.write_bytes(b"x")
    monkeypatch.setattr("pathlib.Path.read_bytes",
                        lambda self: (_ for _ in ()).throw(OSError("denied")))
    with pytest.raises(ImageError, match="denied"):
        load_image(path)


def test_size_warning(png_bytes):
    small = load_image(png_bytes)
    assert small.warnings == ()
    big = load_image(png_bytes + b"\x00" * SIZE_WARNING_BYTES)
    assert any("5 MB" in w for w in big.warnings)


def test_describe(png_file, png_bytes):
    assert load_image(png_file).describe() == f"{png_file.resolve()} (image/png, {len(png_bytes)} bytes)"
    assert load_image(png_bytes).describe() == f"<bytes> (image/png, {len(png_bytes)} bytes)"
