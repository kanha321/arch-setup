from profile_switcher.executor import Executor
from profile_switcher.manifest import parse_manifest
from profile_switcher.planner import make_plan
from profile_switcher.runner import Result


def mk(name, extra=""):
    head = f'name = "{name}"\ncompositor = "hyprland"\nstart = "s"\nstop = "t"\n'
    return parse_manifest(head + extra)


def test_wait_covers_names_of_both_profiles(tmp_path, runner, clock):
    runner.set(["busctl", "--user", "list", "--no-legend"], Result(0, "org.example.OnlyNew 1 x\n"))
    a, b = mk("a"), mk("b", 'dbus_names = ["org.example.OnlyNew"]\n')
    ex = Executor(runner, tmp_path / "s.json", tmp_path, tmp_path, {"a": a, "b": b}, clock)
    assert ex.execute(make_plan(a, b), "a", "b") == "rolled_back"
