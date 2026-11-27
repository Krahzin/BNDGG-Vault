"""Background task helper so the Argon2 KDF never freezes the UI."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Signals(QObject):
    done = Signal(object)
    error = Signal(str)


class Task(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = _Signals()
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D401 - QRunnable API
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            self.signals.error.emit(str(exc))
        else:
            self.signals.done.emit(result)


def run_async(fn: Callable[..., Any], on_done: Callable[[Any], None],
              on_error: Callable[[str], None], *args: Any, **kwargs: Any) -> Task:
    task = Task(fn, *args, **kwargs)
    task.signals.done.connect(on_done)
    task.signals.error.connect(on_error)
    QThreadPool.globalInstance().start(task)
    return task
