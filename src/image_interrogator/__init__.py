"""Vision-LLM-driven image interrogation: image in, text-to-image prompt out"""

from .config import Config, load_config
from .errors import (ConfigError, ImageError, ImageInterrogatorError, OverloadedError,
                     PresetNotFoundError, ProviderError, RefusalError)
from .image import ImageInput, load_image
from .postprocess import clean_output, is_refusal, single_paragraph
from .presets import DEFAULT_PRESET, Preset, list_presets, load_preset
from .prompt import DEFAULT_LANGUAGE, LANGUAGE_DIRECTIVES, build_system, build_user
from .providers import Provider, create_provider

__version__ = "0.1.0"


class Interrogator:
    """Single-pass interrogation of one image against one provider.

    `language` is the default output language; `preset_dirs` are searched
    before the user and bundled preset directories"""

    def __init__(self, provider, *, language=None, preset_dirs=()):
        self.provider = provider
        self.language = language or DEFAULT_LANGUAGE
        self.preset_dirs = list(preset_dirs)
        self._check_language(self.language)

    @staticmethod
    def _check_language(language):
        if language not in LANGUAGE_DIRECTIVES:
            raise ConfigError(f'unknown language "{language}" '
                              f"(known: {', '.join(sorted(LANGUAGE_DIRECTIVES))})")

    @classmethod
    def from_config(cls, provider=None, overrides=None, *, language=None,
                    preset_dirs=(), config_path=None):
        """Build from the user config file: `provider` names a profile
        (the configured default when None), `overrides` patch its settings.
        Language precedence: argument > config file > en"""
        config = load_config(config_path)
        settings = config.provider_settings(provider, overrides)
        return cls(create_provider(settings),
                   language=language or config.language,
                   preset_dirs=list(preset_dirs) + config.preset_dirs)

    def prepare(self, preset=None, instruction=None, language=None, explicit=False):
        """Resolve the preset into (system, fixed_language); exposed so
        callers can show or log the instruction"""
        language = language or self.language
        self._check_language(language)
        loaded = load_preset(preset or DEFAULT_PRESET, self.preset_dirs)
        system = build_system(loaded.rule, loaded.fixed_language, language,
                              instruction, explicit)
        return system, loaded.fixed_language

    def interrogate(self, image, *, preset=None, instruction=None, language=None,
                    explicit=False):
        """Return the prompt reconstructed from `image` (a path, bytes,
        a binary stream or an ImageInput). Raises ImageInterrogatorError
        subclasses"""
        image = load_image(image)
        system, _ = self.prepare(preset, instruction, language, explicit)
        raw = self.provider.complete(system, build_user(), image)
        result = clean_output(raw or "", paragraph=True)
        if not result:
            raise ProviderError(f"{self.provider.describe()}: empty response")
        if is_refusal(result):
            raise RefusalError(f"{self.provider.describe()}: refused: {result}")
        return result


def interrogate(image, *, preset=None, instruction=None, language=None, explicit=False,
                provider=None, overrides=None, preset_dirs=(), config_path=None):
    """One-call convenience wrapper around Interrogator.from_config().interrogate()"""
    interrogator = Interrogator.from_config(provider, overrides, language=language,
                                            preset_dirs=preset_dirs, config_path=config_path)
    return interrogator.interrogate(image, preset=preset, instruction=instruction,
                                    explicit=explicit)


__all__ = [
    "Interrogator", "interrogate", "Config", "load_config", "ImageInput", "load_image",
    "Provider", "create_provider", "Preset", "list_presets", "load_preset",
    "DEFAULT_PRESET", "DEFAULT_LANGUAGE", "LANGUAGE_DIRECTIVES", "build_system",
    "build_user", "clean_output", "single_paragraph", "is_refusal",
    "ImageInterrogatorError", "ConfigError", "PresetNotFoundError", "ImageError",
    "ProviderError", "RefusalError", "OverloadedError", "__version__",
]
