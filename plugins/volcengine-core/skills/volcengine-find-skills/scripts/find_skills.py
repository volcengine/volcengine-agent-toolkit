#!/usr/bin/env python3
"""List the Volcengine skills catalog and install exact skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = SKILL_ROOT / "references" / "catalog.json"
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

# When GitHub is unreachable, skills are installed from the toolkit package the
# release workflow publishes to the Volcengine CDN, unpacked to a local directory.
DEFAULT_TOOLKIT_BASE_URL = "https://cloudcache.volccdn.com/ve/skills"
TOOLKIT_MANIFEST_NAME = "toolkit-manifest.json"
GITHUB_PROBE_TIMEOUT_SECONDS = 10
DOWNLOAD_TIMEOUT_SECONDS = 300
MAX_TOOLKIT_BYTES = 50 * 1024 * 1024


def fail(message: str, code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_catalog() -> dict[str, Any]:
    try:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"catalog not found: {CATALOG_PATH}")
    except json.JSONDecodeError as exc:
        fail(f"invalid catalog JSON: {exc}")
    if catalog.get("schema_version") != 1 or not isinstance(
        catalog.get("plugins"), list
    ):
        fail("unsupported or malformed catalog")
    return catalog


def iter_records(catalog: dict[str, Any]):
    for plugin in catalog["plugins"]:
        for skill in plugin["skills"]:
            yield {
                **skill,
                "plugin": plugin["name"],
                "plugin_display_name": plugin["display_name"],
                "domain": plugin["domain"],
                "domain_en": plugin["domain_en"],
                "default_plugin": bool(plugin.get("default")),
            }


def plugin_by_name(catalog: dict[str, Any], name: str) -> dict[str, Any] | None:
    return next(
        (plugin for plugin in catalog["plugins"] if plugin["name"] == name), None
    )


def resolve_target(
    catalog: dict[str, Any], target: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    plugin = plugin_by_name(catalog, target)
    if plugin:
        records = [
            record for record in iter_records(catalog) if record["plugin"] == target
        ]
        return plugin, records
    exact = [record for record in iter_records(catalog) if record["name"] == target]
    if exact:
        owner = plugin_by_name(catalog, exact[0]["plugin"])
        assert owner is not None
        return owner, exact
    skill_names = ", ".join(record["name"] for record in iter_records(catalog))
    plugin_names = ", ".join(plugin["name"] for plugin in catalog["plugins"])
    fail(
        f"target must be an exact skill or plugin name: {target!r}\n"
        f"Valid skills: {skill_names}\n"
        f"Valid plugins: {plugin_names}"
    )


def resolve_skills(
    catalog: dict[str, Any], targets: list[str]
) -> list[dict[str, Any]]:
    records_by_name = {record["name"]: record for record in iter_records(catalog)}
    invalid = [target for target in targets if target not in records_by_name]
    if invalid:
        valid_names = ", ".join(records_by_name)
        fail(
            "install targets must be exact skill names; plugins are not install targets: "
            f"{', '.join(invalid)}\nValid skills: {valid_names}"
        )
    return [records_by_name[name] for name in dict.fromkeys(targets)]


def output_records(records: list[dict[str, Any]], as_json: bool) -> None:
    if as_json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return
    if not records:
        print("No Volcengine skills are catalogued.")
        return
    for record in records:
        print(
            f"{record['name']}\n"
            f"  domain: {record['domain']} / {record['domain_en']}\n"
            f"  plugin: {record['plugin']}\n"
            f"  {record['summary_zh']}"
        )


def run_json(
    command: list[str], attempts: int = 3
) -> tuple[subprocess.CompletedProcess[str], Any | None]:
    completed: subprocess.CompletedProcess[str] | None = None
    for _ in range(attempts):
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            return completed, None
        try:
            return completed, json.loads(completed.stdout)
        except json.JSONDecodeError:
            continue
    assert completed is not None
    return completed, None


def installed_skill_names(
    catalog: dict[str, Any], agent: str | None, scope: str
) -> set[str]:
    command = ["npx", "--yes", "skills", "list"]
    if scope == "global":
        command.append("--global")
    if agent:
        command.extend(["--agent", agent])

    completed, payload = run_json([*command, "--json"])
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        fail(f"unable to list installed skills: {detail}", completed.returncode)
    if isinstance(payload, list):
        return {
            item.get("name")
            for item in payload
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }

    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        fail(f"unable to list installed skills: {detail}", completed.returncode)
    catalog_names = {record["name"] for record in iter_records(catalog)}
    installed: set[str] = set()
    for raw_line in completed.stdout.splitlines():
        fields = ANSI_ESCAPE_RE.sub("", raw_line).split()
        if fields and fields[0] in catalog_names:
            installed.add(fields[0])
    return installed


def toolkit_base_url() -> str:
    return os.environ.get("VOLCENGINE_TOOLKIT_BASE_URL", DEFAULT_TOOLKIT_BASE_URL).rstrip("/")


def toolkit_dir() -> Path:
    configured = os.environ.get("VOLCENGINE_TOOLKIT_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".volcengine" / "agent-toolkit"


def is_toolkit_dir(path: Path) -> bool:
    return (path / ".claude-plugin" / "marketplace.json").is_file() and (
        path / "plugins" / "volcengine-core" / "skills"
    ).is_dir()


def local_toolkit_version(path: Path) -> str | None:
    if not is_toolkit_dir(path):
        return None
    try:
        version = json.loads((path / "package.json").read_text(encoding="utf-8")).get(
            "version"
        )
    except (OSError, json.JSONDecodeError):
        return None
    return version if isinstance(version, str) and version else None


def github_reachable(repository: str) -> bool:
    """Probe GitHub with a short timeout: it often stalls instead of refusing."""
    request = urllib.request.Request(
        f"https://github.com/{repository}", method="HEAD"
    )
    try:
        with urllib.request.urlopen(request, timeout=GITHUB_PROBE_TIMEOUT_SECONDS):
            return True
    except (OSError, ValueError):
        return False


def fetch_bytes(url: str, limit: int) -> bytes:
    with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"download is larger than {limit} bytes: {url}")
    return data


def extract_toolkit(archive_path: Path, destination: Path) -> None:
    root = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            target = (destination / info.filename).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"toolkit package entry escapes its root: {info.filename}")
            extracted = archive.extract(info, destination)
            mode = (info.external_attr >> 16) & 0o777
            if mode and not info.is_dir():
                os.chmod(extracted, mode)


def refresh_local_toolkit(target: Path) -> str:
    """Download the latest toolkit package into `target` and return its version.

    The package is verified against the manifest's SHA-256 and unpacked beside
    the target, so a failed download never replaces a working copy.
    """
    base_url = toolkit_base_url()
    manifest_url = f"{base_url}/latest/{TOOLKIT_MANIFEST_NAME}"
    manifest = json.loads(fetch_bytes(manifest_url, 1024 * 1024).decode("utf-8"))
    version = manifest.get("version")
    package = manifest.get("toolkit")
    if not isinstance(version, str) or not isinstance(package, dict):
        raise ValueError(f"malformed toolkit manifest: {manifest_url}")
    expected = str(package.get("sha256", "")).lower()
    url = str(package.get("url", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or not url:
        raise ValueError(f"toolkit manifest has no usable url and sha256: {manifest_url}")
    if "://" not in url:
        url = f"{base_url}/v{version}/{url}"
    if local_toolkit_version(target) == version:
        return version
    if target.exists() and not is_toolkit_dir(target) and (
        not target.is_dir() or any(target.iterdir())
    ):
        raise ValueError(
            f"{target} exists and is not a Volcengine toolkit directory; "
            "set VOLCENGINE_TOOLKIT_DIR to another location"
        )

    data = fetch_bytes(url, MAX_TOOLKIT_BYTES)
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ValueError(
            f"toolkit package checksum mismatch: expected {expected}, got {actual}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f"{target.name}.install.", dir=target.parent))
    previous = target.with_name(f"{target.name}.previous.{os.getpid()}")
    try:
        archive_path = staging / "toolkit.zip"
        archive_path.write_bytes(data)
        unpacked = staging / "unpacked"
        unpacked.mkdir()
        extract_toolkit(archive_path, unpacked)
        if not is_toolkit_dir(unpacked):
            raise ValueError("toolkit package does not contain the expected layout")
        if target.exists():
            shutil.rmtree(previous, ignore_errors=True)
            target.rename(previous)
        try:
            unpacked.rename(target)
        except OSError:
            if previous.exists():
                previous.rename(target)
            raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(previous, ignore_errors=True)
    return version


def resolve_install_source(catalog: dict[str, Any], source: str | None) -> str:
    """Pick where the skills CLI installs from: GitHub first, then the CDN copy."""
    if source:
        return source
    repository = catalog["repository"]
    if github_reachable(repository):
        return repository
    target = toolkit_dir()
    try:
        version = refresh_local_toolkit(target)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        stale = local_toolkit_version(target)
        if stale is None:
            fail(
                "GitHub is unreachable and the Volcengine CDN toolkit package could not be "
                f"installed: {exc}"
            )
        print(
            f"WARNING: GitHub and the Volcengine CDN are unreachable ({exc}); "
            f"installing from the local toolkit v{stale} at {target}",
            file=sys.stderr,
        )
        return str(target)
    print(
        f"GitHub is unreachable; installing from the Volcengine CDN toolkit v{version} "
        f"at {target}",
        file=sys.stderr,
    )
    return str(target)


def install_skills_cli(
    catalog: dict[str, Any],
    records: list[dict[str, Any]],
    agent: str | None,
    scope: str,
    source: str | None,
    dry_run: bool,
    as_json: bool,
) -> None:
    skill_names = [record["name"] for record in records]
    package_source = source or catalog["repository"]
    command = [
        "npx",
        "--yes",
        "skills",
        "add",
        package_source,
    ]
    if scope == "global":
        command.append("--global")
    command.extend(
        [
            "--yes",
            "--copy",
            "--full-depth",
            "--skill",
            *skill_names,
        ]
    )
    if agent:
        command.extend(["--agent", agent])
    if dry_run:
        payload = {
            "method": "skills",
            "skills": skill_names,
            "scope": scope,
            "source": package_source,
            "command": command,
        }
        print(
            json.dumps(payload, ensure_ascii=False, indent=2)
            if as_json
            else " ".join(command)
        )
        return
    if shutil.which("npx") is None:
        fail("npx executable not found; install Node.js to install skills")
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        fail(f"skills CLI install failed: {detail}", completed.returncode)

    installed_names = installed_skill_names(catalog, agent, scope)
    missing = sorted(set(skill_names) - installed_names)
    if missing:
        fail(
            f"skills CLI reported success but did not list installed skills: {', '.join(missing)}"
        )
    result = {
        "status": "installed",
        "method": "skills",
        "skills": skill_names,
        "agent": agent,
        "scope": scope,
        "source": package_source,
        "verified": True,
    }
    print(
        json.dumps(result, ensure_ascii=False, indent=2)
        if as_json
        else f"Installed: {', '.join(skill_names)}"
    )


def show_status(
    catalog: dict[str, Any], agent: str | None, scope: str, as_json: bool
) -> None:
    if shutil.which("npx") is None:
        fail("npx executable not found; install Node.js to inspect installed skills")
    installed_names = installed_skill_names(catalog, agent, scope)
    rows = [
        {
            "skill": record["name"],
            "plugin": record["plugin"],
            "domain": record["domain"],
            "state": (
                "installed"
                if record["name"] in installed_names
                else "not_installed"
            ),
        }
        for record in iter_records(catalog)
    ]
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"{row['skill']}: {row['state']} ({row['plugin']})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser(
        "list", help="List all catalogued skills for agent selection"
    )
    list_parser.add_argument("--json", action="store_true")

    info_parser = subparsers.add_parser("info", help="Show one exact skill or plugin")
    info_parser.add_argument("target")
    info_parser.add_argument("--json", action="store_true")

    install_parser = subparsers.add_parser(
        "install", help="Install one or more exact skills"
    )
    install_parser.add_argument("targets", nargs="+")
    install_parser.add_argument("--agent", help="Target agent name for skills CLI")
    install_parser.add_argument(
        "--scope",
        choices=("global", "project"),
        default="global",
        help="Installation scope for skills CLI",
    )
    install_parser.add_argument(
        "--source",
        help=(
            "Repository or reviewed local checkout for skills CLI; by default GitHub, "
            "or the Volcengine CDN toolkit package when GitHub is unreachable"
        ),
    )
    install_parser.add_argument("--dry-run", action="store_true")
    install_parser.add_argument("--json", action="store_true")

    status_parser = subparsers.add_parser(
        "status", help="Show catalogued skill installation status"
    )
    status_parser.add_argument("--agent", help="Target agent name for skills CLI")
    status_parser.add_argument(
        "--scope", choices=("global", "project"), default="global"
    )
    status_parser.add_argument("--json", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    catalog = load_catalog()
    if args.command == "list":
        output_records(list(iter_records(catalog)), args.json)
    elif args.command == "info":
        _, records = resolve_target(catalog, args.target)
        output_records(records, args.json)
    elif args.command == "install":
        records = resolve_skills(catalog, args.targets)
        install_skills_cli(
            catalog,
            records,
            args.agent,
            args.scope,
            # A dry run only prints the command, so it must not touch the network.
            args.source if args.dry_run else resolve_install_source(catalog, args.source),
            args.dry_run,
            args.json,
        )
    elif args.command == "status":
        show_status(catalog, args.agent, args.scope, args.json)


if __name__ == "__main__":
    main()
