from __future__ import annotations

import json
from pathlib import Path

from profile_switcher.cli import main
from profile_switcher.executor import Executor
from profile_switcher.lock import switch_lock
from profile_switcher.manifest import parse_manifest
from profile_switcher.runner import Result

ENV = {"HYPRLAND_INSTANCE_SIGNATURE": "x", "DBUS_SESSION_BUS_ADDRESS": "y", "XDG_SESSION_ID": "1"}
NEVER = 10**6


def sh(cmd):
    return ["sh", "-c", cmd]


def pgrep(name):
    return ("pgrep", "-f", f"proc-{name}")


class Script:
    """Fake runner: chosen commands fail for their first N calls, everything else succeeds."""

    def __init__(self, fail_first=None):
        self.calls = []
        self.fail_first = dict(fail_first or {})
        self.seen = {}

    def run(self, cmd, timeout=10):
        key = tuple(cmd)
        self.calls.append(list(cmd))
        self.seen[key] = self.seen.get(key, 0) + 1
        return Result(1 if self.seen[key] <= self.fail_first.get(key, 0) else 0)


def mf(name, extra=""):
    head = (
        f'name = "{name}"\ncompositor = "hyprland"\nstart = "start-{name}"\nstop = "stop-{name}"\n'
    )
    return parse_manifest(head + extra + "\n")


def mk(tmp_path, runner, clock):
    ms = {"a": mf("a", 'process = "proc-a"'), "bare": mf("bare")}
    return Executor(
        runner, tmp_path / "state.json", tmp_path / "dots", tmp_path / "home", ms, clock
    )


def test_resume_leaves_a_running_shell_alone(tmp_path, clock):
    r = Script()
    assert mk(tmp_path, r, clock).resume("a") == "already running"
    assert sh("start-a") not in r.calls


def test_resume_waits_for_the_profiles_own_autostart(tmp_path, clock):
    r = Script({pgrep("a"): 3})
    assert mk(tmp_path, r, clock).resume("a") == "already running"
    assert sh("start-a") not in r.calls
    assert clock.t > 0


def test_resume_starts_the_shell_when_nothing_brings_it_up(tmp_path, clock):
    r = Script({pgrep("a"): NEVER})
    assert mk(tmp_path, r, clock).resume("a") == "started"
    assert sh("start-a") in r.calls
    assert clock.t >= 10


def test_resume_retries_a_start_that_fails_early_in_the_session(tmp_path, clock):
    r = Script({pgrep("a"): NEVER, tuple(sh("start-a")): 2})
    assert mk(tmp_path, r, clock).resume("a") == "started"
    assert r.seen[tuple(sh("start-a"))] == 3


def test_resume_has_nothing_to_do_for_a_profile_without_a_process(tmp_path, clock):
    r = Script()
    assert mk(tmp_path, r, clock).resume("bare") == "nothing to start"
    assert r.calls == []


def test_resume_gives_up_after_the_retry_window(tmp_path, clock):
    r = Script({pgrep("a"): NEVER, tuple(sh("start-a")): NEVER})
    assert mk(tmp_path, r, clock).resume("a").startswith("failed")
    assert clock.t >= 25


def cli_env(tmp_path):
    dots = tmp_path / "dots"
    for n in ("a", "b"):
        d = dots / "profiles" / n
        d.mkdir(parents=True)
        body = f'name = "{n}"\ncompositor = "hyprland"\nstart = "start-{n}"\nstop = "stop-{n}"\n'
        (d / "profile.toml").write_text(body + f'process = "proc-{n}"\n')
    env = {**ENV, "HOME": str(tmp_path / "home"), "DOTFILES": str(dots)}
    env |= {"XDG_RUNTIME_DIR": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state")}
    return env


def state_dir(env):
    return Path(env["XDG_STATE_HOME"]) / "profile-switcher"


def write_state(env, data):
    state_dir(env).mkdir(parents=True, exist_ok=True)
    (state_dir(env) / "state.json").write_text(json.dumps(data))


def read_state(env):
    return json.loads((state_dir(env) / "state.json").read_text())


def test_cli_resume_starts_the_recorded_profile(tmp_path, clock, capsys):
    env = cli_env(tmp_path)
    write_state(env, {"state": "idle", "active": "a"})
    r = Script({pgrep("a"): NEVER})
    assert main(["resume"], env=env, runner=r, clock=clock) == 0
    assert sh("start-a") in r.calls
    assert sh("start-b") not in r.calls
    assert read_state(env) == {"state": "idle", "active": "a"}
    assert "started" in capsys.readouterr().out


def test_cli_resume_repairs_an_interrupted_switch_first(tmp_path, clock):
    env = cli_env(tmp_path)
    write_state(env, {"state": "switching", "from": "a", "to": "b", "step": 3})
    r = Script({pgrep("b"): NEVER})
    assert main(["resume"], env=env, runner=r, clock=clock) == 0
    assert sh("stop-b") in r.calls
    assert read_state(env) == {"state": "idle", "active": "a"}


def test_cli_resume_does_nothing_without_a_recorded_profile(tmp_path, clock):
    env = cli_env(tmp_path)
    r = Script()
    assert main(["resume"], env=env, runner=r, clock=clock) == 0
    assert r.calls == []


def test_cli_resume_skips_quietly_while_a_switch_holds_the_lock(tmp_path, clock):
    env = cli_env(tmp_path)
    write_state(env, {"state": "idle", "active": "a"})
    r = Script({pgrep("a"): NEVER})
    with switch_lock(tmp_path / "profile-switcher.lock"):
        assert main(["resume"], env=env, runner=r, clock=clock) == 0
    assert r.calls == []


def test_cli_resume_never_fails_login_and_writes_a_log(tmp_path, clock):
    env = cli_env(tmp_path)
    write_state(env, {"state": "idle", "active": "a"})
    r = Script({pgrep("a"): NEVER, tuple(sh("start-a")): NEVER})
    assert main(["resume"], env=env, runner=r, clock=clock) == 0
    log = (state_dir(env) / "resume.log").read_text()
    assert "resume: a: failed" in log


def test_cli_resume_leaves_a_broken_journal_alone(tmp_path, clock):
    env = cli_env(tmp_path)
    write_state(env, {"state": "broken", "from": "a", "to": "b"})
    r = Script({tuple(sh("stop-b")): NEVER})
    assert main(["resume"], env=env, runner=r, clock=clock) == 0
    assert read_state(env)["state"] == "broken"
    assert list(pgrep("a")) not in r.calls
