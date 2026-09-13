from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from lamarck_translator.main import TranslatorApp
from lamarck_translator.worker import LoginStatusWorker


def _controller(**attrs) -> TranslatorApp:
    """A TranslatorApp with only the collaborators these tests touch."""
    app = TranslatorApp.__new__(TranslatorApp)
    app._busy = False
    app.messages = []
    app.started = []
    app.tray = SimpleNamespace(showMessage=lambda *args: app.messages.append(args))
    app.thread_pool = SimpleNamespace(start=app.started.append)
    for key, value in attrs.items():
        setattr(app, key, value)
    return app


def test_start_worker_refuses_a_second_job_and_deletes_its_screenshot(tmp_path: Path) -> None:
    # Alt+S opens the overlay, Alt+C starts a translation, then the overlay is
    # released: the image path must not start a second worker behind the first.
    controller = _controller()
    controller._busy = True
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"not really a png")

    controller._start_worker("prompt", shot, "Reading image…", source_text=None)

    assert controller.started == []
    assert not shot.exists(), "the worker that deletes the temp file never runs"
    assert controller.messages


def test_check_codex_status_does_not_block_the_ui_thread() -> None:
    QApplication.instance() or QApplication([])
    inline_calls = []
    labels = []
    controller = _controller(
        backend=SimpleNamespace(login_status=lambda: inline_calls.append(1) or "ok"),
        result_window=SimpleNamespace(show_loading=labels.append),
    )

    controller.check_codex_status()

    assert inline_calls == [], "login_status must run on the pool, not inline"
    assert len(controller.started) == 1
    assert isinstance(controller.started[0], LoginStatusWorker)
    assert labels == ["Checking Codex…"]
    assert controller._busy is True


def test_check_codex_status_waits_for_a_running_translation() -> None:
    QApplication.instance() or QApplication([])
    controller = _controller(backend=SimpleNamespace(login_status=lambda: "ok"))
    controller._busy = True

    controller.check_codex_status()

    assert controller.started == []
    assert controller.messages
