from ..errors import ConfigError
from .base import Provider

PROVIDER_TYPES = {}


def register(cls):
    """Class decorator adding a Provider subclass to PROVIDER_TYPES"""
    PROVIDER_TYPES[cls.type_name] = cls
    return cls


def create_provider(settings):
    kind = settings.get("type")
    cls = PROVIDER_TYPES.get(kind)
    if cls is None:
        raise ConfigError(f'unknown provider type "{kind}" '
                          f"(known: {', '.join(sorted(PROVIDER_TYPES))})")
    return cls(settings)


__all__ = ["Provider", "PROVIDER_TYPES", "create_provider", "register"]
