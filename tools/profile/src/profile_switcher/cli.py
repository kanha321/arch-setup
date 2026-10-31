from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path

from profile_switcher.doctor import (
    find_claim_conflicts,
    find_overlaps,
    list_stow_files,
    read_text_files,
    stray_files,
)
from profile_switcher.executor import Executor
from profile_switcher.lock import LockHeld, switch_lock
from profile_switcher.manifest import Manifest, ManifestError
from profile_switcher.planner import make_plan
from profile_switcher.preflight import preflight
from profile_switcher.profiles import load_manifests
from profile_switcher.runner import Runner, SubprocessRunner


def _read_state(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="profile")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("repair")
    sub.add_parser("resume")
    sub.add_parser("doctor")
    sub.add_parser("init").add_argument("name")
    sub.add_parser("switch").add_argument("name")
    return ap


def _doctor(dots: Path, manifests: dict[str, Manifest]) -> int:
    names = sorted(manifests)
    common = list_stow_files(dots / "common")
    bad = 0
    for name in names:
        files = {"common": common, name: list_stow_files(dots / "profiles" / name / "stow")}
        for path, owners in find_overlaps(files).items():
            print(f"overlap: {path} owned by {', '.join(owners)}")
            bad = 1
    claims = {n: list(getattr(manifests[n], "claims", None) or ()) for n in names}
    for warning in find_claim_conflicts(claims, read_text_files(dots / "common")):
        print(f"warning: {warning}")
    if not bad:
        print("doctor: ok")
    return bad


def _stray_block(ex: Executor, name: str) -> str | None:
    stray = stray_files(ex.dotfiles / "profiles" / name / "stow", ex.home)
    if not stray:
        return None
    head = "stray files would block stow (move or remove them, never --adopt):"
    return head + "\n  " + "\n  ".join(stray)


def _switch(ex: Executor, state: dict | None, name: str, env: Mapping[str, str], runner) -> int:
    if state is None:
        print("no active profile recorded; run: profile init NAME")
        return 2
    if state["state"] != "idle":
        print(f"journal says {state['state']}; run: profile repair")
        return 2
    active = state["active"]
    if active == name:
        print(f"{name} is already active")
        return 0
    problems = preflight(ex.manifests[name], runner, env)
    if problems:
        print("preflight failed:\n  " + "\n  ".join(problems))
        return 1
    block = _stray_block(ex, name)
    if block:
        print(block)
        return 1
    result = ex.execute(make_plan(ex.manifests[active], ex.manifests[name]), active, name)
    print(f"switch {active} -> {name}: {result}")
    if ex.last_failure:
        print(f"failed step: {ex.last_failure}")
    return 0 if result == "ok" else 1


def _resume(ex: Executor, journal: Path, log: Path) -> int:
    def note(msg: str) -> None:
        print(msg)
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a") as f:
                f.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")
        except OSError:
            pass

    try:
        state = _read_state(journal)
    except (OSError, ValueError):
        note("resume: journal unreadable, leaving it alone")
        return 0
    if state is None:
        note("resume: no profile recorded, nothing to do")
        return 0
    if state.get("state") != "idle":
        note(f"resume: journal says {state.get('state')}, repairing first")
        note(f"resume: repair: {ex.repair()}")
        state = _read_state(journal)
        if state is None or state.get("state") != "idle":
            note("resume: journal still not idle, run: profile repair")
            return 0
    name = state.get("active")
    if name not in ex.manifests:
        note(f"resume: unknown profile {name!r} in the journal")
        return 0
    note(f"resume: {name}: {ex.resume(name)}")
    return 0


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    runner: Runner | None = None,
    clock=None,
) -> int:
    env = os.environ if env is None else env
    args = _parser().parse_args(argv)
    home = Path(env.get("HOME", "~")).expanduser()
    dots = Path(env.get("DOTFILES", home / "dotfiles"))
    state_dir = Path(env.get("XDG_STATE_HOME", home / ".local/state")) / "profile-switcher"
    journal = state_dir / "state.json"
    lock = Path(env.get("XDG_RUNTIME_DIR", "/tmp")) / "profile-switcher.lock"
    runner = runner or SubprocessRunner()

    try:
        manifests = load_manifests(dots)
    except ManifestError as e:
        print(f"manifest error: {e}")
        return 2
    if args.cmd == "doctor":
        return _doctor(dots, manifests)
    if args.cmd == "status":
        st = _read_state(journal)
        print("no active profile (run: profile init NAME)" if st is None else json.dumps(st))
        return 0
    if getattr(args, "name", None) and args.name not in manifests:
        print(f"unknown profile: {args.name}")
        return 2
    ex = Executor(runner, journal, dots, home, manifests, clock)
    if args.cmd == "init":
        block = _stray_block(ex, args.name)
        if block:
            print(block)
            return 1
        if not ex.stow(args.name):
            print(f"init failed: stow of {args.name} did not complete; nothing recorded")
            return 1
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text(json.dumps({"state": "idle", "active": args.name}))
        print(f"active profile recorded: {args.name}")
        return 0
    try:
        with switch_lock(lock):
            if args.cmd == "resume":
                return _resume(ex, journal, state_dir / "resume.log")
            if args.cmd == "repair":
                result = ex.repair()
                print(f"repair: {result}")
                return 0 if result != "failed" else 1
            return _switch(ex, _read_state(journal), args.name, env, runner)
    except LockHeld as e:
        print(str(e))
        return 0 if args.cmd == "resume" else 3
