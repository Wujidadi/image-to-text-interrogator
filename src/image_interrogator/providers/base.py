import json
import os
import urllib.error
import urllib.request

from ..errors import ConfigError, OverloadedError, ProviderError

DEFAULT_TIMEOUT = 300
OVERLOADED_STATUSES = (429, 503, 529)


class Provider:
    """One backend that turns (system, prompt, image) into model output.

    Common settings keys: type, model, url, timeout, api_key_env, api_key,
    extra (merged verbatim into the request body)"""

    type_name = ""
    default_url = ""
    default_model = ""
    default_api_key_env = ""

    def __init__(self, settings):
        self.settings = settings
        self.name = settings.get("name", self.type_name)
        self.model = settings.get("model") or self.default_model
        self.url = (settings.get("url") or self.default_url).rstrip("/")
        self.timeout = settings.get("timeout", DEFAULT_TIMEOUT)
        self.extra = settings.get("extra") or {}
        if not self.model:
            raise ConfigError(f'provider "{self.name}" has no model')

    @property
    def api_key(self):
        if "api_key" in self.settings:
            return self.settings["api_key"]
        env = self.settings.get("api_key_env") or self.default_api_key_env
        if env:
            value = os.environ.get(env)
            if not value:
                raise ConfigError(f'provider "{self.name}": environment '
                                  f"variable {env} is not set")
            return value
        return None

    def describe(self):
        return f"{self.type_name} {self.model}"

    def complete(self, system, prompt, image):
        """Return the raw model text for the system instruction, the user
        prompt and an ImageInput"""
        raise NotImplementedError

    def _post_json(self, url, payload, headers=None):
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace").strip()
            message = (f"{self.describe()}: HTTP {e.code} from {url}"
                       + (f": {detail[:500]}" if detail else ""))
            if e.code in OVERLOADED_STATUSES:
                raise OverloadedError(message) from e
            raise ProviderError(message) from e
        except (OSError, ValueError) as e:
            raise ProviderError(f"{self.describe()}: request to {url} failed: {e}") from e
