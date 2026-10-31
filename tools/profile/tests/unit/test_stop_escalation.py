from __future__ import annotations

import json
from pathlib import Path

from profile_switcher.cli import main
from profile_switcher.executor import Executor
from profile_switcher.manifest import parse_manifest
from profile_switcher.planner import Step, make_plan
from profile_switcher.runner import Result

ENV = {"HYPRLAND_INSTANCE_SIGNATURE": "x", "DBUS_SESSION_BUS_ADDRESS": "y", "XDG_SESSION_ID": "1"}


def sh(cmd):
    return ["sh", "-c", cmd]


def mf(name, extra=""):
    head = [
        f'name = "{name}"',
        'compositor = "hyprland"',
        f'start = "start-{name}"',
        f'stop = "stop-{name}"',
    ]
    return parse_manifest("\n".join(head) + "\n" + extra + "\n")


def mk(tmp_path, runner, clock, old=""):
    ms = {"old": mf("old", old), "new": mf("new")}
    ex = Executor(runner, tmp_path / "state.json", tmp_path / "dots", tmp_path / "home", ms, clock)
    return ex, ms


class Wedged:
    """The stop command times out; the process dies only on the signal named in dies_on."""

    def __init__(self, dies_on):
        self.calls = []
        self.dies_on = dies_on
        self.dead = False

    def run(self, cmd, timeout=10):
        self.calls.append(list(cmd))
        if cmd == sh("stop-old"):
            return Result(124, "", "timeout")
        if cmd[0] == "pkill":
            self.dead = self.dead or cmd[1] == self.dies_on
            return Result(0)
        if cmd[0] == "pgrep":
            return Result(1 if self.dead else 0)
        return Result(0)


def test_timed_out_stop_escalates_to_term(tmp_path, clock):
    r = Wedged("-TERM")
    ex, _ = mk(tmp_path, r, clock, 'process = "old-proc"')
    assert ex.run_step(Step("stop", "old")) is True
    assert ["pkill", "-TERM", "-f", "old-proc"] in r.calls
    assert ["pkill", "-KILL", "-f", "old-proc"] not in r.calls


def test_stop_escalates_to_kill_when_term_is_ignored(tmp_path, clock):
    r = Wedged("-KILL")
    ex, _ = mk(tmp_path, r, clock, 'process = "old-proc"')
    assert ex.run_step(Step("stop", "old")) is True
    term = r.calls.index(["pkill", "-TERM", "-f", "old-proc"])
    kill = r.calls.index(["pkill", "-KILL", "-f", "old-proc"])
    assert term < kill


def test_failed_stop_without_a_process_name_still_fails(tmp_path, clock):
    r = Wedged("-TERM")
    ex, _ = mk(tmp_path, r, clock)
    assert ex.run_step(Step("stop", "old")) is False
    assert not any(c[0] == "pkill" for c in r.calls)


def test_last_failure_names_the_failed_step(tmp_path, runner, clock):
    ex, ms = mk(tmp_path, runner, clock)
    runner.set(sh("start-new"), Result(1))
    assert ex.execute(make_plan(ms["old"], ms["new"]), "old", "new") == "rolled_back"
    assert ex.last_failure == "start new"


def test_last_failure_is_cleared_by_a_successful_switch(tmp_path, runner, clock):
    ex, ms = mk(tmp_path, runner, clock)
    ex.last_failure = "stale"
    assert ex.execute(make_plan(ms["old"], ms["new"]), "old", "new") == "ok"
    assert ex.last_failure is None


def test_switch_prints_the_failed_step(tmp_path, runner, capsys):
    dots = tmp_path / "dots"
    for n in ("bare", "other"):
        d = dots / "profiles" / n
        d.mkdir(parents=True)
        head = f'name = "{n}"\ncompositor = "hyprland"\n'
        (d / "profile.toml").write_text(head + f'start = "start-{n}"\nstop = "stop-{n}"\n')
    env = {**ENV, "HOME": str(tmp_path / "home"), "DOTFILES": str(dots)}
    env |= {"XDG_RUNTIME_DIR": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state")}
    state = Path(env["XDG_STATE_HOME"]) / "profile-switcher" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"state": "idle", "active": "bare"}))
    runner.set(sh("start-other"), Result(1))
    assert main(["switch", "other"], env=env, runner=runner) == 1
    out = capsys.readouterr().out
    assert "rolled_back" in out
    assert "failed step: start other" in out
