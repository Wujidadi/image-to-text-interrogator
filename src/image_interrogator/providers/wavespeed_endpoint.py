"""WaveSpeed model endpoints (api.wavespeed.ai/api/v3/<model id>): the image
is uploaded first, the prediction is submitted, then polled until completed.
Slower and pricier per image than the LLM service (`wavespeed` type), kept
for endpoints that only exist in this form"""

import time

from ..errors import ProviderError
from . import register
from .base import Provider

TERMINAL_FAILURES = ("failed", "cancelled", "timeout", "deleted")
_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp",
               "image/gif": "gif"}


@register
class WaveSpeedEndpointProvider(Provider):
    """Settings: model (endpoint id), max_tokens (default 1024),
    poll_interval (seconds, default 2), timeout (total seconds to wait
    for the prediction), extra (merged into the submission)"""

    type_name = "wavespeed-endpoint"
    default_url = "https://api.wavespeed.ai/api/v3"
    default_model = "nvidia/nemotron-3-nano-omni/vision"
    default_api_key_env = "WAVESPEED_API_KEY"

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def _upload(self, image):
        name = image.path.name if image.path else f"image.{_EXTENSIONS[image.media_type]}"
        reply = self._post_json(self.url + "/media/uploads",
                                {"filename": name, "size": len(image.data),
                                 "content_type": image.media_type}, self._headers())
        data = reply.get("data") or {}
        upload = data.get("upload") or {}
        if not data.get("download_url") or not upload.get("url"):
            raise ProviderError(f"{self.describe()}: unexpected upload response shape")
        self._put_bytes(upload["url"], image.data, upload.get("headers") or {})
        return data["download_url"]

    def complete(self, system, prompt, image):
        headers = self._headers()
        payload = {"prompt": prompt, "system_prompt": system, "image": self._upload(image),
                   "max_tokens": self.settings.get("max_tokens", 1024), **self.extra}
        reply = self._post_json(f"{self.url}/{self.model}", payload, headers)
        prediction = (reply.get("data") or {}).get("id")
        if not prediction:
            raise ProviderError(f"{self.describe()}: no prediction id in the reply")
        result = self._wait(prediction, headers)
        outputs = result.get("outputs") or []
        text = outputs[0] if outputs else None
        if isinstance(text, dict):
            text = text.get("output") or text.get("text")
        if not isinstance(text, str):
            raise ProviderError(f"{self.describe()}: no text output in prediction {prediction}")
        inference = (result.get("timings") or {}).get("inference")
        self.last_usage = {"inference_ms": inference} if inference is not None else None
        return text

    def _wait(self, prediction, headers):
        interval = self.settings.get("poll_interval", 2)
        deadline = time.monotonic() + self.timeout
        while True:
            reply = self._get_json(f"{self.url}/predictions/{prediction}/result", headers)
            result = reply.get("data") or {}
            status = result.get("status")
            if status == "completed":
                return result
            if status in TERMINAL_FAILURES:
                raise ProviderError(f"{self.describe()}: prediction {prediction} {status}: "
                                    f"{result.get('error') or 'no details'}")
            if time.monotonic() >= deadline:
                raise ProviderError(f"{self.describe()}: prediction {prediction} still "
                                    f"{status} after {self.timeout}s")
            time.sleep(interval)
