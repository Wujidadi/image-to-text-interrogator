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
#   "image-to-text-interrogator @ git+https://github.com/Wujidadi/image-to-text-interrogator@v0.3.0",
# ]
# ///

# As a dependency of a project
uv add "image-to-text-interrogator @ git+https://github.com/Wujidadi/image-to-text-interrogator@v0.3.0"
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
image-interrogator -p tags illustration.png                 # Danbooru-style tag line
image-interrogator -p concise -l zh photo.png               # short prompt in Simplified Chinese
image-interrogator --type claude-code photo.png             # Sonnet 5 through the Claude Code CLI
image-interrogator --sidecar *.png                          # batch: each prompt to <image>.txt
image-interrogator --json --output-dir prompts/ *.png       # batch: files plus a JSON report
image-interrogator --fallback wavespeed photo.png           # try another profile on refusal or overload
image-interrogator --timing --show-system photo.png         # diagnostics on stderr
pngpaste - | image-interrogator -                           # image from stdin
image-interrogator --list-presets
image-interrogator --list-providers
```

| Option                       | Description                                                                  |
| ---------------------------- | ---------------------------------------------------------------------------- |
| `image...`                   | PNG, JPEG, WebP or GIF files, or `-` for stdin                               |
| `--preset`, `-p`             | Preset name (subdirectories allowed) or plain path; default `faithful`       |
| `--instruction`, `-i`        | Ad-hoc instruction appended to the preset                                    |
| `--explicit`                 | Ask for adult and sexually explicit elements to be described, not softened   |
| `--language`, `-l`           | Output language `en` (default) or `zh` (Simplified Chinese)                  |
| `--provider`, `-P`           | Provider profile from the config file                                        |
| `--type`, `--model`, `--url` | Override the chosen profile's type, model or endpoint                        |
| `--fallback`                 | Profile tried next on refusal or overload (repeatable); overrides the config |
| `--no-fallback`              | Never fall back to another profile                                           |
| `--preset-dir`               | Extra preset directory searched first (repeatable)                           |
| `--config`                   | Config file path                                                             |
| `--sidecar`                  | Write each prompt to `<image>.txt` next to the image instead of stdout       |
| `--output-dir`               | Write each prompt to `<dir>/<image stem>.txt` instead of stdout              |
| `--json`                     | Print a JSON list with prompt, elapsed time, usage and errors per image      |
| `--show-system`              | Print the assembled system instruction to stderr                             |
| `--timing`                   | Print the elapsed time per image to stderr                                   |
| `--quiet`, `-q`              | Suppress the progress lines on stderr                                        |
| `--list-presets`             | List visible presets with their source path and marks                        |
| `--list-providers`           | List provider profiles (`*` marks the default)                               |

The prompt goes to stdout; everything else goes to stderr.\
With several images, each prompt on stdout is preceded by a `# <path>` line and separated by a blank line;\
one failed image does not stop the others, and the exit status is 1 when any image failed.\
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
    result = interrogator.interrogate_detailed("photo.png")   # Result: text, provider, elapsed, usage, attempts
except ImageInterrogatorError as e:
    ...
```

- `Interrogator(provider, language=None, preset_dirs=(), fallbacks=(), on_fallback=None)` takes any `Provider`.\
  `Interrogator.from_config(provider=None, overrides=None, *, language=None, preset_dirs=(), config_path=None, fallbacks=None, on_fallback=None)` builds one from the config file;\
  `fallbacks=None` takes the config file's list, `[]` disables fallbacks, and `on_fallback(error, next_provider)` is called on every switch.
- `interrogate(image, *, preset=None, instruction=None, language=None, explicit=False) -> str` performs a single pass;\
  `image` is a path, `bytes`, a binary stream or an `ImageInput`.\
  It raises an `ImageInterrogatorError` subclass on failure:\
  `ConfigError`, `PresetNotFoundError`, `ImageError`, or `ProviderError`, whose subclasses `RefusalError` (content policy) and `OverloadedError` (HTTP 429 / 503 / 529) let callers pick a different fallback strategy.
- `interrogate_detailed(...)` returns a `Result` instead of the bare string:\
  `text`, `provider` (the one that answered), `elapsed` seconds, `usage` (the provider's report, see below) and `attempts` (the errors of the providers tried before, when fallbacks were used).
- `prepare(preset, instruction, language, explicit)` returns `(system, preset)` without calling the model.
- `interrogator.provider.describe()` gives a short `"<type> <model>"` label.
- `interrogate(...)` at module level wraps both steps in one call.
- Also exported for callers that need the pieces:
  - `load_image(source)`, `ImageInput`
  - `list_presets(extra_dirs=())`, `load_preset(name, extra_dirs=())`
  - `load_config(path=None)`, `create_provider(settings)`
  - `clean_output(text, paragraph=False)`, `single_paragraph(text)`, `normalize_tags(text)`, `to_simplified(text)`, `is_refusal(text)`

Interactive review loops belong to the caller: the library is single-pass, apart from the fallback chain.

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

[providers.claude-code]         # Claude Code CLI on a Max subscription: best accuracy, quota-billed
type = "claude-code"
model = "sonnet"
```

| Type          | Endpoint                      | Default `url`                 | Notes                                                                          |
| ------------- | ----------------------------- | ----------------------------- | ------------------------------------------------------------------------------ |
| `ollama`      | `POST {url}/api/chat`         | `http://localhost:11434`      | `think` (default `false`), `num_ctx` (default `16384`); image on the user turn |
| `openai`      | `POST {url}/chat/completions` | `https://api.openai.com/v1`   | `max_tokens` (default `4000`, reasoning models need it); image as a data URI   |
| `wavespeed`   | `POST {url}/chat/completions` | `https://llm.wavespeed.ai/v1` | key from `$WAVESPEED_API_KEY` unless `api_key_env` is set                      |
| `anthropic`   | `POST {url}/v1/messages`      | `https://api.anthropic.com`   | `max_tokens` (default `4096`); refusals raise `RefusalError`                   |
| `claude-code` | `claude -p` subprocess        | the `claude` on `PATH`        | `model` is a Claude Code alias (default `sonnet`); `command`, `extra_args`     |

Keys common to every profile:

- `model`
- `url`
- `timeout`: seconds, default 300
- `retries`: attempts after an HTTP 429 / 503 / 529, default 2, with 1 s then 2 s of backoff (the `claude-code` type never retries)
- `api_key_env`: environment variable holding the key; an `api_key` literal also works but is discouraged
- `price`: a table `{ input = <USD per million input tokens>, output = <USD per million output tokens> }` used to add `cost_usd` to the usage report
- `extra`: a table merged verbatim into the request body, e.g. `temperature` or vendor-specific options

Callers may pass any of these as overrides on top of a profile.

### Fallbacks

`fallbacks` lists profiles to try in order when the chosen one raises `RefusalError` (the model declined) or `OverloadedError` (429 / 503 / 529 after the retries, or a Claude Code 529);\
the chosen profile is skipped when it appears in the list, and other errors never fall back.\
`--fallback <name>` (repeatable) replaces the list for one run, `--no-fallback` disables it, and every switch is reported on stderr.

### Usage Reports

After a call, `provider.last_usage` (also `Result.usage` and the `usage` field of `--json`) holds what the backend reported:\
token counts, durations and `tokens_per_second` from ollama, `usage` from Chat Completions and Anthropic, `total_cost_usd` and `modelUsage` from Claude Code.\
With a `price` table on the profile, `cost_usd` is estimated from the input and output token counts.

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

### Claude Code

The `claude-code` type runs the Claude Code CLI (`claude -p --model <alias> --output-format json --tools Read --allowedTools Read`) with the preset as its system prompt and hands the image over as a file path;\
it works from inside a Claude Code session too.\
Sonnet 5 through this route had the highest accuracy in the maintainer's evaluation, but every call carries 50k to 70k tokens of Claude Code's own context, so it suits a few images at a time, not batches.\
`provider.last_usage` (and the `usage` field of `--json`) carries `total_cost_usd` and `modelUsage` from the CLI's report.

### Output Cleanup

Reasoning blocks (`<think>...</think>`), Markdown code fences, "Prompt:"-style headings and wrapping quotes are stripped from the model output, and the result is merged into a single paragraph (or normalized as a tag line for `format=tags` presets).

## Development

```sh
uv sync
uv run pytest --cov
uv run image-interrogator --list-presets
uv run image-interrogator ~/Desktop/photo.png     # real call against local ollama
```
