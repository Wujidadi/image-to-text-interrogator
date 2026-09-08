import argparse
import sys
import time

from . import (DEFAULT_PRESET, ImageInterrogatorError, Interrogator, __version__,
               list_presets, load_config, load_image)
from .prompt import LANGUAGE_DIRECTIVES

PROG = "image-interrogator"


def die(message):
    print(f"{PROG}: {message}", file=sys.stderr)
    sys.exit(1)


def build_parser():
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Reconstruct a text-to-image prompt from an image with a "
                    "vision LLM. The prompt is printed to stdout; progress and "
                    "diagnostics go to stderr.")
    parser.add_argument("image", nargs="?",
                        help='image file (PNG, JPEG, WebP or GIF), or "-" for stdin')
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
                        help="output language; overrides the config file, default en")
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
    parser.add_argument("--preset-dir", metavar="<dir>", action="append", default=[],
                        help="extra preset directory searched first (repeatable)")
    parser.add_argument("--config", metavar="<file>",
                        help="config file (default: $IMAGE_INTERROGATOR_CONFIG or "
                             "~/.config/image-interrogator/config.toml)")
    parser.add_argument("--show-system", action="store_true",
                        help="print the assembled system instruction to stderr")
    parser.add_argument("--timing", action="store_true",
                        help="print the elapsed time to stderr")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="suppress the progress line on stderr")
    parser.add_argument("--list-presets", action="store_true",
                        help="list visible presets and exit")
    parser.add_argument("--list-providers", action="store_true",
                        help="list provider profiles and exit")
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    return parser


def parse_args(argv):
    """The listing flags need no image, so a missing positional is only
    an error when a real run is requested"""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.image is None and not (args.list_presets or args.list_providers):
        parser.error("the following arguments are required: image")
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


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.list_presets or args.list_providers:
            run_listing(args)
            return
        overrides = {k: v for k, v in
                     (("type", args.type), ("model", args.model), ("url", args.url))
                     if v is not None}
        interrogator = Interrogator.from_config(args.provider, overrides,
                                                language=args.language,
                                                preset_dirs=args.preset_dir,
                                                config_path=args.config)
        image = read_image(args.image)
        for warning in image.warnings:
            print(f"{PROG}: warning: {warning}", file=sys.stderr)
        if args.show_system:
            system, _ = interrogator.prepare(args.preset, args.instruction,
                                             args.language, args.explicit)
            print(system, file=sys.stderr)
        if not args.quiet:
            print(f"{PROG}: interrogating {image.describe()} "
                  f"({interrogator.provider.describe()}, preset {args.preset})...",
                  file=sys.stderr)
        started = time.monotonic()
        result = interrogator.interrogate(image, preset=args.preset,
                                          instruction=args.instruction,
                                          language=args.language, explicit=args.explicit)
        if args.timing:
            print(f"{PROG}: elapsed {time.monotonic() - started:.1f}s", file=sys.stderr)
        print(result)
    except ImageInterrogatorError as e:
        die(str(e))


if __name__ == "__main__":  # pragma: no cover
    main()
