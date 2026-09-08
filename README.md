# Image-to-text Interrogator

Vision-LLM-driven image interrogation: turn an image into a faithful, detailed prompt for text-to-image models.\
Usable as a Python library or as the `image-interrogator` command.\
Zero runtime dependencies, Python 3.11+.

Companion of [text-to-image-prompt-enhancer](https://github.com/Wujidadi/text-to-image-prompt-enhancer):\
the interrogator reconstructs the prompt from an image, the enhancer restyles a prompt.

## Development

```sh
uv sync
uv run pytest --cov
```
