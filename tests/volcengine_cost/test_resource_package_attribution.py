from __future__ import annotations

import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "skills" / "core" / "volcengine-cost"
SCRIPTS = ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "resource_package" / "used_up"
sys.path.insert(0, str(SCRIPTS))

from cost_query.arrears.resource_package import analyze_resource_package_attribution  # noqa: E402
from cost_query.billing.client import FixtureBillingClient  # noqa: E402
from cost_query.billing.fetch import FetchConfig, collect_query  # noqa: E402
from cost_query.billing.validation import validate_request_body  # noqa: E402
from cost_query.common.errors import BillingQueryError, ErrorCode  # noqa: E402
from attribute_resource_packages import main as attribute_main  # noqa: E402
from query_billing import main as query_main  # noqa: E402


def load_result_list(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["Result"]["List"]


def write_rows_csv(path: Path, rows: list[dict]) -> None:
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                for key, value in row.items()
            }
            for row in rows
        )


def write_metadata(path: Path, *, complete: bool) -> None:
    path.with_suffix(".meta.json").write_text(
        json.dumps(
            {
                "output_protocol_version": "1.0",
                "coverage": {
                    "is_complete": complete,
                    "failed_queries": [] if complete else [{"query_id": "truncated"}],
                },
                "freshness": {"partial_period": False},
            }
        ),
        encoding="utf-8",
    )


def write_inline(path: Path, rows: list[dict], *, complete: bool) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "success",
                "message": "fixture",
                "result": rows,
                "_meta": {
                    "output_protocol_version": "1.0",
                    "coverage": {
                        "is_complete": complete,
                        "failed_queries": [] if complete else [{"query_id": "page_only"}],
                    },
                    "freshness": {"partial_period": False},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class ResourcePackageQueryTest(unittest.TestCase):
    def _run(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = query_main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_resource_package_request_contract_accepts_integer_limit_and_enforces_bounds_and_utc(self) -> None:
        self.assertEqual(
            {"ResourceType": "Package", "MaxResults": "20"},
            validate_request_body("ListResourcePackages", {"ResourceType": "Package", "MaxResults": 20}),
        )
        with self.assertRaises(BillingQueryError) as context:
            validate_request_body("ListResourcePackages", {"ResourceType": "Package", "MaxResults": "21"})
        self.assertEqual(ErrorCode.INVALID_ARGUMENT, context.exception.code)
        with self.assertRaises(BillingQueryError):
            validate_request_body(
                "ListPackageUsageDetails",
                {
                    "ResourceType": "Package",
                    "DeductBeginTime": "2026-08-01 00:00:00",
                    "DeductEndTime": "2026-10-01T00:00:00Z",
                    "MaxResults": "50",
                },
            )

    def test_resource_packages_full_follows_next_token_and_hides_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "packages.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListResourcePackages",
                    "--body", '{"ResourceType":"Package","Product":"TOS","MaxResults":20}',
                    "--pagination", "full",
                    "--fixture-dir", str(FIXTURES),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
            with output.open(encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
            metadata = json.loads(output.with_suffix(".meta.json").read_text(encoding="utf-8"))
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("success", payload["status"])
        self.assertEqual(2, len(rows))
        self.assertEqual(2, metadata["coverage"]["pages_fetched"])
        self.assertTrue(metadata["coverage"]["is_complete"])
        self.assertTrue({"OwnerID", "UserName", "SubjectNo"}.isdisjoint(rows[0]))

    def test_resource_packages_full_uses_next_token_without_limit_or_offset(self) -> None:
        client = FixtureBillingClient(FIXTURES)
        result = collect_query(
            client=client,
            action="ListResourcePackages",
            query_id="packages",
            base_body={"ResourceType": "Package", "Product": "TOS", "MaxResults": 20},
            config=FetchConfig(pagination="full", page_size=20),
            sleeper=lambda _: None,
        )

        self.assertTrue(result.is_complete)
        self.assertEqual(2, result.pages_fetched)
        self.assertEqual(["", "p2"], [call["body"]["NextToken"] for call in client.calls])
        self.assertEqual(["20", "20"], [call["body"]["MaxResults"] for call in client.calls])
        self.assertTrue(all({"Limit", "Offset"}.isdisjoint(call["body"]) for call in client.calls))

    def test_usage_details_full_follows_next_token_and_exposes_match_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "usage.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListPackageUsageDetails",
                    "--body", '{"ResourceType":"Package","DeductBeginTime":"2026-08-01T00:00:00Z","DeductEndTime":"2026-10-01T00:00:00Z","MaxResults":"50"}',
                    "--pagination", "full",
                    "--fixture-dir", str(FIXTURES),
                    "--out", str(output),
                ]
            )
            with output.open(encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual(2, json.loads(stdout)["_meta"]["row_count"])
        self.assertEqual(
            {"InstanceNo", "DeductionProduct", "DeductionElementCode", "DeductionInstanceNo", "DeductionRegionCode"},
            {field for field in rows[0] if field in {"InstanceNo", "DeductionProduct", "DeductionElementCode", "DeductionInstanceNo", "DeductionRegionCode"}},
        )
        self.assertTrue({"OwnerID", "UserName", "DeductionAccountID", "DeductionUserName", "SubjectNo"}.isdisjoint(rows[0]))

    def test_token_actions_reject_offset_and_nonempty_full_start(self) -> None:
        code, stdout, stderr = self._run(
            [
                "--action", "ListResourcePackages",
                "--body", '{"ResourceType":"Package","MaxResults":"20"}',
                "--pagination", "full",
                "--page-offset", "1",
                "--fixture-dir", str(FIXTURES),
            ]
        )
        self.assertEqual(2, code)
        self.assertEqual("", stderr)
        self.assertEqual("INVALID_ARGUMENT", json.loads(stdout)["_meta"]["error"]["code"])

        code, stdout, stderr = self._run(
            [
                "--action", "ListResourcePackages",
                "--body", '{"ResourceType":"Package","MaxResults":"20","NextToken":"p2"}',
                "--pagination", "full",
                "--fixture-dir", str(FIXTURES),
            ]
        )
        self.assertEqual(2, code)
        self.assertEqual("", stderr)
        self.assertEqual("INVALID_ARGUMENT", json.loads(stdout)["_meta"]["error"]["code"])

    def test_token_page_preserves_requested_next_token(self) -> None:
        code, stdout, stderr = self._run(
            [
                "--action", "ListResourcePackages",
                "--body", '{"ResourceType":"Package","MaxResults":"20","NextToken":"p2"}',
                "--pagination", "page",
                "--fixture-dir", str(FIXTURES),
            ]
        )
        payload = json.loads(stdout)
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("success", payload["status"])
        self.assertEqual(1, payload["_meta"]["row_count"])
        self.assertEqual("tos-pack-other", payload["result"][0]["InstanceNo"])

    def test_repeated_next_token_returns_partial_evidence(self) -> None:
        first = json.loads((FIXTURES / "ListResourcePackages__token-start.json").read_text(encoding="utf-8"))
        second = json.loads((FIXTURES / "ListResourcePackages__token-p2.json").read_text(encoding="utf-8"))
        first["Result"]["NextToken"] = "repeat"
        second["Result"]["NextToken"] = "repeat"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ListResourcePackages__token-start.json").write_text(json.dumps(first), encoding="utf-8")
            (root / "ListResourcePackages__token-repeat.json").write_text(json.dumps(second), encoding="utf-8")
            output = root / "partial.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListResourcePackages",
                    "--body", '{"ResourceType":"Package","MaxResults":"20"}',
                    "--pagination", "full",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
            metadata = json.loads(output.with_suffix(".meta.json").read_text(encoding="utf-8"))
        self.assertEqual((6, ""), (code, stderr))
        self.assertEqual("partial", payload["status"])
        self.assertEqual("PAGINATION_INCOMPLETE", metadata["coverage"]["failed_queries"][0]["error"]["code"])


class ResourcePackageAttributionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.packages = [
            *load_result_list(FIXTURES / "ListResourcePackages__token-start.json"),
            *load_result_list(FIXTURES / "ListResourcePackages__token-p2.json"),
        ]
        self.usage = [
            *load_result_list(FIXTURES / "ListPackageUsageDetails__token-start.json"),
            *load_result_list(FIXTURES / "ListPackageUsageDetails__token-u2.json"),
        ]
        self.bills = json.loads((FIXTURES / "bill-details.json").read_text(encoding="utf-8"))["rows"]

    def run_cli(self, packages: Path, usage: Path, bills: Path) -> tuple[int, dict, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = attribute_main(
                [
                    "--packages", str(packages),
                    "--usage-details", str(usage),
                    "--bill-details", str(bills),
                    "--analysis-period", "2026-09",
                    "--comparison-period", "2026-08",
                ]
            )
        return code, json.loads(stdout.getvalue()), stderr.getvalue()

    def write_inputs(self, root: Path) -> tuple[Path, Path, Path]:
        packages = root / "packages.csv"
        usage = root / "usage.csv"
        bills = root / "bills.csv"
        write_rows_csv(packages, self.packages)
        write_rows_csv(usage, self.usage)
        write_rows_csv(bills, self.bills)
        return packages, usage, bills

    def test_manual_csv_only_returns_insufficient_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inputs = self.write_inputs(Path(directory))
            code, payload, stderr = self.run_cli(*inputs)

        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("success", payload["status"])
        result = payload["result"]
        self.assertEqual([], result["supported_reasons"])
        self.assertEqual(
            {"packages": "unknown", "usage_details": "unknown", "bill_details": "unknown"},
            {item["input"]: item["completeness"] for item in result["input_evidence"]},
        )

    def test_one_incomplete_query_artifact_makes_result_partial(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packages, usage, bills = self.write_inputs(Path(directory))
            write_metadata(packages, complete=False)
            write_metadata(usage, complete=True)
            write_metadata(bills, complete=True)

            code, payload, stderr = self.run_cli(packages, usage, bills)

        self.assertEqual((6, ""), (code, stderr))
        self.assertEqual("partial", payload["status"])
        result = payload["result"]
        self.assertEqual([], result["supported_reasons"])
        self.assertEqual(
            {"packages": "partial", "usage_details": "complete", "bill_details": "complete"},
            {item["input"]: item["completeness"] for item in result["input_evidence"]},
        )

    def test_page_completed_inline_input_makes_result_partial(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packages = root / "packages.json"
            usage = root / "usage.json"
            bills = root / "bills.json"
            write_inline(packages, self.packages, complete=False)
            write_inline(usage, self.usage, complete=True)
            write_inline(bills, self.bills, complete=True)

            code, payload, stderr = self.run_cli(packages, usage, bills)

        self.assertEqual((6, ""), (code, stderr))
        self.assertEqual("partial", payload["status"])
        result = payload["result"]
        self.assertEqual([], result["supported_reasons"])
        self.assertEqual(
            {"packages": "partial", "usage_details": "complete", "bill_details": "complete"},
            {item["input"]: item["completeness"] for item in result["input_evidence"]},
        )

    def test_used_up_and_deduction_decline_are_supported_with_exact_evidence(self) -> None:
        result = analyze_resource_package_attribution(
            packages=self.packages,
            usage_details=self.usage,
            bill_details=self.bills,
            analysis_period="2026-09",
            comparison_period="2026-08",
        )
        reasons = {item["reason_type"]: item for item in result["supported_reasons"]}
        self.assertEqual(
            {"resource_package_used_up", "resource_package_deduction_declined"},
            set(reasons),
        )
        used_up = reasons["resource_package_used_up"]
        self.assertEqual("tos-pack-001", used_up["package"]["InstanceNo"])
        self.assertEqual("0", used_up["package"]["AvailableAmount"])
        self.assertTrue(used_up["scope_match"]["product"])
        self.assertTrue(used_up["scope_match"]["charge_item"])
        self.assertEqual("not_declared_by_package_contract", used_up["scope_match"]["wildcards"])
        decline = reasons["resource_package_deduction_declined"]["evidence"]
        self.assertEqual("4.8", decline["comparison_period_deduction_use_amount"])
        self.assertEqual("0.2", decline["analysis_period_deduction_use_amount"])
        self.assertEqual("860.00", decline["analysis_period_payable_amount"])

    def test_missing_usage_link_yields_insufficient_evidence(self) -> None:
        result = analyze_resource_package_attribution(
            packages=self.packages,
            usage_details=[],
            bill_details=self.bills,
            analysis_period="2026-09",
            comparison_period="2026-08",
        )
        self.assertEqual([], result["supported_reasons"])
        self.assertGreater(result["summary"]["insufficient_candidate_count"], 0)

    def test_expired_package_uses_bill_consumption_time(self) -> None:
        package = dict(self.packages[0])
        package.update(Status="Expired", AvailableAmount="1", ExpiryTime="2026-08-31T23:59:59Z")
        result = analyze_resource_package_attribution(
            packages=[package],
            usage_details=self.usage,
            bill_details=self.bills,
            analysis_period="2026-09",
            comparison_period="2026-08",
        )
        self.assertIn(
            "resource_package_expired",
            {item["reason_type"] for item in result["supported_reasons"]},
        )

    def test_not_effective_package_uses_bill_consumption_time(self) -> None:
        package = dict(self.packages[0])
        package.update(Status="NotEffective", AvailableAmount="5", EffectiveTime="2026-10-01T00:00:00Z")
        result = analyze_resource_package_attribution(
            packages=[package],
            usage_details=self.usage,
            bill_details=self.bills,
            analysis_period="2026-09",
            comparison_period="2026-08",
        )
        self.assertIn(
            "resource_package_not_effective",
            {item["reason_type"] for item in result["supported_reasons"]},
        )

    def test_configuration_wildcard_text_is_not_treated_as_scope_contract(self) -> None:
        package = dict(self.packages[0])
        package["ConfigurationName"] = "全部配置 / 全部计费项"
        result = analyze_resource_package_attribution(
            packages=[package],
            usage_details=[],
            bill_details=self.bills,
            analysis_period="2026-09",
            comparison_period="2026-08",
        )
        self.assertEqual([], result["supported_reasons"])

    def test_noncoverage_requires_explicit_candidate_and_contract_mismatch(self) -> None:
        package = dict(self.packages[0])
        package.update(InstanceNo="ecs-pack-001", Product="ECS", ProductName="云服务器")
        without_candidate = analyze_resource_package_attribution(
            packages=[package],
            usage_details=[],
            bill_details=self.bills,
            analysis_period="2026-09",
        )
        self.assertEqual([], without_candidate["supported_reasons"])

        with_candidate = analyze_resource_package_attribution(
            packages=[package],
            usage_details=[],
            bill_details=self.bills,
            analysis_period="2026-09",
            candidate_instance_nos=["ecs-pack-001"],
        )
        self.assertEqual(1, len(with_candidate["supported_reasons"]))
        reason = with_candidate["supported_reasons"][0]
        self.assertEqual("resource_package_not_covering", reason["reason_type"])
        self.assertEqual("product", reason["evidence"]["mismatch_dimension"])
        self.assertFalse(reason["scope_match"]["product"])

    def analyze(self, bills=None, usage=None) -> dict:
        return analyze_resource_package_attribution(
            packages=self.packages,
            usage_details=self.usage if usage is None else usage,
            bill_details=self.bills if bills is None else bills,
            analysis_period="2026-09", comparison_period="2026-08",
        )

    def declines(self, bills=None, usage=None) -> list[dict]:
        return [item for item in self.analyze(bills=bills, usage=usage)["supported_reasons"] if item["reason_type"] == "resource_package_deduction_declined"]

    def test_period_payable_fall_is_not_reported_as_an_increase(self) -> None:
        bills = [*self.bills, dict(self.bills[0], PayableAmount="1200.00")]
        self.assertEqual([], self.declines(bills=bills))
        self.assertEqual(self.analyze(bills=bills), self.analyze(bills=list(reversed(bills)), usage=list(reversed(self.usage))))

    def test_bill_totals_sum_both_periods_and_usage_is_not_multiplied(self) -> None:
        previous = dict(self.bills[0], PayableAmount="100.00")
        current = dict(self.bills[1], PayableAmount="430.00")
        reasons = self.declines(bills=[previous, current, dict(previous), dict(current)])
        self.assertEqual(1, len(reasons))
        evidence = reasons[0]["evidence"]
        self.assertEqual("200.00", evidence["comparison_period_payable_amount"])
        self.assertEqual("860.00", evidence["analysis_period_payable_amount"])
        self.assertEqual("4.8", evidence["comparison_period_deduction_use_amount"])
        self.assertEqual("0.2", evidence["analysis_period_deduction_use_amount"])
        self.assertEqual(2, evidence["analysis_period_row_count"])

    def test_missing_bill_identity_or_amount_blocks_comparison(self) -> None:
        for field in ("Product", "ConfigName", "InstanceNo", "ElementCode", "Region", "BillingMode", "Unit", "Currency", "PayableAmount", "Count", "DeductionCount"):
            for index in (0, 1):
                with self.subTest(field=field, index=index):
                    bills = [dict(row) for row in self.bills]
                    bills[index].pop(field)
                    self.assertEqual([], self.declines(bills=bills))

    def test_missing_usage_identity_or_amount_does_not_allow_partial_sum(self) -> None:
        for field in ("InstanceNo", "DeductionProduct", "DeductionElementCode", "DeductionInstanceNo", "DeductionRegionCode", "DeductionUseAmount", "DeductionInstanceUnit"):
            with self.subTest(field=field):
                usage = [dict(row) for row in self.usage]
                usage.append(dict(self.usage[1]))
                usage[-1].pop(field)
                result = self.analyze(usage=usage)
                self.assertEqual([], self.declines(usage=usage))
                self.assertTrue(any(field in str(item["missing_evidence"]) for item in result["insufficient_evidence"]))

    def test_usage_unit_must_match_bill_unit_without_fallback(self) -> None:
        usage = [dict(row, DeductionInstanceUnit="GB") for row in self.usage]
        self.assertEqual([], self.declines(usage=usage))

    def test_usage_consumption_time_cannot_fall_back_to_deduction_time(self) -> None:
        usage = [dict(row) for row in self.usage]
        usage[1].pop("BeginTime")
        self.assertEqual([], self.declines(usage=usage))

    def test_usage_spanning_months_cannot_be_assigned_to_start_month(self) -> None:
        usage = [dict(row) for row in self.usage]
        usage[1]["EndTime"] = "2026-10-02T00:00:00Z"
        self.assertEqual([], self.declines(usage=usage))

    def test_usage_without_config_key_cannot_be_joined_to_multiple_bill_configs(self) -> None:
        bills = [*self.bills, *(dict(row, ConfigName="another-config") for row in self.bills)]
        self.assertEqual([], self.declines(bills=bills))

    def test_comparison_period_only_config_also_makes_usage_assignment_ambiguous(self) -> None:
        bills = [*self.bills, dict(self.bills[0], ConfigName="another-config")]
        self.assertEqual([], self.declines(bills=bills))

    def test_positive_attribution_is_independent_of_bill_and_usage_order(self) -> None:
        self.assertEqual(
            self.analyze(),
            self.analyze(bills=list(reversed(self.bills)), usage=list(reversed(self.usage))),
        )

    def test_invalid_time_in_an_extra_usage_row_blocks_partial_sum(self) -> None:
        usage = [*self.usage, dict(self.usage[1], BeginTime="invalid-time")]
        self.assertEqual([], self.declines(usage=usage))

    def test_consumption_interval_starting_before_window_cannot_be_silently_skipped(self) -> None:
        usage = [*self.usage, dict(self.usage[0], BeginTime="2026-07-31T00:00:00Z")]
        self.assertEqual([], self.declines(usage=usage))


if __name__ == "__main__":
    unittest.main()
