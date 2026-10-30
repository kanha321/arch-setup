from __future__ import annotations

import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class LockHeld(RuntimeError):
    pass


@contextmanager
def switch_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LockHeld("another switch is in progress") from None
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
