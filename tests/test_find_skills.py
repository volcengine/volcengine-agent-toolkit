from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
FINDER_PATH = (
    REPO_ROOT
    / "skills"
    / "core"
    / "volcengine-find-skills"
    / "scripts"
    / "find_skills.py"
)
SPEC = importlib.util.spec_from_file_location("find_skills", FINDER_PATH)
assert SPEC and SPEC.loader
FINDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FINDER)


class FinderInstallVerificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = FINDER.load_catalog()
        self.record = next(
            record
            for record in FINDER.iter_records(self.catalog)
            if record["name"] == "volcengine-tosutil"
        )

    def completed(self, returncode: int, stdout: str = "", stderr: str = ""):
        return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)

    def test_list_contains_every_catalogued_skill_and_maps_to_its_plugin(self) -> None:
        records = list(FINDER.iter_records(self.catalog))
        expected_names = [
            skill["name"]
            for plugin in self.catalog["plugins"]
            for skill in plugin["skills"]
        ]
        self.assertEqual([record["name"] for record in records], expected_names)
        for record in records:
            with self.subTest(skill=record["name"]):
                plugin, resolved = FINDER.resolve_target(
                    self.catalog, record["name"]
                )
                self.assertEqual(plugin["name"], record["plugin"])
                self.assertEqual([item["name"] for item in resolved], [record["name"]])

    def test_sale_skill_is_owned_by_service_support_plugin(self) -> None:
        sale = next(
            record
            for record in FINDER.iter_records(self.catalog)
            if record["name"] == "volcengine-sale"
        )
        self.assertEqual(sale["plugin"], "volcengine-service-support")
        self.assertEqual(
            sale["path"],
            "plugins/volcengine-service-support/skills/volcengine-sale",
        )

    def test_service_support_exposes_sale_discovery_keywords(self) -> None:
        service_support = FINDER.plugin_by_name(
            self.catalog, "volcengine-service-support"
        )
        assert service_support is not None

        self.assertIn("开通", service_support["keywords"])
        self.assertIn("commonbuy", service_support["keywords"])
        self.assertNotIn("计费", service_support["keywords"])

    def test_search_subcommand_is_not_available(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(
            SystemExit
        ) as raised:
            FINDER.build_parser().parse_args(["search", "object storage"])
        self.assertEqual(raised.exception.code, 2)

    def test_install_accepts_exact_skills_only(self) -> None:
        records = FINDER.resolve_skills(
            self.catalog, ["volcengine-iac", "volcengine-tosutil"]
        )
        self.assertEqual(
            [record["name"] for record in records],
            ["volcengine-iac", "volcengine-tosutil"],
        )
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            FINDER.resolve_skills(self.catalog, ["volcengine-service-support"])

    def test_install_parser_has_no_plugin_method(self) -> None:
        args = FINDER.build_parser().parse_args(
            ["install", "volcengine-iac", "--agent", "codex", "--dry-run"]
        )
        self.assertEqual(args.targets, ["volcengine-iac"])
        self.assertFalse(hasattr(args, "method"))

    @mock.patch.object(FINDER.subprocess, "run")
    def test_json_reader_retries_truncated_success_output(self, run) -> None:
        run.side_effect = [
            self.completed(0, '[{"name": "incomplete"}'),
            self.completed(0, '[{"name": "volcengine-iac"}]'),
        ]
        completed, payload = FINDER.run_json(["npx", "skills", "list"])
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(payload, [{"name": "volcengine-iac"}])
        self.assertEqual(run.call_count, 2)

    @mock.patch.object(FINDER.subprocess, "run")
    def test_installed_skill_reader_falls_back_to_plain_output(self, run) -> None:
        run.side_effect = [
            self.completed(0, "["),
            self.completed(0, "["),
            self.completed(0, "["),
            self.completed(
                0,
                "  \x1b[36mvolcengine-iac\x1b[0m  "
                "~/.agents/skills/volcengine-iac  Agents: Codex\n",
            ),
        ]
        installed = FINDER.installed_skill_names(self.catalog, "codex", "global")
        self.assertEqual(installed, {"volcengine-iac"})
        self.assertEqual(run.call_count, 4)

    @mock.patch.object(FINDER.shutil, "which", return_value="/usr/bin/npx")
    @mock.patch.object(FINDER.subprocess, "run")
    def test_skills_install_is_verified_from_project_list(self, run, _which) -> None:
        run.side_effect = [
            self.completed(0),
            self.completed(
                0,
                json.dumps(
                    [
                        {
                            "name": "volcengine-tosutil",
                            "path": "<installed-skill-path>",
                            "scope": "project",
                            "agents": ["Codex"],
                        }
                    ]
                ),
            ),
        ]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            FINDER.install_skills_cli(
                self.catalog,
                [self.record],
                "codex",
                "project",
                "<reviewed-repository>",
                False,
                True,
            )

        payload = json.loads(output.getvalue())
        self.assertTrue(payload["verified"])
        self.assertEqual(payload["scope"], "project")
        install_command = run.call_args_list[0].args[0]
        verify_command = run.call_args_list[1].args[0]
        self.assertEqual(install_command[:4], ["npx", "--yes", "skills", "add"])
        self.assertNotIn("--global", install_command)
        self.assertIn("--full-depth", install_command)
        self.assertIn("volcengine-tosutil", install_command)
        self.assertNotIn("volcengine-storage", install_command)
        self.assertEqual(verify_command[-3:], ["--agent", "codex", "--json"])

    @mock.patch.object(FINDER.shutil, "which", return_value="/usr/bin/npx")
    @mock.patch.object(FINDER.subprocess, "run")
    def test_skills_install_fails_when_post_check_cannot_find_skill(
        self, run, _which
    ) -> None:
        run.side_effect = [
            self.completed(0),
            self.completed(0, "[]"),
        ]
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            FINDER.install_skills_cli(
                self.catalog,
                [self.record],
                "codex",
                "global",
                None,
                False,
                True,
            )

    @mock.patch.object(FINDER.shutil, "which", return_value="/usr/bin/npx")
    @mock.patch.object(FINDER.subprocess, "run")
    def test_status_reports_installed_skills_instead_of_plugins(
        self, run, _which
    ) -> None:
        run.return_value = self.completed(
            0, json.dumps([{"name": "volcengine-tosutil"}])
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            FINDER.show_status(self.catalog, "codex", "global", True)

        rows = json.loads(output.getvalue())
        states = {row["skill"]: row["state"] for row in rows}
        self.assertEqual(states["volcengine-tosutil"], "installed")
        self.assertEqual(states["volcengine-iac"], "not_installed")
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ["npx", "--yes", "skills", "list"])
        self.assertNotIn("plugin", command)


class FinderSourceFallbackTest(unittest.TestCase):
    """GitHub first; the CDN toolkit package when GitHub is unreachable."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.cdn = self.root / "cdn"
        self.target = self.root / "home" / ".volcengine" / "agent-toolkit"
        self.catalog = FINDER.load_catalog()
        patcher = mock.patch.dict(
            os.environ,
            {
                # urllib reads file:// URLs, so the CDN is a local directory.
                "VOLCENGINE_TOOLKIT_BASE_URL": self.cdn.as_uri(),
                "VOLCENGINE_TOOLKIT_DIR": str(self.target),
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def publish(self, version: str, *, corrupt: bool = False, entry: str | None = None) -> None:
        release_dir = self.cdn / f"v{version}"
        release_dir.mkdir(parents=True, exist_ok=True)
        archive = release_dir / "volcengine-agent-toolkit.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("package.json", json.dumps({"version": version}))
            bundle.writestr(".claude-plugin/marketplace.json", "{}")
            bundle.writestr(
                "plugins/volcengine-core/skills/volcengine-cli/SKILL.md", "# cli\n"
            )
            info = zipfile.ZipInfo("hooks/run.sh")
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o755) << 16
            bundle.writestr(info, "#!/bin/sh\n")
            if entry:
                bundle.writestr(entry, "escape")
        manifest = {
            "schemaVersion": 1,
            "version": version,
            "toolkit": {
                "file": archive.name,
                "sha256": "0" * 64
                if corrupt
                else hashlib.sha256(archive.read_bytes()).hexdigest(),
                "size": archive.stat().st_size,
                "url": archive.name,
            },
        }
        (self.cdn / "latest").mkdir(exist_ok=True)
        (self.cdn / "latest" / "toolkit-manifest.json").write_text(json.dumps(manifest))

    def resolve(self, source: str | None = None) -> tuple[str, str]:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            resolved = FINDER.resolve_install_source(self.catalog, source)
        return resolved, stderr.getvalue()

    def test_explicit_source_is_used_without_probing(self) -> None:
        with mock.patch.object(FINDER, "github_reachable") as probe:
            self.assertEqual(self.resolve("<reviewed-repository>")[0], "<reviewed-repository>")
        probe.assert_not_called()

    def test_reachable_github_keeps_the_catalog_repository(self) -> None:
        with mock.patch.object(FINDER, "github_reachable", return_value=True):
            resolved, _ = self.resolve()
        self.assertEqual(resolved, self.catalog["repository"])
        self.assertFalse(self.target.exists())

    def test_unreachable_github_downloads_and_verifies_the_cdn_package(self) -> None:
        self.publish("1.3.4")
        with mock.patch.object(FINDER, "github_reachable", return_value=False):
            resolved, message = self.resolve()
        self.assertEqual(resolved, str(self.target))
        self.assertIn("Volcengine CDN toolkit v1.3.4", message)
        self.assertTrue(FINDER.is_toolkit_dir(self.target))
        self.assertTrue(os.access(self.target / "hooks" / "run.sh", os.X_OK))
        self.assertEqual(
            [path.name for path in self.target.parent.iterdir()], ["agent-toolkit"]
        )

    def test_current_local_copy_is_reused_and_newer_release_replaces_it(self) -> None:
        self.publish("1.3.4")
        with mock.patch.object(FINDER, "github_reachable", return_value=False):
            self.resolve()
            marker = self.target / "marker"
            marker.write_text("x")
            self.resolve()
            self.assertTrue(marker.exists())
            self.publish("1.3.5")
            self.resolve()
        self.assertFalse(marker.exists())
        self.assertEqual(FINDER.local_toolkit_version(self.target), "1.3.5")

    def test_checksum_mismatch_keeps_the_existing_copy_and_reports_it(self) -> None:
        self.publish("1.3.4")
        with mock.patch.object(FINDER, "github_reachable", return_value=False):
            self.resolve()
            self.publish("1.3.5", corrupt=True)
            resolved, message = self.resolve()
        self.assertEqual(resolved, str(self.target))
        self.assertIn("checksum mismatch", message)
        self.assertIn("local toolkit v1.3.4", message)
        self.assertEqual(FINDER.local_toolkit_version(self.target), "1.3.4")

    def test_fails_when_neither_github_nor_the_cdn_nor_a_local_copy_is_available(
        self,
    ) -> None:
        with mock.patch.object(FINDER, "github_reachable", return_value=False):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
                FINDER.resolve_install_source(self.catalog, None)
        self.assertIn("GitHub is unreachable", stderr.getvalue())
        self.assertFalse(self.target.exists())

    def test_package_entry_outside_the_target_is_rejected(self) -> None:
        self.publish("1.3.4", entry="../escaped.txt")
        with mock.patch.object(FINDER, "github_reachable", return_value=False):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
                FINDER.resolve_install_source(self.catalog, None)
        self.assertIn("escapes its root", stderr.getvalue())
        self.assertFalse((self.target.parent / "escaped.txt").exists())
        self.assertFalse(self.target.exists())

    def test_foreign_directory_is_not_replaced(self) -> None:
        self.publish("1.3.4")
        self.target.mkdir(parents=True)
        (self.target / "keep.txt").write_text("mine")
        with mock.patch.object(FINDER, "github_reachable", return_value=False):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                FINDER.resolve_install_source(self.catalog, None)
        self.assertEqual((self.target / "keep.txt").read_text(), "mine")

    def test_dry_run_prints_the_command_without_touching_the_network(self) -> None:
        output = io.StringIO()
        with mock.patch.object(FINDER, "github_reachable") as probe, mock.patch(
            "sys.argv", ["find_skills.py", "install", "volcengine-tosutil", "--dry-run"]
        ), contextlib.redirect_stdout(output):
            FINDER.main()
        probe.assert_not_called()
        self.assertIn(self.catalog["repository"], output.getvalue())


if __name__ == "__main__":
    unittest.main()
