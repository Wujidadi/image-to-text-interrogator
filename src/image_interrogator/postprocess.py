"""Cleanup of raw model output"""

import re
from pathlib import Path

T2S_MAP_PATH = Path(__file__).parent / "data" / "t2s.txt"
_t2s_table = None

_THINK = re.compile(r"<think>.*?(</think>|\Z)", re.DOTALL)
_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
# A leading line that only introduces the output, e.g. "Prompt:",
# "**Prompt:**", "Here is the prompt:", "## Prompt", "Tags:"
_NOUN = r"(?:prompt|tags?|tag list|description)"
_LEADING_MARKER = re.compile(
    r"^\s*(?:#+\s*|\*\*)?(?:here(?:'s| is)\s+(?:the\s+|your\s+)?)?"
    r"(?:[\w -]*\b" + _NOUN + r"\b[\w -]*)(?:\s+for\s+this\s+image)?\s*[:：]?\*{0,2}\s*(?:\n|$)",
    re.IGNORECASE)
_INLINE_MARKER = re.compile(r"^\s*(?:\*\*)?(?:[\w -]*\b" + _NOUN + r"\b)\s*[:：]\*{0,2}\s+",
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


def normalize_tags(text):
    """Comma-separated tags: one per item, trimmed, deduplicated in order"""
    items = []
    for raw in re.split(r"[,\n]", _BULLET.sub("", text)):
        item = raw.strip().rstrip(".;").strip()
        if item and item not in items:
            items.append(item)
    return ", ".join(items)


_NEGATIVE_SPLIT = re.compile(r"^\s*(?:\*\*)?\s*negative(?:\s+prompt)?\s*[:：]\s*(?:\*\*)?\s*",
                             re.IGNORECASE | re.MULTILINE)
_PROMPT_HEAD = re.compile(r"^\s*(?:\*\*)?\s*(?:positive\s+)?prompt\s*[:：]\s*(?:\*\*)?\s*",
                          re.IGNORECASE)
_NO_NEGATIVE = {"", "none", "none.", "n/a", "-"}


def split_negative(text):
    """Split a "PROMPT: ... NEGATIVE: ..." reply into (prompt, negative),
    each merged into one paragraph; the negative is empty when absent"""
    match = _NEGATIVE_SPLIT.search(text)
    if match:
        prompt, negative = text[:match.start()], text[match.end():]
    else:
        prompt, negative = text, ""
    prompt = single_paragraph(_PROMPT_HEAD.sub("", prompt, count=1))
    negative = single_paragraph(negative)
    if negative.strip().lower() in _NO_NEGATIVE:
        negative = ""
    return prompt, negative


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


def to_simplified(text):
    """Deterministic char-level Traditional-to-Simplified conversion:
    models ignore the zh directive now and then, and model-side conversion
    can silently rewrite wording"""
    global _t2s_table
    if _t2s_table is None:
        lines = [l for l in T2S_MAP_PATH.read_text(encoding="utf-8").splitlines()
                 if l and not l.startswith("#")]
        _t2s_table = str.maketrans(lines[0], lines[1])
    return text.translate(_t2s_table)
