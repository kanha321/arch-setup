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
    process: str | None = None
    dbus_names: list[str] = field(default_factory=list)
    stop_timeout: int = 5
    resume_wait: int = 10


def _str_list(data: dict, key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ManifestError(f"{key} must be a list of strings")
    return list(value)


def _positive_int(data: dict, key: str, default: int) -> int:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ManifestError(f"{key} must be a positive integer")
    return value


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
        packages=_str_list(data, "packages"),
        stow=_str_list(data, "stow"),
        claims=_str_list(data, "claims"),
        health=data.get("health"),
        health_timeout=_positive_int(data, "health_timeout", 10),
        hooks=dict(data.get("hooks", {})),
        process=data.get("process"),
        dbus_names=_str_list(data, "dbus_names"),
        stop_timeout=_positive_int(data, "stop_timeout", 5),
        resume_wait=_positive_int(data, "resume_wait", 10),
    )
