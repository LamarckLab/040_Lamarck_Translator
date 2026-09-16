from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from .translation_pairs import TranslationPair


# How many translations stay reachable. The window keeps one page of cards per
# job so marks and scroll position survive a switch, so this also caps how much
# is held in memory. Nothing is written to disk: a translation lives only as
# long as the window does.
MAX_HISTORY = 5

# How many translations may be in flight at once. Each one is a separate
# codex process, and the history only holds MAX_HISTORY anyway, so there is
# nothing to gain from letting them pile up without limit.
MAX_IN_FLIGHT = 3

SELECTION = "selection"
SCREENSHOT = "screenshot"

RUNNING = "running"
DONE = "done"
FAILED = "failed"


@dataclass(slots=True)
class TranslationJob:
    """One translation, from the moment its hotkey fires until it is evicted."""

    job_id: int
    mode: str
    prompt: str
    label: str
    source_text: str | None = None
    image_path: Path | None = None
    status: str = RUNNING
    response: str = ""
    error: str = ""
    pairs: list[TranslationPair] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    # False while a finished translation has not been looked at yet, which is
    # what puts the unread dot on its tab.
    seen: bool = True

    @property
    def is_running(self) -> bool:
        return self.status == RUNNING

    @property
    def is_screenshot(self) -> bool:
        return self.mode == SCREENSHOT

    @property
    def can_retry(self) -> bool:
        # A screenshot is deleted as soon as its translation returns, so there
        # is nothing left to send a second time.
        return not self.is_screenshot and not self.is_running

    def started_label(self) -> str:
        """Clock time is how a reader recalls which translation was which."""
        return time.strftime("%H:%M", time.localtime(self.started_at))

    def preview(self, width: int = 22) -> str:
        """Short label for the tab: enough to tell one translation from another."""
        if self.is_screenshot:
            return "Screenshot"
        text = " ".join((self.source_text or "").split())
        if not text:
            return "Selection"
        return text if len(text) <= width else text[: width - 1].rstrip() + "…"


class History:
    """The last MAX_HISTORY translations, newest last, with one of them active."""

    def __init__(self, limit: int = MAX_HISTORY) -> None:
        self._limit = limit
        self._jobs: list[TranslationJob] = []
        self._active_id: int | None = None
        self._next_id = 1

    def __len__(self) -> int:
        return len(self._jobs)

    @property
    def jobs(self) -> list[TranslationJob]:
        return list(self._jobs)

    def add(
        self,
        mode: str,
        prompt: str,
        label: str,
        source_text: str | None = None,
        image_path: Path | None = None,
    ) -> tuple[TranslationJob, list[TranslationJob]]:
        """Append a job, returning it along with any jobs pushed out."""
        job = TranslationJob(
            job_id=self._next_id,
            mode=mode,
            prompt=prompt,
            label=label,
            source_text=source_text,
            image_path=image_path,
        )
        self._next_id += 1
        self._jobs.append(job)

        evicted: list[TranslationJob] = []
        while len(self._jobs) > self._limit:
            evicted.append(self._jobs.pop(0))
        if self._active_id is not None and self.get(self._active_id) is None:
            self._active_id = None
        return job, evicted

    @property
    def running(self) -> list[TranslationJob]:
        return [job for job in self._jobs if job.is_running]

    def get(self, job_id: int | None) -> TranslationJob | None:
        if job_id is None:
            return None
        for job in self._jobs:
            if job.job_id == job_id:
                return job
        return None

    @property
    def active(self) -> TranslationJob | None:
        return self.get(self._active_id)

    def activate(self, job_id: int) -> TranslationJob | None:
        job = self.get(job_id)
        if job is not None:
            self._active_id = job_id
            job.seen = True
        return job

    def complete(self, job_id: int, response: str) -> TranslationJob | None:
        job = self.get(job_id)
        if job is None:
            return None
        job.status = DONE
        job.response = response
        job.seen = job.job_id == self._active_id
        return job

    def fail(self, job_id: int, error: str) -> TranslationJob | None:
        job = self.get(job_id)
        if job is None:
            return None
        job.status = FAILED
        job.error = error
        job.seen = job.job_id == self._active_id
        return job
