import pytest

from profile_switcher.manifest import ManifestError, parse_manifest
from profile_switcher.planner import make_plan
from profile_switcher.profiles import load_manifests


def write(dots, name, inner=None):
    d = dots / "profiles" / name
    d.mkdir(parents=True)
    body = f'name = "{inner or name}"\ncompositor = "hyprland"\nstart = "s"\nstop = "t"\n'
    (d / "profile.toml").write_text(body)


def test_new_profile_directory_is_switchable_without_code_changes(tmp_path):
    write(tmp_path, "a")
    write(tmp_path, "b")
    assert sorted(load_manifests(tmp_path)) == ["a", "b"]
    write(tmp_path, "c")
    ms = load_manifests(tmp_path)
    assert sorted(ms) == ["a", "b", "c"]
    plan = make_plan(ms["a"], ms["c"])
    assert plan and {s.profile for s in plan} == {"a", "c"}


def test_name_must_match_directory(tmp_path):
    write(tmp_path, "a", inner="other")
    with pytest.raises(ManifestError, match="does not match"):
        load_manifests(tmp_path)


def test_no_profiles_dir_gives_empty(tmp_path):
    assert load_manifests(tmp_path) == {}


def test_new_fields_default_and_validate():
    base = 'name = "x"\ncompositor = "hyprland"\nstart = "a"\nstop = "b"\n'
    m = parse_manifest(base)
    assert m.process is None and m.dbus_names == [] and m.stop_timeout == 5
    with pytest.raises(ManifestError, match="stop_timeout"):
        parse_manifest(base + "stop_timeout = 0\n")
    with pytest.raises(ManifestError, match="dbus_names"):
        parse_manifest(base + 'dbus_names = "x"\n')
