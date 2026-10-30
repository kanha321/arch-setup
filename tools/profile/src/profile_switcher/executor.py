from __future__ import annotations

import json
import os
from pathlib import Path

from profile_switcher.manifest import Manifest
from profile_switcher.planner import Step
from profile_switcher.runner import Runner


class Executor:
    def __init__(
        self,
        runner: Runner,
        journal: Path,
        dotfiles: Path,
        home: Path,
        manifests: dict[str, Manifest],
    ):
        self.runner = runner
        self.journal = journal
        self.dotfiles = dotfiles
        self.home = home
        self.manifests = manifests

    def _write_journal(self, data: dict) -> None:
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.journal.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        os.replace(tmp, self.journal)

    def _stow(self, name: str, delete: bool) -> list[str] | None:
        packages = self.manifests[name].stow
        if not packages:
            return None
        pkg_dir = str(self.dotfiles / "profiles" / name / "stow")
        flag = ["-D"] if delete else []
        return ["stow", "--no-folding", *flag, "-d", pkg_dir, "-t", str(self.home), *packages]

    def _command(self, step: Step) -> list[str] | None:
        m = self.manifests[step.profile]
        match step.kind:
            case "stop":
                return ["sh", "-c", m.stop]
            case "start":
                return ["sh", "-c", m.start]
            case "health":
                return ["sh", "-c", m.health or "true"]
            case "hook":
                return ["sh", "-c", m.hooks[step.arg or ""]]
            case "reload":
                return ["hyprctl", "reload"]
            case "unstow":
                return self._stow(step.profile, delete=True)
            case "stow":
                return self._stow(step.profile, delete=False)
        return None

    def _run_step(self, step: Step) -> bool:
        cmd = self._command(step)
        return cmd is None or self.runner.run(cmd).returncode == 0

    def _rollback(self, old: str, new: str) -> bool:
        self._write_journal({"state": "rolling_back", "from": old, "to": new})
        steps = (
            Step("stop", new),
            Step("unstow", new),
            Step("stow", old),
            Step("reload", old),
            Step("start", old),
        )
        results = [self._run_step(s) for s in steps]
        ok = all(results)
        if ok:
            self._write_journal({"state": "idle", "active": old})
        else:
            self._write_journal({"state": "broken", "from": old, "to": new})
        return ok

    def execute(self, plan: list[Step], old: str, new: str) -> str:
        for i, step in enumerate(plan):
            if step.kind == "commit":
                self._write_journal({"state": "idle", "active": new})
                continue
            self._write_journal({"state": "switching", "from": old, "to": new, "step": i})
            if not self._run_step(step):
                return "rolled_back" if self._rollback(old, new) else "failed"
        return "ok"
