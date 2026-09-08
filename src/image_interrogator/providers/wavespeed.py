from . import register
from .openai_compatible import OpenAICompatibleProvider


@register
class WaveSpeedProvider(OpenAICompatibleProvider):
    """WaveSpeed LLM API: Chat Completions served at llm.wavespeed.ai with
    provider-prefixed model ids. The default model was the best balance of
    accuracy, speed and price in the maintainer's evaluation (11 s, under
    $0.001 per image). The key is the same WaveSpeed key used for image
    generation"""

    type_name = "wavespeed"
    default_url = "https://llm.wavespeed.ai/v1"
    default_model = "minimax/minimax-m3"
    default_api_key_env = "WAVESPEED_API_KEY"
