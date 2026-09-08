"""Preset lookup: caller directories, then the user directory, then bundled"""

from dataclasses import dataclass
from pathlib import Path

from .config import PRESET_DIR_NAME, user_preset_dir
from .errors import PresetNotFoundError
from .prompt import split_pragma

BUNDLED_DIR = Path(__file__).parent / PRESET_DIR_NAME
DEFAULT_PRESET = "faithful"
PRESET_EXT = ".txt"
FORMATS = ("paragraph", "tags", "negative")


@dataclass(frozen=True)
class Preset:
    name: str
    path: Path
    rule: str
    fixed_language: bool
    format: str = "paragraph"


def search_dirs(extra_dirs=()):
    return [Path(d).expanduser() for d in extra_dirs] + [user_preset_dir(), BUNDLED_DIR]


def _is_plain_path(value):
    return value.startswith(("/", "~", "./", "../"))


def find_preset(name, extra_dirs=()):
    """Values starting with "/", "~", "./" or "../" are plain paths;
    anything else (subdirectories allowed) is searched in order under the
    caller's directories, the user directory and the bundled directory,
    appending .txt when the last segment has no extension"""
    if _is_plain_path(name):
        path = Path(name).expanduser()
        if path.is_file():
            return path
        raise PresetNotFoundError(f"preset not found: {path}")
    relative = Path(name)
    if not relative.suffix:
        relative = relative.with_suffix(PRESET_EXT)
    for base in search_dirs(extra_dirs):
        candidate = base / relative
        if candidate.is_file():
            return candidate
    raise PresetNotFoundError(f"preset not found: {name}")


def _read(name, path):
    rule, pragmas = split_pragma(path.read_text(encoding="utf-8"))
    fmt = "paragraph"
    for pragma in pragmas:
        if pragma.startswith("format="):
            fmt = pragma[len("format="):]
    if fmt not in FORMATS:
        raise PresetNotFoundError(f"preset {path}: unknown format \"{fmt}\" "
                                  f"(known: {', '.join(FORMATS)})")
    return Preset(name=name, path=path, rule=rule,
                  fixed_language="fixed-language" in pragmas, format=fmt)


def load_preset(name, extra_dirs=()):
    return _read(name, find_preset(name, extra_dirs))


def list_presets(extra_dirs=()):
    """All presets visible through the search order; a name shadowed by an
    earlier directory is listed once, from the directory that wins"""
    seen = {}
    for base in search_dirs(extra_dirs):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*" + PRESET_EXT)):
            name = path.relative_to(base).with_suffix("").as_posix()
            if name not in seen:
                seen[name] = _read(name, path)
    return [seen[k] for k in sorted(seen)]
