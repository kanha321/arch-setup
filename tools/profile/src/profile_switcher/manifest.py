from __future__ import annotations

import tomllib
from dataclasses import dataclass, field

COMPOSITORS = {"hyprland"}
REQUIRED = ("name", "compositor", "start", "stop")


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Manifest:
    name: str
    compositor: str
    start: str
    stop: str
    packages: list[str] = field(default_factory=list)
    stow: list[str] = field(default_factory=list)
    claims: list[str] = field(default_factory=list)
    health: str | None = None
    health_timeout: int = 10
    hooks: dict[str, str] = field(default_factory=dict)


def parse_manifest(text: str) -> Manifest:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ManifestError(f"invalid TOML: {e}") from e

    for key in REQUIRED:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ManifestError(f"missing or empty field: {key}")

    compositor = data["compositor"]
    if compositor not in COMPOSITORS:
        raise ManifestError(f"unknown compositor: {compositor!r}")

    return Manifest(
        name=data["name"],
        compositor=compositor,
        start=data["start"],
        stop=data["stop"],
        packages=list(data.get("packages", [])),
        stow=list(data.get("stow", [])),
        claims=list(data.get("claims", [])),
        health=data.get("health"),
        health_timeout=int(data.get("health_timeout", 10)),
        hooks=dict(data.get("hooks", {})),
    )
