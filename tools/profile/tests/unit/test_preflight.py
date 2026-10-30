import pytest

from profile_switcher.manifest import parse_manifest
from profile_switcher.preflight import preflight
from profile_switcher.runner import Result

ENV = {
    "HYPRLAND_INSTANCE_SIGNATURE": "sig",
    "DBUS_SESSION_BUS_ADDRESS": "unix:path=/x",
    "XDG_SESSION_ID": "2",
}
LOCKED = ["loginctl", "show-session", "2", "-p", "LockedHint", "--value"]


def target(packages=""):
    return parse_manifest(
        'name = "b"\ncompositor = "hyprland"\nstart = "s"\nstop = "t"\n' + packages
    )


def test_all_good(runner):
    assert preflight(target('packages = ["a"]'), runner, ENV) == []


@pytest.mark.parametrize("var", ["HYPRLAND_INSTANCE_SIGNATURE", "DBUS_SESSION_BUS_ADDRESS"])
def test_missing_session_env(runner, var):
    env = {k: v for k, v in ENV.items() if k != var}
    problems = preflight(target(), runner, env)
    assert any(var in p for p in problems)


def test_missing_packages(runner):
    runner.set(["pacman", "-T", "a", "b"], Result(127, "b\n"))
    problems = preflight(target('packages = ["a", "b"]'), runner, ENV)
    assert problems == ["missing packages: b"]


def test_locked_session(runner):
    runner.set(LOCKED, Result(0, "yes\n"))
    assert any("locked" in p for p in preflight(target(), runner, ENV))


def test_no_packages_skips_pacman(runner):
    preflight(target(), runner, ENV)
    assert not any(c[0] == "pacman" for c in runner.calls)
