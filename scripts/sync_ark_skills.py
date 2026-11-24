#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: MIT
"""Vendor the official Ark CLI skills into the volcengine-ark skill.

The upstream repository (volcengine/ark-cli) ships one skill per arkcli
capability. This toolkit exposes them as a single `volcengine-ark` skill, so the
upstream skills become guides under its `references/` directory:

    <upstream>/skills/arkcli-models/SKILL.md
        -> references/arkcli-models/GUIDE.md
    <upstream>/skills/arkcli-models/references/*.md
        -> references/arkcli-models/references/*.md

The sibling layout is kept, so every relative link between upstream skills
still resolves. Only four things change:

* `SKILL.md` is renamed to `GUIDE.md` and mentions of it are rewritten and Markdown files end with a single newline, because
  a nested `SKILL.md` would be discovered as a second, unprefixed skill.
* Skills listed in EXCLUDED_SKILLS are left out.
* Local Markdown links whose target is not vendored are reduced to their text.
* Endpoint IDs in examples are replaced with one placeholder.

Usage:
    git clone https://github.com/volcengine/ark-cli /tmp/ark-cli
    python3 scripts/sync_ark_skills.py --upstream /tmp/ark-cli
    python3 scripts/sync_ark_skills.py --upstream /tmp/ark-cli --check
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "plugins" / "volcengine-ark" / "skills" / "volcengine-ark"
TARGET = SKILL_DIR / "references"
UPSTREAM_URL = "https://github.com/volcengine/ark-cli"
UPSTREAM_PREFIX = "arkcli-"
ENTRY_NAME = "SKILL.md"
GUIDE_NAME = "GUIDE.md"
PROVENANCE_NAME = "UPSTREAM.md"
LICENSE_NAME = "LICENSE"
# arkcli-connect installs the upstream skills into every local agent and removes
# skills it considers conflicting. The toolkit distributes skills itself.
EXCLUDED_SKILLS = {
    "arkcli-connect": "installs upstream skills into local agents; the toolkit distributes skills",
    # Documentation questions have one owner in this toolkit: volcengine-knowledge-search.
    "arkcli-docs": "documentation lookup belongs to the volcengine-knowledge-search skill",
}
IGNORED_NAMES = {".DS_Store", "__pycache__"}
# Upstream examples carry endpoint IDs copied from real accounts. This repository
# does not publish resource IDs, so they become one format-preserving placeholder.
ENDPOINT_ID_RE = re.compile(r"\bep-\d{14}-[a-z0-9]{5}\b")
ENDPOINT_ID_PLACEHOLDER = "ep-20260101000000-xxxxx"
LINK_RE = re.compile(r"(?<!!)\[([^\]\n]*)\]\(\s*(<[^>\n]+>|[^\s)]+)(?:\s+\"[^\"\n]*\")?\s*\)")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def git(upstream: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(upstream), *args], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed in {upstream}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def upstream_skills(upstream: Path) -> list[Path]:
    skills_root = upstream / "skills"
    if not skills_root.is_dir():
        raise SystemExit(f"{upstream} has no skills/ directory")
    found = sorted(
        path
        for path in skills_root.iterdir()
        if path.is_dir()
        and path.name.startswith(UPSTREAM_PREFIX)
        and (path / ENTRY_NAME).is_file()
    )
    if not found:
        raise SystemExit(f"no {UPSTREAM_PREFIX}* skills found under {skills_root}")
    return found


def frontmatter_field(text: str, field: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---\n", 4)
    if end < 0:
        return ""
    match = re.search(rf"^{re.escape(field)}:\s*(.+)$", text[4:end], re.MULTILINE)
    if not match:
        return ""
    return match.group(1).strip().strip("\"'")


def short_description(description: str, limit: int = 110) -> str:
    """First clause of an upstream description, for the generated index."""
    head = re.split(r"[。；;]|\.\s", description, maxsplit=1)[0].strip()
    head = head.replace("|", "/")
    return head if len(head) <= limit else head[: limit - 1].rstrip() + "…"


def copy_skill(source: Path, destination: Path) -> None:
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in IGNORED_NAMES for part in relative.parts):
            continue
        if path.is_symlink():
            raise SystemExit(f"upstream skill contains a symlink: {path}")
        if path.is_dir():
            continue
        if relative.name == GUIDE_NAME:
            raise SystemExit(f"upstream already has a {GUIDE_NAME}: {path}")
        target = destination / relative
        if relative == Path(ENTRY_NAME):
            target = destination / GUIDE_NAME
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copyfile(path, target)
            continue
        text = ENDPOINT_ID_RE.sub(ENDPOINT_ID_PLACEHOLDER, text)
        if path.suffix.lower() == ".md":
            text = text.replace(ENTRY_NAME, GUIDE_NAME).rstrip("\n") + "\n"
        target.write_text(text, encoding="utf-8")


def delink_missing_targets(root: Path) -> list[str]:
    """Reduce local links with no vendored target to plain text.

    Fenced code is left alone: a link there is an example, not navigation.
    """
    changed: list[str] = []
    for path in sorted(root.rglob("*.md")):
        lines = path.read_text(encoding="utf-8").split("\n")
        fence = None
        dirty = False
        for index, line in enumerate(lines):
            marker = FENCE_RE.match(line)
            if marker:
                token = marker.group(1)
                if fence is None:
                    fence = token
                elif token[0] == fence[0] and len(token) >= len(fence):
                    fence = None
                continue
            if fence is not None:
                continue

            def replace(match: re.Match[str]) -> str:
                target = match.group(2).removeprefix("<").removesuffix(">")
                parts = urlsplit(target)
                if parts.scheme or target.startswith(("#", "/")):
                    return match.group(0)
                local = unquote(parts.path)
                if not local or (path.parent / local).exists():
                    return match.group(0)
                changed.append(f"{path.relative_to(root).as_posix()}: {target}")
                return match.group(1)

            updated = LINK_RE.sub(replace, line)
            if updated != line:
                lines[index] = updated
                dirty = True
        if dirty:
            path.write_text("\n".join(lines), encoding="utf-8")
    return changed


def provenance(
    commit: str, commit_date: str, guides: list[tuple[str, str, str]], delinked: list[str]
) -> str:
    lines = [
        "# Upstream provenance",
        "",
        "Everything in this directory except this file is generated by",
        "`scripts/sync_ark_skills.py` from the official Ark CLI skills. Do not edit the",
        "guides here: change them upstream, then run the script again.",
        "",
        f"- Source: [{UPSTREAM_URL.removeprefix('https://github.com/')}]({UPSTREAM_URL}/tree/{commit}/skills)",
        f"- Commit: `{commit}` ({commit_date})",
        f"- License: Apache-2.0, see [{LICENSE_NAME}]({LICENSE_NAME})",
        "",
        "## Changes made while vendoring",
        "",
        f"- Each upstream `skills/<name>/{ENTRY_NAME}` is stored as `<name>/{GUIDE_NAME}`, and",
        f"  mentions of `{ENTRY_NAME}` in the guides are rewritten to `{GUIDE_NAME}`.",
        "- Markdown files end with a single newline.",
        "- Local Markdown links whose target is not vendored are reduced to their text.",
        f"- Endpoint IDs in examples are replaced with the placeholder `{ENDPOINT_ID_PLACEHOLDER}`.",
    ]
    for name, reason in sorted(EXCLUDED_SKILLS.items()):
        lines.append(f"- `{name}` is not vendored: {reason}.")
    lines += [
        "",
        "Command examples keep the upstream `arkcli ...` form. `SKILL.md` of this skill",
        "says how to run them through `ve`.",
        "",
        "## Guides",
        "",
        "| Guide | Upstream version | Covers |",
        "| --- | --- | --- |",
    ]
    for name, version, description in guides:
        lines.append(
            f"| [{name}]({name}/{GUIDE_NAME}) | {version or '-'} | {description or '-'} |"
        )
    if delinked:
        lines += ["", "## Links reduced to text", ""]
        lines += [f"- `{entry}`" for entry in delinked]
    return "\n".join(lines) + "\n"


def build(upstream: Path, destination: Path) -> None:
    commit = git(upstream, "rev-parse", "HEAD")
    commit_date = git(upstream, "log", "-1", "--format=%cs")
    license_path = upstream / "LICENSE"
    if not license_path.is_file():
        raise SystemExit(f"{upstream} has no LICENSE file")

    destination.mkdir(parents=True, exist_ok=True)
    guides: list[tuple[str, str, str]] = []
    for skill in upstream_skills(upstream):
        if skill.name in EXCLUDED_SKILLS:
            continue
        copy_skill(skill, destination / skill.name)
        entry = (skill / ENTRY_NAME).read_text(encoding="utf-8")
        guides.append(
            (
                skill.name,
                frontmatter_field(entry, "version"),
                short_description(frontmatter_field(entry, "description")),
            )
        )
    shutil.copyfile(license_path, destination / LICENSE_NAME)
    delinked = delink_missing_targets(destination)
    (destination / PROVENANCE_NAME).write_text(
        provenance(commit, commit_date, guides, delinked), encoding="utf-8"
    )
    if list(destination.rglob(ENTRY_NAME)):
        raise SystemExit(f"a nested {ENTRY_NAME} survived the sync")


def tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not any(part in IGNORED_NAMES for part in path.parts)
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--upstream", required=True, type=Path, help="local clone of volcengine/ark-cli"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the vendored guides differ from what this clone produces",
    )
    args = parser.parse_args()
    upstream = args.upstream.expanduser().resolve()

    with tempfile.TemporaryDirectory(prefix="ark-skills-") as scratch:
        staged = Path(scratch) / "references"
        build(upstream, staged)
        if args.check:
            current = tree(TARGET) if TARGET.is_dir() else {}
            expected = tree(staged)
            stale = sorted(
                name
                for name in current.keys() | expected.keys()
                if current.get(name) != expected.get(name)
            )
            if stale:
                print(f"{TARGET.relative_to(REPO_ROOT)} is stale:", file=sys.stderr)
                for name in stale[:40]:
                    print(f"  {name}", file=sys.stderr)
                raise SystemExit(1)
            print(f"{TARGET.relative_to(REPO_ROOT)} matches {upstream}")
            return
        if not SKILL_DIR.is_dir():
            raise SystemExit(f"missing skill directory: {SKILL_DIR}")
        if TARGET.exists():
            shutil.rmtree(TARGET)
        shutil.copytree(staged, TARGET)
    print(f"vendored {len(list(TARGET.glob(UPSTREAM_PREFIX + '*')))} guides into {TARGET.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
