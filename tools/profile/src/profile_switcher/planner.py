from __future__ import annotations

from dataclasses import dataclass

from profile_switcher.manifest import Manifest


@dataclass(frozen=True)
class Step:
    kind: str
    profile: str
    arg: str | None = None


def make_plan(active: Manifest, target: Manifest) -> list[Step]:
    if active.name == target.name:
        return []

    old, new = active.name, target.name
    steps = [
        Step("preflight", new),
        Step("stop", old),
        Step("wait_dbus", old),
        Step("unstow", old),
        Step("stow", new),
        Step("reload", new),
    ]
    if "post_stow" in target.hooks:
        steps.append(Step("hook", new, "post_stow"))
    steps.append(Step("start", new))
    if target.health:
        steps.append(Step("health", new))
    steps.append(Step("commit", new))
    return steps
