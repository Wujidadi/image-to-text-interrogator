import pytest

from image_interrogator import ConfigError, ProviderError, load_image
from image_interrogator.providers import create_provider


def make(monkeypatch, *, poll=({"data": {"status": "completed", "outputs": ["out"]}},),
         submit=None, upload=None, settings=None):
    monkeypatch.setenv("WAVESPEED_API_KEY", "ws")
    monkeypatch.setattr("time.sleep", lambda s: None)
    p = create_provider({"type": "wavespeed-endpoint", **(settings or {})})
    calls = {"post": [], "get": [], "put": []}
    polls = list(poll)

    def fake_post(url, payload, headers=None):
        calls["post"].append((url, payload, headers or {}))
        if url.endswith("/media/uploads"):
            return upload or {"data": {"download_url": "https://cdn/x.png",
                                       "upload": {"method": "PUT", "url": "https://put/x",
                                                  "headers": {"X-Up": "1"}}}}
        return submit or {"data": {"id": "pred-1"}}

    def fake_get(url, headers=None):
        calls["get"].append((url, headers or {}))
        return polls.pop(0)

    def fake_put(url, data, headers=None):
        calls["put"].append((url, data, headers or {}))

    monkeypatch.setattr(p, "_post_json", fake_post)
    monkeypatch.setattr(p, "_get_json", fake_get)
    monkeypatch.setattr(p, "_put_bytes", fake_put)
    return p, calls


def test_upload_submit_poll(monkeypatch, png_file, png_bytes):
    p, calls = make(monkeypatch, settings={"extra": {"temperature": 0.2}})
    image = load_image(png_file)
    assert p.describe() == "wavespeed-endpoint nvidia/nemotron-3-nano-omni/vision"
    assert p.complete("S", "U", image) == "out"
    upload_url, upload_payload, headers = calls["post"][0]
    assert upload_url == "https://api.wavespeed.ai/api/v3/media/uploads"
    assert upload_payload == {"filename": "sample.png", "size": len(png_bytes),
                              "content_type": "image/png"}
    assert headers["Authorization"] == "Bearer ws"
    assert calls["put"] == [("https://put/x", png_bytes, {"X-Up": "1"})]
    submit_url, payload, _ = calls["post"][1]
    assert submit_url == "https://api.wavespeed.ai/api/v3/nvidia/nemotron-3-nano-omni/vision"
    assert payload == {"prompt": "U", "system_prompt": "S", "image": "https://cdn/x.png",
                       "max_tokens": 1024, "temperature": 0.2}
    assert calls["get"][0][0] == "https://api.wavespeed.ai/api/v3/predictions/pred-1/result"


def test_bytes_input_gets_a_filename(monkeypatch, png_bytes):
    p, calls = make(monkeypatch)
    p.complete("S", "U", load_image(png_bytes))
    assert calls["post"][0][1]["filename"] == "image.png"


def test_polls_until_completed(monkeypatch, png_bytes):
    p, calls = make(monkeypatch, poll=({"data": {"status": "created"}},
                                       {"data": {"status": "processing"}},
                                       {"data": {"status": "completed",
                                                 "outputs": [{"output": "done"}],
                                                 "timings": {"inference": 1500}}}))
    assert p.complete("S", "U", load_image(png_bytes)) == "done"
    assert len(calls["get"]) == 3
    assert p.last_usage == {"inference_ms": 1500}


def test_failed_status(monkeypatch, png_bytes):
    p, _ = make(monkeypatch, poll=({"data": {"status": "failed", "error": "bad"}},))
    with pytest.raises(ProviderError, match="failed: bad"):
        p.complete("S", "U", load_image(png_bytes))


def test_poll_timeout(monkeypatch, png_bytes):
    p, _ = make(monkeypatch, poll=[{"data": {"status": "processing"}}] * 50,
                settings={"timeout": 0, "poll_interval": 1})
    with pytest.raises(ProviderError, match="still processing after 0s"):
        p.complete("S", "U", load_image(png_bytes))


def test_bad_shapes(monkeypatch, png_bytes):
    p, _ = make(monkeypatch, upload={"data": {}})
    with pytest.raises(ProviderError, match="upload"):
        p.complete("S", "U", load_image(png_bytes))
    p, _ = make(monkeypatch, submit={"data": {}})
    with pytest.raises(ProviderError, match="no prediction id"):
        p.complete("S", "U", load_image(png_bytes))
    p, _ = make(monkeypatch, poll=({"data": {"status": "completed", "outputs": []}},))
    with pytest.raises(ProviderError, match="no text output"):
        p.complete("S", "U", load_image(png_bytes))
    p, _ = make(monkeypatch, poll=({"data": {"status": "completed", "outputs": [{"x": 1}]}},))
    with pytest.raises(ProviderError, match="no text output"):
        p.complete("S", "U", load_image(png_bytes))


def test_key_required(monkeypatch, png_bytes):
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="WAVESPEED_API_KEY"):
        create_provider({"type": "wavespeed-endpoint"}).complete("S", "U", load_image(png_bytes))
