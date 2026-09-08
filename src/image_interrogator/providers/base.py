import json
import os
import time
import urllib.error
import urllib.request

from ..errors import ConfigError, OverloadedError, ProviderError

DEFAULT_TIMEOUT = 300
DEFAULT_RETRIES = 2
OVERLOADED_STATUSES = (429, 503, 529)


class Provider:
    """One backend that turns (system, prompt, image) into model output.

    Common settings keys: type, model, url, timeout, retries (on HTTP 429 /
    503 / 529, default 2 with 1 s then 2 s backoff), api_key_env, api_key,
    price (table with input and output USD per million tokens, used to
    estimate cost_usd in last_usage), extra (merged verbatim into the
    request body)"""

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
        self.retries = settings.get("retries", DEFAULT_RETRIES)
        self.last_usage = None
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

    def _record_usage(self, usage, input_key, output_key):
        """Keep the backend's usage report, adding cost_usd when the
        profile carries a price table"""
        if not isinstance(usage, dict):
            self.last_usage = None
            return
        usage = dict(usage)
        price = self.settings.get("price")
        if price:
            cost = (usage.get(input_key, 0) * price.get("input", 0)
                    + usage.get(output_key, 0) * price.get("output", 0)) / 1_000_000
            usage["cost_usd"] = round(cost, 6)
        self.last_usage = usage

    def _post_json(self, url, payload, headers=None):
        """POST JSON and decode the reply; overload statuses are retried
        with exponential backoff, other errors are raised at once"""
        attempt = 0
        while True:
            try:
                return self._post_once(url, payload, headers)
            except OverloadedError:
                if attempt == self.retries:
                    raise
                time.sleep(2 ** attempt)
                attempt += 1

    def _post_once(self, url, payload, headers=None):
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json", **(headers or {})})
        return self._decode(url, self._open(request))

    def _get_json(self, url, headers=None):
        request = urllib.request.Request(url, headers=headers or {}, method="GET")
        return self._decode(url, self._open(request))

    def _put_bytes(self, url, data, headers=None):
        """Raw PUT, e.g. to a signed upload URL; the reply body is ignored"""
        request = urllib.request.Request(url, data=data, headers=headers or {}, method="PUT")
        self._open(request)

    def _decode(self, url, body):
        try:
            return json.loads(body)
        except ValueError as e:
            raise ProviderError(f"{self.describe()}: request to {url} failed: {e}") from e

    def _open(self, request):
        """Send one request and return the body bytes; HTTP errors are
        classified into OverloadedError or ProviderError"""
        url = request.full_url
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace").strip()
            message = (f"{self.describe()}: HTTP {e.code} from {url}"
                       + (f": {detail[:500]}" if detail else ""))
            if e.code in OVERLOADED_STATUSES:
                raise OverloadedError(message) from e
            raise ProviderError(message) from e
        except OSError as e:
            raise ProviderError(f"{self.describe()}: request to {url} failed: {e}") from e
