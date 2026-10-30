import json

from profile_switcher.executor import Executor
from profile_switcher.manifest import parse_manifest
from profile_switcher.planner import Step, make_plan
from profile_switcher.runner import Result

PROC = 'process = "qs -c a"\n'
HELD = "org.freedesktop.Notifications 1 x\n"
NAMES = 'dbus_names = ["org.freedesktop.Notifications"]\n'


def mk(name, extra=""):
    head = f'name = "{name}"\ncompositor = "hyprland"\n'
    return parse_manifest(head + f'start = "s-{name}"\nstop = "t-{name}"\n' + extra)


class Scripted:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []
        self.timeouts = []

    def run(self, cmd, timeout=10):
        self.calls.append(list(cmd))
        self.timeouts.append(timeout)
        return self.handler(cmd)


def make(tmp_path, runner, clock, *manifests):
    ms = {m.name: m for m in manifests}
    journal = tmp_path / "state.json"
    return Executor(runner, journal, tmp_path / "dots", tmp_path / "home", ms, clock)


def test_stop_escalates_term_then_kill_on_right_process_only(tmp_path, clock):
    alive = {"v": True}

    def handler(cmd):
        if cmd[0] == "pgrep":
            return Result(0 if alive["v"] else 1)
        if cmd[:2] == ["pkill", "-KILL"]:
            alive["v"] = False
        return Result(0)

    r = Scripted(handler)
    ex = make(tmp_path, r, clock, mk("a", PROC))
    assert ex.run_step(Step("stop", "a")) is True
    pkills = [c for c in r.calls if c[0] == "pkill"]
    assert pkills == [["pkill", "-TERM", "-f", "qs -c a"], ["pkill", "-KILL", "-f", "qs -c a"]]


def test_no_escalation_when_shell_exits_in_time(tmp_path, clock):
    def handler(cmd):
        if cmd[0] == "pgrep":
            return Result(0 if clock.now() < 1 else 1)
        return Result(0)

    r = Scripted(handler)
    ex = make(tmp_path, r, clock, mk("a", PROC))
    assert ex.run_step(Step("stop", "a")) is True
    assert not any(c[0] == "pkill" for c in r.calls)


def test_unkillable_process_fails_the_step(tmp_path, clock):
    r = Scripted(lambda cmd: Result(0))
    ex = make(tmp_path, r, clock, mk("a", PROC))
    assert ex.run_step(Step("stop", "a")) is False


def test_dbus_wait_polls_until_free(tmp_path, clock):
    outs = iter([HELD, HELD, "other.name 2 y\n"])

    def handler(cmd):
        return Result(0, next(outs)) if cmd[0] == "busctl" else Result(0)

    ex = make(tmp_path, Scripted(handler), clock, mk("a", NAMES))
    assert ex.run_step(Step("wait_dbus", "a")) is True
    assert len(clock.sleeps) == 2


def test_dbus_never_free_fails_the_step(tmp_path, clock):
    r = Scripted(lambda cmd: Result(0, HELD) if cmd[0] == "busctl" else Result(0))
    ex = make(tmp_path, r, clock, mk("a", NAMES))
    assert ex.run_step(Step("wait_dbus", "a")) is False


def test_dbus_never_free_triggers_rollback(tmp_path, clock):
    r = Scripted(lambda cmd: Result(0, HELD) if cmd[0] == "busctl" else Result(0))
    a, b = mk("a", NAMES), mk("b")
    ex = make(tmp_path, r, clock, a, b)
    assert ex.execute(make_plan(a, b), "a", "b") == "rolled_back"
    assert json.loads((tmp_path / "state.json").read_text()) == {"state": "idle", "active": "a"}


def test_health_check_uses_manifest_timeout(tmp_path, clock):
    r = Scripted(lambda cmd: Result(0))
    a, b = mk("a"), mk("b", 'health = "h"\nhealth_timeout = 7\n')
    ex = make(tmp_path, r, clock, a, b)
    assert ex.execute(make_plan(a, b), "a", "b") == "ok"
    assert r.timeouts[r.calls.index(["sh", "-c", "h"])] == 7
