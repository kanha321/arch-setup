import json
import shutil
import subprocess

import pytest

from profile_switcher.executor import Executor
from profile_switcher.manifest import parse_manifest
from profile_switcher.planner import make_plan
from profile_switcher.runner import Result, SubprocessRunner

pytestmark = pytest.mark.skipif(shutil.which("stow") is None, reason="stow missing")


class NoHypr:
    def __init__(self):
        self.calls = []
        self.real = SubprocessRunner()

    def run(self, cmd, timeout=10):
        self.calls.append(list(cmd))
        if cmd[0] == "hyprctl":
            return Result(0)
        return self.real.run(cmd, timeout)


def mk(n):
    return parse_manifest(
        f'name = "{n}"\ncompositor = "hyprland"\nstart = "true"\nstop = "true"\nstow = ["p"]\n'
    )


def build(tmp_path):
    dots, home = tmp_path / "dots", tmp_path / "home"
    home.mkdir()
    for n in ("a", "b"):
        d = dots / "profiles" / n / "stow" / "p" / ".config" / "x"
        d.mkdir(parents=True)
        (d / "shared").write_text(n)
        (d / f"only-{n}").write_text(n)
    ms = {"a": mk("a"), "b": mk("b")}
    runner = NoHypr()
    ex = Executor(runner, tmp_path / "state.json", dots, home, ms)
    pkg = str(dots / "profiles" / "a" / "stow")
    subprocess.run(["stow", "--no-folding", "-d", pkg, "-t", str(home), "p"], check=True)
    return ex, ms, home, runner


def snapshot(home):
    out = {}
    for p in sorted(home.rglob("*")):
        rel = str(p.relative_to(home))
        if p.is_symlink():
            out[rel] = ("link", str(p.readlink()))
        elif p.is_dir():
            out[rel] = ("dir",)
        else:
            out[rel] = ("file", p.read_text())
    return out


def test_switch_produces_exactly_b_links_no_folding(tmp_path):
    ex, ms, home, _ = build(tmp_path)
    assert ex.execute(make_plan(ms["a"], ms["b"]), "a", "b") == "ok"
    x = home / ".config" / "x"
    assert x.is_dir() and not x.is_symlink()
    assert sorted(p.name for p in x.iterdir()) == ["only-b", "shared"]
    assert all("profiles/b/" in str((x / n).readlink()) for n in ("only-b", "shared"))


def test_round_trip_leaves_tree_identical(tmp_path):
    ex, ms, home, _ = build(tmp_path)
    before = snapshot(home)
    assert ex.execute(make_plan(ms["a"], ms["b"]), "a", "b") == "ok"
    assert ex.execute(make_plan(ms["b"], ms["a"]), "b", "a") == "ok"
    assert snapshot(home) == before


def test_stray_file_fails_switch_and_is_never_adopted(tmp_path):
    ex, ms, home, runner = build(tmp_path)
    stray = home / ".config" / "x" / "only-b"
    stray.write_text("mine")
    before = snapshot(home)
    assert ex.execute(make_plan(ms["a"], ms["b"]), "a", "b") == "rolled_back"
    assert snapshot(home) == before
    assert stray.read_text() == "mine"
    assert not any("--adopt" in c for c in runner.calls)
    assert json.loads((tmp_path / "state.json").read_text()) == {"state": "idle", "active": "a"}
