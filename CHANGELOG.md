# Changelog

All notable changes to this project are documented in this file.\
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Wujidadi/image-to-text-interrogator/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Wujidadi/image-to-text-interrogator/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Wujidadi/image-to-text-interrogator/releases/tag/v0.1.0
