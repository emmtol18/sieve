"""Capsule file writer."""

import shutil
from datetime import datetime
from pathlib import Path

from ..config import Settings
from .schema import Capsule


class CapsuleWriter:
    """Writes capsules to disk and manages assets."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def write(self, capsule: Capsule, original_file: Path | None = None) -> Path:
        """Write capsule to disk and copy original asset if provided.

        Returns the path to the created capsule file.
        """
        # Ensure category directory exists
        category_dir = self.settings.capsules_path / capsule.metadata.category
        category_dir.mkdir(parents=True, exist_ok=True)

        # Write capsule markdown
        capsule_path = category_dir / capsule.filename
        capsule_path.write_text(capsule.to_markdown(), encoding="utf-8")

        # Copy original asset if provided
        if original_file and original_file.exists():
            asset_path = self._copy_asset(original_file)
            # Update capsule with relative asset path
            rel_path = asset_path.relative_to(self.settings.vault_root)
            capsule.metadata.original_asset = str(rel_path)
            # Rewrite with updated asset path
            capsule_path.write_text(capsule.to_markdown(), encoding="utf-8")

        return capsule_path

    def _copy_asset(self, source: Path) -> Path:
        """Copy original file to Assets folder, organized by month."""
        month_dir = self.settings.assets_path / datetime.now().strftime("%Y-%m")
        month_dir.mkdir(parents=True, exist_ok=True)

        dest = month_dir / source.name

        # Handle name collision
        if dest.exists():
            stem = source.stem
            suffix = source.suffix
            counter = 1
            while dest.exists():
                dest = month_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        shutil.copy2(source, dest)
        return dest

    def move_to_legacy(self, capsule_path: Path) -> Path:
        """Move a capsule to the Legacy folder."""
        self.settings.legacy_path.mkdir(parents=True, exist_ok=True)
        dest = self.settings.legacy_path / capsule_path.name

        # Handle collision
        if dest.exists():
            stem = capsule_path.stem
            suffix = capsule_path.suffix
            counter = 1
            while dest.exists():
                dest = self.settings.legacy_path / f"{stem}_{counter}{suffix}"
                counter += 1

        shutil.move(capsule_path, dest)
        return dest
