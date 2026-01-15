#!/usr/bin/env python3
"""Setup script to fix UV editable install.

UV's virtual environments don't process .pth files properly with hatchling,
so we use sitecustomize.py to add the src directory to sys.path.

Usage: python scripts/setup_venv.py
"""

import sys
from pathlib import Path


SITECUSTOMIZE_CONTENT = '''\
"""Add src directory to path for neural-sieve editable install."""
import sys
from pathlib import Path

# Add the src directory for neural-sieve editable install
src_path = Path(__file__).parent.parent.parent.parent.parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
'''


def main():
    """Setup sitecustomize.py in the current virtual environment."""
    # Find site-packages directory
    site_packages = None
    for path in sys.path:
        if "site-packages" in path:
            site_packages = Path(path)
            break

    if not site_packages:
        print("Error: Could not find site-packages directory")
        print("Make sure you're running this from within the venv:")
        print("  .venv/bin/python scripts/setup_venv.py")
        return 1

    sitecustomize_path = site_packages / "sitecustomize.py"

    # Check if it already exists with our content
    if sitecustomize_path.exists():
        existing = sitecustomize_path.read_text()
        if "neural-sieve" in existing:
            print(f"Already configured: {sitecustomize_path}")
            return 0
        # Append to existing
        print(f"Appending to: {sitecustomize_path}")
        with open(sitecustomize_path, "a") as f:
            f.write("\n" + SITECUSTOMIZE_CONTENT)
    else:
        print(f"Creating: {sitecustomize_path}")
        sitecustomize_path.write_text(SITECUSTOMIZE_CONTENT)

    print("Done! The 'uv run sieve' command should now work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
