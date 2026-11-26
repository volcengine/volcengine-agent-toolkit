"""Guard the credential rules of the volcengine-cli skill against truncation.

Agent hosts may show a model only the head and tail of a long tool output. Codex
keeps about 10,000 bytes (half from each end) for models it has no metadata for,
so the rules that must never be missed sit in the first and last part of the
skill entry file. The middle may grow, within a loose overall cap.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills/core/volcengine-cli"
SKILL = SKILL_DIR / "SKILL.md"
CORE_COPY = REPO_ROOT / "plugins/volcengine-core/skills/volcengine-cli"

MAX_SKILL_BYTES = 20_000
VISIBLE_BYTES = 4_900
# Printed at both edges of the region a host may cut out of the middle.
CUT_RECOVERY_COMMAND = "sed -n '/^## Product CLI routing/,/^## References/p'"
ENV_DUMP_COMMANDS = ("`env`", "`printenv`", "`set`", "`export -p`", "`echo $VOLCENGINE_*`")
STEERING_PHRASES = (
    r"runtime\s+environment",
    r"host\s+environment",
    r"actual\s+Agent\s+environment",
    r"verify\s+credentials",
    r"运行环境",
    r"宿主环境",
)


class CliSkillCredentialGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SKILL.read_text(encoding="utf-8")
        raw = cls.text.encode("utf-8")
        cls.head = raw[:VISIBLE_BYTES].decode("utf-8", "ignore")
        cls.tail = raw[-VISIBLE_BYTES:].decode("utf-8", "ignore")

    def assert_credential_rules(self, section: str) -> None:
        for command in ENV_DUMP_COMMANDS:
            self.assertIn(command, section)
        self.assertIn("~/.volcengine/config.json", section)
        self.assertIn("`sed`", section)
        self.assertIn("`ve sts GetCallerIdentity` is the only credential check", section.replace(
            "The only credential check is `ve sts GetCallerIdentity`",
            "`ve sts GetCallerIdentity` is the only credential check",
        ))

    def test_skill_stays_an_entry_file(self) -> None:
        self.assertLessEqual(len(self.text.encode("utf-8")), MAX_SKILL_BYTES)

    def test_head_states_credential_and_caller_rules(self) -> None:
        head = self.head
        self.assert_credential_rules(head)
        self.assertIn(CUT_RECOVERY_COMMAND, head)
        self.assertIn("`/proc/*/environ`", head)
        self.assertIn("`declare -x`", head)
        self.assertIn("## Agent caller metadata (mandatory)", head)
        self.assertIn("Your own Agent product name", head)
        self.assertIn("do not look at environment variables or host information", head)
        caller_end = self.text.index("\n## Product CLI routing\n")
        self.assertLessEqual(len(self.text[:caller_end].encode("utf-8")), VISIBLE_BYTES)
        self.assertLess(
            self.text.index("## Credential safety (mandatory)"),
            self.text.index("## Agent caller metadata (mandatory)"),
        )

    def test_tail_holds_rules_flow_and_credential_reminder(self) -> None:
        self.assert_credential_rules(self.tail)
        for heading in ("\n## References\n", "\n## Mandatory rules\n", "\n## Native OpenAPI execution flow\n"):
            self.assertIn(heading, self.tail)
        self.assertIn(CUT_RECOVERY_COMMAND, self.tail)

    def test_extended_api_and_realname_guidance_present(self) -> None:
        self.assertIn("### Extended APIs", self.text)
        self.assertIn("ve account_verify GetVerifyInfo", self.text)
        self.assertIn("scripts/call_extend_api.py", self.text)
        self.assertIn("https://console.volcengine.com/user/authentication/detail/", self.text)

    def test_no_wording_that_points_at_the_environment(self) -> None:
        files = [SKILL, *sorted((SKILL_DIR / "references").glob("*.md"))]
        files.append(REPO_ROOT / "skills/core/volcengine-knowledge-search/SKILL.md")
        for path in files:
            text = path.read_text(encoding="utf-8")
            for phrase in STEERING_PHRASES:
                with self.subTest(path=path.name, phrase=phrase):
                    self.assertIsNone(re.search(phrase, text, re.IGNORECASE))

    def test_credential_variables_carry_no_description(self) -> None:
        frontmatter = self.text.split("---", 2)[1]
        for name in ("ACCESS_KEY", "SECRET_KEY", "SESSION_TOKEN"):
            with self.subTest(variable=name):
                self.assertRegex(
                    frontmatter,
                    rf"- name: VOLCENGINE_{name}\n        required: false\n      - name:",
                )

    def test_core_plugin_copy_matches_source(self) -> None:
        for source in sorted(SKILL_DIR.rglob("*.md")):
            with self.subTest(path=str(source.relative_to(SKILL_DIR))):
                copy = CORE_COPY / source.relative_to(SKILL_DIR)
                self.assertEqual(copy.read_bytes(), source.read_bytes())


if __name__ == "__main__":
    unittest.main()
