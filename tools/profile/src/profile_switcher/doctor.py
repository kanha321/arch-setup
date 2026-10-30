from __future__ import annotations


def find_overlaps(files: dict[str, set[str]]) -> dict[str, list[str]]:
    owners: dict[str, list[str]] = {}
    for package, paths in files.items():
        for path in paths:
            owners.setdefault(path, []).append(package)
    return {p: sorted(o) for p, o in owners.items() if len(o) > 1}
