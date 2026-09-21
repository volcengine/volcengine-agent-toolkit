import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/volcengine-identity-access-control/skills/volcengine-landing-zone"


class SolutionDeploymentContractTest(unittest.TestCase):
    def test_setup_requires_explicit_landing_zone_architecture_intent(self):
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Route by the requested outcome", skill)
        self.assertIn("部署网络/安全/数据/应用方案", skill)
        self.assertIn(
            "G1 applies only after routing has conclusively selected", skill
        )
        self.assertNotIn("| `landing zone`、`首次搭建`、`组织`", skill)

    def test_solution_deployment_keeps_secrets_customer_owned(self):
        guide = (
            SKILL / "references/solution-deployment/guidebook.md"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "The customer owns credential secrets and permission policy.",
            guide,
        )
        self.assertIn("prefer the `volcenginecc` provider", guide)
        self.assertIn("Use it by default when generating a new package", guide)
        self.assertIn("do not silently replace", guide)
        self.assertIn("recommend `ve login` first", guide)
        self.assertIn("### 2. Resolve and Confirm the Targets", guide)
        self.assertNotIn("credential paths", guide)
        self.assertNotIn("Make target adaptations", guide)

    def test_ve_login_profile_can_bootstrap_all_execution_paths(self):
        preflight = (SKILL / "references/preflight-checks.md").read_text(
            encoding="utf-8"
        )
        setup = (
            SKILL / "references/landing-zone-setup/guidebook.md"
        ).read_text(encoding="utf-8")
        account_factory = (
            SKILL / "references/account-factory/guidebook.md"
        ).read_text(encoding="utf-8")

        self.assertIn("recommend `ve login` first", preflight)
        self.assertIn("reuse the resulting profile", preflight)
        self.assertNotIn("proves CLI identity only", preflight)
        self.assertIn("`ve login`-first branch", setup)
        self.assertIn("`ve login`-first guidance", account_factory)

    def test_volcenginecc_070_reuses_ve_login_profile(self):
        guide = (
            SKILL / "references/solution-deployment/guidebook.md"
        ).read_text(encoding="utf-8")

        self.assertIn("`required_providers`", guide)
        self.assertIn("`.terraform.lock.hcl`", guide)
        self.assertIn("`volcenginecc` provider version is `0.0.70` or later", guide)
        self.assertIn("do not request separate AK/SK", guide)
        self.assertIn("For an older `volcenginecc` version or another provider", guide)

    def test_solution_deployment_supports_two_identity_strategies(self):
        guide = (
            SKILL / "references/solution-deployment/guidebook.md"
        ).read_text(encoding="utf-8")
        preflight = (SKILL / "references/preflight-checks.md").read_text(
            encoding="utf-8"
        )
        solution_checks = preflight.split("- `Solution Deployment`", 1)[1].split(
            "- `Cross-account execution phases`", 1
        )[0]

        self.assertIn("Provider role assumption", guide)
        self.assertIn("Target runtime identity", guide)
        self.assertIn("OrganizationAccessControlRole", guide)
        self.assertIn("target-to-identity strategy", guide)
        self.assertIn("provider role assumption", solution_checks)
        self.assertIn("runtime credential/profile", solution_checks)
        self.assertIn("OrganizationAccessControlRole", solution_checks)
        self.assertIn("target-to-identity mapping", solution_checks)


if __name__ == "__main__":
    unittest.main()
