import pytest

from profile_switcher.manifest import ManifestError, parse_manifest

BASE = """
name = "x"
compositor = "hyprland"
start = "a"
stop = "b"
"""


def test_defaults():
    m = parse_manifest(BASE)
    assert m.packages == [] and m.stow == [] and m.claims == []
    assert m.health is None and m.health_timeout == 10 and m.hooks == {}


def test_invalid_toml():
    with pytest.raises(ManifestError, match="invalid TOML"):
        parse_manifest("name = ")


@pytest.mark.parametrize("field", ["name", "start", "stop", "compositor"])
def test_empty_or_blank_field(field):
    text = BASE.replace(f"{field} = ", f'{field} = " " #')
    with pytest.raises(ManifestError, match=field):
        parse_manifest(text)


@pytest.mark.parametrize("field", ["packages", "stow", "claims"])
def test_list_fields_must_be_list_of_strings(field):
    for bad in ('"foo"', "[1, 2]"):
        with pytest.raises(ManifestError, match=field):
            parse_manifest(BASE + f"{field} = {bad}\n")


@pytest.mark.parametrize("bad", ['"abc"', "0", "-5"])
def test_health_timeout_must_be_positive_int(bad):
    with pytest.raises(ManifestError, match="health_timeout"):
        parse_manifest(BASE + f"health_timeout = {bad}\n")
