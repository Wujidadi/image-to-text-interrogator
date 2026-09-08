"""System-instruction assembly"""

FIXED_LANGUAGE_PRAGMA = "# image-interrogator:fixed-language"

LANGUAGE_DIRECTIVES = {
    "en": "Write the final prompt in English.",
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
    """Return (rule, fixed_language) for a preset file's text"""
    text = text.strip()
    first, _, rest = text.partition("\n")
    if first.strip() == FIXED_LANGUAGE_PRAGMA:
        return rest.strip(), True
    return text, False


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
