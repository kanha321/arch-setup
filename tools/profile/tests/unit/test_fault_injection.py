import json
from pathlib import Path

import pytest

from profile_switcher.executor import Executor
from profile_switcher.manifest import parse_manifest
from profile_switcher.planner import make_plan
from profile_switcher.runner import Result


def mk(n):
    return parse_manifest(
        f'name = "{n}"\ncompositor = "hyprland"\n'
        f'start = "start-{n}"\nstop = "stop-{n}"\nhealth = "health-{n}"\nstow = ["p"]\n'
    )


class World:
    def __init__(self, fail_at=None):
        self.stowed, self.running = {"a"}, {"a"}
        self.n, self.fail_at = 0, fail_at

    def run(self, cmd, timeout=10):
        i, self.n = self.n, self.n + 1
        if i == self.fail_at:
            return Result(1, "", "boom")
        if cmd[0] == "stow":
            name = Path(cmd[cmd.index("-d") + 1]).parent.name
            if "-D" in cmd:
                self.stowed.discard(name)
            else:
                self.stowed.add(name)
        elif cmd[:2] == ["sh", "-c"]:
            verb, _, name = cmd[2].partition("-")
            if verb == "start":
                self.running.add(name)
            elif verb == "stop":
                self.running.discard(name)
        return Result(0)


def run_switch(tmp_path, fail_at):
    world = World(fail_at)
    journal = tmp_path / "state.json"
    ms = {"a": mk("a"), "b": mk("b")}
    ex = Executor(world, journal, tmp_path / "dots", tmp_path / "home", ms)
    result = ex.execute(make_plan(ms["a"], ms["b"]), "a", "b")
    return result, world, json.loads(journal.read_text())


def test_success_ends_on_b(tmp_path):
    result, world, j = run_switch(tmp_path, None)
    assert result == "ok" and j == {"state": "idle", "active": "b"}
    assert world.stowed == {"b"} and world.running == {"b"}


@pytest.mark.parametrize("fail_at", range(6))
def test_any_single_failure_ends_fully_on_a(tmp_path, fail_at):
    result, world, j = run_switch(tmp_path, fail_at)
    assert result == "rolled_back"
    assert world.stowed == {"a"} and world.running == {"a"}
    assert j == {"state": "idle", "active": "a"}


class DoubleFault(World):
    def __init__(self, second):
        super().__init__(5)
        self.second = second

    def run(self, cmd, timeout=10):
        if self.n == self.second:
            self.n += 1
            return Result(1, "", "boom2")
        return super().run(cmd, timeout)


@pytest.mark.parametrize("second", range(6, 11))
def test_failure_during_rollback_marks_journal_broken(tmp_path, second):
    world = DoubleFault(second)
    journal = tmp_path / "state.json"
    ms = {"a": mk("a"), "b": mk("b")}
    ex = Executor(world, journal, tmp_path / "dots", tmp_path / "home", ms)
    result = ex.execute(make_plan(ms["a"], ms["b"]), "a", "b")
    assert result == "failed"
    assert json.loads(journal.read_text()) == {"state": "broken", "from": "a", "to": "b"}
