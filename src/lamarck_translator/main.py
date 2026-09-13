from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .backend import CodexCLIBackend
from .clipboard import SelectionReader
from .config import AppConfig, config_path, load_config
from .hotkeys import HotkeyManager
from .identity import load_codex_identity
from .prompts import build_image_prompt, build_text_prompt
from .result_window import ResultWindow
from .screenshot import ScreenshotOverlay
from .worker import LoginStatusWorker, TranslationWorker


TEXT_HOTKEY_ID = 1
SCREENSHOT_HOTKEY_ID = 2


def resource_path(relative_path: str) -> Path:
    bundled_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return bundled_root / relative_path


class TranslatorApp:
    def __init__(self, qt_app: QApplication, config: AppConfig) -> None:
        self.qt_app = qt_app
        self.config = config
        self.backend = CodexCLIBackend(
            model=config.model,
            reasoning_effort=config.reasoning_effort,
            timeout_seconds=config.timeout_seconds,
        )
        self.thread_pool = QThreadPool.globalInstance()
        app_icon = self._tray_icon()
        self.result_window = ResultWindow()
        self.result_window.setWindowIcon(app_icon)
        self.result_window.set_brand_icon(app_icon)
        self.result_window.set_backend_info(config.model, config.reasoning_effort)
        self._refresh_account_identity()
        self.selection_reader = SelectionReader(
            wait_ms=config.clipboard_wait_ms,
            restore_clipboard=config.restore_clipboard,
        )
        self.screenshot_overlay = ScreenshotOverlay()
        self.hotkeys = HotkeyManager()
        self._last_prompt = ""
        self._last_image: Path | None = None
        self._last_source_text: str | None = None
        self._active_source_text: str | None = None
        self._active_worker: TranslationWorker | None = None
        self._busy = False

        self.selection_reader.captured.connect(self._translate_text)
        self.selection_reader.failed.connect(self.result_window.show_error)
        self.screenshot_overlay.captured.connect(self._translate_image)
        self.result_window.retry_requested.connect(self._retry)
        self.hotkeys.activated.connect(self._on_hotkey)
        qt_app.installNativeEventFilter(self.hotkeys)

        self.tray = QSystemTrayIcon(app_icon, qt_app)
        self.tray.setToolTip("Lamarck Translator")
        self.tray.setContextMenu(self._build_menu())
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()
        qt_app.aboutToQuit.connect(self.hotkeys.unregister_all)

        try:
            self.hotkeys.register(TEXT_HOTKEY_ID, config.text_hotkey)
            self.hotkeys.register(SCREENSHOT_HOTKEY_ID, config.screenshot_hotkey)
        except Exception as exc:
            self.hotkeys.unregister_all()
            QTimer.singleShot(0, lambda message=str(exc): self._fatal(message))

    def _tray_icon(self) -> QIcon:
        icon = QIcon(str(resource_path("assets/LamarckTranslator-icon.png")))
        if not icon.isNull():
            return icon

        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#315EFB"))
        painter.drawRoundedRect(3, 3, 58, 58, 15, 15)
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "L")
        painter.end()
        return QIcon(pixmap)

    def _build_menu(self) -> QMenu:
        menu = QMenu()
        text_action = QAction(f"Translate selection ({self.config.text_hotkey})", menu)
        text_action.triggered.connect(self.capture_selection)
        screenshot_action = QAction(
            f"Translate screenshot ({self.config.screenshot_hotkey})", menu
        )
        screenshot_action.triggered.connect(self.capture_screenshot)
        status_action = QAction("Check Codex login status", menu)
        status_action.triggered.connect(self.check_codex_status)
        config_action = QAction("Show configuration file location", menu)
        config_action.triggered.connect(self.show_config_path)
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.qt_app.quit)
        menu.addAction(text_action)
        menu.addAction(screenshot_action)
        menu.addSeparator()
        menu.addAction(status_action)
        menu.addAction(config_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        return menu

    def _on_hotkey(self, hotkey_id: int) -> None:
        if hotkey_id == TEXT_HOTKEY_ID:
            self.capture_selection()
        elif hotkey_id == SCREENSHOT_HOTKEY_ID:
            self.capture_screenshot()

    def capture_selection(self) -> None:
        if self._busy:
            self.tray.showMessage("Lamarck Translator", "A translation is already in progress.")
            return
        self.selection_reader.capture()

    def capture_screenshot(self) -> None:
        if self._busy:
            self.tray.showMessage("Lamarck Translator", "A translation is already in progress.")
            return
        self.screenshot_overlay.begin()

    def _translate_text(self, text: str) -> None:
        prompt = build_text_prompt(self.config.prompt, text)
        self._start_worker(prompt, None, "Translating…", source_text=text)

    def _translate_image(self, path: Path) -> None:
        prompt = build_image_prompt(self.config.prompt)
        self._start_worker(prompt, path, "Reading image…", source_text=None)

    def _start_worker(
        self,
        prompt: str,
        image: Path | None,
        label: str,
        source_text: str | None,
    ) -> None:
        # The hotkey entry points check this too, but a screenshot selection
        # started before a text translation can still land here mid-flight.
        if self._busy:
            if image is not None:
                # Nothing will run the worker that would have deleted it.
                image.unlink(missing_ok=True)
            self.tray.showMessage("Lamarck Translator", "A translation is already in progress.")
            return
        self._busy = True
        self._last_prompt = prompt
        self._last_image = image
        self._last_source_text = source_text
        self._active_source_text = source_text
        self._refresh_account_identity()
        self.result_window.show_loading(label)
        worker = TranslationWorker(self.backend, prompt, image)
        self._active_worker = worker
        worker.signals.succeeded.connect(self._translation_succeeded)
        worker.signals.failed.connect(self._translation_failed)
        worker.signals.finished.connect(self._worker_finished)
        self.thread_pool.start(worker)

    def _translation_succeeded(self, text: str) -> None:
        # Release the UI immediately. Keeping the worker referenced until its
        # finished signal prevents PySide from dropping the final state update.
        self._busy = False
        # Both selection and screenshot translation use the same linked,
        # bilingual sentence-card view. For screenshots, Codex supplies the
        # recognized English source inside the structured response.
        self.result_window.show_bilingual_result(self._active_source_text, text)

    def _translation_failed(self, message: str) -> None:
        self._busy = False
        self.result_window.show_error(message)

    def _worker_finished(self) -> None:
        self._busy = False
        self._last_image = None
        self._active_source_text = None
        self._active_worker = None

    def _retry(self) -> None:
        if self._busy:
            return
        if not self._last_prompt:
            self.result_window.show_error("There is no translation to retry yet.")
            return
        if "所附截图" in self._last_prompt:
            self.result_window.show_error("The temporary screenshot has been deleted. Please capture the area again.")
            return
        self._start_worker(
            self._last_prompt,
            None,
            "Retrying…",
            source_text=self._last_source_text,
        )

    def check_codex_status(self) -> None:
        if self._busy:
            self.tray.showMessage("Lamarck Translator", "A translation is already in progress.")
            return
        self._busy = True
        self.result_window.show_loading("Checking Codex…")
        worker = LoginStatusWorker(self.backend)
        self._active_worker = worker
        worker.signals.succeeded.connect(self._status_succeeded)
        worker.signals.failed.connect(self._translation_failed)
        worker.signals.finished.connect(self._worker_finished)
        self.thread_pool.start(worker)

    def _status_succeeded(self, status: str) -> None:
        self._busy = False
        identity = load_codex_identity()
        self.result_window.set_account_identity(identity.display_text)
        self.result_window.show_result(f"{status}\n{identity.display_text}")

    def _refresh_account_identity(self) -> None:
        self.result_window.set_account_identity(load_codex_identity().display_text)

    def show_config_path(self) -> None:
        self.result_window.show_result(
            f"Configuration file:\n{config_path()}\n\nQuit and restart the app after making changes."
        )

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.capture_selection()

    def _fatal(self, message: str) -> None:
        QMessageBox.critical(None, "Lamarck Translator", message)
        self.qt_app.quit()


def main() -> int:
    if sys.platform != "win32":
        print("Lamarck Translator currently supports Windows only.", file=sys.stderr)
        return 1
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Lamarck Translator")
    qt_app.setQuitOnLastWindowClosed(False)
    try:
        config = load_config()
    except Exception as exc:
        QMessageBox.critical(None, "Configuration error", f"Unable to read the configuration file:\n{exc}")
        return 1
    controller = TranslatorApp(qt_app, config)
    qt_app._translator_controller = controller  # keep the controller alive
    controller.result_window.show_welcome()
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
