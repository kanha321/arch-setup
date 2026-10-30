import json

from profile_switcher.cli import main
from profile_switcher.lock import switch_lock


def write(dots, name):
    d = dots / "profiles" / name
    d.mkdir(parents=True)
    (d / "profile.toml").write_text(
        f'name = "{name}"\ncompositor = "hyprland"\nstart = "s"\nstop = "t"\n'
    )


def env_for(tmp_path):
    write(tmp_path / "dots", "a")
    write(tmp_path / "dots", "b")
    return {
        "HOME": str(tmp_path),
        "DOTFILES": str(tmp_path / "dots"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "XDG_RUNTIME_DIR": str(tmp_path / "run"),
        "HYPRLAND_INSTANCE_SIGNATURE": "s",
        "DBUS_SESSION_BUS_ADDRESS": "u",
        "XDG_SESSION_ID": "2",
    }


def journal(tmp_path):
    return tmp_path / "state" / "profile-switcher" / "state.json"


def test_switch_before_init_is_refused(tmp_path, runner, clock):
    env = env_for(tmp_path)
    assert main(["switch", "b"], env, runner, clock) == 2
    assert runner.calls == []


def test_init_switch_status(tmp_path, runner, clock, capsys):
    env = env_for(tmp_path)
    assert main(["init", "a"], env, runner, clock) == 0
    assert main(["switch", "b"], env, runner, clock) == 0
    assert json.loads(journal(tmp_path).read_text()) == {"state": "idle", "active": "b"}
    assert main(["status"], env, runner, clock) == 0
    assert '"active": "b"' in capsys.readouterr().out


def test_unknown_profile(tmp_path, runner, clock):
    env = env_for(tmp_path)
    assert main(["switch", "zzz"], env, runner, clock) == 2


def test_same_profile_is_noop(tmp_path, runner, clock):
    env = env_for(tmp_path)
    main(["init", "a"], env, runner, clock)
    assert main(["switch", "a"], env, runner, clock) == 0
    assert runner.calls == []


def test_preflight_problem_blocks_before_anything_runs(tmp_path, runner, clock, capsys):
    env = env_for(tmp_path)
    main(["init", "a"], env, runner, clock)
    del env["HYPRLAND_INSTANCE_SIGNATURE"]
    assert main(["switch", "b"], env, runner, clock) == 1
    assert "HYPRLAND_INSTANCE_SIGNATURE" in capsys.readouterr().out
    assert not any(c[0] in ("sh", "stow", "hyprctl") for c in runner.calls)


def test_held_lock_exits_3(tmp_path, runner, clock):
    env = env_for(tmp_path)
    main(["init", "a"], env, runner, clock)
    with switch_lock(tmp_path / "run" / "profile-switcher.lock"):
        assert main(["switch", "b"], env, runner, clock) == 3
    assert runner.calls == []


def test_repair_fixes_broken_journal(tmp_path, runner, clock):
    env = env_for(tmp_path)
    journal(tmp_path).parent.mkdir(parents=True)
    journal(tmp_path).write_text(json.dumps({"state": "broken", "from": "a", "to": "b"}))
    assert main(["repair"], env, runner, clock) == 0
    assert json.loads(journal(tmp_path).read_text()) == {"state": "idle", "active": "a"}


def test_doctor_reports_overlap_with_common(tmp_path, runner, clock, capsys):
    env = env_for(tmp_path)
    for root in (
        tmp_path / "dots" / "common" / "p",
        tmp_path / "dots" / "profiles" / "a" / "stow" / "p",
    ):
        (root / ".config").mkdir(parents=True)
        (root / ".config" / "x").write_text("1")
    assert main(["doctor"], env, runner, clock) == 1
    assert ".config/x" in capsys.readouterr().out
