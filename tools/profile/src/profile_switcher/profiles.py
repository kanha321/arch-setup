from __future__ import annotations

from pathlib import Path

from profile_switcher.manifest import Manifest, ManifestError, parse_manifest


def load_manifests(dotfiles: Path) -> dict[str, Manifest]:
    out: dict[str, Manifest] = {}
    for toml in sorted((dotfiles / "profiles").glob("*/profile.toml")):
        m = parse_manifest(toml.read_text())
        if m.name != toml.parent.name:
            raise ManifestError(f"{toml}: name {m.name!r} does not match its directory")
        out[m.name] = m
    return out
