# image-to-text-interrogator

Vision-LLM-driven image interrogation, packaged as a Python library plus the `image-interrogator` CLI:\
an image goes in, a faithful and detailed prompt for text-to-image models comes out.\
See [README.md](README.md) for usage;\
this file only records what matters for development and maintenance.

The design mirrors [text-to-image-prompt-enhancer](https://github.com/Wujidadi/text-to-image-prompt-enhancer) (local checkout at `~/Documents/Workspaces/AI/Text-to-image/prompt-enhancer`) on purpose:\
same layering, same config format, same release process, so that consumers such as `dtgen` integrate both the same way.\
The two stay separate packages because the input type (image), the usable model set, the Claude Code route and the content-policy handling all differ.

## Architecture and Files

- `pyproject.toml`: distribution name `image-to-text-interrogator`, import name `image_interrogator`, hatchling build, no runtime dependencies (`pytest` and `pytest-cov` are the only dev dependencies).\
  Python 3.11+ is required for `tomllib`.
- `src/image_interrogator/__init__.py`: the public API and `__version__`.
- `errors.py`: `ImageInterrogatorError` is the base of everything;\
  `ProviderError` has two subclasses that callers treat differently, `RefusalError` (content policy, switch model or platform) and `OverloadedError` (HTTP 429 / 503 / 529, retry or switch to a peer).
- `image.py`: `load_image()` accepts a path, bytes, a binary stream or an `ImageInput`, sniffs PNG / JPEG / WebP / GIF from the file signature (`imghdr` is gone in 3.13) and never trusts the extension.\
  No resizing: that needs Pillow, which would break the zero-dependency rule;\
  images above 5 MB only get a warning (Anthropic's base64 limit).
- `config.py`: `~/.config/image-interrogator/config.toml` (or `$IMAGE_INTERROGATOR_CONFIG`), optional;\
  provider profiles under `[providers.<name>]`, `default_provider`, `language`, `preset_dirs`, `fallbacks`.\
  The built-in `ollama` profile (`http://localhost:11434`, `qwen3.6:35b`) always exists;\
  the model was chosen from the maintainer's evaluation as the best local vision model, and machine-specific choices belong in the config file.
- `presets.py`: preset lookup in the order caller directories, `~/.config/image-interrogator/interrogators/`, bundled `interrogators/`;\
  a name found earlier shadows the same name later.
- `prompt.py`: language directives, the explicit-content addendum, `build_system()` and `build_user()`.\
  The language directive leads the system instruction (measured in prompt-enhancer: a trailing directive loses to the model's habits).\
  A preset whose first line is `# image-interrogator:fixed-language` gets no directive.
- `providers/`: one class per backend type, registered with the `@register` decorator, all raw HTTP via `urllib` in `Provider._post_json()`;\
  `complete(system, prompt, image)` takes an `ImageInput`.
- `interrogators/`: the bundled presets, one file per preset, each being the complete system instruction;\
  `faithful` is the default.
- `CHANGELOG.md`: release history in Keep a Changelog format, the only document in this repository that records history.
- `tests/`: pytest;\
  `conftest.py` provides `FakeProvider`, `make_png()` (a valid PNG from the standard library), the `png_bytes` / `jpeg_bytes` / `png_file` fixtures and `isolated_config`, which points the user config at an empty temp directory so tests never read the developer's real config or presets.

## Development and Testing

```sh
uv sync
uv run pytest --cov
uv run image-interrogator --list-presets
```

- The project is developed test-first:\
  write the failing test in `tests/test_<module>.py`, make it pass with the least code, refactor, and commit test and implementation together.\
  Nothing goes into a commit without a test.
- Coverage is measured with branch mode and `fail_under = 100` in `pyproject.toml`;\
  the suite fails below 100% line and branch coverage.\
  Real network and real subprocess calls are never made in tests:\
  `urllib.request.urlopen` and `subprocess.run` are replaced with fakes, and `Provider._post_json` is monkeypatched in provider tests.
- Real model calls against `~/Desktop/AI Paintings/鬼門行軍.png` are manual checks used to tune the preset texts;\
  they are not part of the suite.
- There is no CI, but the suite must pass before every commit:\
  run `uv run pytest --cov` and never commit on red.
- To test a consumer such as `dtgen` against this checkout before a tag exists:\
  `uv run --no-project --with <this directory> python <script> ...`.

## Releases

- Version numbers follow `x.y.z`:
  - bump `z` for the usual change, including new presets, providers and options;
  - bump `y` for a breaking change to the public API, the config schema or a preset name;
  - bumping `x` (in particular `0` to `1`) is decided explicitly by the maintainer, never by an agent.
- `version` in `pyproject.toml` and `__version__` in `src/image_interrogator/__init__.py` must match;\
  `tests/test_version.py` fails when they drift.
- `CHANGELOG.md` follows Keep a Changelog;\
  every behavior change adds a line under `[Unreleased]` in the same commit.
- Release steps, in order:
  1. finish and commit all code changes, with `README.md` updated in sync and the suite green;
  2. bump the two version numbers, rename `[Unreleased]` in `CHANGELOG.md` to the new version with the release date and update the comparison links, and commit these release-only changes as `chore: release vX.Y.Z`;
  3. create an annotated tag `vX.Y.Z` whose message briefly lists the changes since the previous tag, mirroring the changelog entry;
  4. push the branch and the tag only when the maintainer asks.
- Consumers pin a release tag, so after a release tell the maintainer which consumers must move their pin and which changelog entries are breaking for them.\
  The intended consumer is `dtgen` (`~/Documents/Workspaces/AI/Draw Things/custom/dtgen`), a PEP 723 script whose inline `dependencies` will pin `image-to-text-interrogator @ git+https://github.com/Wujidadi/image-to-text-interrogator@vX.Y.Z`.

## Conventions

- Everything in this repository is written in English:\
  code, comments, documentation, commit messages.
- Markdown prose is wrapped by meaning, not by column width:
  - one sentence per line, however long;\
    break only at a sentence end, at a semicolon joining two substantial clauses, or at a colon or dash that introduces a clause or list;
  - never break after a comma, unless a single sentence is long enough to span three or four displayed lines;
  - inside a paragraph or a list item, every line except the last ends with a `\` hard break, so GitHub renders the line breaks instead of collapsing them into spaces;
  - a comma-separated enumeration with long or many items becomes a Markdown list;
  - tables and code blocks are left as they are;\
    re-align tables by display width after editing (CJK characters count as two columns).
- Documents describe the current state only;\
  history belongs to Git, not to the documents.
