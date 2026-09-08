# Changelog

All notable changes to this project are documented in this file.\
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.1] - 2026-09-08

### Fixed

- `-l zh` produced English on the `faithful` preset with qwen3.6:35b and gemma4:26b: the language requirement is now repeated as the last line of the system instruction, after the custom instruction, and `LANGUAGE_REMINDERS` is exported.
- The `faithful` and `faithful-negative` presets forbid section labels, which the Chinese output had started to add.

## [0.4.0] - 2026-09-08

### Added

- Provider type `wavespeed-endpoint` for WaveSpeed model endpoints (`api.wavespeed.ai/api/v3/<model id>`, default `nvidia/nemotron-3-nano-omni/vision`): uploads the image through `/media/uploads`, submits the prediction and polls `/predictions/<id>/result` (`poll_interval`, `timeout` as the total wait); `Provider` gains `_get_json()` and `_put_bytes()`.
- Optional downscaling before the call: `max_side` in the config file or on `Interrogator`, `--max-side` on the CLI, through the `resize` extra (`image-to-text-interrogator[resize]`, Pillow); `Result.image` carries the image actually sent.
- Preset `faithful-negative` and the `format=negative` pragma: the model answers with `PROMPT:` and `NEGATIVE:` sections, split into `Result.negative`; the CLI prints `Negative: ...` after the prompt, writes `<image>.negative.txt` alongside a sidecar, and adds `negative` to `--json`.
- `--compare <profile>` (repeatable) runs every image through the chosen profile and each named one, side by side with a `# <provider>` header per result, `<image>.<profile>.txt` sidecars and a `profile` field in `--json`; fallbacks are disabled in this mode.

## [0.3.0] - 2026-09-08

### Added

- Fallback chain: `fallbacks` in the config file, `fallbacks=` on `Interrogator.from_config()`, `--fallback` / `--no-fallback` on the CLI; the next profile is tried on `RefusalError` or `OverloadedError` only, and every switch is reported on stderr.
- HTTP 429 / 503 / 529 are retried with 1 s then 2 s backoff (`retries`, default 2) before `OverloadedError` is raised; the Claude Code route is never retried.
- `Interrogator.interrogate_detailed()` returns a `Result` with the answering provider, elapsed time, usage report and the errors of the providers tried before it; `--json` and `--timing` show them.
- Usage reports on every provider (`provider.last_usage`): token counts and speed from ollama, `usage` from Chat Completions and Anthropic, plus `cost_usd` when the profile carries a `price` table (USD per million input and output tokens).

## [0.2.0] - 2026-09-08

### Added

- Provider type `claude-code`: runs `claude -p` with the system instruction, the Read tool only and JSON output, hands the image over as a path (bytes go through a temporary file), strips the nested-session variables so it works from inside a Claude Code session, and reports `total_cost_usd` and `modelUsage` on `provider.last_usage`.
- Output language `zh` (Simplified Chinese), guaranteed by a deterministic char-level Traditional-to-Simplified pass over `data/t2s.txt` (distilled from OpenCC, Apache 2.0).
- Presets `tags` (Danbooru-style tag line, fixed language, normalized and deduplicated) and `concise` (40 to 80 words); preset files may stack several `# image-interrogator:<pragma>` lines, and `format=tags` selects the tag normalization.
- `--list-presets` shows `[fixed-language, tags]` style marks; "Tags:" and "Description:" headings are stripped from the output like "Prompt:".
- Batch mode: several images per run, `--sidecar` (write `<image>.txt` next to the image), `--output-dir`, `--json` (prompt, elapsed time, provider usage and errors per image); one failure does not stop the rest, and the exit status is 1 when any image failed.

## [0.1.0] - 2026-09-08

### Added

- Package skeleton: errors, image loading with format sniffing, user config with provider profiles and `fallbacks`, preset lookup, system-instruction assembly, the `Provider` base class with HTTP error classification, and the bundled `faithful` preset.
- Providers `ollama` (`/api/chat`, image on the user turn, `num_ctx` 16384 by default), `openai` (Chat Completions with an `image_url` data URI, `max_tokens` 4000 by default for reasoning models), `wavespeed` (`llm.wavespeed.ai`, default `minimax/minimax-m3`, key from `$WAVESPEED_API_KEY`) and `anthropic` (Messages API image block, refusals raised as `RefusalError`).
- `Interrogator` and the `interrogate()` wrapper: preset resolution, the `explicit` switch, output cleanup (reasoning blocks, code fences, prompt headings, wrapping quotes, single-paragraph merge) and text-level refusal detection.
- The `image-interrogator` CLI: one image (or `-` for stdin), preset, instruction, `--explicit`, provider selection and overrides, `--show-system`, `--timing`, `--list-presets`, `--list-providers`.

[Unreleased]: https://github.com/Wujidadi/image-to-text-interrogator/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/Wujidadi/image-to-text-interrogator/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Wujidadi/image-to-text-interrogator/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Wujidadi/image-to-text-interrogator/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Wujidadi/image-to-text-interrogator/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Wujidadi/image-to-text-interrogator/releases/tag/v0.1.0
