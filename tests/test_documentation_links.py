from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_codex_plugin_layout", REPO_ROOT / "scripts/validate_codex_plugin_layout.py"
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class MarkdownLinksTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "README.md"
        patch = mock.patch.multiple(VALIDATOR, REPO_ROOT=self.root, errors=[])
        patch.start()
        self.addCleanup(patch.stop)

    def test_checks_local_links_and_reference_links_but_not_code_examples(self) -> None:
        (self.root / "SKILL.md").write_text("# Skill\n")
        (self.root / "with space.md").write_text("# Reference\n")
        self.path.write_text(
            "[Skill](SKILL.md#skill)\n"
            "[Reference](<with space.md>)\n"
            "[Encoded](with%20space.md)\n"
            "[Website](https://example.com/docs)\n"
            "[Section](#skills)\n"
            "`[example](not-a-file.md)`\n"
            "```markdown\n[example](also-not-a-file.md)\n```\n"
            "~~~markdown\n[example](another-example.md)\n~~~\n"
            "[Missing](missing-skill/SKILL.md)\n"
            "[Reference][missing]\n[missing]: deleted.md\n"
        )
        VALIDATOR.validate_markdown_links([self.path])
        self.assertEqual(len(VALIDATOR.errors), 2)
        self.assertIn("missing-skill/SKILL.md", VALIDATOR.errors[0])
        self.assertIn("deleted.md", VALIDATOR.errors[1])

    def test_ignores_shorter_fences_inside_a_long_fenced_example(self) -> None:
        self.path.write_text("````markdown\n```\n[example](not-a-file.md)\n```\n````\n")
        VALIDATOR.validate_markdown_links([self.path])
        self.assertEqual(VALIDATOR.errors, [])


if __name__ == "__main__":
    unittest.main()
