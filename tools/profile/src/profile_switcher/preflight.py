from __future__ import annotations

from collections.abc import Mapping

from profile_switcher.manifest import Manifest
from profile_switcher.runner import Runner

REQUIRED_ENV = ("HYPRLAND_INSTANCE_SIGNATURE", "DBUS_SESSION_BUS_ADDRESS", "XDG_SESSION_ID")


def preflight(target: Manifest, runner: Runner, env: Mapping[str, str]) -> list[str]:
    problems = [f"{var} is not set" for var in REQUIRED_ENV if not env.get(var)]

    if target.packages:
        result = runner.run(["pacman", "-T", *target.packages])
        if result.returncode != 0:
            problems.append(f"missing packages: {' '.join(result.stdout.split())}")

    session = env.get("XDG_SESSION_ID")
    if session:
        cmd = ["loginctl", "show-session", session, "-p", "LockedHint", "--value"]
        if runner.run(cmd).stdout.strip() == "yes":
            problems.append("session is locked")

    return problems
