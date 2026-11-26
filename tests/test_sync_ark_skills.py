from __future__ import annotations

import importlib.util
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SYNC_PATH = REPO_ROOT / "scripts" / "sync_ark_skills.py"
SPEC = importlib.util.spec_from_file_location("sync_ark_skills", SYNC_PATH)
assert SPEC and SPEC.loader
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)

SKILL_DIR = REPO_ROOT / "plugins" / "volcengine-ark" / "skills" / "volcengine-ark"
REFERENCES = SKILL_DIR / "references"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class VendorTransformTest(unittest.TestCase):
    """Run the sync against a small stand-in for the upstream repository."""

    def setUp(self) -> None:
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        root = Path(self.scratch.name)
        self.upstream = root / "ark-cli"
        skills = self.upstream / "skills"
        write(
            skills / "arkcli-models" / "SKILL.md",
            "---\n"
            "name: arkcli-models\n"
            "version: 1.2.3\n"
            'description: "List and search models。More detail follows."\n'
            "---\n\n"
            "Read [`../arkcli-shared/SKILL.md`](../arkcli-shared/SKILL.md) first.\n"
            "Install with [connect](../arkcli-connect/SKILL.md) and see [docs](../arkcli-docs/SKILL.md).\n"
            "See [search](references/search.md).\n\n"
            "```bash\n"
            "arkcli +chat --model ep-20250102030405-ab1cd hello\n"
            "echo '[kept](../arkcli-connect/SKILL.md)'\n"
            "```\n",
        )
        write(
            skills / "arkcli-models" / "references" / "search.md",
            "Back to [the skill](../SKILL.md) and [shared](../../arkcli-shared/SKILL.md).\n",
        )
        write(
            skills / "arkcli-shared" / "SKILL.md",
            "---\nname: arkcli-shared\nversion: 2.0.0\ndescription: Shared rules\n---\n\nRules.\n",
        )
        write(skills / "arkcli-connect" / "SKILL.md", "---\nname: arkcli-connect\n---\n")
        write(skills / "arkcli-docs" / "SKILL.md", "---\nname: arkcli-docs\n---\n")
        write(skills / "arkcli-shared" / "assets" / "data.bin", "")
        (skills / "arkcli-shared" / "assets" / "data.bin").write_bytes(b"\xff\xfe\x00binary")
        write(self.upstream / "LICENSE", "Apache License\n")
        for command in (
            ["init", "-q"],
            ["add", "-A"],
            [
                "-c", "user.name=test", "-c", "user.email=test@example.com",
                "commit", "-q", "-m", "fixture",
            ],
        ):
            subprocess.run(["git", "-C", str(self.upstream), *command], check=True)
        self.commit = subprocess.run(
            ["git", "-C", str(self.upstream), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.target = root / "references"
        SYNC.build(self.upstream, self.target)

    def test_entry_files_become_guides(self) -> None:
        self.assertFalse(list(self.target.rglob("SKILL.md")))
        self.assertTrue((self.target / "arkcli-models" / "GUIDE.md").is_file())
        self.assertTrue((self.target / "arkcli-shared" / "GUIDE.md").is_file())
        self.assertTrue((self.target / "arkcli-models" / "references" / "search.md").is_file())

    def test_links_between_guides_still_resolve(self) -> None:
        guide = (self.target / "arkcli-models" / "GUIDE.md").read_text(encoding="utf-8")
        self.assertIn("[`../arkcli-shared/GUIDE.md`](../arkcli-shared/GUIDE.md)", guide)
        reference = (self.target / "arkcli-models" / "references" / "search.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("[the skill](../GUIDE.md)", reference)
        self.assertIn("[shared](../../arkcli-shared/GUIDE.md)", reference)

    def test_excluded_skills_are_left_out_and_their_links_reduced_to_text(self) -> None:
        for name in SYNC.EXCLUDED_SKILLS:
            self.assertFalse((self.target / name).exists(), name)
        guide = (self.target / "arkcli-models" / "GUIDE.md").read_text(encoding="utf-8")
        self.assertIn("Install with connect and see docs.", guide)
        # A link inside a fenced example is not navigation and stays as written.
        self.assertIn("echo '[kept](../arkcli-connect/GUIDE.md)'", guide)

    def test_endpoint_ids_are_replaced_with_the_placeholder(self) -> None:
        guide = (self.target / "arkcli-models" / "GUIDE.md").read_text(encoding="utf-8")
        self.assertNotIn("ep-20250102030405-ab1cd", guide)
        self.assertIn(f"--model {SYNC.ENDPOINT_ID_PLACEHOLDER} hello", guide)

    def test_binary_files_are_copied_unchanged(self) -> None:
        self.assertEqual(
            (self.target / "arkcli-shared" / "assets" / "data.bin").read_bytes(),
            b"\xff\xfe\x00binary",
        )

    def test_provenance_records_commit_license_and_guides(self) -> None:
        provenance = (self.target / SYNC.PROVENANCE_NAME).read_text(encoding="utf-8")
        self.assertIn(self.commit, provenance)
        self.assertIn("| [arkcli-models](arkcli-models/GUIDE.md) | 1.2.3 | List and search models |", provenance)
        self.assertIn("`arkcli-connect` is not vendored", provenance)
        self.assertEqual((self.target / SYNC.LICENSE_NAME).read_text(encoding="utf-8"), "Apache License\n")

    def test_repeated_runs_produce_the_same_tree(self) -> None:
        again = Path(self.scratch.name) / "again"
        SYNC.build(self.upstream, again)
        self.assertEqual(SYNC.tree(self.target), SYNC.tree(again))


class VendoredTreeTest(unittest.TestCase):
    """Check the committed guides without needing the upstream repository."""

    def test_only_the_skill_itself_has_an_entry_file(self) -> None:
        self.assertEqual(list(REFERENCES.rglob("SKILL.md")), [])
        self.assertTrue((SKILL_DIR / "SKILL.md").is_file())

    def test_provenance_lists_exactly_the_vendored_guides(self) -> None:
        provenance = (REFERENCES / SYNC.PROVENANCE_NAME).read_text(encoding="utf-8")
        listed = set(re.findall(r"^\| \[(arkcli-[a-z-]+)\]\(", provenance, re.MULTILINE))
        vendored = {path.name for path in REFERENCES.iterdir() if path.is_dir()}
        self.assertEqual(listed, vendored)
        self.assertTrue(vendored.isdisjoint(SYNC.EXCLUDED_SKILLS))
        self.assertRegex(provenance, r"Commit: `[0-9a-f]{40}`")
        for name in vendored:
            self.assertTrue((REFERENCES / name / SYNC.GUIDE_NAME).is_file(), name)

    def test_entry_file_links_point_at_vendored_guides(self) -> None:
        entry = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        targets = re.findall(r"\]\((references/[^)#]+)", entry)
        self.assertGreater(len(targets), 20)
        for target in targets:
            self.assertTrue((SKILL_DIR / target).is_file(), target)
        self.assertNotIn("arkcli-docs", entry.replace("`arkcli docs`", ""))

    def test_no_account_endpoint_ids_are_published(self) -> None:
        pattern = SYNC.ENDPOINT_ID_RE
        for path in REFERENCES.rglob("*"):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            found = set(pattern.findall(text)) - {SYNC.ENDPOINT_ID_PLACEHOLDER}
            self.assertEqual(found, set(), path.relative_to(REPO_ROOT).as_posix())


if __name__ == "__main__":
    unittest.main()
