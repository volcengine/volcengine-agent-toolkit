from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SYNC_PATH = REPO_ROOT / "scripts" / "sync_plugins.py"
SPEC = importlib.util.spec_from_file_location("sync_plugins", SYNC_PATH)
assert SPEC and SPEC.loader
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


class SyncCatalogSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = json.loads(SYNC.CATALOG_PATH.read_text(encoding="utf-8"))

    def assert_rejected(self, catalog: dict) -> None:
        with self.assertRaises(ValueError):
            SYNC.validate_catalog(catalog)

    def test_current_catalog_is_safe(self) -> None:
        SYNC.validate_catalog(self.catalog)

    def test_plugin_path_traversal_is_rejected(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["plugins"][1]["name"] = "foo/../volcengine-skills"
        self.assert_rejected(catalog)

    def test_plugin_without_required_prefix_is_rejected(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["plugins"][1]["name"] = "storage"
        self.assert_rejected(catalog)

    def test_skill_path_traversal_is_rejected(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["plugins"][1]["skills"][0]["name"] = "../../escaped"
        self.assert_rejected(catalog)

    def test_source_path_traversal_is_rejected(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["plugins"][1]["skills"][0]["path"] = "skills/../README.md"
        self.assert_rejected(catalog)

    def test_optional_skill_must_be_owned_by_its_plugin(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["plugins"][1]["skills"][0]["path"] = "skills/core/volcengine-tosutil"
        self.assert_rejected(catalog)

    def test_core_skill_must_live_in_core(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["plugins"][0]["skills"][0]["path"] = (
            "plugins/volcengine-core/skills/volcengine-cli"
        )
        self.assert_rejected(catalog)

    def test_only_volcengine_core_may_be_default(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["plugins"][0]["default"] = False
        catalog["plugins"][1]["default"] = True
        self.assert_rejected(catalog)

    def test_duplicate_plugin_is_rejected(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["plugins"].append(copy.deepcopy(catalog["plugins"][1]))
        self.assert_rejected(catalog)

    def test_output_outside_repository_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SYNC.ensure_safe_output(REPO_ROOT.parent / "outside-volcengine-sync.json")


class SpecializedSyncTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "skills/core").mkdir(parents=True)
        self.source = self.root / "plugins/volcengine-database/skills/volcengine-db-example"
        (self.source / "references").mkdir(parents=True)
        (self.source / "SKILL.md").write_text("# Database\n")
        (self.source / "references/usage.md").write_text("Database usage\n")
        (self.source / "run.sh").write_text("#!/bin/sh\nexit 0\n")
        (self.source / "run.sh").chmod(0o755)
        self.target = self.root / "skills/specialized/database/volcengine-db-example"
        self.catalog = {"plugins": [
            {"name": "volcengine-core", "default": True, "skills": []},
            {"name": "volcengine-database", "default": False, "skills": [
                {"name": "volcengine-db-example", "path": self.source.relative_to(self.root).as_posix()}
            ]},
        ]}
        patches = mock.patch.multiple(SYNC, REPO_ROOT=self.root, PLUGINS_ROOT=self.root / "plugins")
        patches.start()
        self.addCleanup(patches.stop)

    def sync(self, check: bool = False) -> list[str]:
        mismatches = []
        SYNC.sync_specialized_skill_tree(self.catalog, check, mismatches)
        return mismatches

    def test_copies_complete_skill_and_preserves_sources_and_executable_mode(self) -> None:
        before = SYNC.tree_hashes(self.source)
        self.assertEqual(self.sync(), [])
        self.assertEqual(SYNC.tree_hashes(self.target), before)
        self.assertEqual(SYNC.tree_hashes(self.source), before)
        self.assertEqual((self.target / "run.sh").stat().st_mode & 0o777, 0o755)
        self.assertFalse((self.root / "skills/specialized/core").exists())
        self.assertEqual(self.sync(check=True), [])

    def test_check_detects_missing_stale_and_extra_files_without_writing(self) -> None:
        self.assertTrue(self.sync(check=True))
        self.assertFalse(self.target.exists())
        self.sync()
        (self.target / "SKILL.md").write_text("stale\n")
        (self.target / "references/usage.md").unlink()
        (self.target / "extra.md").write_text("extra\n")
        (self.root / "skills/specialized/wrong-category").mkdir()
        before = SYNC.tree_hashes(self.root)
        mismatches = "\n".join(self.sync(check=True))
        for expected in ("SKILL.md", "usage.md", "extra.md", "categories"):
            self.assertIn(expected, mismatches)
        self.assertEqual(SYNC.tree_hashes(self.root), before)
        self.sync()
        self.assertEqual(self.sync(check=True), [])
        self.assertFalse((self.root / "skills/specialized/wrong-category").exists())

    def test_source_update_and_removal_propagate_without_changing_source(self) -> None:
        self.sync()
        (self.source / "references/usage.md").unlink()
        (self.source / "SKILL.md").write_text("Updated database\n")
        self.assertTrue(self.sync(check=True))
        self.sync()
        self.assertFalse((self.target / "references/usage.md").exists())
        self.assertEqual((self.target / "SKILL.md").read_text(), "Updated database\n")
        self.catalog["plugins"][1]["skills"] = []
        self.sync()
        self.assertFalse(self.target.exists())
        self.assertTrue((self.source / "SKILL.md").is_file())

    def test_rejects_symlink_destinations_and_ancestors_without_touching_source(self) -> None:
        for nested in (False, True):
            with self.subTest(nested=nested):
                destination = self.root / "skills/specialized"
                if nested:
                    destination.mkdir()
                    link = destination / "database"
                else:
                    link = destination
                link.symlink_to(self.source, target_is_directory=True)
                for check in (False, True):
                    with self.assertRaises(ValueError):
                        self.sync(check)
                self.assertEqual((self.source / "SKILL.md").read_text(), "# Database\n")
                link.unlink()
                if nested:
                    destination.rmdir()
        (self.root / "skills/core").rmdir()
        (self.root / "skills").rmdir()
        (self.root / "skills").symlink_to(self.root / "plugins", target_is_directory=True)
        with self.assertRaises(ValueError):
            self.sync()

    def test_rejects_foreign_sources_and_source_symlinks(self) -> None:
        record = self.catalog["plugins"][1]["skills"][0]
        original = record["path"]
        record["path"] = "skills/core/volcengine-db-example"
        with self.assertRaises(ValueError):
            self.sync()
        record["path"] = original
        (self.source / "references/linked.md").symlink_to(self.source / "SKILL.md")
        with self.assertRaises(ValueError):
            self.sync()
        self.assertFalse(self.target.exists())

    def test_category_mapping_rejects_traversal_and_core(self) -> None:
        for plugin, skill in (("volcengine-../database", "volcengine-db-example"),
                              ("volcengine-core", "volcengine-cli"),
                              ("volcengine-database", "../volcengine-db-example")):
            with self.subTest(plugin=plugin, skill=skill), self.assertRaises(ValueError):
                SYNC.specialized_skill_path(plugin, skill)


class DocumentationSyncTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "README.md"
        self.path.write_text(
            "Introduction\n<!-- BEGIN GENERATED: skills -->\nstale\n"
            "<!-- END GENERATED: skills -->\nInstallation\n"
        )
        patch = mock.patch.object(SYNC, "REPO_ROOT", self.root)
        patch.start()
        self.addCleanup(patch.stop)

    def test_repairs_catalog_section_preserving_handwritten_content(self) -> None:
        sections = {self.path: {"skills": "updated skill catalog"}}
        before = self.path.read_text()
        mismatches = []
        SYNC.sync_document_sections(sections, True, mismatches)
        self.assertTrue(mismatches)
        self.assertEqual(self.path.read_text(), before)
        SYNC.sync_document_sections(sections, False, [])
        self.assertEqual(self.path.read_text(), before.replace("stale", "updated skill catalog"))
        mismatches = []
        SYNC.sync_document_sections(sections, True, mismatches)
        self.assertEqual(mismatches, [])

    def test_missing_duplicate_or_reversed_markers_do_not_overwrite_document(self) -> None:
        for text in ("no markers", "<!-- BEGIN GENERATED: skills -->\n" * 2,
                     "<!-- END GENERATED: skills --><!-- BEGIN GENERATED: skills -->"):
            with self.subTest(text=text):
                self.path.write_text(text)
                with self.assertRaises(ValueError):
                    SYNC.sync_document_sections({self.path: {"skills": "new"}}, False, [])
                self.assertEqual(self.path.read_text(), text)

    def test_catalog_change_updates_both_languages_and_host_lists(self) -> None:
        catalog = json.loads(SYNC.CATALOG_PATH.read_text())
        before = SYNC.generated_document_sections(catalog)
        skill = catalog["plugins"][2]["skills"][0]
        skill["summary"] = "New English summary"
        skill["summary_zh"] = "新的中文说明"
        after = SYNC.generated_document_sections(catalog)
        self.assertNotEqual(before, after)
        chinese = after[self.root / "README.md"]["skill-catalog"]
        self.assertIn("新的中文说明", chinese)
        self.assertIn("./skills/specialized/database/volcengine-db-supabase/SKILL.md", chinese)
        for name in ("README_en.md", "GEMINI.md", ".cursor/rules/volcengine-skills.mdc"):
            self.assertIn("New English summary", after[self.root / name]["skill-catalog"])


if __name__ == "__main__":
    unittest.main()
