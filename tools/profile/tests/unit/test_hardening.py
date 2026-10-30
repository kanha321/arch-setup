from __future__ import annotations

import json
from pathlib import Path

from profile_switcher.cli import main
from profile_switcher.executor import Executor
from profile_switcher.manifest import parse_manifest
from profile_switcher.planner import Step, make_plan
from profile_switcher.runner import Result

BUSCTL = ["busctl", "--user", "list", "--no-legend"]
ENV = {"HYPRLAND_INSTANCE_SIGNATURE": "x", "DBUS_SESSION_BUS_ADDRESS": "y", "XDG_SESSION_ID": "1"}
NAMES = 'dbus_names = ["org.freedesktop.Notifications"]'
HOOK = '[hooks]\npost_stow = "hook-old"'
HEALTHY = 'health = "health-new"'


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


def mk(tmp_path, runner, clock, old="", new=""):
    ms = {"old": mf("old", old), "new": mf("new", new)}
    ex = Executor(runner, tmp_path / "state.json", tmp_path / "dots", tmp_path / "home", ms, clock)
    return ex, ms


def jr(tmp_path):
    return json.loads((tmp_path / "state.json").read_text())


def last(calls, cmd):
    return len(calls) - 1 - calls[::-1].index(cmd)


def failing_start(tmp_path, runner, clock, old="", new=""):
    ex, ms = mk(tmp_path, runner, clock, old, new)
    runner.set(sh("start-new"), Result(1))
    return ex.execute(make_plan(ms["old"], ms["new"]), "old", "new")


def test_rollback_waits_for_dbus_before_restarting_old(tmp_path, runner, clock):
    result = failing_start(tmp_path, runner, clock, NAMES, NAMES)
    c = runner.calls
    assert result == "rolled_back"
    assert c.count(BUSCTL) == 2
    assert c.index(sh("stop-new")) < last(c, BUSCTL) < last(c, sh("start-old"))


def test_rollback_reruns_the_old_post_stow_hook(tmp_path, runner, clock):
    result = failing_start(tmp_path, runner, clock, HOOK)
    c = runner.calls
    assert result == "rolled_back"
    assert last(c, ["hyprctl", "reload"]) < c.index(sh("hook-old")) < last(c, sh("start-old"))


def test_failed_hook_during_rollback_marks_the_journal_broken(tmp_path, runner, clock):
    runner.set(sh("hook-old"), Result(1))
    assert failing_start(tmp_path, runner, clock, HOOK) == "failed"
    assert jr(tmp_path)["state"] == "broken"


def test_stop_counts_as_done_when_the_process_is_already_gone(tmp_path, runner, clock):
    ex, _ = mk(tmp_path, runner, clock, 'process = "old-proc"')
    runner.set(sh("stop-old"), Result(1))
    runner.set(["pgrep", "-f", "old-proc"], Result(1))
    assert ex.run_step(Step("stop", "old")) is True


def test_stop_still_fails_when_the_process_is_alive(tmp_path, runner, clock):
    ex, _ = mk(tmp_path, runner, clock, 'process = "old-proc"')
    runner.set(sh("stop-old"), Result(1))
    assert ex.run_step(Step("stop", "old")) is False


class SeqRunner:
    def __init__(self, fail_first):
        self.calls = []
        self.fail_first = fail_first
        self.health_calls = 0

    def run(self, cmd, timeout=10):
        self.calls.append(list(cmd))
        if cmd == sh("health-new"):
            self.health_calls += 1
            return Result(1 if self.health_calls <= self.fail_first else 0)
        return Result(0)


def test_health_polls_until_it_passes(tmp_path, clock):
    r = SeqRunner(2)
    ex, _ = mk(tmp_path, r, clock, "", HEALTHY + "\nhealth_timeout = 15")
    assert ex.run_step(Step("health", "new")) is True
    assert r.health_calls == 3


def test_health_gives_up_after_health_timeout(tmp_path, clock):
    r = SeqRunner(10**6)
    ex, _ = mk(tmp_path, r, clock, "", HEALTHY + "\nhealth_timeout = 15")
    assert ex.run_step(Step("health", "new")) is False
    assert clock.t >= 15
    assert r.health_calls > 3


def crash_at(tmp_path, ms, kind):
    plan = make_plan(ms["old"], ms["new"])
    step = next(i for i, s in enumerate(plan) if s.kind == kind)
    state = {"state": "switching", "from": "old", "to": "new", "step": step}
    (tmp_path / "state.json").write_text(json.dumps(state))


def test_repair_completes_the_switch_when_the_new_shell_is_healthy(tmp_path, runner, clock):
    ex, ms = mk(tmp_path, runner, clock, "", HEALTHY)
    crash_at(tmp_path, ms, "health")
    assert ex.repair() == "completed"
    assert jr(tmp_path) == {"state": "idle", "active": "new"}
    assert sh("stop-new") not in runner.calls


def test_repair_rolls_back_when_the_new_shell_is_unhealthy(tmp_path, runner, clock):
    ex, ms = mk(tmp_path, runner, clock, "", HEALTHY)
    runner.set(sh("health-new"), Result(1))
    crash_at(tmp_path, ms, "health")
    assert ex.repair() == "repaired"
    assert jr(tmp_path) == {"state": "idle", "active": "old"}
    assert sh("stop-new") in runner.calls


def test_repair_rolls_back_when_the_crash_was_at_the_start_step(tmp_path, runner, clock):
    ex, ms = mk(tmp_path, runner, clock, "", HEALTHY)
    crash_at(tmp_path, ms, "start")
    assert ex.repair() == "repaired"
    assert jr(tmp_path)["active"] == "old"


def cli_env(tmp_path):
    dots = tmp_path / "dots"
    for n in ("bare", "other"):
        d = dots / "profiles" / n
        d.mkdir(parents=True)
        head = f'name = "{n}"\ncompositor = "hyprland"\n'
        head += f'start = "start-{n}"\nstop = "stop-{n}"\nstow = ["hypr"]\n'
        (d / "profile.toml").write_text(head)
    extra = {"HOME": str(tmp_path / "home"), "DOTFILES": str(dots)}
    extra |= {"XDG_RUNTIME_DIR": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state")}
    return {**ENV, **extra}


def stow_cmd(env, name):
    pkg = Path(env["DOTFILES"]) / "profiles" / name / "stow"
    return ["stow", "--no-folding", "-d", str(pkg), "-t", env["HOME"], "hypr"]


def state_file(env):
    return Path(env["XDG_STATE_HOME"]) / "profile-switcher" / "state.json"


def test_init_stows_the_profile(tmp_path, runner):
    env = cli_env(tmp_path)
    assert main(["init", "bare"], env=env, runner=runner) == 0
    assert stow_cmd(env, "bare") in runner.calls
    assert json.loads(state_file(env).read_text()) == {"state": "idle", "active": "bare"}


def test_init_fails_and_records_nothing_when_stow_fails(tmp_path, runner):
    env = cli_env(tmp_path)
    runner.set(stow_cmd(env, "bare"), Result(1))
    assert main(["init", "bare"], env=env, runner=runner) == 1
    assert not state_file(env).exists()


def test_switch_stops_before_touching_anything_when_a_stray_file_blocks_stow(
    tmp_path, runner, capsys
):
    env = cli_env(tmp_path)
    pkg = Path(env["DOTFILES"]) / "profiles" / "other" / "stow" / "hypr" / ".config" / "hypr"
    pkg.mkdir(parents=True)
    (pkg / "active_profile.lua").write_text("-- profile\n")
    live = Path(env["HOME"]) / ".config" / "hypr"
    live.mkdir(parents=True)
    (live / "active_profile.lua").write_text("my own file\n")
    state_file(env).parent.mkdir(parents=True)
    state_file(env).write_text(json.dumps({"state": "idle", "active": "bare"}))
    assert main(["switch", "other"], env=env, runner=runner) == 1
    out = capsys.readouterr().out
    assert "stray" in out
    assert ".config/hypr/active_profile.lua" in out
    assert sh("stop-bare") not in runner.calls


def test_stray_files_ignores_symlinks_and_missing_targets(tmp_path):
    from profile_switcher.doctor import stray_files

    stow = tmp_path / "stow"
    (stow / "hypr" / ".config" / "hypr").mkdir(parents=True)
    for n in ("a.lua", "b.lua", "c.lua"):
        (stow / "hypr" / ".config" / "hypr" / n).write_text("x")
    live = tmp_path / "home" / ".config" / "hypr"
    live.mkdir(parents=True)
    (live / "a.lua").write_text("mine")
    (live / "b.lua").symlink_to(tmp_path / "elsewhere")
    assert stray_files(stow, tmp_path / "home") == [".config/hypr/a.lua"]


def test_claim_conflicts_flag_autostarts_in_common():
    from profile_switcher.doctor import find_claim_conflicts

    claims = {"caelestia": ["notifications", "bar"], "dms": ["notifications"]}
    out = find_claim_conflicts(claims, 'hl.exec_cmd("mako")\nhl.exec_cmd("kitty")')
    assert len(out) == 1
    assert "mako" in out[0]
    assert "caelestia, dms" in out[0]
    assert find_claim_conflicts(claims, 'hl.exec_cmd("kitty")') == []


def test_doctor_warns_about_claim_conflicts_but_still_passes(tmp_path, runner, capsys):
    env = cli_env(tmp_path)
    toml = 'name = "bare"\ncompositor = "hyprland"\nstart = "true"\nstop = "true"\n'
    (Path(env["DOTFILES"]) / "profiles" / "bare" / "profile.toml").write_text(
        toml + 'claims = ["notifications"]\n'
    )
    common = Path(env["DOTFILES"]) / "common" / "hypr" / ".config" / "hypr"
    common.mkdir(parents=True)
    (common / "hyprland.lua").write_text('hl.exec_cmd("mako")\n')
    assert main(["doctor"], env=env, runner=runner) == 0
    out = capsys.readouterr().out
    assert "warning" in out
    assert "mako" in out
