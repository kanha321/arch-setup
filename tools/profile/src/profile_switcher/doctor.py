from __future__ import annotations


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
