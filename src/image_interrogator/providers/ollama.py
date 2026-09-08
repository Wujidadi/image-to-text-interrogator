from ..errors import ProviderError
from . import register
from .base import Provider

# Qwen encodes a 768x1024 image into ~840 tokens; the ollama default of 4096
# leaves too little room for the system instruction plus a long prompt
DEFAULT_NUM_CTX = 16384


@register
class OllamaProvider(Provider):
    """ollama /api/chat with the image attached to the user turn.
    Thinking is off by default: it was measured slower and no better for
    describing an image"""

    type_name = "ollama"
    default_url = "http://localhost:11434"
    default_model = "qwen3.6:35b"

    def complete(self, system, prompt, image):
        extra = dict(self.extra)
        options = {"num_ctx": self.settings.get("num_ctx", DEFAULT_NUM_CTX),
                   **(extra.pop("options", None) or {})}
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt, "images": [image.base64]}],
            "stream": False,
            "think": self.settings.get("think", False),
            "options": options,
            **extra,
        }
        reply = self._post_json(self.url + "/api/chat", payload)
        message = reply.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise ProviderError(f"{self.describe()}: unexpected response shape")
        return message["content"]
