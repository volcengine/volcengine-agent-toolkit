import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_release_bundle.py"
CORE_ROOT = REPO_ROOT / "skills" / "core"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
SPEC = importlib.util.spec_from_file_location("build_release_bundle", BUILD_SCRIPT)
BUILD_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD_MODULE)


class BuildReleaseBundleTests(unittest.TestCase):
    def build(self, output_dir):
        subprocess.run(
            [
                sys.executable,
                str(BUILD_SCRIPT),
                "--output-dir",
                str(output_dir),
                "--cdn-base-url",
                "https://cloudcache.volccdn.com/ve/skills",
            ],
            cwd=REPO_ROOT,
            check=True,
        )

    def test_builds_deterministic_core_bundle_and_manifest(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            self.build(first)
            self.build(second)

            first_bundle = Path(first) / "volcengine-skill-bundle.zip"
            second_bundle = Path(second) / "volcengine-skill-bundle.zip"
            first_manifest = Path(first) / "manifest.json"

            self.assertEqual(first_bundle.read_bytes(), second_bundle.read_bytes())
            self.assertEqual(
                json.loads(first_manifest.read_text()),
                json.loads((Path(second) / "manifest.json").read_text()),
            )

            package = json.loads((REPO_ROOT / "package.json").read_text())
            manifest = json.loads(first_manifest.read_text())
            digest = hashlib.sha256(first_bundle.read_bytes()).hexdigest()

            self.assertEqual(manifest["schemaVersion"], 1)
            self.assertEqual(manifest["version"], package["version"])
            self.assertEqual(manifest["bundle"]["file"], first_bundle.name)
            self.assertEqual(manifest["bundle"]["sha256"], digest)
            self.assertEqual(manifest["bundle"]["size"], first_bundle.stat().st_size)
            self.assertEqual(manifest["bundle"]["url"], first_bundle.name)
            cdn_manifest = json.loads(
                (Path(first) / "cdn-manifest.json").read_text()
            )
            self.assertEqual(
                cdn_manifest["bundle"]["url"],
                "https://cloudcache.volccdn.com/ve/skills/v%s/%s"
                % (package["version"], first_bundle.name),
            )
            core_skills = {
                path.name for path in CORE_ROOT.iterdir() if path.is_dir()
            }
            self.assertEqual(
                {entry["name"] for entry in manifest["skills"]}, core_skills
            )

            with zipfile.ZipFile(first_bundle) as archive:
                names = archive.namelist()
                roots = {name.split("/", 1)[0] for name in names}
                self.assertEqual(roots, core_skills)
                for skill in core_skills:
                    self.assertIn("%s/SKILL.md" % skill, names)

    def test_builds_deterministic_toolkit_package_and_manifest(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            self.build(first)
            self.build(second)

            toolkit = Path(first) / "volcengine-agent-toolkit.zip"
            self.assertEqual(
                toolkit.read_bytes(),
                (Path(second) / "volcengine-agent-toolkit.zip").read_bytes(),
            )
            package = json.loads((REPO_ROOT / "package.json").read_text())
            manifest = json.loads((Path(first) / "toolkit-manifest.json").read_text())
            self.assertEqual(manifest["schemaVersion"], 1)
            self.assertEqual(manifest["version"], package["version"])
            self.assertEqual(
                manifest["toolkit"]["sha256"],
                hashlib.sha256(toolkit.read_bytes()).hexdigest(),
            )
            self.assertEqual(manifest["toolkit"]["size"], toolkit.stat().st_size)
            self.assertEqual(manifest["toolkit"]["url"], toolkit.name)
            cdn_manifest = json.loads(
                (Path(first) / "cdn-toolkit-manifest.json").read_text()
            )
            self.assertEqual(
                cdn_manifest["toolkit"]["url"],
                "https://cloudcache.volccdn.com/ve/skills/v%s/%s"
                % (package["version"], toolkit.name),
            )
            # The core bundle manifest is the Volcengine CLI contract; the
            # toolkit must not leak into it.
            self.assertNotIn(
                "toolkit", json.loads((Path(first) / "manifest.json").read_text())
            )

            with zipfile.ZipFile(toolkit) as archive:
                names = set(archive.namelist())
                script = archive.getinfo("hooks/run-apmplus-reporter.sh")
            self.assertTrue((script.external_attr >> 16) & 0o100)
            # Everything a host reads at install time is at the archive root.
            for required in (
                ".claude-plugin/marketplace.json",
                ".agents/plugins/marketplace.json",
                ".cursor-plugin/marketplace.json",
                "package.json",
                "plugins/volcengine-core/.claude-plugin/plugin.json",
                "plugins/volcengine-core/skills/volcengine-find-skills/SKILL.md",
                "skills/core/volcengine-find-skills/references/catalog.json",
            ):
                self.assertIn(required, names)
            roots = {name.split("/", 1)[0] for name in names}
            self.assertFalse(roots & {"tests", "scripts", ".github", "docs", "README.md"})
            catalog = json.loads(
                (
                    CORE_ROOT / "volcengine-find-skills" / "references" / "catalog.json"
                ).read_text()
            )
            for plugin in catalog["plugins"]:
                for skill in plugin["skills"]:
                    self.assertIn(
                        "plugins/%s/skills/%s/SKILL.md" % (plugin["name"], skill["name"]),
                        names,
                    )

    def test_interpreter_caches_are_left_out_of_release_archives(self):
        with tempfile.TemporaryDirectory() as root:
            skill_dir = Path(root) / "volcengine-cli"
            (skill_dir / "scripts" / "__pycache__").mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# test\n")
            (skill_dir / "scripts" / "tool.py").write_text("print('x')\n")
            (skill_dir / "scripts" / "__pycache__" / "tool.cpython-312.pyc").write_bytes(b"x")
            (skill_dir / "scripts" / "stray.pyc").write_bytes(b"x")
            (skill_dir / ".DS_Store").write_bytes(b"x")
            files = [
                path.relative_to(skill_dir).as_posix()
                for path in BUILD_MODULE.skill_files(skill_dir)
            ]
            self.assertEqual(files, ["SKILL.md", "scripts/tool.py"])

            clean = Path(root) / "clean"
            clean.mkdir()
            (clean / "SKILL.md").write_text("# test\n")
            (clean / "scripts").mkdir()
            (clean / "scripts" / "tool.py").write_text("print('x')\n")
            self.assertEqual(
                BUILD_MODULE.content_digest(skill_dir, BUILD_MODULE.skill_files(skill_dir)),
                BUILD_MODULE.content_digest(clean, BUILD_MODULE.skill_files(clean)),
            )

    def test_toolkit_paths_must_be_valid_on_every_supported_os(self):
        BUILD_MODULE.validate_portable_paths(
            [".agents/plugins/marketplace.json", "plugins/a/skills/b/SKILL.md"]
        )
        for paths, message in (
            (["skills/aux.md"], "not valid on Windows"),
            (["skills/a:b.md"], "not valid on Windows"),
            (["skills/trailing./SKILL.md"], "not valid on Windows"),
            (["skills/Readme.md", "skills/README.md"], "differ only by case"),
            (["skills/" + "x" * 200], "Windows path limit"),
        ):
            with self.assertRaisesRegex(ValueError, message):
                BUILD_MODULE.validate_portable_paths(paths)

    def test_discovers_core_skills_without_a_fixed_allowlist(self):
        with tempfile.TemporaryDirectory() as root:
            core_root = Path(root)
            for name in ("volcengine-cli", "volcengine-new-skill"):
                skill_dir = core_root / name
                skill_dir.mkdir()
                (skill_dir / "SKILL.md").write_text("# test\n")
            with mock.patch.object(BUILD_MODULE, "CORE_ROOT", core_root):
                self.assertEqual(
                    [path.name for path in BUILD_MODULE.core_skill_directories()],
                    ["volcengine-cli", "volcengine-new-skill"],
                )

    def test_rejects_bundle_larger_than_fifty_mib(self):
        with self.assertRaisesRegex(ValueError, "50 MiB"):
            BUILD_MODULE.validate_bundle_size(50 * 1024 * 1024 + 1)

    def test_rejects_release_version_that_differs_from_package(self):
        with tempfile.TemporaryDirectory() as output_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(BUILD_SCRIPT),
                    "--output-dir",
                    output_dir,
                    "--version",
                    "9.9.9",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match package.json", result.stderr)

    def test_release_workflow_uses_cli_tos_upload_contract(self):
        workflow = RELEASE_WORKFLOW.read_text()

        self.assertIn("python3 -m pip install --user --upgrade awscli", workflow)
        self.assertIn("secrets.TOS_ACCESS_KEY_ID", workflow)
        self.assertIn("secrets.TOS_SECRET_ACCESS_KEY", workflow)
        self.assertIn("https://tos-s3-cn-beijing.volces.com", workflow)
        self.assertIn(
            '"s3://${bucket}/${prefix}/v${version}/volcengine-skill-bundle.zip"',
            workflow,
        )
        self.assertIn(
            '"s3://${bucket}/${prefix}/v${version}/manifest.json"', workflow
        )
        self.assertIn(
            '"s3://${bucket}/${prefix}/latest/manifest.json"', workflow
        )
        self.assertNotIn("tosutil", workflow)

    def test_release_workflow_publishes_the_toolkit_and_installers(self):
        workflow = RELEASE_WORKFLOW.read_text()

        for target in (
            '"s3://${bucket}/${prefix}/v${version}/volcengine-agent-toolkit.zip"',
            '"s3://${bucket}/${prefix}/v${version}/toolkit-manifest.json"',
            '"s3://${bucket}/${prefix}/latest/toolkit-manifest.json"',
            '"s3://${bucket}/${prefix}/install.sh"',
            '"s3://${bucket}/${prefix}/install.ps1"',
            '"s3://${bucket}/${prefix}/install.md"',
        ):
            self.assertIn(target, workflow)
        for source in (
            "scripts/install_toolkit.sh",
            "scripts/install_toolkit.ps1",
            "docs/install.md",
        ):
            self.assertIn(source, workflow)
            self.assertTrue((REPO_ROOT / source).is_file())
        self.assertIn("published toolkit sha256 mismatch", workflow)
        # Versioned objects are verified before any latest pointer moves.
        self.assertLess(
            workflow.index("- name: Install the published toolkit from the CDN"),
            workflow.index("- name: Publish latest manifest last"),
        )
        self.assertLess(
            workflow.index('"s3://${bucket}/${prefix}/v${version}/toolkit-manifest.json"'),
            workflow.index('"s3://${bucket}/${prefix}/latest/toolkit-manifest.json"'),
        )
        for refreshed in (
            "latest/toolkit-manifest.json",
            "install.sh",
            "install.ps1",
            "install.md",
        ):
            self.assertIn('"$refresh_base/%s"' % refreshed, workflow)

    def test_release_workflow_refreshes_latest_cdn_manifest(self):
        workflow = RELEASE_WORKFLOW.read_text()

        self.assertIn("- name: Refresh CDN release pointers", workflow)
        self.assertIn("secrets.VOLCENGINE_ACCESS_KEY", workflow)
        self.assertIn("secrets.VOLCENGINE_SECRET_KEY", workflow)
        self.assertIn("vars.VOLCENGINE_REGION", workflow)
        self.assertIn('npm install -g "@volcengine/cli@1.1.5"', workflow)
        self.assertIn("ve cdn SubmitRefreshTask", workflow)
        self.assertIn(
            'refresh_url="${public_base%/}/${prefix#/}/latest/manifest.json"',
            workflow,
        )
        self.assertIn('--UrlList.1 "$refresh_url"', workflow)


if __name__ == "__main__":
    unittest.main()
