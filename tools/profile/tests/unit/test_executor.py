import json

from profile_switcher.executor import Executor
from profile_switcher.manifest import parse_manifest
from profile_switcher.planner import make_plan


def mk(name):
    return parse_manifest(
        f'name = "{name}"\ncompositor = "hyprland"\nstart = "s"\nstop = "t"\n'
        'health = "h"\nstow = ["p"]\n'
    )


def setup(tmp_path, runner):
    manifests = {"a": mk("a"), "b": mk("b")}
    journal = tmp_path / "state.json"
    ex = Executor(runner, journal, tmp_path / "dots", tmp_path / "home", manifests)
    return ex, manifests, journal


def stow_cmd(tmp_path, name, delete=False):
    flag = ["-D"] if delete else []
    pkg_dir = str(tmp_path / "dots" / "profiles" / name / "stow")
    return ["stow", "--no-folding", *flag, "-d", pkg_dir, "-t", str(tmp_path / "home"), "p"]


def test_commands_run_in_plan_order(tmp_path, runner):
    ex, m, _ = setup(tmp_path, runner)
    ex.execute(make_plan(m["a"], m["b"]), "a", "b")
    assert runner.calls == [
        ["sh", "-c", "t"],
        stow_cmd(tmp_path, "a", delete=True),
        stow_cmd(tmp_path, "b"),
        ["hyprctl", "reload"],
        ["sh", "-c", "s"],
        ["sh", "-c", "h"],
    ]


def test_journal_says_switching_before_each_step(tmp_path, runner):
    ex, m, journal = setup(tmp_path, runner)
    seen = []
    orig = runner.run

    def spy(cmd, timeout=10):
        seen.append(json.loads(journal.read_text()))
        return orig(cmd, timeout)

    runner.run = spy
    ex.execute(make_plan(m["a"], m["b"]), "a", "b")
    assert [s["step"] for s in seen] == [1, 3, 4, 5, 6, 7]
    assert all(s["state"] == "switching" and s["from"] == "a" and s["to"] == "b" for s in seen)


def test_journal_idle_after_commit(tmp_path, runner):
    ex, m, journal = setup(tmp_path, runner)
    ex.execute(make_plan(m["a"], m["b"]), "a", "b")
    assert json.loads(journal.read_text()) == {"state": "idle", "active": "b"}


def test_empty_plan_touches_nothing(tmp_path, runner):
    ex, _m, journal = setup(tmp_path, runner)
    ex.execute([], "a", "a")
    assert runner.calls == [] and not journal.exists()
