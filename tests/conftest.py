import struct
import zlib

import pytest

from image_interrogator.providers.base import Provider


def _png_chunk(kind, body):
    return (struct.pack(">I", len(body)) + kind + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))


def make_png(width=1, height=1):
    """A valid 8-bit RGB PNG built from the standard library only"""
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", header)
            + _png_chunk(b"IDAT", zlib.compress(raw)) + _png_chunk(b"IEND", b""))


# Not decodable, but carries the JPEG start-of-image and JFIF markers
MINIMAL_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


class FakeProvider(Provider):
    type_name = "fake"
    default_model = "fake-model"

    def __init__(self, reply="", settings=None):
        super().__init__(settings or {})
        self.reply = reply
        self.calls = []

    def complete(self, system, prompt, image):
        self.calls.append((system, prompt, image))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@pytest.fixture
def fake():
    return FakeProvider


@pytest.fixture
def png_bytes():
    return make_png()


@pytest.fixture
def jpeg_bytes():
    return MINIMAL_JPEG


@pytest.fixture
def png_file(tmp_path, png_bytes):
    path = tmp_path / "sample.png"
    path.write_bytes(png_bytes)
    return path


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point the user config at an empty temp directory"""
    path = tmp_path / "config.toml"
    monkeypatch.setenv("IMAGE_INTERROGATOR_CONFIG", str(path))
    return path
