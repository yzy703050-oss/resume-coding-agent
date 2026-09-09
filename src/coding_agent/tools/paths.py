"""Canonical repository path confinement."""

from pathlib import Path


class PathPolicyError(ValueError):
    pass


def resolve_confined(root: Path, relative_path: str | Path) -> Path:
    root = root.resolve(strict=True)
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise PathPolicyError("absolute paths are not allowed")
    try:
        resolved = (root / candidate).resolve(strict=False)
    except OSError as error:
        raise PathPolicyError(f"cannot resolve path: {relative_path}") from error
    if not resolved.is_relative_to(root):
        raise PathPolicyError("path escapes repository root")
    return resolved
