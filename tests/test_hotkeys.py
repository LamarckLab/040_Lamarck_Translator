import pytest

from lamarck_translator.hotkeys import MOD_ALT, MOD_NOREPEAT, parse_hotkey


def test_parse_hotkey() -> None:
    parsed = parse_hotkey("Alt+C")
    assert parsed.modifiers == MOD_ALT | MOD_NOREPEAT
    assert parsed.virtual_key == ord("C")


def test_reject_unknown_key() -> None:
    with pytest.raises(ValueError):
        parse_hotkey("Ctrl+PageDown")
