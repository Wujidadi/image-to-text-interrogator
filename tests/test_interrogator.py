import pytest

from image_interrogator import (ConfigError, ImageError, Interrogator, ProviderError,
                                RefusalError, interrogate, load_image)
from image_interrogator.prompt import EXPLICIT_ADDENDUM, LANGUAGE_DIRECTIVES, USER_MESSAGE


def test_default_preset(isolated_config, fake, png_file):
    provider = fake("  a cat  ")
    assert Interrogator(provider).interrogate(png_file) == "a cat"
    system, prompt, image = provider.calls[0]
    assert system.startswith(LANGUAGE_DIRECTIVES["en"])
    assert "expert prompt engineer" in system
    assert prompt == USER_MESSAGE
    assert image.path == png_file.resolve()


def test_accepts_bytes_and_image_input(isolated_config, fake, png_bytes):
    provider = fake("a cat")
    image = load_image(png_bytes)
    assert Interrogator(provider).interrogate(png_bytes) == "a cat"
    assert Interrogator(provider).interrogate(image) == "a cat"
    assert provider.calls[1][2] is image


def test_explicit_and_instruction(isolated_config, fake, png_bytes):
    provider = fake("a cat")
    Interrogator(provider).interrogate(png_bytes, instruction="focus on fur", explicit=True)
    system = provider.calls[0][0]
    assert EXPLICIT_ADDENDUM in system and system.endswith("focus on fur")


def test_prepare_exposes_system(isolated_config, fake):
    system, preset = Interrogator(fake()).prepare(instruction="x")
    assert system.endswith("x") and preset.name == "faithful"


def test_custom_preset_dir(isolated_config, fake, tmp_path, png_bytes):
    (tmp_path / "mine.txt").write_text("MINE", encoding="utf-8")
    provider = fake("out")
    Interrogator(provider, preset_dirs=[tmp_path]).interrogate(png_bytes, preset="mine")
    assert provider.calls[0][0].endswith("MINE")


def test_cleans_output_and_merges_paragraphs(isolated_config, fake, png_bytes):
    provider = fake("<think>hmm</think>\nPrompt:\n```\na cat\n\nsoft light\n```")
    assert Interrogator(provider).interrogate(png_bytes) == "a cat soft light"


def test_empty_reply(isolated_config, fake, png_bytes):
    with pytest.raises(ProviderError, match="empty response"):
        Interrogator(fake("```\n```")).interrogate(png_bytes)


def test_refusal_text(isolated_config, fake, png_bytes):
    with pytest.raises(RefusalError, match="refused"):
        Interrogator(fake("I cannot fulfill this request.")).interrogate(png_bytes)


def test_bad_image(isolated_config, fake, tmp_path):
    with pytest.raises(ImageError):
        Interrogator(fake("x")).interrogate(tmp_path / "nope.png")


def test_unknown_language(isolated_config, fake, png_bytes):
    with pytest.raises(ConfigError, match="unknown language"):
        Interrogator(fake("x"), language="fr")
    with pytest.raises(ConfigError, match="unknown language"):
        Interrogator(fake("x")).interrogate(png_bytes, language="fr")


def test_from_config(isolated_config):
    isolated_config.write_text("""
language = "en"
preset_dirs = ["/tmp/presets"]
[providers.p]
type = "openai"
model = "m"
""", encoding="utf-8")
    interrogator = Interrogator.from_config("p", {"model": "n"}, preset_dirs=["/x"])
    assert interrogator.provider.model == "n"
    assert interrogator.language == "en"
    assert [str(d) for d in interrogator.preset_dirs] == ["/x", "/tmp/presets"]
    assert Interrogator.from_config().provider.model == "qwen3.6:35b"


def test_convenience_wrapper(isolated_config, monkeypatch, fake, png_bytes):
    provider = fake("done")
    monkeypatch.setattr("image_interrogator.create_provider", lambda s: provider)
    assert interrogate(png_bytes, instruction="x") == "done"


def test_zh_forces_simplified(isolated_config, fake, png_bytes):
    provider = fake("一隻橘貓")
    assert Interrogator(provider, language="zh").interrogate(png_bytes) == "一只橘猫"
    assert provider.calls[0][0].startswith(LANGUAGE_DIRECTIVES["zh"])


def test_fixed_language_ignores_zh(isolated_config, fake, tmp_path, png_bytes):
    (tmp_path / "fixed.txt").write_text("# image-interrogator:fixed-language\nRULE",
                                        encoding="utf-8")
    provider = fake("一隻橘貓")
    result = Interrogator(provider, preset_dirs=[tmp_path]).interrogate(
        png_bytes, preset="fixed", language="zh")
    assert result == "一隻橘貓"
    assert provider.calls[0][0] == "RULE"


def test_tags_preset_normalizes(isolated_config, fake, png_bytes):
    provider = fake("Tags: 1girl,  solo,\nsolo, red hair")
    result = Interrogator(provider).interrogate(png_bytes, preset="tags", language="zh")
    assert result == "1girl, solo, red hair"
    assert "Danbooru" in provider.calls[0][0]
