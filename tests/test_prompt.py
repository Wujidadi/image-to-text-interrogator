import pytest

from image_interrogator.prompt import (EXPLICIT_ADDENDUM, FIXED_LANGUAGE_PRAGMA,
                                       LANGUAGE_DIRECTIVES, USER_MESSAGE,
                                       build_system, build_user, split_pragma)


def test_language_directive_leads():
    system = build_system("RULE", False, "en")
    assert system.startswith(LANGUAGE_DIRECTIVES["en"])
    assert system.endswith("RULE")


def test_fixed_language_omits_directive():
    assert build_system("RULE", True, "en") == "RULE"


def test_explicit_addendum_after_rule():
    system = build_system("RULE", True, "en", explicit=True)
    assert system == "RULE\n\n" + EXPLICIT_ADDENDUM


def test_instruction_last():
    system = build_system("RULE", True, "en", instruction="focus on clothing", explicit=True)
    assert system.index(EXPLICIT_ADDENDUM) < system.index("focus on clothing")
    assert system.endswith("Custom instruction (takes precedence over the rules above): focus on clothing")


def test_unknown_language():
    with pytest.raises(ValueError):
        build_system("RULE", False, "fr")


def test_split_pragma():
    assert split_pragma(f"{FIXED_LANGUAGE_PRAGMA}\nRULE\n") == ("RULE", True)
    assert split_pragma("RULE\nmore") == ("RULE\nmore", False)


def test_build_user():
    assert build_user() == USER_MESSAGE
    assert build_user("/abs/a.png").startswith("Read /abs/a.png")
