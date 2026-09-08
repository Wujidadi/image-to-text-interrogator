# Image-to-text Interrogator

Vision-LLM-driven image interrogation: turn an image into a faithful, detailed prompt for text-to-image models.\
Talks to a local ollama by default, and can be pointed at ollama cloud, the WaveSpeed LLM API, or any OpenAI-compatible or Anthropic endpoint.\
Usable as a Python library or as the `image-interrogator` command.\
Zero runtime dependencies, Python 3.11+.

Companion of [text-to-image-prompt-enhancer](https://github.com/Wujidadi/text-to-image-prompt-enhancer):\
the interrogator reconstructs a prompt from an image, the enhancer restyles a prompt.\
Chain them when the reconstructed prompt has to follow a specific model's format or style.

## Installation

```sh
# As a command-line tool
uv tool install git+https://github.com/Wujidadi/image-to-text-interrogator

# As a command-line tool from a checkout, tracking the working tree without reinstalling
uv tool install --editable .

# As a dependency of a script (PEP 723 inline metadata)
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "image-to-text-interrogator @ git+https://github.com/Wujidadi/image-to-text-interrogator@v0.1.0",
# ]
# ///

# As a dependency of a project
uv add "image-to-text-interrogator @ git+https://github.com/Wujidadi/image-to-text-interrogator@v0.1.0"
```

Without any configuration, interrogation runs against a local [ollama](https://ollama.com) at `http://localhost:11434` with `qwen3.6:35b`, the most accurate local vision model in the maintainer's evaluation (a 35B mixture-of-experts model, about 22 GB).\
Machines that cannot hold it point a profile at a smaller model, a LAN server or a cloud service (see [Configuration](#configuration)).

## Command Line

```sh
image-interrogator photo.png                                # default preset faithful, default profile
image-interrogator -i "focus on the clothing" photo.png     # ad-hoc instruction appended to the preset
image-interrogator --explicit photo.png                     # describe adult content accurately
image-interrogator -P wavespeed photo.png                   # provider profile from the config file
image-interrogator -m gemma4:26b photo.png                  # another model on the default profile
image-interrogator --type wavespeed photo.png               # another type, with that type's defaults
image-interrogator --timing --show-system photo.png         # diagnostics on stderr
pngpaste - | image-interrogator -                           # image from stdin
image-interrogator --list-presets
image-interrogator --list-providers
```

| Option                       | Description                                                                |
| ---------------------------- | -------------------------------------------------------------------------- |
| `image`                      | PNG, JPEG, WebP or GIF file, or `-` for stdin                              |
| `--preset`, `-p`             | Preset name (subdirectories allowed) or plain path; default `faithful`     |
| `--instruction`, `-i`        | Ad-hoc instruction appended to the preset                                  |
| `--explicit`                 | Ask for adult and sexually explicit elements to be described, not softened |
| `--language`, `-l`           | Output language, `en`                                                      |
| `--provider`, `-P`           | Provider profile from the config file                                      |
| `--type`, `--model`, `--url` | Override the chosen profile's type, model or endpoint                      |
| `--preset-dir`               | Extra preset directory searched first (repeatable)                         |
| `--config`                   | Config file path                                                           |
| `--show-system`              | Print the assembled system instruction to stderr                           |
| `--timing`                   | Print the elapsed time to stderr                                           |
| `--quiet`, `-q`              | Suppress the progress line on stderr                                       |
| `--list-presets`             | List visible presets with their source path                                |
| `--list-providers`           | List provider profiles (`*` marks the default)                             |

The prompt goes to stdout; everything else goes to stderr.\
Exit status is 1 on any failure.\
`--type` switches the backend type and drops the profile's `url`, `model` and `api_key_env`, so that the new type's defaults apply unless overridden on the same command line.

## Library

```python
from image_interrogator import Interrogator, ImageInterrogatorError

interrogator = Interrogator.from_config()                  # default profile
interrogator = Interrogator.from_config("wavespeed")       # named profile
interrogator = Interrogator.from_config(overrides={"model": "gemma4:26b"})

try:
    prompt = interrogator.interrogate("photo.png")
    prompt = interrogator.interrogate(image_bytes, instruction="focus on the clothing")
    prompt = interrogator.interrogate("photo.png", explicit=True)
except ImageInterrogatorError as e:
    ...
```

- `Interrogator(provider, language=None, preset_dirs=())` takes any `Provider`.\
  `Interrogator.from_config(provider=None, overrides=None, *, language=None, preset_dirs=(), config_path=None)` builds one from the config file.
- `interrogate(image, *, preset=None, instruction=None, language=None, explicit=False) -> str` performs a single pass;\
  `image` is a path, `bytes`, a binary stream or an `ImageInput`.\
  It raises an `ImageInterrogatorError` subclass on failure:\
  `ConfigError`, `PresetNotFoundError`, `ImageError`, or `ProviderError`, whose subclasses `RefusalError` (content policy) and `OverloadedError` (HTTP 429 / 503 / 529) let callers pick a different fallback strategy.
- `prepare(preset, instruction, language, explicit)` returns the assembled system instruction without calling the model.
- `interrogator.provider.describe()` gives a short `"<type> <model>"` label.
- `interrogate(...)` at module level wraps both steps in one call.
- Also exported for callers that need the pieces:
  - `load_image(source)`, `ImageInput`
  - `list_presets(extra_dirs=())`, `load_preset(name, extra_dirs=())`
  - `load_config(path=None)`, `create_provider(settings)`
  - `clean_output(text, paragraph=False)`, `single_paragraph(text)`, `is_refusal(text)`

Interactive review loops and fallback decisions belong to the caller: the library is single-pass.

## Configuration

The config file is `~/.config/image-interrogator/config.toml`, or the file named by `$IMAGE_INTERROGATOR_CONFIG`; see [config.example.toml](config.example.toml) for every provider type and the profiles that came out of the maintainer's evaluation.\
The file is optional.

A convenient way to keep the local config next to a checkout, where `config.toml` is git-ignored:

```sh
cp config.example.toml config.toml
mkdir -p ~/.config/image-interrogator
ln -s "$PWD/config.toml" ~/.config/image-interrogator/config.toml
```

```toml
default_provider = "ollama"
language = "en"
preset_dirs = []
fallbacks = []

[providers.ollama]
type = "ollama"
url = "http://localhost:11434"
model = "qwen3.6:35b"

[providers.lan]                 # an ollama server elsewhere on the LAN
type = "ollama"
url = "http://a2780.local:11434"
model = "huihui_ai/Qwen3.6-abliterated:35b-a3b"

[providers.ollama-cloud]        # needs "ollama signin"; -cloud tags run on ollama.com
type = "ollama"
model = "gemma4:31b-cloud"

[providers.wavespeed]
type = "wavespeed"
model = "minimax/minimax-m3"

[providers.claude]
type = "anthropic"
model = "claude-sonnet-5"
api_key_env = "ANTHROPIC_API_KEY"
```

| Type        | Endpoint                      | Default `url`                 | Notes                                                                          |
| ----------- | ----------------------------- | ----------------------------- | ------------------------------------------------------------------------------ |
| `ollama`    | `POST {url}/api/chat`         | `http://localhost:11434`      | `think` (default `false`), `num_ctx` (default `16384`); image on the user turn |
| `openai`    | `POST {url}/chat/completions` | `https://api.openai.com/v1`   | `max_tokens` (default `4000`, reasoning models need it); image as a data URI   |
| `wavespeed` | `POST {url}/chat/completions` | `https://llm.wavespeed.ai/v1` | key from `$WAVESPEED_API_KEY` unless `api_key_env` is set                      |
| `anthropic` | `POST {url}/v1/messages`      | `https://api.anthropic.com`   | `max_tokens` (default `4096`); refusals raise `RefusalError`                   |

Keys common to every profile:

- `model`
- `url`
- `timeout`: seconds, default 300
- `api_key_env`: environment variable holding the key; an `api_key` literal also works but is discouraged
- `extra`: a table merged verbatim into the request body, e.g. `temperature` or vendor-specific options

Callers may pass any of these as overrides on top of a profile.\
`fallbacks` lists profiles to try in order when the chosen one refuses or is overloaded;\
the CLI does not act on it yet.

## Presets

A preset file is the complete system instruction sent to the model.\
Lookup order for a name such as `faithful` or `styles/mine`:

1. directories passed by the caller (`--preset-dir` / `preset_dirs`)
2. `~/.config/image-interrogator/interrogators/` (next to the config file)
3. the bundled presets

Names starting with `/`, `~`, `./` or `../` are plain file paths.\
`.txt` is appended when the last segment has no extension.\
A name found in an earlier directory shadows the same name later on, so a bundled preset can be overridden by dropping a file into the user directory.

| Preset     | Description                                                                                                                       |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `faithful` | One paragraph covering subject, pose, composition, environment, light, color, materials, style and visible text, nothing invented |

A language directive is placed ahead of the preset rule;\
presets whose output format fixes the language declare `# image-interrogator:fixed-language` as their first line, and the line is stripped.

### Explicit Content

Official models soften or refuse adult content.\
`--explicit` (or `explicit=True`) appends an addendum asking for every adult element to be described accurately;\
it only helps on models that are willing, such as the uncensored `huihui_ai/Qwen3.6-abliterated:35b-a3b` on ollama.\
A refusal, whether signalled by the API or written as a reply, is raised as `RefusalError`.

### Output Cleanup

Reasoning blocks (`<think>...</think>`), Markdown code fences, "Prompt:"-style headings and wrapping quotes are stripped from the model output, and the result is merged into a single paragraph.

## Development

```sh
uv sync
uv run pytest --cov
uv run image-interrogator --list-presets
uv run image-interrogator ~/Desktop/photo.png     # real call against local ollama
```
