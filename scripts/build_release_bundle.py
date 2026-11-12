#!/usr/bin/env python3
"""Build the versioned release artifacts published to TOS.

Two artifacts are produced:

* the core Skill bundle consumed by Volcengine CLI (`ve skills update`);
* the full toolkit package, used as the installation source when GitHub is
  unreachable. It holds only what the hosts read at runtime.
"""

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = REPO_ROOT / "skills" / "core"
BUNDLE_NAME = "volcengine-skill-bundle.zip"
MAX_BUNDLE_BYTES = 50 * 1024 * 1024
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
TOOLKIT_NAME = "volcengine-agent-toolkit.zip"
TOOLKIT_MANIFEST_NAME = "toolkit-manifest.json"
# Runtime-only content: plugins and skills, the hooks they reference, the agent
# rules, and each host's marketplace or extension manifest. package.json carries
# the version the installer compares against.
TOOLKIT_PATHS = (
    ".agents",
    ".claude-plugin",
    ".cursor-plugin",
    ".opencode/INSTALL.md",
    ".opencode/opencode.json",
    ".opencode/plugin",
    "GEMINI.md",
    "LICENSE",
    "gemini-extension.json",
    "hooks",
    "openclaw.plugin.json",
    "package.json",
    "plugins",
    "rules",
    "skills",
)
EXCLUDED_NAMES = {"__pycache__", ".DS_Store", "node_modules"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
# The toolkit package is unpacked on Windows, macOS and Linux, so every path in
# it has to be valid on all three. The length limit leaves room under Windows'
# 260-character MAX_PATH for the user's home and the install directory.
MAX_ARCHIVE_PATH_LENGTH = 180
WINDOWS_FORBIDDEN_CHARS = re.compile(r'[<>:"|?*\\\x00-\x1f]')
WINDOWS_RESERVED_NAMES = re.compile(
    r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.IGNORECASE
)


def load_package_version():
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    version = package.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("package.json version must be a non-empty string")
    return version


def core_skill_directories():
    skills = sorted(path for path in CORE_ROOT.iterdir() if path.is_dir())
    if not skills:
        raise ValueError("skills/core must contain at least one Skill")
    return skills


def is_excluded(path, root):
    """Interpreter caches and OS metadata are build noise, not release content."""
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    return any(part in EXCLUDED_NAMES for part in path.relative_to(root).parts)


def release_files(root):
    files = []
    for path in sorted(root.rglob("*")):
        if is_excluded(path, root):
            continue
        if path.is_symlink():
            raise ValueError("symbolic links are not allowed in release bundle: %s" % path)
        if path.is_file():
            files.append(path)
    return files


def skill_files(skill_dir):
    files = release_files(skill_dir)
    if skill_dir / "SKILL.md" not in files:
        raise ValueError("missing SKILL.md in %s" % skill_dir)
    return files


def content_digest(skill_dir, files):
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(skill_dir).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def zip_external_attributes(path):
    executable = os.access(path, os.X_OK)
    mode = 0o755 if executable else 0o644
    return (stat.S_IFREG | mode) << 16


def write_zip_entry(archive, archive_path, path):
    info = zipfile.ZipInfo(archive_path.as_posix(), ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = zip_external_attributes(path)
    archive.writestr(info, path.read_bytes())


def build_bundle(bundle_path, skills):
    skill_entries = []
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for skill_dir in skills:
            files = skill_files(skill_dir)
            skill_entries.append(
                {
                    "name": skill_dir.name,
                    "sha256": content_digest(skill_dir, files),
                }
            )
            for path in files:
                archive_path = Path(skill_dir.name) / path.relative_to(skill_dir)
                write_zip_entry(archive, archive_path, path)
    return skill_entries


def validate_portable_paths(archive_paths):
    """Reject archive paths that cannot be created on every supported OS."""
    seen = {}
    for archive_path in archive_paths:
        if len(archive_path) > MAX_ARCHIVE_PATH_LENGTH:
            raise ValueError(
                "path is longer than %d characters and may exceed the Windows path limit: %s"
                % (MAX_ARCHIVE_PATH_LENGTH, archive_path)
            )
        for part in archive_path.split("/"):
            if (
                WINDOWS_FORBIDDEN_CHARS.search(part)
                or WINDOWS_RESERVED_NAMES.match(part)
                or part != part.rstrip(". ")
            ):
                raise ValueError("path is not valid on Windows: %s" % archive_path)
        folded = archive_path.lower()
        if folded in seen:
            raise ValueError(
                "paths differ only by case and collide on Windows and macOS: %s, %s"
                % (seen[folded], archive_path)
            )
        seen[folded] = archive_path


def toolkit_files(repo_root):
    files = []
    for name in TOOLKIT_PATHS:
        path = repo_root / name
        if path.is_symlink():
            raise ValueError("symbolic links are not allowed in toolkit package: %s" % path)
        if path.is_dir():
            files.extend(release_files(path))
        elif path.is_file():
            files.append(path)
        else:
            raise ValueError("missing toolkit path: %s" % name)
    return sorted(files)


def build_toolkit(toolkit_path, repo_root):
    """Zip the runtime content at the archive root, so it unpacks in place."""
    files = toolkit_files(repo_root)
    validate_portable_paths([path.relative_to(repo_root).as_posix() for path in files])
    with zipfile.ZipFile(toolkit_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            write_zip_entry(archive, path.relative_to(repo_root), path)


def validate_bundle_size(size):
    if size > MAX_BUNDLE_BYTES:
        raise ValueError(
            "release archive is larger than the 50 MiB download limit: %d bytes" % size
        )


def write_manifest(path, manifest):
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build_release(output_dir, version, cdn_base_url=None):
    package_version = load_package_version()
    if version and version != package_version:
        raise ValueError(
            "release version %s does not match package.json version %s"
            % (version, package_version)
        )
    version = package_version

    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = output_dir / BUNDLE_NAME
    skills = build_bundle(bundle_path, core_skill_directories())
    bundle_bytes = bundle_path.read_bytes()
    validate_bundle_size(len(bundle_bytes))
    bundle_sha256 = hashlib.sha256(bundle_bytes).hexdigest()
    manifest = {
        "schemaVersion": 1,
        "version": version,
        "bundle": {
            "file": BUNDLE_NAME,
            "sha256": bundle_sha256,
            "size": len(bundle_bytes),
            "url": BUNDLE_NAME,
        },
        "skills": skills,
    }
    manifest_path = output_dir / "manifest.json"
    write_manifest(manifest_path, manifest)

    cdn_manifest_path = None
    if cdn_base_url:
        cdn_manifest = dict(manifest)
        cdn_manifest["bundle"] = dict(manifest["bundle"])
        cdn_manifest["bundle"]["url"] = "%s/v%s/%s" % (
            cdn_base_url.rstrip("/"),
            version,
            BUNDLE_NAME,
        )
        cdn_manifest_path = output_dir / "cdn-manifest.json"
        write_manifest(cdn_manifest_path, cdn_manifest)
    return manifest_path, bundle_path, cdn_manifest_path


def build_toolkit_release(output_dir, cdn_base_url=None):
    """Build the toolkit package and its own manifest.

    The manifest is separate from the core bundle's, so the contract that
    Volcengine CLI reads stays untouched.
    """
    version = load_package_version()
    output_dir.mkdir(parents=True, exist_ok=True)
    toolkit_path = output_dir / TOOLKIT_NAME
    build_toolkit(toolkit_path, REPO_ROOT)
    toolkit_bytes = toolkit_path.read_bytes()
    validate_bundle_size(len(toolkit_bytes))
    manifest = {
        "schemaVersion": 1,
        "version": version,
        "toolkit": {
            "file": TOOLKIT_NAME,
            "sha256": hashlib.sha256(toolkit_bytes).hexdigest(),
            "size": len(toolkit_bytes),
            "url": TOOLKIT_NAME,
        },
    }
    manifest_path = output_dir / TOOLKIT_MANIFEST_NAME
    write_manifest(manifest_path, manifest)

    cdn_manifest_path = None
    if cdn_base_url:
        cdn_manifest = dict(manifest)
        cdn_manifest["toolkit"] = dict(manifest["toolkit"])
        cdn_manifest["toolkit"]["url"] = "%s/v%s/%s" % (
            cdn_base_url.rstrip("/"),
            version,
            TOOLKIT_NAME,
        )
        cdn_manifest_path = output_dir / ("cdn-" + TOOLKIT_MANIFEST_NAME)
        write_manifest(cdn_manifest_path, cdn_manifest)
    return manifest_path, toolkit_path, cdn_manifest_path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--version")
    parser.add_argument("--cdn-base-url")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        manifest_path, bundle_path, cdn_manifest_path = build_release(
            args.output_dir, args.version, args.cdn_base_url
        )
        toolkit_outputs = build_toolkit_release(args.output_dir, args.cdn_base_url)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print("build release bundle failed: %s" % error, file=sys.stderr)
        return 1
    print(manifest_path)
    print(bundle_path)
    if cdn_manifest_path:
        print(cdn_manifest_path)
    for path in toolkit_outputs:
        if path:
            print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
