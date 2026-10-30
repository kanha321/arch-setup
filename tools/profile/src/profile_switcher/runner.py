from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Result:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class Runner(Protocol):
    def run(self, cmd: list[str], timeout: float = 10) -> Result: ...


class SubprocessRunner:
    def run(self, cmd: list[str], timeout: float = 10) -> Result:
        import subprocess

        try:
            p = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return Result(124, "", "timeout")
        except FileNotFoundError as e:
            return Result(127, "", str(e))
        return Result(p.returncode, p.stdout, p.stderr)
