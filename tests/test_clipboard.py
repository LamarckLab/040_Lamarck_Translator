from __future__ import annotations

from lamarck_translator import clipboard as clipboard_module
from lamarck_translator.clipboard import (
    CLIPBOARD_MAX_CHECKS,
    HOTKEY_RELEASE_POLL_MS,
    SelectionReader,
)


def test_reader_waits_for_trigger_key_release(monkeypatch) -> None:
    reader = SelectionReader(wait_ms=220, restore_clipboard=True)
    key_states = iter((True, False))
    scheduled: list[tuple[int, object]] = []
    copy_attempts: list[bool] = []

    monkeypatch.setattr(reader, "_trigger_keys_are_down", lambda: next(key_states))
    monkeypatch.setattr(reader, "_begin_copy_attempt", lambda: copy_attempts.append(True))
    monkeypatch.setattr(
        clipboard_module.QTimer,
        "singleShot",
        lambda delay, callback: scheduled.append((delay, callback)),
    )

    reader._copy_after_hotkey_release()
    assert scheduled[0][0] == HOTKEY_RELEASE_POLL_MS
    scheduled.pop(0)[1]()
    assert scheduled[0][0] == 40
    scheduled.pop(0)[1]()
    assert copy_attempts == [True]


def test_reader_retries_when_clipboard_stays_empty(monkeypatch) -> None:
    class EmptyClipboard:
        @staticmethod
        def text() -> str:
            return ""

    class FakeGuiApplication:
        @staticmethod
        def clipboard() -> EmptyClipboard:
            return EmptyClipboard()

    reader = SelectionReader(wait_ms=220, restore_clipboard=True)
    reader._copy_attempts = 1
    reader._clipboard_checks = CLIPBOARD_MAX_CHECKS
    scheduled: list[tuple[int, object]] = []

    monkeypatch.setattr(clipboard_module, "QGuiApplication", FakeGuiApplication)
    monkeypatch.setattr(reader, "_read_clipboard_text", lambda: "")
    monkeypatch.setattr(
        clipboard_module.QTimer,
        "singleShot",
        lambda delay, callback: scheduled.append((delay, callback)),
    )

    reader._check_clipboard()

    assert len(scheduled) == 1
    assert scheduled[0][0] == 80
    assert scheduled[0][1].__name__ == "_begin_copy_attempt"


def test_reader_uses_three_distinct_copy_methods(monkeypatch) -> None:
    reader = SelectionReader(wait_ms=220, restore_clipboard=True)
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(
        reader,
        "_send_with_send_input",
        lambda key: calls.append(("send_input", key)) or True,
    )
    monkeypatch.setattr(
        reader,
        "_send_with_keybd_event",
        lambda key: calls.append(("keybd_event", key)) or True,
    )
    monkeypatch.setattr(
        reader,
        "_send_with_wm_copy",
        lambda: calls.append(("wm_copy", 0)) or True,
    )

    for attempt in (1, 2, 3, 4):
        reader._copy_attempts = attempt
        assert reader._send_copy()

    assert calls == [
        ("send_input", clipboard_module.VK_C),
        ("wm_copy", 0),
        ("keybd_event", clipboard_module.VK_C),
        ("send_input", clipboard_module.VK_INSERT),
    ]
