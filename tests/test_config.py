import pytest

from image_interrogator import ConfigError, load_config
from image_interrogator.config import config_path, user_preset_dir
from image_interrogator.providers import Provider, create_provider


def test_missing_file_gives_builtin(isolated_config):
    config = load_config()
    settings = config.provider_settings()
    assert settings["type"] == "ollama"
    assert settings["model"] == "qwen3.6:35b"
    assert settings["name"] == "ollama"
    assert config.fallbacks == []
    assert config.path is None


def test_default_path_without_env(monkeypatch):
    monkeypatch.delenv("IMAGE_INTERROGATOR_CONFIG", raising=False)
    assert config_path().as_posix().endswith("/.config/image-interrogator/config.toml")
    assert user_preset_dir().name == "interrogators"


def test_profiles_and_overrides(isolated_config):
    isolated_config.write_text("""
default_provider = "cloud"
language = "zh"
fallbacks = ["ollama"]
preset_dirs = ["~/presets"]
[providers.cloud]
type = "openai"
url = "https://example.test/v1"
model = "m"
api_key_env = "EXAMPLE_KEY"
""", encoding="utf-8")
    config = load_config()
    assert config.language == "zh"
    assert config.fallbacks == ["ollama"]
    assert config.preset_dirs[0].name == "presets" and "~" not in str(config.preset_dirs[0])
    assert config.provider_settings()["model"] == "m"
    assert config.provider_settings("ollama")["type"] == "ollama"
    assert config.provider_settings(overrides={"model": "n"})["model"] == "n"
    with pytest.raises(ConfigError, match="unknown provider profile"):
        config.provider_settings("nope")


def test_explicit_path(tmp_path):
    path = tmp_path / "other.toml"
    path.write_text('[providers.x]\ntype = "ollama"\n', encoding="utf-8")
    assert "x" in load_config(path).providers


def test_bad_default(isolated_config):
    isolated_config.write_text('default_provider = "x"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="not defined"):
        load_config()


def test_bad_fallback(isolated_config):
    isolated_config.write_text('fallbacks = ["x"]\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="fallback"):
        load_config()


def test_profile_without_type(isolated_config):
    isolated_config.write_text('[providers.x]\nmodel = "m"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match='"type"'):
        load_config()


def test_parse_error(isolated_config):
    isolated_config.write_text("not = = toml", encoding="utf-8")
    with pytest.raises(ConfigError, match="failed to parse"):
        load_config()


def test_api_key_env(fake, monkeypatch):
    provider = fake(settings={"api_key_env": "K"})
    monkeypatch.delenv("K", raising=False)
    with pytest.raises(ConfigError, match="K is not set"):
        provider.api_key
    monkeypatch.setenv("K", "secret")
    assert provider.api_key == "secret"


def test_api_key_literal_and_none(fake):
    assert fake(settings={"api_key": "lit"}).api_key == "lit"
    assert fake().api_key is None


def test_unknown_type():
    with pytest.raises(ConfigError, match="unknown provider type"):
        create_provider({"type": "nope", "model": "m"})


def test_provider_without_model():
    class NoDefault(Provider):
        type_name = "nodefault"

    with pytest.raises(ConfigError, match="no model"):
        NoDefault({"name": "x"})


def test_provider_defaults(fake):
    provider = fake(settings={"name": "p", "url": "http://h/"})
    assert provider.name == "p" and provider.url == "http://h"
    assert provider.timeout == 300 and provider.extra == {}
    assert provider.describe() == "fake fake-model"
    with pytest.raises(NotImplementedError):
        Provider({"model": "m"}).complete("S", "U", None)
