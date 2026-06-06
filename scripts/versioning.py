from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "blender_manifest.toml"
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
MANIFEST_VERSION_RE = re.compile(r'(?m)^(version[^\S\r\n]*=[^\S\r\n]*")([^"]+)("[^\S\r\n]*)(\r?)$')


def parse_version(version: str) -> tuple[int, int, int]:
    match = VERSION_RE.fullmatch(version)
    if match is None:
        raise RuntimeError(f"Expected X.Y.Z version, got {version!r}")
    return tuple(int(part) for part in match.groups())


def format_version(parts: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in parts)


def read_manifest_version() -> str:
    with MANIFEST_PATH.open("rb") as handle:
        manifest = tomllib.load(handle)
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise RuntimeError(f"Missing string version in {MANIFEST_PATH}")
    parse_version(version)
    return version


def replace_once(path: Path, pattern: re.Pattern[str], replacement: str) -> None:
    text = path.read_text(encoding="utf-8", newline="")
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"Expected exactly one version field in {path}")
    path.write_text(text, encoding="utf-8", newline="")


def write_manifest_version(version: str) -> None:
    parse_version(version)
    replace_once(MANIFEST_PATH, MANIFEST_VERSION_RE, rf'\g<1>{version}\g<3>\g<4>')


def bump_patch() -> str:
    major, minor, patch = parse_version(read_manifest_version())
    version = format_version((major, minor, patch + 1))
    write_manifest_version(version)
    return version


def assert_version_matches_release_tag(release_tag: str | None = None) -> str:
    version = read_manifest_version()
    if release_tag is not None and release_tag != f"v{version}":
        raise RuntimeError(f"Release tag mismatch: expected v{version}, got {release_tag}")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Concept Art Tools versions.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("current")
    set_parser = subparsers.add_parser("set")
    set_parser.add_argument("version")
    subparsers.add_parser("bump-patch")
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--release-tag")
    args = parser.parse_args()

    if args.command == "current":
        print(read_manifest_version())
    elif args.command == "set":
        write_manifest_version(args.version)
        print(args.version)
    elif args.command == "bump-patch":
        print(bump_patch())
    elif args.command == "check":
        print(assert_version_matches_release_tag(args.release_tag))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())