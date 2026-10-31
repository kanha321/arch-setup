from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

from profile_switcher.clock import Clock, RealClock
from profile_switcher.manifest import Manifest
from profile_switcher.planner import Step, make_plan
from profile_switcher.runner import Runner

DBUS_WAIT = 5.0
KILL_WAIT = 2.0
POLL = 0.2
RESUME_WAIT = 10.0
START_RETRY = 15.0


class Executor:
    def __init__(
        self,
        runner: Runner,
        journal: Path,
        dotfiles: Path,
        home: Path,
        manifests: dict[str, Manifest],
        clock: Clock | None = None,
    ):
        self.runner = runner
        self.journal = journal
        self.dotfiles = dotfiles
        self.home = home
        self.manifests = manifests
        self.clock = clock or RealClock()
        self.last_failure: str | None = None

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

    def stow(self, name: str) -> bool:
        cmd = self._stow(name, delete=False)
        return cmd is None or self.runner.run(cmd).returncode == 0

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

    def _poll(self, done: Callable[[], bool], timeout: float) -> bool:
        deadline = self.clock.now() + timeout
        while not done():
            if self.clock.now() >= deadline:
                return False
            self.clock.sleep(POLL)
        return True

    def _gone(self, m: Manifest) -> bool:
        return self.runner.run(["pgrep", "-f", m.process or ""]).returncode != 0

    def _stop(self, m: Manifest) -> bool:
        ok = self.runner.run(["sh", "-c", m.stop], m.stop_timeout).returncode == 0
        if not m.process:
            return ok
        if ok:
            gone = self._poll(lambda: self._gone(m), m.stop_timeout)
        else:
            # a failed or timed-out stop command: fine if the process is gone, else escalate
            gone = self._gone(m)
        if gone:
            return True
        for sig in ("TERM", "KILL"):
            self.runner.run(["pkill", f"-{sig}", "-f", m.process])
            if self._poll(lambda: self._gone(m), KILL_WAIT):
                return True
        return False

    def _wait_dbus(self, names: list[str]) -> bool:
        if not names:
            return True

        def free() -> bool:
            out = self.runner.run(["busctl", "--user", "list", "--no-legend"]).stdout
            held = {line.split()[0] for line in out.splitlines() if line.strip()}
            return not held & set(names)

        return self._poll(free, DBUS_WAIT)

    def _healthy(self, m: Manifest) -> bool:
        probe = ["sh", "-c", m.health or "true"]
        per_try = m.health_timeout
        return self._poll(lambda: self.runner.run(probe, per_try).returncode == 0, m.health_timeout)

    def resume(self, name: str) -> str:
        """Bring the recorded profile's shell up at login; never touches the journal."""
        m = self.manifests[name]
        if not m.process:
            return "nothing to start"
        # the profile's own config may autostart the shell, so give it time to appear first
        if self._poll(lambda: not self._gone(m), RESUME_WAIT):
            return "already running"
        start = ["sh", "-c", m.start]
        # retry: a start can fail early in the session (e.g. the graphical target is not up yet)
        if not self._poll(lambda: self.runner.run(start, 10).returncode == 0, START_RETRY):
            return "failed: the start command never succeeded"
        return "started" if self._healthy(m) else "started but not healthy"

    def run_step(self, step: Step) -> bool:
        m = self.manifests[step.profile]
        if step.kind == "stop":
            return self._stop(m)
        if step.kind == "wait_dbus":
            names = list(m.dbus_names)
            if step.arg:
                names += self.manifests[step.arg].dbus_names
            return self._wait_dbus(names)
        if step.kind == "health":
            return self._healthy(m)
        cmd = self._command(step)
        if cmd is None:
            return True
        return self.runner.run(cmd, 10).returncode == 0

    def _rollback(self, old: str, new: str, failed_kind: str = "") -> bool:
        if failed_kind in ("preflight", "stop"):
            self._write_journal({"state": "idle", "active": old})
            return True
        self._write_journal({"state": "rolling_back", "from": old, "to": new})
        steps = [
            Step("stop", new),
            Step("wait_dbus", new),
            Step("unstow", new),
            Step("stow", old),
            Step("reload", old),
        ]
        if "post_stow" in self.manifests[old].hooks:
            steps.append(Step("hook", old, "post_stow"))
        steps.append(Step("start", old))
        # the D-Bus wait is best effort: starting the old shell beats leaving none
        results = [self.run_step(s) or s.kind == "wait_dbus" for s in steps]
        ok = all(results)
        if ok:
            self._write_journal({"state": "idle", "active": old})
        else:
            self._write_journal({"state": "broken", "from": old, "to": new})
        return ok

    def execute(self, plan: list[Step], old: str, new: str) -> str:
        self.last_failure = None
        for i, step in enumerate(plan):
            if step.kind == "commit":
                self._write_journal({"state": "idle", "active": new})
                continue
            self._write_journal({"state": "switching", "from": old, "to": new, "step": i})
            if not self.run_step(step):
                self.last_failure = f"{step.kind} {step.profile}"
                return "rolled_back" if self._rollback(old, new, step.kind) else "failed"
        return "ok"

    def _crashed_at_health(self, state: dict) -> bool:
        if state.get("state") != "switching":
            return False
        plan = make_plan(self.manifests[state["from"]], self.manifests[state["to"]])
        i = state.get("step", -1)
        return 0 <= i < len(plan) and plan[i].kind == "health"

    def repair(self) -> str:
        if not self.journal.exists():
            return "idle"
        state = json.loads(self.journal.read_text())
        if state["state"] == "idle":
            return "idle"
        old, new = state["from"], state["to"]
        if self._crashed_at_health(state) and self.run_step(Step("health", new)):
            self._write_journal({"state": "idle", "active": new})
            return "completed"
        return "repaired" if self._rollback(old, new) else "failed"
