import json
import subprocess

import pytest

from image_interrogator import ConfigError, OverloadedError, ProviderError, load_image
from image_interrogator.providers import create_provider


def success(result="out", **extra):
    payload = {"type": "result", "subtype": "success", "is_error": False,
               "result": result, "total_cost_usd": 0.097,
               "modelUsage": {"claude-sonnet-5": {"inputTokens": 1}}, **extra}
    return json.dumps(payload)


def fake_run(monkeypatch, stdout="", stderr="", returncode=0, error=None):
    calls = []

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        if error is not None:
            raise error
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr("subprocess.run", run)
    return calls


def test_command_and_environment(monkeypatch, png_file):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    monkeypatch.setenv("HOME", "/h")
    calls = fake_run(monkeypatch, stdout=success())
    p = create_provider({"type": "claude-code", "timeout": 42})
    assert p.describe() == "claude-code sonnet"
    assert p.complete("SYS", "U", load_image(png_file)) == "out"
    cmd, kwargs = calls[0]
    assert cmd[:2] == ["claude", "-p"]
    assert cmd[cmd.index("--model") + 1] == "sonnet"
    assert cmd[cmd.index("--output-format") + 1] == "json"
    assert cmd[cmd.index("--system-prompt") + 1] == "SYS"
    assert cmd[cmd.index("--tools") + 1] == "Read"
    assert cmd[cmd.index("--allowedTools") + 1] == "Read"
    assert kwargs["input"] == f"Read {png_file.resolve()} with the Read tool, then: U"
    assert kwargs["capture_output"] and kwargs["text"] and kwargs["timeout"] == 42
    env = kwargs["env"]
    assert "CLAUDECODE" not in env and "CLAUDE_CODE_ENTRYPOINT" not in env
    assert env["HOME"] == "/h"
    assert p.last_usage == {"total_cost_usd": 0.097,
                            "modelUsage": {"claude-sonnet-5": {"inputTokens": 1}}}


def test_custom_command_and_model(monkeypatch, png_file):
    calls = fake_run(monkeypatch, stdout=success())
    p = create_provider({"type": "claude-code", "model": "opus",
                         "command": "/opt/bin/claude", "extra_args": ["--verbose"]})
    p.complete("S", "U", load_image(png_file))
    cmd = calls[0][0]
    assert cmd[0] == "/opt/bin/claude" and cmd[cmd.index("--model") + 1] == "opus"
    assert cmd[-1] == "--verbose"


def test_bytes_input_goes_through_temp_file(monkeypatch, png_bytes, tmp_path):
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    calls = fake_run(monkeypatch, stdout=success())
    create_provider({"type": "claude-code"}).complete("S", "U", load_image(png_bytes))
    prompt = calls[0][1]["input"]
    path = prompt.split(" ")[1]
    assert path.startswith(str(tmp_path)) and path.endswith(".png")
    assert not tmp_path.joinpath(path).exists()


def test_missing_executable(monkeypatch, png_file):
    fake_run(monkeypatch, error=FileNotFoundError())
    with pytest.raises(ConfigError, match="claude executable not found"):
        create_provider({"type": "claude-code"}).complete("S", "U", load_image(png_file))


def test_timeout(monkeypatch, png_file):
    fake_run(monkeypatch, error=subprocess.TimeoutExpired("claude", 1))
    with pytest.raises(ProviderError, match="timed out"):
        create_provider({"type": "claude-code"}).complete("S", "U", load_image(png_file))


def test_nonzero_exit(monkeypatch, png_file):
    fake_run(monkeypatch, returncode=1, stderr="Not logged in")
    with pytest.raises(ProviderError, match="exit status 1: Not logged in"):
        create_provider({"type": "claude-code"}).complete("S", "U", load_image(png_file))


def test_overloaded_exit(monkeypatch, png_file):
    fake_run(monkeypatch, returncode=1, stderr="API Error: 529 {\"type\":\"overloaded_error\"}")
    with pytest.raises(OverloadedError, match="529"):
        create_provider({"type": "claude-code"}).complete("S", "U", load_image(png_file))


def test_error_result(monkeypatch, png_file):
    fake_run(monkeypatch, stdout=json.dumps({"type": "result", "subtype": "error_max_turns",
                                             "is_error": True, "result": "Overloaded"}))
    with pytest.raises(OverloadedError, match="Overloaded"):
        create_provider({"type": "claude-code"}).complete("S", "U", load_image(png_file))
    fake_run(monkeypatch, stdout=json.dumps({"type": "result", "subtype": "error",
                                             "is_error": True}))
    with pytest.raises(ProviderError, match="error"):
        create_provider({"type": "claude-code"}).complete("S", "U", load_image(png_file))


def test_unparseable_output(monkeypatch, png_file):
    fake_run(monkeypatch, stdout="not json")
    with pytest.raises(ProviderError, match="unexpected output"):
        create_provider({"type": "claude-code"}).complete("S", "U", load_image(png_file))
    fake_run(monkeypatch, stdout=json.dumps({"type": "result", "result": 5}))
    with pytest.raises(ProviderError, match="unexpected output"):
        create_provider({"type": "claude-code"}).complete("S", "U", load_image(png_file))
