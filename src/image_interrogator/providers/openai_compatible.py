from ..errors import ProviderError
from . import register
from .base import Provider

# Reasoning models count their reasoning tokens against max_tokens; with
# 700 the measured output was one sentence (gemini) or empty (kimi)
DEFAULT_MAX_TOKENS = 4000


@register
class OpenAICompatibleProvider(Provider):
    """Chat Completions API with the image as an image_url data URI, as
    served by OpenAI, OpenRouter, LM Studio, llama.cpp server, vLLM and
    most other hosts. `url` is the API base, e.g. https://api.openai.com/v1"""

    type_name = "openai"
    default_url = "https://api.openai.com/v1"

    def complete(self, system, prompt, image):
        payload = {
            "model": self.model,
            "max_tokens": self.settings.get("max_tokens", DEFAULT_MAX_TOKENS),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image.data_uri}},
                ]},
            ],
            **self.extra,
        }
        headers = {}
        key = self.api_key
        if key:
            headers["Authorization"] = f"Bearer {key}"
        reply = self._post_json(self.url + "/chat/completions", payload, headers)
        try:
            content = reply["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ProviderError(f"{self.describe()}: unexpected response shape") from None
        if not isinstance(content, str):
            raise ProviderError(f"{self.describe()}: empty response")
        return content
