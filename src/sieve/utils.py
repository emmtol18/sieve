"""Shared utility functions for Neural Sieve."""

from pathlib import Path


def get_unique_path(dest: Path) -> Path:
    """Get a unique path by appending a counter if the file already exists.

    Args:
        dest: The desired destination path

    Returns:
        The original path if it doesn't exist, or a path with a counter suffix
    """
    if not dest.exists():
        return dest

    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    counter = 1

    while dest.exists():
        dest = parent / f"{stem}_{counter}{suffix}"
        counter += 1

    return dest
