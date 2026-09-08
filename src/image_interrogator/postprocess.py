"""Cleanup of raw model output"""

import re

_THINK = re.compile(r"<think>.*?(</think>|\Z)", re.DOTALL)
_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
# A leading line that only introduces the prompt, e.g. "Prompt:",
# "**Prompt:**", "Here is the prompt:", "## Prompt"
_LEADING_MARKER = re.compile(
    r"^\s*(?:#+\s*|\*\*)?(?:here(?:'s| is)\s+(?:the\s+|your\s+)?)?"
    r"(?:[\w -]*\bprompt\b[\w -]*)(?:\s+for\s+this\s+image)?\s*[:：]?\*{0,2}\s*(?:\n|$)",
    re.IGNORECASE)
_INLINE_MARKER = re.compile(r"^\s*(?:\*\*)?(?:[\w -]*\bprompt\b)\s*[:：]\*{0,2}\s+",
                            re.IGNORECASE)
_QUOTES = (('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"))
_BULLET = re.compile(r"^\s*[-*•]\s+", re.MULTILINE)

_REFUSAL_PATTERNS = re.compile(
    r"^(?:sorry,?\s*)?(?:but\s+)?i(?:'m| am)?\s*(?:cannot|can't|can not|won't|will not|"
    r"unable to|not able to)\b", re.IGNORECASE)
_REFUSAL_MAX_LENGTH = 400


def strip_think(text):
    return _THINK.sub("", text)


def strip_leading_marker(text):
    """Drop a first line that is only a "Prompt:" style heading, or an
    inline "Prompt: " prefix, leaving inner colons alone"""
    match = _LEADING_MARKER.match(text)
    if match:
        return text[match.end():].strip()
    match = _INLINE_MARKER.match(text)
    if match:
        return text[match.end():].strip()
    return text


def strip_quotes(text):
    while len(text) >= 2:
        for open_, close in _QUOTES:
            if text[0] == open_ and text[-1] == close:
                text = text[1:-1].strip()
                break
        else:
            return text
    return text


def single_paragraph(text):
    """Merge lines and paragraphs into one paragraph; bullet items become
    comma-separated phrases"""
    if _BULLET.search(text):
        items = [_BULLET.sub("", line).strip() for line in text.splitlines()]
        return ", ".join(i.rstrip(",;") for i in items if i)
    return " ".join(part.strip() for part in text.split("\n") if part.strip())


def clean_output(text, paragraph=False):
    """Strip reasoning blocks, code fences, prompt headings and wrapping
    quotes; optionally collapse the result into a single paragraph"""
    text = strip_think(text).strip()
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    text = strip_leading_marker(text)
    text = strip_quotes(text)
    if paragraph:
        text = single_paragraph(text)
    return text.strip()


def is_refusal(text):
    """A short reply that opens with "I cannot / I can't / I'm unable"
    is a policy refusal rather than a description"""
    return len(text) <= _REFUSAL_MAX_LENGTH and bool(_REFUSAL_PATTERNS.match(text.strip()))
