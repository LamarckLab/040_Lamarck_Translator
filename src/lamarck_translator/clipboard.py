from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QByteArray, QMimeData, QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication


VK_CONTROL = 0x11
VK_MENU = 0x12
VK_SHIFT = 0x10
VK_C = 0x43
VK_INSERT = 0x2D
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
CF_UNICODETEXT = 13
WM_COPY = 0x0301
SMTO_ABORTIFHUNG = 0x0002
HOTKEY_RELEASE_POLL_MS = 20
HOTKEY_RELEASE_MAX_CHECKS = 75
CLIPBOARD_POLL_MS = 100
CLIPBOARD_MAX_CHECKS = 10
MAX_COPY_ATTEMPTS = 4


class _KeyboardInput(ctypes.Structure):
    _fields_ = (
        ("virtual_key", wintypes.WORD),
        ("scan_code", wintypes.WORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("extra_info", wintypes.WPARAM),
    )


class _InputValue(ctypes.Union):
    _fields_ = (("keyboard", _KeyboardInput),)


class _Input(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = (("type", wintypes.DWORD), ("value", _InputValue))


class _GuiThreadInfo(ctypes.Structure):
    _fields_ = (
        ("size", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("active_window", wintypes.HWND),
        ("focused_window", wintypes.HWND),
        ("capture_window", wintypes.HWND),
        ("menu_owner", wintypes.HWND),
        ("move_size_window", wintypes.HWND),
        ("caret_window", wintypes.HWND),
        ("caret_rect", wintypes.RECT),
    )


def _keyboard_input(virtual_key: int, flags: int = 0) -> _Input:
    return _Input(
        type=INPUT_KEYBOARD,
        value=_InputValue(
            keyboard=_KeyboardInput(
                virtual_key=virtual_key,
                scan_code=0,
                flags=flags,
                time=0,
                extra_info=0,
            )
        ),
    )


def clone_mime_data(source: QMimeData) -> QMimeData:
    clone = QMimeData()
    for mime_type in source.formats():
        clone.setData(mime_type, QByteArray(source.data(mime_type)))
    return clone


class SelectionReader(QObject):
    captured = Signal(str)
    failed = Signal(str)

    def __init__(self, wait_ms: int, restore_clipboard: bool) -> None:
        super().__init__()
        self.wait_ms = wait_ms
        self.restore_clipboard = restore_clipboard
        self._saved: QMimeData | None = None
        self._release_checks = 0
        self._clipboard_checks = 0
        self._copy_attempts = 0
        self._foreground_window: int | None = None
        self._focused_window: int | None = None
        self._capturing = False

    def capture(self) -> None:
        if self._capturing:
            return
        self._capturing = True
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = wintypes.HWND
        self._foreground_window = user32.GetForegroundWindow()
        self._focused_window = self._get_focused_window(self._foreground_window)
        clipboard = QGuiApplication.clipboard()
        # Always snapshot, because capture() always clears. restore_clipboard
        # decides what happens after a *successful* copy; a failed one must put
        # the user's clipboard back either way.
        self._saved = clone_mime_data(clipboard.mimeData())
        clipboard.clear()
        self._release_checks = 0
        self._clipboard_checks = 0
        self._copy_attempts = 0
        self._copy_after_hotkey_release()

    def _copy_after_hotkey_release(self) -> None:
        if self._trigger_keys_are_down() and self._release_checks < HOTKEY_RELEASE_MAX_CHECKS:
            self._release_checks += 1
            QTimer.singleShot(HOTKEY_RELEASE_POLL_MS, self._copy_after_hotkey_release)
            return

        # Give the source app one event-loop turn after the physical keys are
        # released. This matters for Chromium's built-in PDF viewer.
        QTimer.singleShot(40, self._begin_copy_attempt)

    def _begin_copy_attempt(self) -> None:
        clipboard = QGuiApplication.clipboard()
        clipboard.clear()
        self._clipboard_checks = 0
        self._copy_attempts += 1
        self._restore_source_focus()
        # SetForegroundWindow is asynchronous for some Chromium and Firefox
        # windows. Let the target process receive focus before sending copy.
        QTimer.singleShot(60, self._dispatch_copy_attempt)

    def _dispatch_copy_attempt(self) -> None:
        if not self._send_copy():
            if self._copy_attempts < MAX_COPY_ATTEMPTS:
                QTimer.singleShot(100, self._begin_copy_attempt)
            else:
                self._complete("")
            return
        QTimer.singleShot(max(100, self.wait_ms), self._check_clipboard)

    def _check_clipboard(self) -> None:
        text = self._read_clipboard_text()
        if text:
            self._complete(text)
            return
        if self._clipboard_checks < CLIPBOARD_MAX_CHECKS:
            self._clipboard_checks += 1
            QTimer.singleShot(CLIPBOARD_POLL_MS, self._check_clipboard)
            return

        if self._copy_attempts < MAX_COPY_ATTEMPTS:
            QTimer.singleShot(80, self._begin_copy_attempt)
            return
        self._complete("")

    def _complete(self, text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        # On success, restore_clipboard says whether to put the old contents
        # back or leave the copied selection there. On failure there is nothing
        # worth keeping, so never leave the clipboard emptied by capture().
        if self._saved is not None and (self.restore_clipboard or not text):
            clipboard.setMimeData(self._saved)
        self._saved = None
        self._capturing = False
        self._foreground_window = None
        self._focused_window = None
        if text:
            self.captured.emit(text)
        else:
            self.failed.emit(
                "The selected app did not provide text after multiple copy methods. "
                "Try Alt+C again, or use screenshot translation."
            )

    @staticmethod
    def _get_focused_window(foreground_window: int | None) -> int | None:
        if not foreground_window:
            return None
        user32 = ctypes.windll.user32
        user32.GetWindowThreadProcessId.argtypes = (
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        )
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.GetGUIThreadInfo.argtypes = (
            wintypes.DWORD,
            ctypes.POINTER(_GuiThreadInfo),
        )
        user32.GetGUIThreadInfo.restype = wintypes.BOOL
        thread_id = user32.GetWindowThreadProcessId(foreground_window, None)
        info = _GuiThreadInfo(size=ctypes.sizeof(_GuiThreadInfo))
        if thread_id and user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
            return info.focused_window or foreground_window
        return foreground_window

    @staticmethod
    def _read_clipboard_text() -> str:
        text = QGuiApplication.clipboard().text().strip()
        if text:
            return text
        return SelectionReader._read_native_clipboard_text().strip()

    @staticmethod
    def _read_native_clipboard_text() -> str:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.IsClipboardFormatAvailable.argtypes = (wintypes.UINT,)
        user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
        user32.OpenClipboard.argtypes = (wintypes.HWND,)
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = (wintypes.UINT,)
        user32.GetClipboardData.restype = wintypes.HANDLE
        kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)

        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return ""
        if not user32.OpenClipboard(None):
            return ""
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                return ""
            try:
                return ctypes.wstring_at(pointer)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    @staticmethod
    def _trigger_keys_are_down() -> bool:
        user32 = ctypes.windll.user32
        return any(
            user32.GetAsyncKeyState(key) & 0x8000
            for key in (VK_CONTROL, VK_MENU, VK_SHIFT, VK_C)
        )

    def _restore_source_focus(self) -> None:
        if self._foreground_window:
            user32 = ctypes.windll.user32
            user32.IsWindow.argtypes = (wintypes.HWND,)
            user32.IsWindow.restype = wintypes.BOOL
            user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
            user32.SetForegroundWindow.restype = wintypes.BOOL
            if user32.IsWindow(self._foreground_window):
                user32.SetForegroundWindow(self._foreground_window)

    def _send_copy(self) -> bool:
        if self._copy_attempts == 1:
            return self._send_with_send_input(VK_C)
        if self._copy_attempts == 2:
            return self._send_with_wm_copy()
        if self._copy_attempts == 3:
            return self._send_with_keybd_event(VK_C)
        return self._send_with_send_input(VK_INSERT)

    def _send_with_wm_copy(self) -> bool:
        target = self._focused_window or self._foreground_window
        if not target:
            return False
        user32 = ctypes.windll.user32
        user32.IsWindow.argtypes = (wintypes.HWND,)
        user32.IsWindow.restype = wintypes.BOOL
        user32.SendMessageTimeoutW.argtypes = (
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
            wintypes.UINT,
            wintypes.UINT,
            ctypes.POINTER(ctypes.c_size_t),
        )
        user32.SendMessageTimeoutW.restype = wintypes.LPARAM
        if not user32.IsWindow(target):
            return False
        result = ctypes.c_size_t()
        sent = user32.SendMessageTimeoutW(
            target,
            WM_COPY,
            0,
            0,
            SMTO_ABORTIFHUNG,
            300,
            ctypes.byref(result),
        )
        return bool(sent)

    @staticmethod
    def _send_with_send_input(key: int) -> bool:
        user32 = ctypes.windll.user32
        user32.SendInput.argtypes = (
            wintypes.UINT,
            ctypes.POINTER(_Input),
            ctypes.c_int,
        )
        user32.SendInput.restype = wintypes.UINT
        inputs = (_Input * 4)(
            _keyboard_input(VK_CONTROL),
            _keyboard_input(key),
            _keyboard_input(key, KEYEVENTF_KEYUP),
            _keyboard_input(VK_CONTROL, KEYEVENTF_KEYUP),
        )
        sent = user32.SendInput(len(inputs), inputs, ctypes.sizeof(_Input))
        return sent == len(inputs)

    @staticmethod
    def _send_with_keybd_event(key: int) -> bool:
        user32 = ctypes.windll.user32
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(key, 0, 0, 0)
        user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        return True
