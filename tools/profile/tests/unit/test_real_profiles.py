from pathlib import Path

from profile_switcher.planner import make_plan
from profile_switcher.profiles import load_manifests

DOTS = Path(__file__).parents[4]


def test_real_manifests_load_and_switch_both_ways():
    ms = load_manifests(DOTS)
    assert {"bare", "caelestia", "dms"} <= set(ms)
    for a in ("bare", "caelestia", "dms"):
        for b in ("bare", "caelestia", "dms"):
            assert bool(make_plan(ms[a], ms[b])) == (a != b)


def test_shells_declare_process_and_dbus_names_for_safe_stop():
    ms = load_manifests(DOTS)
    for name in ("caelestia", "dms"):
        assert ms[name].process and ms[name].dbus_names and ms[name].health
    assert set(ms["caelestia"].dbus_names) <= set(ms["dms"].dbus_names)
