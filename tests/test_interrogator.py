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
    assert EXPLICIT_ADDENDUM in system and "focus on fur" in system


def test_prepare_exposes_system(isolated_config, fake):
    system, preset = Interrogator(fake()).prepare(instruction="x")
    assert "above): x" in system and preset.name == "faithful"


def test_custom_preset_dir(isolated_config, fake, tmp_path, png_bytes):
    (tmp_path / "mine.txt").write_text("MINE", encoding="utf-8")
    provider = fake("out")
    Interrogator(provider, preset_dirs=[tmp_path]).interrogate(png_bytes, preset="mine")
    assert "MINE" in provider.calls[0][0]


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


# --- detailed results and fallbacks -----------------------------------------

def test_interrogate_detailed(isolated_config, fake, png_bytes):
    provider = fake("a cat")
    provider.last_usage = {"x": 1}
    result = Interrogator(provider).interrogate_detailed(png_bytes)
    assert result.text == "a cat" and result.provider is provider
    assert result.usage == {"x": 1} and result.elapsed >= 0
    assert result.attempts == [] and str(result) == "a cat"


def test_fallback_on_refusal_and_overload(isolated_config, fake, png_bytes):
    from image_interrogator import OverloadedError
    first = fake(RefusalError("no"))
    second = fake(OverloadedError("busy"))
    third = fake("a cat")
    seen = []
    interrogator = Interrogator(first, fallbacks=[second, third],
                                on_fallback=lambda e, p: seen.append((e, p)))
    result = interrogator.interrogate_detailed(png_bytes)
    assert result.text == "a cat" and result.provider is third
    assert [type(e) for e in result.attempts] == [RefusalError, OverloadedError]
    assert len(seen) == 2 and isinstance(seen[0][0], RefusalError)
    assert seen[0][1] is second and seen[1][1] is third
    assert interrogator.interrogate(png_bytes) == "a cat"


def test_fallback_not_used_for_other_errors(isolated_config, fake, png_bytes):
    first = fake(ProviderError("boom"))
    second = fake("a cat")
    with pytest.raises(ProviderError, match="boom"):
        Interrogator(first, fallbacks=[second]).interrogate(png_bytes)
    assert second.calls == []


def test_fallback_exhausted_raises_last(isolated_config, fake, png_bytes):
    first = fake(RefusalError("no1"))
    second = fake(RefusalError("no2"))
    with pytest.raises(RefusalError, match="no2"):
        Interrogator(first, fallbacks=[second]).interrogate(png_bytes)


def test_from_config_fallbacks(isolated_config):
    isolated_config.write_text("""
fallbacks = ["b", "c"]
[providers.a]
type = "openai"
model = "a"
[providers.b]
type = "openai"
model = "b"
[providers.c]
type = "openai"
model = "c"
""", encoding="utf-8")
    interrogator = Interrogator.from_config("a")
    assert [p.model for p in interrogator.fallbacks] == ["b", "c"]
    assert Interrogator.from_config("b").fallbacks[0].model == "c"
    assert Interrogator.from_config("a", fallbacks=[]).fallbacks == []
    assert [p.model for p in Interrogator.from_config("a", fallbacks=["c"]).fallbacks] == ["c"]
    with pytest.raises(ConfigError, match="unknown provider profile"):
        Interrogator.from_config("a", fallbacks=["nope"])


def test_max_side_resizes_before_the_call(isolated_config, fake, tmp_path):
    from conftest import make_png
    path = tmp_path / "wide.png"
    path.write_bytes(make_png(40, 20))
    provider = fake("a cat")
    Interrogator(provider, max_side=10).interrogate(path)
    assert len(provider.calls[0][2].data) < len(path.read_bytes())
    Interrogator(provider).interrogate(path)
    assert provider.calls[1][2].data == path.read_bytes()


def test_from_config_max_side(isolated_config):
    isolated_config.write_text("max_side = 1024\n", encoding="utf-8")
    assert Interrogator.from_config().max_side == 1024
    assert Interrogator.from_config(max_side=512).max_side == 512
    isolated_config.write_text("", encoding="utf-8")
    assert Interrogator.from_config().max_side is None


def test_negative_preset_splits_result(isolated_config, fake, png_bytes):
    provider = fake("PROMPT: a cat,\nsoft light\nNEGATIVE: blurry, 文字")
    result = Interrogator(provider).interrogate_detailed(png_bytes, preset="faithful-negative")
    assert result.text == "a cat, soft light" and result.negative == "blurry, 文字"


def test_negative_preset_zh(isolated_config, fake, png_bytes):
    provider = fake("PROMPT: 一隻貓\nNEGATIVE: 模糊")
    result = Interrogator(provider, language="zh").interrogate_detailed(
        png_bytes, preset="faithful-negative")
    assert result.text == "一只猫" and result.negative == "模糊"


def test_negative_preset_without_section(isolated_config, fake, png_bytes):
    provider = fake("a cat")
    result = Interrogator(provider).interrogate_detailed(png_bytes, preset="faithful-negative")
    assert result.text == "a cat" and result.negative == ""
    assert Interrogator(provider).interrogate_detailed(png_bytes).negative is None
