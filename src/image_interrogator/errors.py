class ImageInterrogatorError(Exception):
    """Base class for every error raised by image_interrogator"""


class ConfigError(ImageInterrogatorError):
    """Invalid configuration file or provider settings"""


class PresetNotFoundError(ImageInterrogatorError):
    """The named preset could not be found in any search directory"""


class ImageError(ImageInterrogatorError):
    """The input image is missing, unreadable or in an unsupported format"""


class ProviderError(ImageInterrogatorError):
    """The model backend failed or returned an unusable response"""


class RefusalError(ProviderError):
    """The model declined to describe the image (content policy)"""


class OverloadedError(ProviderError):
    """The backend is overloaded or rate-limited (HTTP 429 / 529)"""
