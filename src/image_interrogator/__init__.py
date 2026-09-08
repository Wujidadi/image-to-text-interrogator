"""Vision-LLM-driven image interrogation: image in, text-to-image prompt out"""

import time
from dataclasses import dataclass, field

from .config import Config, load_config
from .errors import (ConfigError, ImageError, ImageInterrogatorError, OverloadedError,
                     PresetNotFoundError, ProviderError, RefusalError)
from .image import ImageInput, load_image, resize_image
from .postprocess import clean_output, is_refusal, normalize_tags, single_paragraph, to_simplified
from .presets import DEFAULT_PRESET, Preset, list_presets, load_preset
from .prompt import DEFAULT_LANGUAGE, LANGUAGE_DIRECTIVES, build_system, build_user
from .providers import Provider, create_provider

__version__ = "0.3.0"

# Errors that justify trying the next provider: a refusal needs a more
# permissive model, an overload needs a peer; anything else is a real fault
FALLBACK_ERRORS = (RefusalError, OverloadedError)


@dataclass
class Result:
    """Outcome of one interrogation: the prompt plus what produced it"""
    text: str
    provider: Provider
    elapsed: float
    usage: dict | None = None
    attempts: list = field(default_factory=list)
    image: ImageInput | None = None

    def __str__(self):
        return self.text


class Interrogator:
    """Single-pass interrogation of one image against one provider, with
    optional fallback providers tried in order on refusal or overload.

    `language` is the default output language; `preset_dirs` are searched
    before the user and bundled preset directories; `on_fallback(error,
    next_provider)` is called each time the next provider is tried;
    `max_side` scales images down before the call (needs Pillow)"""

    def __init__(self, provider, *, language=None, preset_dirs=(), fallbacks=(),
                 on_fallback=None, max_side=None):
        self.provider = provider
        self.language = language or DEFAULT_LANGUAGE
        self.preset_dirs = list(preset_dirs)
        self.fallbacks = list(fallbacks)
        self.on_fallback = on_fallback
        self.max_side = max_side
        self._check_language(self.language)

    @staticmethod
    def _check_language(language):
        if language not in LANGUAGE_DIRECTIVES:
            raise ConfigError(f'unknown language "{language}" '
                              f"(known: {', '.join(sorted(LANGUAGE_DIRECTIVES))})")

    @classmethod
    def from_config(cls, provider=None, overrides=None, *, language=None,
                    preset_dirs=(), config_path=None, fallbacks=None, on_fallback=None,
                    max_side=None):
        """Build from the user config file: `provider` names a profile
        (the configured default when None), `overrides` patch its settings.
        Language precedence: argument > config file > en.
        `fallbacks` names profiles tried in order on refusal or overload;
        None takes the config file's list (minus the chosen profile), an
        empty list disables fallbacks"""
        config = load_config(config_path)
        settings = config.provider_settings(provider, overrides)
        names = config.fallbacks if fallbacks is None else list(fallbacks)
        names = [n for n in names if n != settings["name"]]
        return cls(create_provider(settings),
                   language=language or config.language,
                   preset_dirs=list(preset_dirs) + config.preset_dirs,
                   fallbacks=[create_provider(config.provider_settings(n)) for n in names],
                   on_fallback=on_fallback,
                   max_side=max_side if max_side is not None else config.max_side)

    def prepare(self, preset=None, instruction=None, language=None, explicit=False):
        """Resolve the preset into (system, preset); exposed so callers can
        show or log the instruction"""
        language = language or self.language
        self._check_language(language)
        loaded = load_preset(preset or DEFAULT_PRESET, self.preset_dirs)
        system = build_system(loaded.rule, loaded.fixed_language, language,
                              instruction, explicit)
        return system, loaded

    def interrogate(self, image, *, preset=None, instruction=None, language=None,
                    explicit=False):
        """Return the prompt reconstructed from `image` (a path, bytes,
        a binary stream or an ImageInput). Raises ImageInterrogatorError
        subclasses"""
        return self.interrogate_detailed(image, preset=preset, instruction=instruction,
                                         language=language, explicit=explicit).text

    def interrogate_detailed(self, image, *, preset=None, instruction=None,
                             language=None, explicit=False):
        """Like interrogate(), returning a Result with the provider that
        answered, the elapsed time, its usage report and the errors of the
        providers tried before it"""
        image = load_image(image)
        if self.max_side:
            image = resize_image(image, self.max_side)
        language = language or self.language
        system, loaded = self.prepare(preset, instruction, language, explicit)
        started = time.monotonic()
        attempts = []
        remaining = [self.provider, *self.fallbacks]
        while True:
            provider = remaining.pop(0)
            try:
                text = self._complete(provider, system, image, loaded, language)
            except FALLBACK_ERRORS as e:
                if not remaining:
                    raise
                attempts.append(e)
                if self.on_fallback:
                    self.on_fallback(e, remaining[0])
                continue
            return Result(text=text, provider=provider,
                          elapsed=round(time.monotonic() - started, 2),
                          usage=provider.last_usage, attempts=attempts, image=image)

    def _complete(self, provider, system, image, loaded, language):
        raw = provider.complete(system, build_user(), image)
        tags = loaded.format == "tags"
        result = clean_output(raw or "", paragraph=not tags)
        if not result:
            raise ProviderError(f"{provider.describe()}: empty response")
        if is_refusal(result):
            raise RefusalError(f"{provider.describe()}: refused: {result}")
        if tags:
            result = normalize_tags(result)
        if language == "zh" and not loaded.fixed_language:
            result = to_simplified(result)
        return result


def interrogate(image, *, preset=None, instruction=None, language=None, explicit=False,
                provider=None, overrides=None, preset_dirs=(), config_path=None):
    """One-call convenience wrapper around Interrogator.from_config().interrogate()"""
    interrogator = Interrogator.from_config(provider, overrides, language=language,
                                            preset_dirs=preset_dirs, config_path=config_path)
    return interrogator.interrogate(image, preset=preset, instruction=instruction,
                                    explicit=explicit)


__all__ = [
    "Interrogator", "Result", "FALLBACK_ERRORS", "interrogate", "Config", "load_config", "ImageInput", "load_image", "resize_image",
    "Provider", "create_provider", "Preset", "list_presets", "load_preset",
    "DEFAULT_PRESET", "DEFAULT_LANGUAGE", "LANGUAGE_DIRECTIVES", "build_system",
    "build_user", "clean_output", "single_paragraph", "is_refusal", "normalize_tags", "to_simplified",
    "ImageInterrogatorError", "ConfigError", "PresetNotFoundError", "ImageError",
    "ProviderError", "RefusalError", "OverloadedError", "__version__",
]
