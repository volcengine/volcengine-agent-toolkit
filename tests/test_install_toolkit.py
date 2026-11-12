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

    def test_doubao_work_always_uses_the_cdn_package(self) -> None:
        self.publish("1.3.4")
        probe = self.root / "probe.html"
        probe.write_text("ok", encoding="utf-8")
        result = self.run_installer("--agent", "doubao-work", "--dry-run", github_url=probe.as_uri())
        self.assertEqual(parse_kv(result.stdout)["SOURCE"], "cdn")

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
        suffix = Path(".doubaowork") / "agent_mode" / "workspace" / ".user_skills"
        roots = [
            self.home / "Library" / "Application Support" / "DoubaoWork",
            self.home / ".config" / "DoubaoWork",
        ]
        profiles = []
        for root in roots:
            for profile in ("Default", "Profile 2"):
                target = root / profile / suffix
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

    def test_doubao_work_without_a_workspace_says_what_to_do(self) -> None:
        result = self.run_installer("--agent", "doubao-work")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No DoubaoWork user skill directory found", result.stderr)

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

    def test_missing_host_cli_is_reported(self) -> None:
        result = self.run_installer("--agent", "claude")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("'claude' is not on PATH", result.stderr)


class InstallerContractTest(unittest.TestCase):
    def core_skills(self) -> set[str]:
        return {path.name for path in CORE_ROOT.iterdir() if path.is_dir()}

    def test_shell_installer_lists_every_core_skill(self) -> None:
        match = re.search(r'^CORE_SKILLS="([^"]+)"$', SCRIPT.read_text(encoding="utf-8"), re.MULTILINE)
        assert match
        self.assertEqual(set(match.group(1).split()), self.core_skills())

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
