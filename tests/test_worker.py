from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from lamarck_translator.worker import LoginStatusWorker


def test_login_status_worker_reports_the_backend_answer() -> None:
    QApplication.instance() or QApplication([])
    worker = LoginStatusWorker(SimpleNamespace(login_status=lambda: "Signed in"))
    succeeded: list[str] = []
    finished: list[int] = []
    worker.signals.succeeded.connect(succeeded.append)
    worker.signals.finished.connect(lambda: finished.append(1))

    worker.run()

    assert succeeded == ["Signed in"]
    assert finished == [1]


def test_login_status_worker_surfaces_failures_instead_of_raising() -> None:
    QApplication.instance() or QApplication([])

    def boom() -> str:
        raise RuntimeError("codex is not logged in")

    worker = LoginStatusWorker(SimpleNamespace(login_status=boom))
    failed: list[str] = []
    finished: list[int] = []
    worker.signals.failed.connect(failed.append)
    worker.signals.finished.connect(lambda: finished.append(1))

    worker.run()

    assert failed == ["codex is not logged in"]
    assert finished == [1]
