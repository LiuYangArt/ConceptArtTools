from __future__ import annotations

import ast
from pathlib import Path

from versioning import assert_version_matches_release_tag


ROOT = Path(__file__).resolve().parents[1]


def iter_python_files():
    for path in ROOT.rglob("*.py"):
        if "__pycache__" not in path.parts:
            yield path


def main() -> int:
    assert_version_matches_release_tag()

    for path in iter_python_files():
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    print("Addon validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())