import argparse
import json
import sys
from pathlib import Path

from . import (DEFAULT_PRESET, ImageInterrogatorError, Interrogator, __version__,
               list_presets, load_config, load_image)
from .prompt import LANGUAGE_DIRECTIVES

PROG = "image-interrogator"
LISTING_FLAGS = ("list_presets", "list_providers")


def die(message):
    print(f"{PROG}: {message}", file=sys.stderr)
    sys.exit(1)


def build_parser():
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Reconstruct a text-to-image prompt from an image with a "
                    "vision LLM. The prompt is printed to stdout; progress and "
                    "diagnostics go to stderr.")
    parser.add_argument("images", nargs="*", metavar="image",
                        help='image files (PNG, JPEG, WebP or GIF), or "-" for stdin')
    parser.add_argument("--preset", "-p", metavar="<name>", default=DEFAULT_PRESET,
                        help="interrogator preset: a name (subdirectories allowed) "
                             "searched under --preset-dir, the user directory and "
                             f"the bundled presets, or a plain path; default {DEFAULT_PRESET}")
    parser.add_argument("--instruction", "-i", metavar="<text>",
                        help="ad-hoc instruction appended to the preset, "
                             "taking precedence over its rules")
    parser.add_argument("--explicit", action="store_true",
                        help="ask for adult and sexually explicit elements to be "
                             "described accurately instead of softened or omitted")
    parser.add_argument("--language", "-l", choices=sorted(LANGUAGE_DIRECTIVES),
                        metavar="<lang>",
                        help="output language: en or zh (Simplified Chinese); "
                             "overrides the config file, default en")
    parser.add_argument("--provider", "-P", metavar="<name>",
                        help="provider profile from the config file "
                             "(default: default_provider, else ollama)")
    parser.add_argument("--type", metavar="<type>",
                        help="override the provider type "
                             "(ollama, openai, wavespeed, anthropic, claude-code)")
    parser.add_argument("--model", "-m", metavar="<name>",
                        help="override the provider's model")
    parser.add_argument("--url", metavar="<url>",
                        help="override the provider's endpoint URL")
    parser.add_argument("--fallback", metavar="<name>", action="append",
                        help="provider profile tried next when the previous one refuses "
                             "or is overloaded (repeatable); overrides the config file's "
                             "fallbacks list")
    parser.add_argument("--no-fallback", action="store_true",
                        help="never fall back to another profile")
    parser.add_argument("--preset-dir", metavar="<dir>", action="append", default=[],
                        help="extra preset directory searched first (repeatable)")
    parser.add_argument("--config", metavar="<file>",
                        help="config file (default: $IMAGE_INTERROGATOR_CONFIG or "
                             "~/.config/image-interrogator/config.toml)")
    parser.add_argument("--sidecar", action="store_true",
                        help="write each prompt to <image>.txt next to the image "
                             "instead of stdout")
    parser.add_argument("--output-dir", metavar="<dir>",
                        help="write each prompt to <dir>/<image stem>.txt instead of stdout")
    parser.add_argument("--json", action="store_true",
                        help="print a JSON list with prompt, timing, usage and errors "
                             "per image")
    parser.add_argument("--show-system", action="store_true",
                        help="print the assembled system instruction to stderr")
    parser.add_argument("--timing", action="store_true",
                        help="print the elapsed time per image to stderr")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="suppress the progress lines on stderr")
    parser.add_argument("--list-presets", action="store_true",
                        help="list visible presets and exit")
    parser.add_argument("--list-providers", action="store_true",
                        help="list provider profiles and exit")
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    return parser


def parse_args(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    listing = any(getattr(args, flag) for flag in LISTING_FLAGS)
    if not args.images and not listing:
        parser.error("the following arguments are required: image")
    if "-" in args.images and (args.sidecar or args.output_dir):
        parser.error("--sidecar and --output-dir need a file name; stdin has none")
    return args


def run_listing(args):
    config = load_config(args.config)
    if args.list_presets:
        for preset in list_presets(list(args.preset_dir) + config.preset_dirs):
            marks = (["fixed-language"] if preset.fixed_language else []) \
                + ([preset.format] if preset.format != "paragraph" else [])
            flag = f"  [{', '.join(marks)}]" if marks else ""
            print(f"{preset.name}\t{preset.path}{flag}")
        return
    for name in sorted(config.providers):
        s = config.providers[name]
        mark = "*" if name == config.default_provider else " "
        print(f"{mark} {name}\t{s.get('type')}\t{s.get('model', '')}\t{s.get('url', '')}")


def read_image(value):
    if value == "-":
        return load_image(sys.stdin.buffer.read())
    return load_image(value)


def output_path(image, args):
    name = image.path.with_suffix(".txt").name
    if args.output_dir:
        return Path(args.output_dir).expanduser() / name
    return image.path.with_name(name)


def process(value, interrogator, args):
    """Interrogate one image; returns the JSON-shaped record"""
    record = {"image": value if value == "-" else str(Path(value).expanduser().resolve()),
              "preset": args.preset, "provider": interrogator.provider.describe()}
    image = read_image(value)
    for warning in image.warnings:
        print(f"{PROG}: warning: {warning}", file=sys.stderr)
    if not args.quiet:
        print(f"{PROG}: interrogating {image.describe()} "
              f"({interrogator.provider.describe()}, preset {args.preset})...",
              file=sys.stderr)
    result = interrogator.interrogate_detailed(
        image, preset=args.preset, instruction=args.instruction,
        language=args.language, explicit=args.explicit)
    record["prompt"] = result.text
    record["provider"] = result.provider.describe()
    record["elapsed"] = result.elapsed
    if result.attempts:
        record["attempts"] = [str(e) for e in result.attempts]
    if result.usage:
        record["usage"] = result.usage
    if args.timing:
        print(f"{PROG}: elapsed {result.elapsed:.1f}s ({result.provider.describe()})",
              file=sys.stderr)
    if args.sidecar or args.output_dir:
        target = output_path(image, args)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(record["prompt"] + "\n", encoding="utf-8")
        record["output"] = str(target)
        if not args.quiet:
            print(f"{PROG}: wrote {target}", file=sys.stderr)
    return record


def emit(record, args, first):
    """Plain stdout output; several images get a "# <path>" header each
    and a blank line between them"""
    if args.sidecar or args.output_dir or args.json:
        return
    if len(args.images) > 1:
        if not first:
            print()
        print(f"# {record['image']}")
    print(record["prompt"])


def main(argv=None):
    args = parse_args(argv)
    if any(getattr(args, flag) for flag in LISTING_FLAGS):
        try:
            run_listing(args)
        except ImageInterrogatorError as e:
            die(str(e))
        return
    overrides = {k: v for k, v in
                 (("type", args.type), ("model", args.model), ("url", args.url))
                 if v is not None}
    fallbacks = [] if args.no_fallback else args.fallback

    def on_fallback(error, next_provider):
        print(f"{PROG}: {error}; falling back to {next_provider.describe()}", file=sys.stderr)

    try:
        interrogator = Interrogator.from_config(args.provider, overrides,
                                                language=args.language,
                                                preset_dirs=args.preset_dir,
                                                config_path=args.config,
                                                fallbacks=fallbacks, on_fallback=on_fallback)
        if args.show_system:
            system, _ = interrogator.prepare(args.preset, args.instruction,
                                             args.language, args.explicit)
            print(system, file=sys.stderr)
    except ImageInterrogatorError as e:
        die(str(e))
    records, failures = [], []
    for value in args.images:
        try:
            record = process(value, interrogator, args)
            emit(record, args, first=not any("prompt" in r for r in records))
            records.append(record)
        except ImageInterrogatorError as e:
            failures.append(value)
            records.append({"image": value, "error": str(e)})
            prefix = f"{value}: " if len(args.images) > 1 and value not in str(e) else ""
            print(f"{PROG}: {prefix}{e}", file=sys.stderr)
    if args.json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
    if failures:
        if len(args.images) > 1:
            print(f"{PROG}: {len(failures)} of {len(args.images)} images failed: "
                  f"{', '.join(failures)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
