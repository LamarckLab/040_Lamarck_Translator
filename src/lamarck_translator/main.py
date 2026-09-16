from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .backend import CodexCLIBackend
from .clipboard import SelectionReader
from .config import AppConfig, config_path, load_config, save_config
from .history import SCREENSHOT, SELECTION
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
        self.result_window.set_pair_font_size(config.pair_font_size)
        self.result_window.set_theme(config.theme)
        self._refresh_account_identity()
        self.selection_reader = SelectionReader(
            wait_ms=config.clipboard_wait_ms,
            restore_clipboard=config.restore_clipboard,
        )
        self.screenshot_overlay = ScreenshotOverlay()
        self.hotkeys = HotkeyManager()
        # One entry per translation still in flight, keyed by job id. PySide
        # drops a QRunnable's queued signals if nothing holds it, so the worker
        # is kept here until its finished signal lands.
        self._workers: dict[int, TranslationWorker] = {}
        self._status_worker: LoginStatusWorker | None = None
        self._busy = False

        self.selection_reader.captured.connect(self._translate_text)
        self.selection_reader.failed.connect(self.result_window.show_error)
        self.screenshot_overlay.captured.connect(self._translate_image)
        self.result_window.retry_requested.connect(self._retry)
        self.result_window.pair_font_size_changed.connect(self._remember_pair_font_size)
        self.result_window.theme_changed.connect(self._remember_theme)
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
        self._start_worker(SELECTION, prompt, None, "Translating\u2026", source_text=text)

    def _translate_image(self, path: Path) -> None:
        prompt = build_image_prompt(self.config.prompt)
        self._start_worker(SCREENSHOT, prompt, path, "Reading image\u2026", source_text=None)

    def _start_worker(
        self,
        mode: str,
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
        self._refresh_account_identity()
        job = self.result_window.add_job(mode, prompt, label, source_text, image)
        worker = TranslationWorker(self.backend, prompt, image)
        self._workers[job.job_id] = worker
        job_id = job.job_id
        worker.signals.succeeded.connect(
            lambda text, i=job_id: self.result_window.complete_job(i, text)
        )
        worker.signals.failed.connect(
            lambda message, i=job_id: self.result_window.fail_job(i, message)
        )
        worker.signals.finished.connect(lambda i=job_id: self._worker_finished(i))
        self.thread_pool.start(worker)

    def _worker_finished(self, job_id: int) -> None:
        self._busy = False
        self._workers.pop(job_id, None)

    def _retry(self) -> None:
        if self._busy:
            return
        job = self.result_window.active_job()
        if job is None:
            self.result_window.show_error("There is no translation to retry yet.")
            return
        if not job.can_retry:
            self.result_window.show_error(
                "The temporary screenshot has been deleted. Please capture the area again."
            )
            return
        self._start_worker(
            job.mode,
            job.prompt,
            None,
            "Retrying\u2026",
            source_text=job.source_text,
        )

    def check_codex_status(self) -> None:
        if self._busy:
            self.tray.showMessage("Lamarck Translator", "A translation is already in progress.")
            return
        self._busy = True
        self.result_window.show_loading("Checking Codex…")
        # A status check is not a translation, so it stays out of the history.
        worker = LoginStatusWorker(self.backend)
        self._status_worker = worker
        worker.signals.succeeded.connect(self._status_succeeded)
        worker.signals.failed.connect(self.result_window.show_error)
        worker.signals.finished.connect(self._status_finished)
        self.thread_pool.start(worker)

    def _status_finished(self) -> None:
        self._busy = False
        self._status_worker = None

    def _status_succeeded(self, status: str) -> None:
        self._busy = False
        identity = load_codex_identity()
        self.result_window.set_account_identity(identity.display_text)
        self.result_window.show_result(f"{status}\n{identity.display_text}")

    def _refresh_account_identity(self) -> None:
        self.result_window.set_account_identity(load_codex_identity().display_text)

    def _remember_pair_font_size(self, font_px: int) -> None:
        """Keep a Ctrl+wheel zoom across restarts."""
        if font_px == self.config.pair_font_size:
            return
        self.config.pair_font_size = font_px
        try:
            save_config(self.config)
        except OSError:
            pass  # zooming must not interrupt reading over a transient write error

    def _remember_theme(self, theme: str) -> None:
        if theme == self.config.theme:
            return
        self.config.theme = theme
        try:
            save_config(self.config)
        except OSError:
            pass  # a transient write error must not undo the switch on screen

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
