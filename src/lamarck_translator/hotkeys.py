from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal


WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000


@dataclass(frozen=True, slots=True)
class ParsedHotkey:
    modifiers: int
    virtual_key: int


def parse_hotkey(value: str) -> ParsedHotkey:
    parts = [part.strip().upper() for part in value.split("+") if part.strip()]
    if not parts:
        raise ValueError("The keyboard shortcut cannot be empty.")

    modifier_map = {
        "ALT": MOD_ALT,
        "CTRL": MOD_CONTROL,
        "CONTROL": MOD_CONTROL,
        "SHIFT": MOD_SHIFT,
        "WIN": MOD_WIN,
        "WINDOWS": MOD_WIN,
    }
    modifiers = MOD_NOREPEAT
    key_name = parts[-1]
    for part in parts[:-1]:
        if part not in modifier_map:
            raise ValueError(f"Unsupported shortcut modifier: {part}")
        modifiers |= modifier_map[part]

    if len(key_name) == 1 and key_name.isalnum():
        virtual_key = ord(key_name)
    elif key_name.startswith("F") and key_name[1:].isdigit():
        number = int(key_name[1:])
        if not 1 <= number <= 24:
            raise ValueError(f"Invalid function key: {key_name}")
        virtual_key = 0x70 + number - 1
    else:
        raise ValueError(f"Unsupported shortcut key: {key_name}")
    return ParsedHotkey(modifiers, virtual_key)


class HotkeyManager(QObject, QAbstractNativeEventFilter):
    activated = Signal(int)

    def __init__(self) -> None:
        QObject.__init__(self)
        QAbstractNativeEventFilter.__init__(self)
        self._registered: set[int] = set()
        self._user32 = ctypes.windll.user32

    def register(self, hotkey_id: int, value: str) -> None:
        parsed = parse_hotkey(value)
        ok = self._user32.RegisterHotKey(
            None, hotkey_id, parsed.modifiers, parsed.virtual_key
        )
        if not ok:
            raise RuntimeError(f"Unable to register {value}. Another app may already be using this shortcut.")
        self._registered.add(hotkey_id)

    def unregister_all(self) -> None:
        for hotkey_id in tuple(self._registered):
            self._user32.UnregisterHotKey(None, hotkey_id)
        self._registered.clear()

    def nativeEventFilter(self, event_type, message):  # noqa: N802
        if event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                self.activated.emit(int(msg.wParam))
                return True, 0
        return False, 0
