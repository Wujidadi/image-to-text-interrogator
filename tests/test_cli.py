import pytest

from image_interrogator import ProviderError, __version__
from image_interrogator.cli import main
from image_interrogator.prompt import EXPLICIT_ADDENDUM


@pytest.fixture
def provider(monkeypatch, fake):
    instance = fake("a cat")
    monkeypatch.setattr("image_interrogator.create_provider", lambda s: instance)
    return instance


def test_single_image(isolated_config, provider, png_file, capsys):
    main([str(png_file)])
    out, err = capsys.readouterr()
    assert out == "a cat\n"
    assert "interrogating" in err and "fake fake-model" in err and "preset faithful" in err


def test_quiet_and_options(isolated_config, provider, png_file, capsys):
    main(["-q", "-p", "faithful", "-i", "focus on fur", "--explicit", "-l", "en", str(png_file)])
    out, err = capsys.readouterr()
    assert out == "a cat\n" and err == ""
    system = provider.calls[0][0]
    assert EXPLICIT_ADDENDUM in system and system.endswith("focus on fur")


def test_show_system_and_timing(isolated_config, provider, png_file, capsys):
    main(["--show-system", "--timing", str(png_file)])
    out, err = capsys.readouterr()
    assert out == "a cat\n"
    assert "expert prompt engineer" in err
    assert "elapsed" in err and "s" in err


def test_provider_overrides(isolated_config, monkeypatch, fake, png_file, capsys):
    seen = {}

    def create(settings):
        seen.update(settings)
        return fake("x")

    monkeypatch.setattr("image_interrogator.create_provider", create)
    main(["-q", "--type", "openai", "-m", "mm", "--url", "http://h/v1", str(png_file)])
    assert seen["type"] == "openai" and seen["model"] == "mm" and seen["url"] == "http://h/v1"


def test_named_profile_and_config(tmp_path, provider, png_file, capsys):
    config = tmp_path / "c.toml"
    config.write_text('[providers.p]\ntype = "openai"\nmodel = "m"\n', encoding="utf-8")
    main(["-q", "--config", str(config), "-P", "p", str(png_file)])
    assert capsys.readouterr().out == "a cat\n"


def test_stdin_image(isolated_config, provider, png_bytes, capsys, monkeypatch):
    import io
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(png_bytes)))
    main(["-q", "-"])
    assert capsys.readouterr().out == "a cat\n"
    assert provider.calls[0][2].path is None


def test_preset_dir(isolated_config, provider, png_file, tmp_path, capsys):
    (tmp_path / "mine.txt").write_text("MINE", encoding="utf-8")
    main(["-q", "--preset-dir", str(tmp_path), "-p", "mine", str(png_file)])
    assert provider.calls[0][0].endswith("MINE")


def test_list_presets(isolated_config, capsys, tmp_path):
    (tmp_path / "fixed.txt").write_text("# image-interrogator:fixed-language\nX",
                                        encoding="utf-8")
    main(["--list-presets", "--preset-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert out.startswith("faithful\t") and "fixed\t" in out and "[fixed-language]" in out


def test_list_providers(isolated_config, capsys):
    isolated_config.write_text('[providers.p]\ntype = "openai"\nmodel = "m"\n', encoding="utf-8")
    main(["--list-providers"])
    out = capsys.readouterr().out
    assert "* ollama\tollama\tqwen3.6:35b\thttp://localhost:11434" in out
    assert "  p\topenai\tm\t\n" in out


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_missing_image_argument(isolated_config, capsys):
    with pytest.raises(SystemExit) as e:
        main([])
    assert e.value.code == 2


def test_error_exit(isolated_config, provider, tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        main(["-q", str(tmp_path / "nope.png")])
    assert e.value.code == 1
    assert "image-interrogator: image not found" in capsys.readouterr().err


def test_provider_error_exit(isolated_config, monkeypatch, fake, png_file, capsys):
    monkeypatch.setattr("image_interrogator.create_provider",
                        lambda s: fake(ProviderError("boom")))
    with pytest.raises(SystemExit) as e:
        main(["-q", str(png_file)])
    assert e.value.code == 1
    assert "boom" in capsys.readouterr().err


def png_bytes_padded(size):
    from conftest import make_png
    data = make_png()
    return data + b"\x00" * (size - len(data))


def test_size_warning_printed(isolated_config, provider, tmp_path, capsys):
    from image_interrogator.image import SIZE_WARNING_BYTES
    path = tmp_path / "big.png"
    path.write_bytes(png_bytes_padded(SIZE_WARNING_BYTES + 1))
    main(["-q", str(path)])
    assert "5 MB" in capsys.readouterr().err
