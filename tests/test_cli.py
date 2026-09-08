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
    assert "\nfaithful\t" in out and "fixed\t" in out and "[fixed-language]" in out
    assert "tags\t" in out and "[fixed-language, tags]" in out


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


def test_language_zh(isolated_config, monkeypatch, fake, png_file, capsys):
    monkeypatch.setattr("image_interrogator.create_provider", lambda s: fake("一隻橘貓"))
    main(["-q", "-l", "zh", str(png_file)])
    assert capsys.readouterr().out == "一只橘猫\n"


# --- batch -------------------------------------------------------------------

@pytest.fixture
def two_images(tmp_path, png_bytes):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    a.write_bytes(png_bytes)
    b.write_bytes(png_bytes)
    return a, b


def test_multiple_images_to_stdout(isolated_config, provider, two_images, capsys):
    a, b = two_images
    main(["-q", str(a), str(b)])
    out = capsys.readouterr().out
    assert out == f"# {a.resolve()}\na cat\n\n# {b.resolve()}\na cat\n"
    assert len(provider.calls) == 2


def test_sidecar(isolated_config, provider, two_images, capsys):
    a, b = two_images
    main(["--sidecar", str(a), str(b)])
    out, err = capsys.readouterr()
    assert out == ""
    assert a.with_suffix(".txt").read_text(encoding="utf-8") == "a cat\n"
    assert b.with_suffix(".txt").read_text(encoding="utf-8") == "a cat\n"
    assert "wrote" in err and str(a.with_suffix(".txt")) in err


def test_output_dir(isolated_config, provider, two_images, tmp_path, capsys):
    a, _ = two_images
    out_dir = tmp_path / "out" / "nested"
    main(["-q", "--output-dir", str(out_dir), str(a)])
    assert (out_dir / "a.txt").read_text(encoding="utf-8") == "a cat\n"
    assert capsys.readouterr().out == ""


def test_sidecar_from_stdin_is_rejected(isolated_config, provider, capsys):
    with pytest.raises(SystemExit) as e:
        main(["-q", "--sidecar", "-"])
    assert e.value.code == 2


def test_json_output(isolated_config, provider, two_images, capsys):
    import json
    a, b = two_images
    main(["-q", "--json", str(a), str(b)])
    items = json.loads(capsys.readouterr().out)
    assert [i["image"] for i in items] == [str(a.resolve()), str(b.resolve())]
    assert items[0]["prompt"] == "a cat" and items[0]["provider"] == "fake fake-model"
    assert items[0]["preset"] == "faithful" and isinstance(items[0]["elapsed"], float)
    assert "error" not in items[0]


def test_json_includes_usage(isolated_config, monkeypatch, fake, png_file, capsys):
    import json
    instance = fake("a cat")
    instance.last_usage = {"total_cost_usd": 0.1}
    monkeypatch.setattr("image_interrogator.create_provider", lambda s: instance)
    main(["-q", "--json", str(png_file)])
    assert json.loads(capsys.readouterr().out)[0]["usage"] == {"total_cost_usd": 0.1}


def test_batch_continues_after_failure(isolated_config, provider, two_images, tmp_path, capsys):
    import json
    a, b = two_images
    missing = tmp_path / "missing.png"
    with pytest.raises(SystemExit) as e:
        main(["-q", "--json", str(a), str(missing), str(b)])
    assert e.value.code == 1
    out, err = capsys.readouterr()
    items = json.loads(out)
    assert len(items) == 3 and "not found" in items[1]["error"] and items[2]["prompt"] == "a cat"
    assert "1 of 3 images failed" in err and str(missing) in err


def test_batch_prefixes_errors_without_path(isolated_config, monkeypatch, fake, two_images, capsys):
    monkeypatch.setattr("image_interrogator.create_provider", lambda s: fake(ProviderError("boom")))
    a, b = two_images
    with pytest.raises(SystemExit):
        main(["-q", str(a), str(b)])
    assert f"{a}: boom" in capsys.readouterr().err


def test_batch_failure_plain_output(isolated_config, provider, two_images, tmp_path, capsys):
    a, _ = two_images
    with pytest.raises(SystemExit):
        main(["-q", str(a), str(tmp_path / "missing.png")])
    out, err = capsys.readouterr()
    assert out == f"# {a.resolve()}\na cat\n"
    assert "missing.png: image not found" not in err and "image not found" in err


def test_timing_per_image(isolated_config, provider, two_images, capsys):
    a, b = two_images
    main(["-q", "--timing", str(a), str(b)])
    assert capsys.readouterr().err.count("elapsed") == 2


def test_listing_with_broken_config(isolated_config, capsys):
    isolated_config.write_text("not = = toml", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        main(["--list-providers"])
    assert e.value.code == 1
    assert "failed to parse" in capsys.readouterr().err


def test_unknown_profile_exit(isolated_config, png_file, capsys):
    with pytest.raises(SystemExit) as e:
        main(["-q", "-P", "nope", str(png_file)])
    assert e.value.code == 1
    assert "unknown provider profile" in capsys.readouterr().err


def test_failure_first_then_success_plain(isolated_config, provider, two_images, tmp_path, capsys):
    a, _ = two_images
    with pytest.raises(SystemExit):
        main(["-q", str(tmp_path / "missing.png"), str(a)])
    assert capsys.readouterr().out == f"# {a.resolve()}\na cat\n"


# --- fallbacks ---------------------------------------------------------------

def write_fallback_config(path):
    path.write_text("""
default_provider = "a"
fallbacks = ["b"]
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


def install_providers(monkeypatch, fake, replies):
    from image_interrogator import RefusalError

    def create(settings):
        reply = replies[settings["model"]]
        instance = fake(reply, settings=settings)
        return instance

    monkeypatch.setattr("image_interrogator.create_provider", create)


def test_cli_fallback_from_config(isolated_config, monkeypatch, fake, png_file, capsys):
    from image_interrogator import RefusalError
    write_fallback_config(isolated_config)
    install_providers(monkeypatch, fake, {"a": RefusalError("a refused"), "b": "from b"})
    main(["--json", str(png_file)])
    out, err = capsys.readouterr()
    import json
    record = json.loads(out)[0]
    assert record["prompt"] == "from b" and record["provider"] == "fake b"
    assert record["attempts"] == ["a refused"]
    assert "falling back" in err and "fake b" in err


def test_cli_fallback_flag_overrides(isolated_config, monkeypatch, fake, png_file, capsys):
    from image_interrogator import RefusalError
    write_fallback_config(isolated_config)
    install_providers(monkeypatch, fake, {"a": RefusalError("no"), "b": "from b", "c": "from c"})
    main(["-q", "--fallback", "c", str(png_file)])
    assert capsys.readouterr().out == "from c\n"


def test_cli_no_fallback(isolated_config, monkeypatch, fake, png_file, capsys):
    from image_interrogator import RefusalError
    write_fallback_config(isolated_config)
    install_providers(monkeypatch, fake, {"a": RefusalError("a refused"), "b": "from b"})
    with pytest.raises(SystemExit) as e:
        main(["-q", "--no-fallback", str(png_file)])
    assert e.value.code == 1 and "a refused" in capsys.readouterr().err


def test_max_side_flag(isolated_config, provider, tmp_path, capsys):
    from conftest import make_png
    path = tmp_path / "wide.png"
    path.write_bytes(make_png(40, 20))
    main(["--max-side", "10", str(path)])
    assert "resized" in capsys.readouterr().err
    assert len(provider.calls[0][2].data) < len(path.read_bytes())


# --- negative prompts --------------------------------------------------------

@pytest.fixture
def negative_provider(monkeypatch, fake):
    instance = fake("PROMPT: a cat\nNEGATIVE: blurry")
    monkeypatch.setattr("image_interrogator.create_provider", lambda s: instance)
    return instance


def test_negative_on_stdout(isolated_config, negative_provider, png_file, capsys):
    main(["-q", "-p", "faithful-negative", str(png_file)])
    assert capsys.readouterr().out == "a cat\n\nNegative: blurry\n"


def test_negative_sidecar_and_json(isolated_config, negative_provider, png_file, capsys):
    import json
    main(["-q", "--sidecar", "--json", "-p", "faithful-negative", str(png_file)])
    assert png_file.with_suffix(".txt").read_text(encoding="utf-8") == "a cat\n"
    assert png_file.with_suffix(".negative.txt").read_text(encoding="utf-8") == "blurry\n"
    record = json.loads(capsys.readouterr().out)[0]
    assert record["negative"] == "blurry" and record["negative_output"].endswith(".negative.txt")


def test_no_negative_no_extra_output(isolated_config, provider, png_file, capsys):
    import json
    main(["-q", "--sidecar", "--json", str(png_file)])
    assert not png_file.with_suffix(".negative.txt").exists()
    assert "negative" not in json.loads(capsys.readouterr().out)[0]


# --- compare mode ------------------------------------------------------------

def test_compare_runs_every_profile(isolated_config, monkeypatch, fake, png_file, capsys):
    write_fallback_config(isolated_config)
    install_providers(monkeypatch, fake, {"a": "from a", "b": "from b", "c": "from c"})
    main(["-q", "--compare", "b", "--compare", "c", str(png_file)])
    out = capsys.readouterr().out
    assert out == ("# fake a\nfrom a\n\n# fake b\nfrom b\n\n# fake c\nfrom c\n")


def test_compare_json_and_failures(isolated_config, monkeypatch, fake, png_file, capsys):
    import json
    from image_interrogator import RefusalError
    write_fallback_config(isolated_config)
    install_providers(monkeypatch, fake, {"a": "from a", "b": RefusalError("b refused")})
    with pytest.raises(SystemExit) as e:
        main(["-q", "--json", "--compare", "b", str(png_file)])
    assert e.value.code == 1
    out, err = capsys.readouterr()
    records = json.loads(out)
    assert [r.get("prompt") for r in records] == ["from a", None]
    assert records[1]["error"] == "b refused" and records[1]["profile"] == "b"
    assert records[0]["profile"] == "a"
    assert "fake b: b refused" in err or "b refused" in err


def test_compare_disables_fallbacks_and_names_unknown_profiles(isolated_config, monkeypatch,
                                                               fake, png_file, capsys):
    from image_interrogator import RefusalError
    write_fallback_config(isolated_config)
    install_providers(monkeypatch, fake, {"a": RefusalError("no"), "b": "from b"})
    with pytest.raises(SystemExit):
        main(["-q", "--compare", "b", str(png_file)])
    assert "falling back" not in capsys.readouterr().err
    with pytest.raises(SystemExit) as e:
        main(["-q", "--compare", "nope", str(png_file)])
    assert e.value.code == 1 and "unknown provider profile" in capsys.readouterr().err


def test_compare_with_several_images(isolated_config, monkeypatch, fake, two_images, capsys):
    write_fallback_config(isolated_config)
    install_providers(monkeypatch, fake, {"a": "from a", "b": "from b"})
    a, b = two_images
    main(["-q", "--compare", "b", str(a), str(b)])
    out = capsys.readouterr().out
    assert out.count("# fake a") == 2 and out.count(f"# {a.resolve()}") == 1


def test_compare_sidecar_uses_profile_suffix(isolated_config, monkeypatch, fake, png_file, capsys):
    write_fallback_config(isolated_config)
    install_providers(monkeypatch, fake, {"a": "from a", "b": "from b"})
    main(["-q", "--sidecar", "--compare", "b", str(png_file)])
    assert png_file.with_suffix(".a.txt").read_text(encoding="utf-8") == "from a\n"
    assert png_file.with_suffix(".b.txt").read_text(encoding="utf-8") == "from b\n"
