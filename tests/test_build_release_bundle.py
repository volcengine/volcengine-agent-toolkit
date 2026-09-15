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
