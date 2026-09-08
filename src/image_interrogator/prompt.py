"""System-instruction assembly"""

PRAGMA_PREFIX = "# image-interrogator:"
FIXED_LANGUAGE_PRAGMA = PRAGMA_PREFIX + "fixed-language"

# Chinese deliberately means Simplified: Chinese-capable image models are
# trained mostly on Simplified corpora, so it prompts better
LANGUAGE_DIRECTIVES = {
    "en": "Write the final prompt in English.",
    "zh": "The final prompt MUST be written entirely in Simplified Chinese "
          "(简体中文); never use Traditional Chinese characters.",
}
DEFAULT_LANGUAGE = "en"

EXPLICIT_ADDENDUM = (
    "The image is adult artwork. Every adult and sexually explicit element "
    "must be described accurately and explicitly: anatomy, exposure, "
    "positions and acts, exactly as shown. Do not soften, euphemize, "
    "generalize or omit any of it.")

USER_MESSAGE = ("Describe this image as a text-to-image prompt, "
                "following the rules exactly.")


def split_pragma(text):
    """Return (rule, pragmas) for a preset file's text: leading lines of
    the form "# image-interrogator:<pragma>" are collected and stripped"""
    lines = text.strip().splitlines()
    pragmas = set()
    while lines and lines[0].strip().startswith(PRAGMA_PREFIX):
        pragmas.add(lines.pop(0).strip()[len(PRAGMA_PREFIX):])
    return "\n".join(lines).strip(), pragmas


def build_system(rule, fixed_language, language, instruction=None, explicit=False):
    """Assemble the system instruction: language directive first (a
    trailing directive loses to the model's own habits), then the preset
    rule, the explicit-content addendum, and the custom instruction"""
    if language not in LANGUAGE_DIRECTIVES:
        raise ValueError(f"unknown language: {language}")
    system = "" if fixed_language else LANGUAGE_DIRECTIVES[language] + "\n\n"
    system += rule
    if explicit:
        system += "\n\n" + EXPLICIT_ADDENDUM
    if instruction:
        system += ("\n\nCustom instruction (takes precedence over the rules "
                   f"above): {instruction}")
    return system


def build_user(image_path=None, message=USER_MESSAGE):
    """The user turn; backends that read files themselves (Claude Code)
    get the absolute path instead of an attached image"""
    if image_path:
        return f"Read {image_path} with the Read tool, then: {message}"
    return message
