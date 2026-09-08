# Changelog

All notable changes to this project are documented in this file.\
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Package skeleton: errors, image loading with format sniffing, user config with provider profiles and `fallbacks`, preset lookup, system-instruction assembly, the `Provider` base class with HTTP error classification, and the bundled `faithful` preset.
- Providers `ollama` (`/api/chat`, image on the user turn, `num_ctx` 16384 by default), `openai` (Chat Completions with an `image_url` data URI, `max_tokens` 4000 by default for reasoning models), `wavespeed` (`llm.wavespeed.ai`, default `minimax/minimax-m3`, key from `$WAVESPEED_API_KEY`) and `anthropic` (Messages API image block, refusals raised as `RefusalError`).
- `Interrogator` and the `interrogate()` wrapper: preset resolution, the `explicit` switch, output cleanup (reasoning blocks, code fences, prompt headings, wrapping quotes, single-paragraph merge) and text-level refusal detection.
- The `image-interrogator` CLI: one image (or `-` for stdin), preset, instruction, `--explicit`, provider selection and overrides, `--show-system`, `--timing`, `--list-presets`, `--list-providers`.

[Unreleased]: https://github.com/Wujidadi/image-to-text-interrogator/commits/main
