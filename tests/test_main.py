from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from lamarck_translator.history import MAX_IN_FLIGHT, SCREENSHOT
from lamarck_translator.main import TranslatorApp
from lamarck_translator.worker import LoginStatusWorker


def _controller(running: int = 0, **attrs) -> TranslatorApp:
    """A TranslatorApp with only the collaborators these tests touch."""
    app = TranslatorApp.__new__(TranslatorApp)
    app._checking_status = False
    app.messages = []
    app.started = []
    app.tray = SimpleNamespace(showMessage=lambda *args: app.messages.append(args))
    app.thread_pool = SimpleNamespace(start=app.started.append)
    app.result_window = SimpleNamespace(
        running_jobs=lambda: running, show_loading=lambda *a: None, show_error=print
    )
    for key, value in attrs.items():
        setattr(app, key, value)
    return app


def test_start_worker_refuses_a_second_job_and_deletes_its_screenshot(tmp_path: Path) -> None:
    # Alt+S opens the overlay while the cap is free, but by the time the box is
    # released it is full: the image must not queue up behind the running ones.
    controller = _controller(running=MAX_IN_FLIGHT)
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"not really a png")

    controller._start_worker(
        SCREENSHOT, "prompt", shot, "Reading image\u2026", source_text=None
    )

    assert controller.started == []
    assert not shot.exists(), "the worker that deletes the temp file never runs"
    assert controller.messages


def test_check_codex_status_does_not_block_the_ui_thread() -> None:
    QApplication.instance() or QApplication([])
    inline_calls = []
    labels = []
    controller = _controller(
        backend=SimpleNamespace(login_status=lambda: inline_calls.append(1) or "ok"),
        result_window=SimpleNamespace(
            running_jobs=lambda: 0, show_loading=labels.append, show_error=print
        ),
    )

    controller.check_codex_status()

    assert inline_calls == [], "login_status must run on the pool, not inline"
    assert len(controller.started) == 1
    assert isinstance(controller.started[0], LoginStatusWorker)
    assert labels == ["Checking Codex…"]
    assert controller._checking_status is True


def test_check_codex_status_waits_for_a_running_translation() -> None:
    QApplication.instance() or QApplication([])
    controller = _controller(running=1, backend=SimpleNamespace(login_status=lambda: "ok"))

    controller.check_codex_status()

    assert controller.started == []
    assert controller.messages


def test_a_second_translation_starts_while_the_first_is_running(tmp_path: Path) -> None:
    # The point of the whole thing: reading one passage while the next is sent.
    controller = _controller(running=1)
    controller.backend = SimpleNamespace()
    controller.result_window.add_job = lambda *a, **k: SimpleNamespace(job_id=2)
    controller._workers = {}
    controller._refresh_account_identity = lambda: None

    controller._start_worker(SCREENSHOT, "prompt", None, "Reading image…", source_text=None)

    assert len(controller.started) == 1, "a running job must not block the next one"
    assert controller.messages == []


def test_the_cap_holds_and_says_so(tmp_path: Path) -> None:
    controller = _controller(running=MAX_IN_FLIGHT)
    controller.backend = SimpleNamespace()
    controller.result_window.add_job = lambda *a, **k: SimpleNamespace(job_id=9)

    controller._start_worker(SCREENSHOT, "prompt", None, "Reading image…", source_text=None)

    assert controller.started == []
    assert controller.messages, "the tray has to say why nothing happened"
    assert str(MAX_IN_FLIGHT) in controller.messages[0][1]


def test_a_status_check_and_a_translation_do_not_overlap() -> None:
    QApplication.instance() or QApplication([])
    controller = _controller(backend=SimpleNamespace(login_status=lambda: "ok"))
    controller.check_codex_status()
    assert controller._checking_status is True

    controller.backend = SimpleNamespace()
    controller.result_window.add_job = lambda *a, **k: SimpleNamespace(job_id=3)
    controller._start_worker(SCREENSHOT, "prompt", None, "Reading image…", source_text=None)

    assert len(controller.started) == 1, "only the status worker started"
    assert controller.messages


def test_the_screenshot_of_a_refused_job_is_deleted(tmp_path: Path) -> None:
    controller = _controller(running=MAX_IN_FLIGHT)
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"png")

    controller._start_worker(SCREENSHOT, "prompt", shot, "Reading image…", source_text=None)

    assert not shot.exists(), "nothing else will clean up the temp file"
