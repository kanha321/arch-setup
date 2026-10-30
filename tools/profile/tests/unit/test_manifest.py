import pytest

from profile_switcher.manifest import ManifestError, parse_manifest

VALID = """
name = "caelestia"
compositor = "hyprland"
packages = ["caelestia-shell", "caelestia-cli", "quickshell-git"]
stow = ["caelestia"]
start = "caelestia shell -d"
stop = "caelestia shell -k"
claims = ["bar", "notifications", "tray"]
health = "qs -c caelestia ipc show"
health_timeout = 10

[hooks]
post_stow = "caelestia scheme set -n caelestia"
"""


def without(line_start: str) -> str:
    return "\n".join(l for l in VALID.splitlines() if not l.startswith(line_start))


def test_valid_manifest_parses():
    m = parse_manifest(VALID)
    assert m.name == "caelestia"
    assert m.stop == "caelestia shell -k"
    assert m.claims == ["bar", "notifications", "tray"]
    assert m.hooks["post_stow"] == "caelestia scheme set -n caelestia"


def test_missing_name_is_rejected():
    with pytest.raises(ManifestError, match="name"):
        parse_manifest(without("name"))


def test_missing_stop_is_rejected():
    with pytest.raises(ManifestError, match="stop"):
        parse_manifest(without("stop"))


def test_unknown_compositor_is_rejected():
    bad = VALID.replace('compositor = "hyprland"', 'compositor = "sway"')
    with pytest.raises(ManifestError, match="compositor"):
        parse_manifest(bad)
