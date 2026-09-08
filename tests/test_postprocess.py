import pytest

from image_interrogator.postprocess import clean_output, is_refusal, single_paragraph


def test_strip_think_block():
    assert clean_output("<think>\nreasoning\n</think>\n\na cat") == "a cat"
    assert clean_output("<think>unterminated") == ""


def test_strip_fence_and_quotes():
    assert clean_output('```text\n"a cat"\n```') == "a cat"
    assert clean_output("'a cat'") == "a cat"
    assert clean_output("“a cat”") == "a cat"


@pytest.mark.parametrize("raw", [
    "Prompt: a cat",
    "**Prompt:** a cat",
    "Here is the prompt:\n\na cat",
    "Here's the text-to-image prompt for this image:\na cat",
    "Text-to-image prompt:\na cat",
    "## Prompt\n\na cat",
])
def test_strip_leading_markers(raw):
    assert clean_output(raw) == "a cat"


def test_keeps_inner_colons():
    assert clean_output("Subject: a cat, style: photo") == "Subject: a cat, style: photo"


def test_single_paragraph():
    assert single_paragraph("a cat,\nsitting.\n\nSoft light.") == "a cat, sitting. Soft light."
    assert single_paragraph("- a cat\n- soft light") == "a cat, soft light"
    assert single_paragraph("a cat") == "a cat"


def test_clean_output_single_paragraph_option():
    assert clean_output("a cat\n\nsoft light", paragraph=True) == "a cat soft light"
    assert clean_output("a cat\n\nsoft light") == "a cat\n\nsoft light"


@pytest.mark.parametrize("text", [
    "I cannot fulfill this request. I am prohibited from generating sexual content.",
    "I can't help with that.",
    "I'm unable to describe this image.",
    "Sorry, I can't assist with this request.",
])
def test_is_refusal(text):
    assert is_refusal(text)


def test_is_not_refusal():
    assert not is_refusal("A warrior raising a bloodied axe, seen from behind.")
    assert not is_refusal("A sign reading \"I can't help falling in love\" on a wall, " * 5)


def test_to_simplified():
    from image_interrogator.postprocess import to_simplified
    assert to_simplified("一隻橘貓在窗臺上睡覺") == "一只橘猫在窗台上睡觉"
    assert to_simplified("plain ascii") == "plain ascii"
