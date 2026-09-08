"""User configuration: ~/.config/image-interrogator/config.toml"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ConfigError

CONFIG_ENV = "IMAGE_INTERROGATOR_CONFIG"
DEFAULT_CONFIG_DIR = Path("~/.config/image-interrogator")
PRESET_DIR_NAME = "interrogators"
BUILTIN_PROVIDER_NAME = "ollama"
BUILTIN_PROVIDERS = {
    BUILTIN_PROVIDER_NAME: {"type": "ollama", "url": "http://localhost:11434",
                            "model": "qwen3.6:35b"},
}


def config_path():
    value = os.environ.get(CONFIG_ENV)
    if value:
        return Path(value).expanduser()
    return (DEFAULT_CONFIG_DIR / "config.toml").expanduser()


def user_preset_dir():
    return config_path().parent / PRESET_DIR_NAME


@dataclass
class Config:
    providers: dict = field(default_factory=dict)
    default_provider: str = BUILTIN_PROVIDER_NAME
    language: str | None = None
    preset_dirs: list = field(default_factory=list)
    fallbacks: list = field(default_factory=list)
    path: Path | None = None

    def provider_settings(self, name=None, overrides=None):
        """Settings dict for a named profile (default profile when None),
        with the caller's overrides merged on top"""
        name = name or self.default_provider
        if name not in self.providers:
            raise ConfigError(f"unknown provider profile: {name} "
                              f"(known: {', '.join(sorted(self.providers))})")
        settings = dict(self.providers[name])
        settings.update(overrides or {})
        settings.setdefault("name", name)
        return settings


def load_config(path=None):
    """Missing file is not an error: the built-in ollama profile applies"""
    path = Path(path).expanduser() if path else config_path()
    providers = {k: dict(v) for k, v in BUILTIN_PROVIDERS.items()}
    if not path.is_file():
        return Config(providers=providers)
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"failed to parse {path}: {e}") from e
    for name, section in (data.get("providers") or {}).items():
        if not isinstance(section, dict) or "type" not in section:
            raise ConfigError(f'provider "{name}" in {path} needs a "type" key')
        providers[name] = dict(section)
    default = data.get("default_provider", BUILTIN_PROVIDER_NAME)
    if default not in providers:
        raise ConfigError(f'default_provider "{default}" in {path} is not defined')
    fallbacks = list(data.get("fallbacks", []))
    for name in fallbacks:
        if name not in providers:
            raise ConfigError(f'fallback "{name}" in {path} is not defined')
    preset_dirs = [Path(d).expanduser() for d in data.get("preset_dirs", [])]
    return Config(providers=providers, default_provider=default,
                  language=data.get("language"), preset_dirs=preset_dirs,
                  fallbacks=fallbacks, path=path)
