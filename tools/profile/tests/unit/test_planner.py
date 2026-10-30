from profile_switcher.manifest import parse_manifest
from profile_switcher.planner import Step, make_plan

HEAD = 'compositor = "hyprland"\nstart = "s"\nstop = "t"\n'


def mk(name, extra='health = "h"\n'):
    return parse_manifest(f'name = "{name}"\n{HEAD}{extra}')


def kinds(plan):
    return [s.kind for s in plan]


def test_same_profile_is_empty_plan():
    a = mk("a")
    assert make_plan(a, a) == []


def test_step_order():
    assert kinds(make_plan(mk("a"), mk("b"))) == [
        "preflight",
        "stop",
        "wait_dbus",
        "unstow",
        "stow",
        "reload",
        "start",
        "health",
        "commit",
    ]


def test_steps_target_the_right_profile():
    by_kind = {s.kind: s.profile for s in make_plan(mk("a"), mk("b"))}
    assert by_kind["stop"] == by_kind["wait_dbus"] == by_kind["unstow"] == "a"
    for k in ("preflight", "stow", "reload", "start", "health", "commit"):
        assert by_kind[k] == "b"


def test_post_stow_hook_between_reload_and_start():
    plan = make_plan(mk("a"), mk("b", '[hooks]\npost_stow = "x"\n'))
    assert Step("hook", "b", "post_stow") in plan
    k = kinds(plan)
    assert k.index("reload") < k.index("hook") < k.index("start")


def test_optional_steps_skipped_when_absent():
    k = kinds(make_plan(mk("a"), mk("b", "")))
    assert "hook" not in k and "health" not in k
