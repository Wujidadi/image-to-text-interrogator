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
        fake(settings={"retries": 0})._post_json("http://h/x", {})


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


# --- concrete backends -------------------------------------------------------

def capture(monkeypatch, provider, reply):
    calls = []

    def fake_post(url, payload, headers=None):
        calls.append((url, payload, headers or {}))
        return reply

    monkeypatch.setattr(provider, "_post_json", fake_post)
    return calls


def test_ollama(monkeypatch, png_bytes):
    from image_interrogator import load_image
    image = load_image(png_bytes)
    p = create_provider({"type": "ollama", "extra": {"options": {"num_predict": 900}}})
    calls = capture(monkeypatch, p, {"message": {"content": "out"}})
    assert p.complete("S", "U", image) == "out"
    url, payload, _ = calls[0]
    assert url == "http://localhost:11434/api/chat"
    assert payload["model"] == "qwen3.6:35b"
    assert payload["think"] is False and payload["stream"] is False
    assert payload["messages"][0] == {"role": "system", "content": "S"}
    assert payload["messages"][1] == {"role": "user", "content": "U", "images": [image.base64]}
    assert payload["options"] == {"num_ctx": 16384, "num_predict": 900}


def test_ollama_think_and_num_ctx_override(monkeypatch, png_bytes):
    from image_interrogator import load_image
    p = create_provider({"type": "ollama", "think": True, "num_ctx": 8192})
    calls = capture(monkeypatch, p, {"message": {"content": "out"}})
    p.complete("S", "U", load_image(png_bytes))
    payload = calls[0][1]
    assert payload["think"] is True and payload["options"]["num_ctx"] == 8192


def test_ollama_bad_shape(monkeypatch, png_bytes):
    from image_interrogator import load_image
    p = create_provider({"type": "ollama"})
    capture(monkeypatch, p, {"message": "nope"})
    with pytest.raises(ProviderError, match="unexpected response shape"):
        p.complete("S", "U", load_image(png_bytes))


def test_openai(monkeypatch, png_bytes):
    from image_interrogator import load_image
    image = load_image(png_bytes)
    p = create_provider({"type": "openai", "model": "m", "api_key": "k",
                         "url": "https://h/v1/", "extra": {"temperature": 0.2}})
    calls = capture(monkeypatch, p, {"choices": [{"message": {"content": "out"}}]})
    assert p.complete("S", "U", image) == "out"
    url, payload, headers = calls[0]
    assert url == "https://h/v1/chat/completions"
    assert headers["Authorization"] == "Bearer k"
    assert payload["temperature"] == 0.2 and payload["max_tokens"] == 4000
    assert payload["messages"][0] == {"role": "system", "content": "S"}
    assert payload["messages"][1] == {
        "role": "user",
        "content": [{"type": "text", "text": "U"},
                    {"type": "image_url", "image_url": {"url": image.data_uri}}]}


def test_openai_without_key_and_custom_max_tokens(monkeypatch, png_bytes):
    from image_interrogator import load_image
    p = create_provider({"type": "openai", "model": "m", "url": "http://localhost:1234/v1",
                         "max_tokens": 700})
    calls = capture(monkeypatch, p, {"choices": [{"message": {"content": "out"}}]})
    p.complete("S", "U", load_image(png_bytes))
    _, payload, headers = calls[0]
    assert "Authorization" not in headers and payload["max_tokens"] == 700


@pytest.mark.parametrize("reply", [{"error": "x"}, {"choices": []},
                                   {"choices": [{"message": {"content": None}}]}])
def test_openai_bad_shape(monkeypatch, png_bytes, reply):
    from image_interrogator import load_image
    p = create_provider({"type": "openai", "model": "m"})
    capture(monkeypatch, p, reply)
    with pytest.raises(ProviderError):
        p.complete("S", "U", load_image(png_bytes))


def test_wavespeed(monkeypatch, png_bytes):
    from image_interrogator import load_image
    monkeypatch.setenv("WAVESPEED_API_KEY", "ws")
    p = create_provider({"type": "wavespeed"})
    calls = capture(monkeypatch, p, {"choices": [{"message": {"content": "out"}}]})
    assert p.complete("S", "U", load_image(png_bytes)) == "out"
    url, payload, headers = calls[0]
    assert url == "https://llm.wavespeed.ai/v1/chat/completions"
    assert headers["Authorization"] == "Bearer ws"
    assert payload["model"] == "minimax/minimax-m3"


def test_wavespeed_key_env_override(monkeypatch):
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    monkeypatch.setenv("OTHER_KEY", "o")
    assert create_provider({"type": "wavespeed", "api_key_env": "OTHER_KEY"}).api_key == "o"
    with pytest.raises(ConfigError, match="WAVESPEED_API_KEY"):
        create_provider({"type": "wavespeed"}).api_key


def test_anthropic(monkeypatch, png_bytes):
    from image_interrogator import load_image
    image = load_image(png_bytes)
    p = create_provider({"type": "anthropic", "api_key": "k"})
    calls = capture(monkeypatch, p, {"stop_reason": "end_turn",
                                     "content": [{"type": "text", "text": "out"},
                                                 {"type": "tool_use"},
                                                 {"type": "text", "text": "!"}]})
    assert p.complete("S", "U", image) == "out!"
    url, payload, headers = calls[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers["x-api-key"] == "k" and headers["anthropic-version"] == "2023-06-01"
    assert payload["system"] == "S" and payload["model"] == "claude-sonnet-5"
    assert payload["max_tokens"] == 4096
    assert payload["messages"] == [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                     "data": image.base64}},
        {"type": "text", "text": "U"}]}]


def test_anthropic_refusal(monkeypatch, png_bytes):
    from image_interrogator import RefusalError, load_image
    p = create_provider({"type": "anthropic", "api_key": "k"})
    capture(monkeypatch, p, {"stop_reason": "refusal", "content": [],
                             "stop_details": {"category": "x"}})
    with pytest.raises(RefusalError, match=r"refused \(x\)"):
        p.complete("S", "U", load_image(png_bytes))
    capture(monkeypatch, p, {"stop_reason": "refusal", "content": []})
    with pytest.raises(RefusalError, match="unspecified"):
        p.complete("S", "U", load_image(png_bytes))


def test_anthropic_bad_shape(monkeypatch, png_bytes):
    from image_interrogator import load_image
    p = create_provider({"type": "anthropic", "api_key": "k"})
    capture(monkeypatch, p, {"content": "x"})
    with pytest.raises(ProviderError, match="unexpected response shape"):
        p.complete("S", "U", load_image(png_bytes))


def test_registered_types():
    assert set(PROVIDER_TYPES) >= {"ollama", "openai", "wavespeed", "anthropic"}


def test_anthropic_without_key(monkeypatch, png_bytes):
    from image_interrogator import load_image
    p = create_provider({"type": "anthropic", "url": "http://proxy.local", "api_key": None})
    calls = capture(monkeypatch, p, {"content": [{"type": "text", "text": "out"}]})
    assert p.complete("S", "U", load_image(png_bytes)) == "out"
    assert "x-api-key" not in calls[0][2]


# --- retries and usage -------------------------------------------------------

def test_retry_on_overload(fake, monkeypatch):
    attempts = []
    sleeps = []

    def urlopen(request, timeout=None):
        attempts.append(1)
        if len(attempts) < 3:
            raise http_error(529, b"overloaded")
        return _Response(b'{"ok": 1}')

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    monkeypatch.setattr("time.sleep", sleeps.append)
    assert fake()._post_json("http://h/x", {}) == {"ok": 1}
    assert len(attempts) == 3 and sleeps == [1, 2]


def test_retry_exhausted(fake, monkeypatch):
    fake_urlopen(monkeypatch, error=http_error(429, b"slow down"))
    monkeypatch.setattr("time.sleep", lambda s: None)
    with pytest.raises(OverloadedError, match="HTTP 429"):
        fake(settings={"retries": 1})._post_json("http://h/x", {})


def test_no_retry_on_other_errors(fake, monkeypatch):
    calls = fake_urlopen(monkeypatch, error=http_error(500))
    monkeypatch.setattr("time.sleep", lambda s: (_ for _ in ()).throw(AssertionError("slept")))
    with pytest.raises(ProviderError):
        fake()._post_json("http://h/x", {})
    assert len(calls) == 1


def test_retries_zero(fake, monkeypatch):
    calls = fake_urlopen(monkeypatch, error=http_error(529))
    with pytest.raises(OverloadedError):
        fake(settings={"retries": 0})._post_json("http://h/x", {})
    assert len(calls) == 1


def test_openai_usage_and_cost(monkeypatch, png_bytes):
    from image_interrogator import load_image
    p = create_provider({"type": "openai", "model": "m",
                         "price": {"input": 0.30, "output": 1.20}})
    capture(monkeypatch, p, {"choices": [{"message": {"content": "out"}}],
                             "usage": {"prompt_tokens": 1000, "completion_tokens": 500}})
    p.complete("S", "U", load_image(png_bytes))
    assert p.last_usage == {"prompt_tokens": 1000, "completion_tokens": 500,
                            "cost_usd": 0.0009}


def test_openai_usage_without_price(monkeypatch, png_bytes):
    from image_interrogator import load_image
    p = create_provider({"type": "openai", "model": "m"})
    capture(monkeypatch, p, {"choices": [{"message": {"content": "out"}}],
                             "usage": {"prompt_tokens": 1}})
    p.complete("S", "U", load_image(png_bytes))
    assert p.last_usage == {"prompt_tokens": 1}
    capture(monkeypatch, p, {"choices": [{"message": {"content": "out"}}]})
    p.complete("S", "U", load_image(png_bytes))
    assert p.last_usage is None


def test_ollama_usage(monkeypatch, png_bytes):
    from image_interrogator import load_image
    p = create_provider({"type": "ollama"})
    capture(monkeypatch, p, {"message": {"content": "out"}, "prompt_eval_count": 900,
                             "eval_count": 300, "eval_duration": 5_000_000_000,
                             "load_duration": 1})
    p.complete("S", "U", load_image(png_bytes))
    assert p.last_usage == {"prompt_eval_count": 900, "eval_count": 300,
                            "eval_duration": 5_000_000_000, "load_duration": 1,
                            "tokens_per_second": 60.0}


def test_anthropic_usage(monkeypatch, png_bytes):
    from image_interrogator import load_image
    p = create_provider({"type": "anthropic", "api_key": "k",
                         "price": {"input": 3, "output": 15}})
    capture(monkeypatch, p, {"content": [{"type": "text", "text": "out"}],
                             "usage": {"input_tokens": 1000, "output_tokens": 100}})
    p.complete("S", "U", load_image(png_bytes))
    assert p.last_usage == {"input_tokens": 1000, "output_tokens": 100, "cost_usd": 0.0045}
