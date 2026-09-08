import pytest

from image_interrogator import DEFAULT_PRESET, PresetNotFoundError, list_presets, load_preset
from image_interrogator.presets import BUNDLED_DIR


def test_bundled_default(isolated_config):
    preset = load_preset(DEFAULT_PRESET)
    assert DEFAULT_PRESET == "faithful"
    assert preset.path == BUNDLED_DIR / "faithful.txt"
    assert not preset.fixed_language
    assert preset.rule


def test_user_dir_shadows_bundled(isolated_config):
    user_dir = isolated_config.parent / "interrogators"
    user_dir.mkdir()
    (user_dir / "faithful.txt").write_text("MINE", encoding="utf-8")
    assert load_preset("faithful").rule == "MINE"
    names = {p.name: p for p in list_presets()}
    assert names["faithful"].path == user_dir / "faithful.txt"


def test_caller_dir_and_subdirectory(isolated_config, tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "mine.txt").write_text("SUB", encoding="utf-8")
    assert load_preset("sub/mine", [tmp_path]).rule == "SUB"
    assert load_preset("sub/mine.txt", [tmp_path]).rule == "SUB"
    assert load_preset(str(tmp_path / "sub" / "mine.txt")).rule == "SUB"
    assert "sub/mine" in {p.name for p in list_presets([tmp_path])}


def test_missing(isolated_config, tmp_path):
    with pytest.raises(PresetNotFoundError):
        load_preset("does-not-exist")
    with pytest.raises(PresetNotFoundError):
        load_preset(str(tmp_path / "nope.txt"))


def test_bundled_names(isolated_config):
    assert [p.name for p in list_presets()] == ["faithful"]
