import json

import pytest

from profile_switcher.executor import Executor
from profile_switcher.manifest import parse_manifest


def mk(n):
    return parse_manifest(
        f'name = "{n}"\ncompositor = "hyprland"\nstart = "start-{n}"\nstop = "stop-{n}"\n'
    )


def make(tmp_path, runner, state):
    journal = tmp_path / "state.json"
    if state:
        journal.write_text(json.dumps(state))
    ms = {"a": mk("a"), "b": mk("b")}
    return Executor(runner, journal, tmp_path / "dots", tmp_path / "home", ms), journal


@pytest.mark.parametrize("state", [None, {"state": "idle", "active": "a"}])
def test_nothing_to_repair(tmp_path, runner, state):
    ex, _ = make(tmp_path, runner, state)
    assert ex.repair() == "idle" and runner.calls == []


@pytest.mark.parametrize("kind", ["switching", "rolling_back", "broken"])
def test_interrupted_switch_rolls_back_to_old(tmp_path, runner, kind):
    ex, journal = make(tmp_path, runner, {"state": kind, "from": "a", "to": "b", "step": 3})
    assert ex.repair() == "repaired"
    assert json.loads(journal.read_text()) == {"state": "idle", "active": "a"}
    assert runner.calls[0] == ["sh", "-c", "stop-b"]
    assert runner.calls[-1] == ["sh", "-c", "start-a"]
