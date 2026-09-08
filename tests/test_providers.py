import io
import json
import urllib.error

import pytest

from image_interrogator import ConfigError, OverloadedError, ProviderError
from image_interrogator.providers import PROVIDER_TYPES, create_provider, register
from image_interrogator.providers.base import Provider


def test_register_and_create(monkeypatch):
    monkeypatch.setattr("image_interrogator.providers.PROVIDER_TYPES", {})

    @register
    class Registered(Provider):
        type_name = "registered"
        default_model = "m"

    assert "registered" not in PROVIDER_TYPES
    assert isinstance(create_provider({"type": "registered"}), Registered)


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def fake_urlopen(monkeypatch, *, reply=None, error=None):
    calls = []

    def urlopen(request, timeout=None):
        calls.append((request, timeout))
        if error is not None:
            raise error
        return _Response(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    return calls


def http_error(code, body=b""):
    return urllib.error.HTTPError("http://h", code, "msg", {}, io.BytesIO(body))


def test_post_json_success(fake, monkeypatch):
    calls = fake_urlopen(monkeypatch, reply={"ok": 1})
    p = fake(settings={"timeout": 7})
    assert p._post_json("http://h/x", {"a": 1}, {"X-K": "v"}) == {"ok": 1}
    request, timeout = calls[0]
    assert timeout == 7
    assert request.full_url == "http://h/x"
    assert json.loads(request.data) == {"a": 1}
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("X-k") == "v"


def test_post_json_http_error(fake, monkeypatch):
    fake_urlopen(monkeypatch, error=http_error(400, b"bad request"))
    with pytest.raises(ProviderError, match="HTTP 400 from http://h/x: bad request"):
        fake()._post_json("http://h/x", {})


def test_post_json_http_error_without_body(fake, monkeypatch):
    fake_urlopen(monkeypatch, error=http_error(500))
    with pytest.raises(ProviderError, match="HTTP 500 from http://h/x$"):
        fake()._post_json("http://h/x", {})


@pytest.mark.parametrize("code", [429, 503, 529])
def test_post_json_overloaded(fake, monkeypatch, code):
    fake_urlopen(monkeypatch, error=http_error(code, b"overloaded"))
    with pytest.raises(OverloadedError, match=f"HTTP {code}"):
        fake()._post_json("http://h/x", {})


def test_post_json_network_error(fake, monkeypatch):
    fake_urlopen(monkeypatch, error=OSError("refused"))
    with pytest.raises(ProviderError, match="request to http://h/x failed: refused"):
        fake()._post_json("http://h/x", {})


def test_post_json_invalid_json(fake, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda request, timeout=None: _Response(b"not json"))
    with pytest.raises(ProviderError, match="failed"):
        fake()._post_json("http://h/x", {})


def test_unknown_type_message():
    with pytest.raises(ConfigError, match="unknown provider type"):
        create_provider({"type": None})
