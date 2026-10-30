from __future__ import annotations

import re
from pathlib import Path

# claim name -> daemons that provide it (matched on "exec" lines in common)
CLAIM_DAEMONS = {
    "notifications": ("mako", "dunst", "swaync", "fnott"),
    "bar": ("waybar", "hyprpanel", "eww"),
    "lock": ("hyprlock", "swaylock"),
    "idle": ("hypridle", "swayidle"),
    "polkit": (
        "hyprpolkitagent",
        "polkit-gnome-authentication-agent-1",
        "polkit-kde-authentication-agent-1",
        "lxqt-policykit-agent",
    ),
    "wallpaper": ("hyprpaper", "swww-daemon", "swww", "swaybg", "wpaperd"),
}


def find_overlaps(files: dict[str, set[str]]) -> dict[str, list[str]]:
    owners: dict[str, list[str]] = {}
    for package, paths in files.items():
        for path in paths:
            owners.setdefault(path, []).append(package)
    return {p: sorted(o) for p, o in owners.items() if len(o) > 1}


def list_stow_files(root):
    files: set[str] = set()
    if not root.is_dir():
        return files
    for pkg in sorted(root.iterdir()):
        if pkg.is_dir():
            files |= {str(f.relative_to(pkg)) for f in pkg.rglob("*") if not f.is_dir()}
    return files


def stray_files(stow_root: Path, home: Path) -> list[str]:
    """Paths the stow packages want to link where a real file or dir already sits."""
    stray = []
    for rel in sorted(list_stow_files(stow_root)):
        target = home / rel
        if target.is_symlink():
            continue
        if target.exists():
            stray.append(rel)
    return stray


def read_text_files(root: Path) -> str:
    if not root.is_dir():
        return ""
    chunks = []
    for f in sorted(root.rglob("*")):
        if f.is_file() and not f.is_symlink():
            try:
                chunks.append(f.read_text())
            except (UnicodeDecodeError, OSError):
                continue
    return "\n".join(chunks)


def find_claim_conflicts(claims: dict[str, list[str]], common_text: str) -> list[str]:
    lines = [ln for ln in common_text.splitlines() if "exec" in ln]
    out = []
    for claim, daemons in CLAIM_DAEMONS.items():
        owners = sorted(n for n, c in claims.items() if claim in c)
        if not owners:
            continue
        for daemon in daemons:
            pattern = rf"(?<![\w-]){re.escape(daemon)}(?![\w-])"
            if any(re.search(pattern, ln) for ln in lines):
                who = ", ".join(owners)
                out.append(f"common autostarts {daemon} ({claim}), also claimed by: {who}")
    return out
