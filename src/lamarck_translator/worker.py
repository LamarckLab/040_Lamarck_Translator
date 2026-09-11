from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from .backend import CodexCLIBackend


class WorkerSignals(QObject):
    succeeded = Signal(str)
    failed = Signal(str)
    finished = Signal()


class TranslationWorker(QRunnable):
    def __init__(
        self,
        backend: CodexCLIBackend,
        prompt: str,
        image_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.backend = backend
        self.prompt = prompt
        self.image_path = image_path
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.backend.translate(self.prompt, self.image_path)
        except Exception as exc:  # surfaced in the result window
            self.signals.failed.emit(str(exc))
        else:
            self.signals.succeeded.emit(result)
        finally:
            if self.image_path is not None:
                self.image_path.unlink(missing_ok=True)
            self.signals.finished.emit()

