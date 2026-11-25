"""Tests for scripts/install_toolkit.sh.

The installer runs end to end against a local "CDN" directory
(VOLCENGINE_TOOLKIT_BASE_URL without a scheme) and fake host CLIs placed ahead
in PATH that record their arguments. GitHub reachability is simulated through
VOLCENGINE_TOOLKIT_GITHUB_URL. No network is used.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "install_toolkit.sh"
POWERSHELL_SCRIPT = REPO_ROOT / "scripts" / "install_toolkit.ps1"
CORE_ROOT = REPO_ROOT / "skills" / "core"
# Nothing listens here, so the probe fails at once: GitHub "unreachable".
UNREACHABLE_URL = "http://127.0.0.1:9/"
CORE_PLUGIN = "volcengine-core@volcengine-skills"


def parse_kv(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


class InstallToolkitHarness(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.cdn = self.root / "cdn"
        self.cdn.mkdir()
        self.fake_bin = self.root / "fakebin"
        self.fake_bin.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()
        self.toolkit_dir = self.home / ".volcengine" / "agent-toolkit"
        self.calls = self.root / "calls.log"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def publish(self, version: str, *, latest: bool = True, corrupt: bool = False,
                valid_layout: bool = True) -> None:
        release_dir = self.cdn / f"v{version}"
        release_dir.mkdir(parents=True, exist_ok=True)
        archive = release_dir / "volcengine-agent-toolkit.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("package.json", json.dumps({"version": version}, indent=2))
            if valid_layout:
                bundle.writestr(".claude-plugin/marketplace.json", "{}")
                for skill in sorted(path.name for path in CORE_ROOT.iterdir() if path.is_dir()):
                    for prefix in ("plugins/volcengine-core/skills", "skills/core"):
                        bundle.writestr(f"{prefix}/{skill}/SKILL.md", f"# {skill} {version}\n")
                info = zipfile.ZipInfo("hooks/run.sh")
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o755) << 16
                bundle.writestr(info, "#!/bin/sh\n")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        manifest = {
            "schemaVersion": 1,
            "toolkit": {
                "file": archive.name,
                "sha256": "0" * 64 if corrupt else digest,
                "size": archive.stat().st_size,
                "url": archive.name,
            },
            "version": version,
        }
        text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        (release_dir / "toolkit-manifest.json").write_text(text, encoding="utf-8")
        if latest:
            (self.cdn / "latest").mkdir(exist_ok=True)
            (self.cdn / "latest" / "toolkit-manifest.json").write_text(text, encoding="utf-8")

    def fake_cli(self, name: str, body: str = "") -> None:
        script = self.fake_bin / name
        script.write_text(
            "#!/bin/sh\n"
            f'echo "{name} $*" >> "{self.calls}"\n'
            f"{body}\n",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)

    def recorded_calls(self) -> list[str]:
        """Install-time calls; the read-only list calls used to verify are dropped."""
        if not self.calls.exists():
            return []
        return [
            line
            for line in self.calls.read_text(encoding="utf-8").splitlines()
            if not line.endswith(" list") and " skills list " not in line
        ]

    def fake_host(self, name: str, listing: str, body: str = "") -> None:
        """A host CLI whose list subcommand prints `listing`."""
        self.fake_cli(
            name,
            f"{body}\n"
            'case "$*" in *list*) cat <<LISTING\n'
            f"{listing}\n"
            "LISTING\n;; esac",
        )

    def run_installer(self, *args: str, github_url: str = UNREACHABLE_URL,
                      env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        full_env = {
            "PATH": f"{self.fake_bin}{os.pathsep}/usr/bin{os.pathsep}/bin",
            "HOME": str(self.home),
            "VOLCENGINE_TOOLKIT_BASE_URL": str(self.cdn),
            "VOLCENGINE_TOOLKIT_GITHUB_URL": github_url,
        }
        full_env.update(env or {})
        return subprocess.run(
            ["sh", str(SCRIPT), *args],
            capture_output=True,
            text=True,
            env=full_env,
            check=False,
        )


class SourceSelectionTest(InstallToolkitHarness):
    def test_unreachable_github_falls_back_to_the_cdn_package(self) -> None:
        self.publish("1.3.4")
        result = self.run_installer("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        values = parse_kv(result.stdout)
        self.assertEqual(values["SOURCE"], "cdn")
        self.assertEqual(values["VERSION"], "1.3.4")
        self.assertEqual(values["TOOLKIT_DIR"], str(self.toolkit_dir))
        self.assertEqual(values["INSTALL_SOURCE"], str(self.toolkit_dir))
        self.assertTrue(values["TOOLKIT_URL"].endswith("/v1.3.4/volcengine-agent-toolkit.zip"))
        self.assertIn("GitHub is not reachable", result.stderr)
        self.assertFalse(self.toolkit_dir.exists(), "a dry run must not download")

    def test_reachable_github_installs_from_the_repository(self) -> None:
        # A local file answers the probe, standing in for a reachable GitHub.
        probe = self.root / "probe.html"
        probe.write_text("ok", encoding="utf-8")
        result = self.run_installer("--dry-run", github_url=probe.as_uri())
        self.assertEqual(result.returncode, 0, result.stderr)
        values = parse_kv(result.stdout)
        self.assertEqual(values["SOURCE"], "github")
        self.assertEqual(values["INSTALL_SOURCE"], "volcengine/volcengine-agent-toolkit")

    def test_source_flag_skips_the_probe(self) -> None:
        self.publish("1.3.4")
        forced_github = self.run_installer("--source", "github", "--dry-run")
        self.assertEqual(parse_kv(forced_github.stdout)["SOURCE"], "github")
        probe = self.root / "probe.html"
        probe.write_text("ok", encoding="utf-8")
        forced_cdn = self.run_installer("--source=cdn", "--dry-run", github_url=probe.as_uri())
        self.assertEqual(parse_kv(forced_cdn.stdout)["SOURCE"], "cdn")

    def test_copy_installed_hosts_also_prefer_github(self) -> None:
        self.publish("1.3.4")
        probe = self.root / "probe.html"
        probe.write_text("ok", encoding="utf-8")
        for agent in ("doubao-work", "workbuddy"):
            result = self.run_installer("--agent", agent, "--dry-run", github_url=probe.as_uri())
            self.assertEqual(parse_kv(result.stdout)["SOURCE"], "github", agent)

    def test_rejects_unknown_source_and_malformed_agent(self) -> None:
        self.assertNotEqual(self.run_installer("--source", "mirror").returncode, 0)
        result = self.run_installer("--agent", "claude;rm", "--dry-run")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --agent", result.stderr)


class CdnPackageTest(InstallToolkitHarness):
    def test_downloads_verifies_and_unpacks_the_package(self) -> None:
        self.publish("1.3.4")
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Checksum OK.", result.stderr)
        self.assertTrue((self.toolkit_dir / ".claude-plugin" / "marketplace.json").is_file())
        self.assertTrue(os.access(self.toolkit_dir / "hooks" / "run.sh", os.X_OK))
        self.assertIn(f'claude plugin marketplace add "{self.toolkit_dir}"', result.stderr)
        leftovers = [path.name for path in self.toolkit_dir.parent.iterdir()]
        self.assertEqual(leftovers, ["agent-toolkit"])

    def test_rerun_keeps_the_current_version_and_upgrade_replaces_it(self) -> None:
        self.publish("1.3.4")
        self.assertEqual(self.run_installer().returncode, 0)
        marker = self.toolkit_dir / "marker"
        marker.write_text("x", encoding="utf-8")

        again = self.run_installer()
        self.assertIn("already in", again.stderr)
        self.assertTrue(marker.exists(), "the same version must not be unpacked again")

        self.publish("1.3.5")
        upgraded = self.run_installer()
        self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
        self.assertEqual(parse_kv(upgraded.stdout)["VERSION"], "1.3.5")
        self.assertFalse(marker.exists())
        package = json.loads((self.toolkit_dir / "package.json").read_text())
        self.assertEqual(package["version"], "1.3.5")

    def test_version_flag_selects_a_published_version(self) -> None:
        self.publish("1.3.4", latest=False)
        self.publish("1.3.5")
        result = self.run_installer("--version", "v1.3.4")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(parse_kv(result.stdout)["VERSION"], "1.3.4")

    def test_checksum_mismatch_leaves_the_working_toolkit_untouched(self) -> None:
        self.publish("1.3.4")
        self.assertEqual(self.run_installer().returncode, 0)
        self.publish("1.3.5", corrupt=True)
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Checksum mismatch", result.stderr)
        package = json.loads((self.toolkit_dir / "package.json").read_text())
        self.assertEqual(package["version"], "1.3.4")

    def test_package_without_the_toolkit_layout_is_rejected(self) -> None:
        self.publish("1.3.4", valid_layout=False)
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected toolkit layout", result.stderr)
        self.assertFalse(self.toolkit_dir.exists())

    def test_refuses_to_replace_a_directory_it_did_not_create(self) -> None:
        self.publish("1.3.4")
        other = self.root / "documents"
        other.mkdir()
        (other / "keep.txt").write_text("mine", encoding="utf-8")
        result = self.run_installer("--dir", str(other))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a Volcengine toolkit directory", result.stderr)
        self.assertEqual((other / "keep.txt").read_text(encoding="utf-8"), "mine")

    def test_missing_manifest_fails_without_touching_the_target(self) -> None:
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot read", result.stderr)
        self.assertFalse(self.toolkit_dir.exists())


class HostRegistrationTest(InstallToolkitHarness):
    def setUp(self) -> None:
        super().setUp()
        self.publish("1.3.4")

    def test_claude_and_codex_install_the_core_plugin_from_the_local_directory(self) -> None:
        self.fake_host("claude", CORE_PLUGIN)
        self.fake_host("codex", f"{CORE_PLUGIN}  installed, enabled")
        result = self.run_installer("--agent", "claude,codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.recorded_calls(),
            [
                f"claude plugin marketplace add {self.toolkit_dir}",
                f"claude plugin install {CORE_PLUGIN}",
                f"codex plugin marketplace add {self.toolkit_dir}",
                f"codex plugin add {CORE_PLUGIN}",
            ],
        )
        self.assertEqual(parse_kv(result.stdout)["AGENT"], "claude,codex")
        self.assertEqual(parse_kv(result.stdout)["VERIFIED"], "claude:ok,codex:ok")

    def test_codex_rebinds_a_marketplace_added_from_another_source(self) -> None:
        # The first add fails the way Codex does for a name bound elsewhere.
        flag = self.root / "codex-added-once"
        self.fake_host(
            "codex",
            f"{CORE_PLUGIN}  installed, enabled",
            f'if [ "$2 $3" = "marketplace add" ] && [ ! -e "{flag}" ]; then touch "{flag}"; exit 1; fi',
        )
        result = self.run_installer("--agent", "codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.recorded_calls(),
            [
                f"codex plugin marketplace add {self.toolkit_dir}",
                "codex plugin marketplace remove volcengine-skills",
                f"codex plugin marketplace add {self.toolkit_dir}",
                f"codex plugin add {CORE_PLUGIN}",
            ],
        )

    def test_github_source_passes_the_repository_to_the_host(self) -> None:
        self.fake_host("claude", CORE_PLUGIN)
        result = self.run_installer("--source", "github", "--agent", "claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.recorded_calls()[0],
            "claude plugin marketplace add volcengine/volcengine-agent-toolkit",
        )
        self.assertFalse(self.toolkit_dir.exists())

    def test_trae_cli_names_the_marketplace_explicitly(self) -> None:
        self.fake_host("coco", "volcengine-core")
        result = self.run_installer("--agent", "trae-cli")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.recorded_calls(),
            [
                # The plugin goes first: Trae CLI keeps a marketplace that
                # still has a plugin installed from it.
                "coco plugin uninstall volcengine-core",
                "coco plugin marketplace remove volcengine-skills",
                f"coco plugin marketplace add {self.toolkit_dir} --name volcengine-skills --type local",
                f"coco plugin install {CORE_PLUGIN} --type marketplace --yes",
            ],
        )

    def test_gemini_installs_each_core_skill_from_its_local_directory(self) -> None:
        self.fake_host("gemini", "\n".join(sorted(p.name for p in CORE_ROOT.iterdir())))
        result = self.run_installer("--agent", "gemini")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.recorded_calls()
        self.assertEqual(len(calls), len(list(CORE_ROOT.iterdir())))
        self.assertIn(
            f"gemini skills install {self.toolkit_dir}/skills/core/volcengine-cli --consent",
            calls,
        )

    def test_other_agents_go_through_the_skills_cli(self) -> None:
        self.fake_host("npx", "\n".join(sorted(p.name for p in CORE_ROOT.iterdir())))
        result = self.run_installer("--agent", "cursor,trae-cn")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.recorded_calls()
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0].startswith(f"npx --yes skills add {self.toolkit_dir} --global"))
        self.assertTrue(calls[0].endswith("--agent cursor"))
        self.assertTrue(calls[1].endswith("--agent trae-cn"))
        self.assertIn("--skill volcengine-cli ", calls[0])

    def test_doubao_work_copies_core_skills_into_every_profile(self) -> None:
        # The standalone DoubaoWork app and the work mode inside the Doubao app
        # keep user skills under different directories; both must be found.
        layouts = (("DoubaoWork", ".doubaowork"), ("Doubao", ".doubao"))
        bases = [self.home / "Library" / "Application Support", self.home / ".config"]
        profiles = []
        for base in bases:
            for app, dot_dir in layouts:
                target = base / app / "Default" / dot_dir / "agent_mode" / "workspace" / ".user_skills"
                target.mkdir(parents=True)
                profiles.append(target)
        stale = profiles[0] / "volcengine-cli"
        stale.mkdir()
        (stale / "old.txt").write_text("old", encoding="utf-8")

        result = self.run_installer("--agent", "doubao-work")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(parse_kv(result.stdout)["VERIFIED"], "doubao-work:ok")
        core_skills = sorted(path.name for path in CORE_ROOT.iterdir() if path.is_dir())
        installed = [
            target for target in profiles if sorted(p.name for p in target.iterdir()) == core_skills
        ]
        # Only the root that belongs to this operating system is populated.
        self.assertEqual(len(installed), 2, result.stderr)
        for target in installed:
            self.assertTrue((target / "volcengine-find-skills" / "SKILL.md").is_file())
            self.assertFalse((target / "volcengine-cli" / "old.txt").exists())

    def test_doubao_work_upgrade_backs_up_legacy_skill_and_keeps_custom_skills(self) -> None:
        base = self.home / ("Library/Application Support" if sys.platform == "darwin" else ".config")
        profiles = [
            base / app / name / dot_dir / "agent_mode/workspace/.user_skills"
            for app, dot_dir in (("DoubaoWork", ".doubaowork"), ("Doubao", ".doubao"))
            for name in ("Default", "Profile 2")
        ]
        for profile in profiles:
            legacy = profile / "volcengine-cost"
            legacy.mkdir(parents=True)
            (legacy / "SKILL.md").write_text("old billing skill", encoding="utf-8")
            (legacy / "custom.md").write_text("user notes", encoding="utf-8")
            current = profile / "volcengine-billing-and-cost-management"
            current.mkdir()
            (current / "SKILL.md").write_text("previous billing and cost management skill", encoding="utf-8")
            custom = profile / "user-custom-skill"
            custom.mkdir()
            (custom / "SKILL.md").write_text("keep", encoding="utf-8")
        result = self.run_installer("--agent", "doubao-work")
        self.assertEqual(0, result.returncode, result.stderr)
        for profile in profiles:
            self.assertEqual(
                (self.toolkit_dir / "skills/core/volcengine-billing-and-cost-management/SKILL.md").read_text(),
                (profile / "volcengine-billing-and-cost-management/SKILL.md").read_text(),
            )
            self.assertFalse((profile / "volcengine-cost").exists())
            self.assertEqual("keep", (profile / "user-custom-skill/SKILL.md").read_text())
            backups = list((profile.parent / ".skill-migration-backups").glob("*/volcengine-cost"))
            self.assertEqual(1, len(backups))
            self.assertEqual("user notes", (backups[0] / "custom.md").read_text())
        repeated = self.run_installer("--agent", "doubao-work")
        self.assertEqual(0, repeated.returncode, repeated.stderr)
        for profile in profiles:
            self.assertEqual(
                (self.toolkit_dir / "skills/core/volcengine-billing-and-cost-management/SKILL.md").read_text(),
                (profile / "volcengine-billing-and-cost-management/SKILL.md").read_text(),
            )
            self.assertEqual(1, len(list((profile.parent / ".skill-migration-backups").iterdir())))

    def test_doubao_work_copy_failure_preserves_existing_billing_and_cost_skills(self) -> None:
        doubao_root = self.home / ("Library/Application Support/DoubaoWork" if sys.platform == "darwin" else ".config/DoubaoWork")
        profile = doubao_root / "Default/.doubaowork/agent_mode/workspace/.user_skills"
        for name in ("volcengine-cost", "volcengine-billing-and-cost-management"):
            target = profile / name
            target.mkdir(parents=True)
            (target / "SKILL.md").write_text("keep old version", encoding="utf-8")
        self.fake_cli("cp", 'case "$*" in *skills/core/volcengine-billing-and-cost-management*) exit 1;; esac\n/bin/cp "$@"')
        result = self.run_installer("--agent", "doubao-work")
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("VERIFIED=doubao-work:ok", result.stdout)
        for name in ("volcengine-cost", "volcengine-billing-and-cost-management"):
            self.assertEqual("keep old version", (profile / name / "SKILL.md").read_text())
        self.assertFalse((profile.parent / ".skill-migration-backups").exists())
        self.assertEqual([], list(profile.parent.glob(".skill-install.*")))

    def test_doubao_work_without_a_workspace_says_what_to_do(self) -> None:
        result = self.run_installer("--agent", "doubao-work")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No Doubao user skill directory found", result.stderr)

    def test_host_that_does_not_list_the_install_fails_the_run(self) -> None:
        # Every command succeeds, but the host does not show the plugin.
        self.fake_host("claude", "no plugins installed")
        result = self.run_installer("--agent", "claude")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(parse_kv(result.stdout)["VERIFIED"], "claude:plugin-not-listed")
        self.assertIn("does not list the core skills", result.stderr)

    def test_skills_cli_agent_missing_a_core_skill_fails_the_run(self) -> None:
        self.fake_host("npx", "volcengine-cli")
        result = self.run_installer("--agent", "cursor")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(parse_kv(result.stdout)["VERIFIED"], "cursor:skills-not-listed")

    def test_host_without_its_cli_is_installed_through_the_skills_cli(self) -> None:
        # Desktop builds often ship without the command; the host still reads
        # its user skill directory, which the skills CLI writes.
        listing = "\n".join(sorted(p.name for p in CORE_ROOT.iterdir()))
        self.fake_host("npx", listing)
        result = self.run_installer("--agent", "claude,codex,gemini,trae-cli")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.recorded_calls()
        self.assertEqual(
            [call.rsplit("--agent ", 1)[1] for call in calls],
            ["claude-code", "codex", "gemini-cli", "trae"],
        )
        self.assertTrue(all(call.startswith("npx --yes skills add ") for call in calls))
        self.assertEqual(
            parse_kv(result.stdout)["VERIFIED"],
            "claude:ok,codex:ok,gemini:ok,trae-cli:ok",
        )
        self.assertIn("'claude' is not on PATH; installing", result.stderr)

    def test_missing_host_cli_and_missing_npx_is_reported(self) -> None:
        result = self.run_installer("--agent", "claude")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("'npx' is not on PATH", result.stderr)

    def test_agent_unknown_to_the_skills_cli_falls_back_to_every_detected_host(self) -> None:
        # The skills CLI prints "Invalid agents" and exits 1 for a name it does not know.
        listing = "\n".join(sorted(p.name for p in CORE_ROOT.iterdir()))
        self.fake_cli(
            "npx",
            'case "$*" in\n'
            '  *"skills add"*"--agent newhost"*) echo "Invalid agents: newhost"; exit 1 ;;\n'
            f'  *"skills list"*) cat <<LISTING\n{listing}\nLISTING\n;;\n'
            "esac",
        )
        result = self.run_installer("--agent", "newhost")
        self.assertEqual(result.returncode, 0, result.stderr)
        adds = [call for call in self.recorded_calls() if " skills add " in call]
        self.assertEqual(len(adds), 2)
        self.assertTrue(adds[0].endswith("--agent newhost"))
        self.assertNotIn("--agent", adds[1])
        self.assertEqual(parse_kv(result.stdout)["VERIFIED"], "newhost:ok")
        self.assertIn("does not know the agent 'newhost'", result.stderr)

    def test_other_installs_for_every_detected_host(self) -> None:
        self.fake_host("npx", "\n".join(sorted(p.name for p in CORE_ROOT.iterdir())))
        result = self.run_installer("--agent", "other")
        self.assertEqual(result.returncode, 0, result.stderr)
        adds = [call for call in self.recorded_calls() if " skills add " in call]
        self.assertEqual(len(adds), 1)
        self.assertNotIn("--agent", adds[0])
        self.assertEqual(parse_kv(result.stdout)["VERIFIED"], "other:ok")

    def test_workbuddy_copies_core_skills_into_its_skill_directory(self) -> None:
        missing = self.run_installer("--agent", "workbuddy")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("No WorkBuddy directory found", missing.stderr)

        target = self.home / ".workbuddy" / "skills"
        (target / "volcengine-cli").mkdir(parents=True)
        (target / "volcengine-cli" / "old.txt").write_text("old", encoding="utf-8")
        (target / "someone-elses-skill").mkdir()
        result = self.run_installer("--agent", "workbuddy")
        self.assertEqual(result.returncode, 0, result.stderr)
        core_skills = {path.name for path in CORE_ROOT.iterdir() if path.is_dir()}
        self.assertEqual(
            {path.name for path in target.iterdir()}, core_skills | {"someone-elses-skill"}
        )
        self.assertFalse((target / "volcengine-cli" / "old.txt").exists())
        self.assertEqual(parse_kv(result.stdout)["VERIFIED"], "workbuddy:ok")

    def test_results_are_reported_in_the_order_the_hosts_were_given(self) -> None:
        (self.home / ".workbuddy").mkdir()
        self.fake_host("codex", f"{CORE_PLUGIN}  installed, enabled")
        self.fake_host("claude", CORE_PLUGIN)
        result = self.run_installer("--agent", "workbuddy,codex,claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            parse_kv(result.stdout)["VERIFIED"], "workbuddy:ok,codex:ok,claude:ok"
        )


class GithubFirstTest(InstallToolkitHarness):
    """GitHub is preferred; the CDN is the retry when an install from GitHub fails."""

    def setUp(self) -> None:
        super().setUp()
        self.publish("1.3.4")
        self.probe = self.root / "probe.html"
        self.probe.write_text("ok", encoding="utf-8")

    def github_archive(self) -> str:
        """A stand-in for <repo>/archive/HEAD.tar.gz; returns the repository URL."""
        import tarfile

        source = self.root / "src" / "volcengine-agent-toolkit-main"
        for skill in sorted(path.name for path in CORE_ROOT.iterdir() if path.is_dir()):
            (source / "skills" / "core" / skill).mkdir(parents=True)
            (source / "skills" / "core" / skill / "SKILL.md").write_text(
                f"# {skill} from github\n", encoding="utf-8"
            )
        repo = self.root / "gh" / "repo"
        (repo / "archive").mkdir(parents=True)
        with tarfile.open(repo / "archive" / "HEAD.tar.gz", "w:gz") as archive:
            archive.add(source, arcname=source.name)
        return repo.as_uri()

    def test_failed_github_install_is_retried_from_the_cdn(self) -> None:
        # The probe passes, but the host cannot clone the repository.
        self.fake_host(
            "claude",
            CORE_PLUGIN,
            'case "$*" in *"marketplace add volcengine/"*) echo "clone failed" >&2; exit 1 ;; esac',
        )
        result = self.run_installer("--agent", "claude", github_url=self.probe.as_uri())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.recorded_calls(),
            [
                "claude plugin marketplace add volcengine/volcengine-agent-toolkit",
                f"claude plugin marketplace add {self.toolkit_dir}",
                f"claude plugin install {CORE_PLUGIN}",
            ],
        )
        values = parse_kv(result.stdout)
        self.assertEqual(values["SOURCE"], "cdn")
        self.assertEqual(values["VERSION"], "1.3.4")
        self.assertEqual(values["VERIFIED"], "claude:ok")
        self.assertIn("retrying from the Volcengine CDN", result.stderr)

    def test_host_blind_to_a_github_install_is_retried_from_the_cdn(self) -> None:
        # Commands succeed from GitHub, but the plugin only shows up after the CDN install.
        flag = self.root / "installed-from-cdn"
        self.fake_cli(
            "claude",
            f'case "$*" in *"marketplace add {self.toolkit_dir}"*) touch "{flag}" ;; esac\n'
            f'case "$*" in *list*) [ -e "{flag}" ] && echo "{CORE_PLUGIN}" ;; esac\nexit 0',
        )
        result = self.run_installer("--agent", "claude", github_url=self.probe.as_uri())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(parse_kv(result.stdout)["VERIFIED"], "claude:ok")
        self.assertEqual(parse_kv(result.stdout)["SOURCE"], "cdn")

    def test_forced_github_source_is_not_retried(self) -> None:
        self.fake_host("claude", CORE_PLUGIN, 'case "$*" in *"marketplace add"*) exit 1 ;; esac')
        result = self.run_installer("--source", "github", "--agent", "claude")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("retrying", result.stderr)
        self.assertFalse(self.toolkit_dir.exists())

    def test_later_hosts_use_the_cdn_after_a_retry(self) -> None:
        self.fake_host("claude", CORE_PLUGIN, 'case "$*" in *"marketplace add volcengine/"*) exit 1 ;; esac')
        self.fake_host("codex", f"{CORE_PLUGIN}  installed, enabled")
        result = self.run_installer("--agent", "claude,codex", github_url=self.probe.as_uri())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"codex plugin marketplace add {self.toolkit_dir}", self.recorded_calls())
        self.assertEqual(parse_kv(result.stdout)["VERIFIED"], "claude:ok,codex:ok")

    def test_copy_installed_host_takes_the_skills_from_the_github_archive(self) -> None:
        target = self.home / ".workbuddy" / "skills"
        target.mkdir(parents=True)
        result = self.run_installer(
            "--source", "github", "--agent", "workbuddy", github_url=self.github_archive()
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (target / "volcengine-cli" / "SKILL.md").read_text(encoding="utf-8"),
            "# volcengine-cli from github\n",
        )
        self.assertEqual(parse_kv(result.stdout)["SOURCE"], "github")
        self.assertFalse(self.toolkit_dir.exists(), "the CDN package must not be downloaded")

    def test_copy_installed_host_falls_back_to_the_cdn_without_the_archive(self) -> None:
        target = self.home / ".workbuddy" / "skills"
        target.mkdir(parents=True)
        # The probe answers, but there is no archive behind it.
        result = self.run_installer("--agent", "workbuddy", github_url=self.probe.as_uri())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (target / "volcengine-cli" / "SKILL.md").read_text(encoding="utf-8"),
            "# volcengine-cli 1.3.4\n",
        )
        self.assertEqual(parse_kv(result.stdout)["SOURCE"], "cdn")


class RobustnessTest(InstallToolkitHarness):
    """Regressions for failure modes found in review."""

    def setUp(self) -> None:
        super().setUp()
        self.publish("1.3.4")
        self.probe = self.root / "probe.html"
        self.probe.write_text("ok", encoding="utf-8")

    def run_piped(self, *args: str, github_url: str = UNREACHABLE_URL) -> subprocess.CompletedProcess[str]:
        """Run the script the documented way: `curl ... | sh -s -- <args>`."""
        return subprocess.run(
            ["sh", "-s", "--", *args],
            input=SCRIPT.read_text(encoding="utf-8"),
            capture_output=True,
            text=True,
            check=False,
            env={
                "PATH": f"{self.fake_bin}{os.pathsep}/usr/bin{os.pathsep}/bin",
                "HOME": str(self.home),
                "VOLCENGINE_TOOLKIT_BASE_URL": str(self.cdn),
                "VOLCENGINE_TOOLKIT_GITHUB_URL": github_url,
            },
        )

    def test_piped_script_survives_host_commands_that_read_stdin(self) -> None:
        # A host CLI that reads stdin must not swallow the rest of the script.
        self.fake_host("claude", CORE_PLUGIN, "cat >/dev/null")
        self.fake_host("coco", "volcengine-core", "cat >/dev/null")
        result = self.run_piped("--agent", "claude,trae-cli")
        self.assertEqual(result.returncode, 0, result.stderr)
        values = parse_kv(result.stdout)
        self.assertEqual(values["VERIFIED"], "claude:ok,trae-cli:ok")
        self.assertEqual(values["SOURCE"], "cdn")

    def test_piped_script_still_fails_when_the_host_does_not_list_the_install(self) -> None:
        self.fake_host("claude", "nothing installed", "cat >/dev/null")
        result = self.run_piped("--agent", "claude")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not list the core skills", result.stderr)

    def test_local_failure_is_reported_as_is_without_a_cdn_retry(self) -> None:
        # GitHub is reachable; the host directory is simply missing. Another
        # download source cannot fix that, and retrying would bury the real error.
        result = self.run_installer("--agent", "workbuddy", github_url=self.probe.as_uri())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No WorkBuddy directory found", result.stderr.strip().splitlines()[-1])
        self.assertNotIn("retrying", result.stderr)
        self.assertFalse(self.toolkit_dir.exists(), "nothing may be downloaded for a local failure")

    def test_relative_directory_is_made_absolute(self) -> None:
        result = subprocess.run(
            ["sh", str(SCRIPT), "--source", "cdn", "--dir", "rel/toolkit", "--dry-run"],
            capture_output=True, text=True, check=False, cwd=self.root,
            env={"PATH": "/usr/bin:/bin", "HOME": str(self.home),
                 "VOLCENGINE_TOOLKIT_BASE_URL": str(self.cdn)},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        install_source = parse_kv(result.stdout)["INSTALL_SOURCE"]
        self.assertTrue(install_source.startswith("/"), install_source)
        self.assertTrue(install_source.endswith("/rel/toolkit"), install_source)

    def test_git_checkout_with_the_toolkit_layout_is_never_replaced(self) -> None:
        checkout = self.root / "checkout"
        (checkout / ".git").mkdir(parents=True)
        (checkout / ".claude-plugin").mkdir()
        (checkout / ".claude-plugin" / "marketplace.json").write_text("{}", encoding="utf-8")
        (checkout / "plugins" / "volcengine-core" / "skills").mkdir(parents=True)
        (checkout / "package.json").write_text('{\n  "version": "0.0.1"\n}\n', encoding="utf-8")
        (checkout / "uncommitted.txt").write_text("work", encoding="utf-8")
        result = self.run_installer("--dir", str(checkout))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is a Git checkout", result.stderr)
        self.assertEqual((checkout / "uncommitted.txt").read_text(encoding="utf-8"), "work")
        self.assertTrue((checkout / ".git").is_dir())

    def test_version_selects_the_cdn_even_when_github_is_reachable(self) -> None:
        result = self.run_installer("--version", "1.3.4", "--dry-run", github_url=self.probe.as_uri())
        self.assertEqual(result.returncode, 0, result.stderr)
        values = parse_kv(result.stdout)
        self.assertEqual((values["SOURCE"], values["VERSION"]), ("cdn", "1.3.4"))

    def test_version_with_forced_github_source_is_rejected(self) -> None:
        result = self.run_installer("--source", "github", "--version", "1.3.4", "--dry-run")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--version selects a released package", result.stderr)

    def test_version_with_path_characters_is_rejected(self) -> None:
        result = self.run_installer("--version", "1.3.4/../../latest", "--dry-run")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid version", result.stderr)

    def test_codex_plugin_listed_as_not_installed_fails_verification(self) -> None:
        self.fake_host("codex", f"{CORE_PLUGIN}  not installed")
        result = self.run_installer("--agent", "codex")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(parse_kv(result.stdout)["VERIFIED"], "codex:plugin-not-listed")

    def test_incomplete_source_keeps_the_existing_host_skills(self) -> None:
        import tarfile

        # A GitHub archive that lacks one core skill.
        source = self.root / "src" / "repo-main"
        for skill in sorted(path.name for path in CORE_ROOT.iterdir() if path.is_dir())[1:]:
            (source / "skills" / "core" / skill).mkdir(parents=True)
            (source / "skills" / "core" / skill / "SKILL.md").write_text("new\n", encoding="utf-8")
        repo = self.root / "gh" / "repo"
        (repo / "archive").mkdir(parents=True)
        with tarfile.open(repo / "archive" / "HEAD.tar.gz", "w:gz") as archive:
            archive.add(source, arcname=source.name)
        target = self.home / ".workbuddy" / "skills"
        for skill in (path.name for path in CORE_ROOT.iterdir() if path.is_dir()):
            (target / skill).mkdir(parents=True)
            (target / skill / "SKILL.md").write_text("old\n", encoding="utf-8")

        result = self.run_installer("--source", "github", "--agent", "workbuddy", github_url=repo.as_uri())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is missing from the downloaded source", result.stderr)
        for skill in (path.name for path in CORE_ROOT.iterdir() if path.is_dir()):
            self.assertEqual((target / skill / "SKILL.md").read_text(encoding="utf-8"), "old\n", skill)
        self.assertFalse(list(target.glob(".*.install.*")), "no staging directory may be left behind")


class InstallerContractTest(unittest.TestCase):
    def core_skills(self) -> set[str]:
        return {path.name for path in CORE_ROOT.iterdir() if path.is_dir()}

    def test_shell_installer_lists_every_core_skill(self) -> None:
        match = re.search(r'^CORE_SKILLS="([^"]+)"$', SCRIPT.read_text(encoding="utf-8"), re.MULTILINE)
        assert match
        self.assertEqual(set(match.group(1).split()), self.core_skills())

    def test_powershell_runs_native_programs_only_through_the_guarded_helper(self) -> None:
        # Windows PowerShell 5.1 turns stderr captured by 2>&1 into a
        # terminating error under ErrorActionPreference Stop, so a bare
        # native call would abort the install on any warning.
        text = POWERSHELL_SCRIPT.read_text(encoding="utf-8")
        helper = re.search(
            r"function Invoke-NativeCommand\(.*?\n}\n", text, re.DOTALL
        )
        assert helper
        self.assertIn("$ErrorActionPreference = 'Continue'", helper.group(0))
        outside = text.replace(helper.group(0), "")
        code_lines = [
            line for line in outside.splitlines() if not line.lstrip().startswith("#")
        ]
        self.assertFalse([line for line in code_lines if "2>&1" in line])
        self.assertFalse([line for line in code_lines if re.match(r"\s*& ", line)])
        self.assertNotIn("$LASTEXITCODE", "\n".join(code_lines))

    def test_powershell_installer_matches_the_shell_installer(self) -> None:
        text = POWERSHELL_SCRIPT.read_text(encoding="utf-8")
        block = re.search(r"\$CoreSkills = @\((.*?)\)", text, re.DOTALL)
        assert block
        self.assertEqual(set(re.findall(r"'([^']+)'", block.group(1))), self.core_skills())
        shell = SCRIPT.read_text(encoding="utf-8")
        for shared in (
            "https://cloudcache.volccdn.com/ve/skills",
            "volcengine-core@volcengine-skills",
            "toolkit-manifest.json",
            "volcengine-agent-toolkit.zip",
            "VOLCENGINE_TOOLKIT_BASE_URL",
            "VOLCENGINE_TOOLKIT_DIR",
            "VOLCENGINE_TOOLKIT_GITHUB_URL",
        ):
            self.assertIn(shared, shell)
            self.assertIn(shared, text)


if __name__ == "__main__":
    unittest.main()
