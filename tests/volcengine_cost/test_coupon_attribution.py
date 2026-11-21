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
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "coupon" / "expired"
sys.path.insert(0, str(SCRIPTS))

from cost_query.arrears.coupon import analyze_coupon_attribution  # noqa: E402
from cost_query.billing.validation import validate_request_body  # noqa: E402
from cost_query.common.errors import BillingQueryError  # noqa: E402
from attribute_coupons import main as attribute_main  # noqa: E402
from query_billing import main as query_main  # noqa: E402


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


class CouponQueryTest(unittest.TestCase):
    def _run(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = query_main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_coupon_request_validates_status_and_iso_time_range(self) -> None:
        self.assertEqual(
            {"Status": "1,2,3", "Limit": 10, "Offset": 0},
            validate_request_body("ListCoupons", {"Status": "1,2,3", "Limit": 10, "Offset": 0}),
        )
        with self.assertRaises(BillingQueryError):
            validate_request_body("ListCoupons", {"Status": "2,9"})
        with self.assertRaises(BillingQueryError):
            validate_request_body(
                "ListCoupons",
                {"ValidBeginTime": "2026-10-01T00:00:00Z", "ValidEndTime": "2026-09-01T00:00:00Z"},
            )

    def test_coupon_full_query_handles_root_response_and_hides_account_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "coupons.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListCoupons",
                    "--body", '{"ProductCode":"TOS"}',
                    "--pagination", "full",
                    "--page-size", "1",
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
        self.assertTrue({"AccountID", "AssignedOwnerIDList"}.isdisjoint(rows[0]))
        limits = json.loads(rows[0]["ProductLimitList"])
        self.assertEqual(1, limits[0]["ConfigurationType"])
        self.assertEqual(0, limits[0]["ChargeItemType"])

    def test_coupon_usage_full_query_requires_coupon_and_hides_account_ids(self) -> None:
        with self.assertRaises(BillingQueryError):
            validate_request_body("ListCouponUsageRecords", {"Limit": 10, "Offset": 0})
        self.assertEqual(
            {"CouponID": "cpn-tos-expired", "Limit": 1000, "Offset": 0},
            validate_request_body(
                "ListCouponUsageRecords",
                {"CouponID": "cpn-tos-expired", "Limit": 1000, "Offset": 0},
            ),
        )
        with self.assertRaises(BillingQueryError):
            validate_request_body(
                "ListCouponUsageRecords",
                {"CouponID": "cpn-tos-expired", "Limit": 1001, "Offset": 0},
            )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "usage.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListCouponUsageRecords",
                    "--body", '{"CouponID":"cpn-tos-expired"}',
                    "--pagination", "full",
                    "--page-size", "1",
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
        self.assertTrue({"AccountID", "UserAccountID"}.isdisjoint(rows[0]))
        self.assertEqual({"2", "3"}, {row["ChangeType"] for row in rows})


class CouponAttributionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.coupons = [
            *json.loads((FIXTURES / "ListCoupons__offset-0.json").read_text(encoding="utf-8"))["List"],
            *json.loads((FIXTURES / "ListCoupons__offset-1.json").read_text(encoding="utf-8"))["List"],
        ]
        self.bills = json.loads((FIXTURES / "bill-details.json").read_text(encoding="utf-8"))["rows"]
        self.usage_records = [
            *json.loads((FIXTURES / "ListCouponUsageRecords__offset-0.json").read_text(encoding="utf-8"))["List"],
            *json.loads((FIXTURES / "ListCouponUsageRecords__offset-1.json").read_text(encoding="utf-8"))["List"],
        ]

    def analyze(self, coupons=None, bills=None, usage_records=None, candidates=()):
        return analyze_coupon_attribution(
            coupons=self.coupons if coupons is None else coupons,
            bill_details=self.bills if bills is None else bills,
            usage_records=usage_records,
            analysis_period="2026-09",
            comparison_period="2026-08",
            candidate_coupon_ids=candidates,
        )

    def run_cli(self, coupons: Path, bills: Path, usage_records: list[Path] | None = None) -> tuple[int, dict, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        usage_args = [
            argument
            for path in (usage_records or [])
            for argument in ("--usage-records", str(path))
        ]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = attribute_main(
                [
                    "--coupons", str(coupons),
                    "--bill-details", str(bills),
                    *usage_args,
                    "--analysis-period", "2026-09",
                    "--comparison-period", "2026-08",
                ]
            )
        return code, json.loads(stdout.getvalue()), stderr.getvalue()

    def test_manual_csv_only_returns_insufficient_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coupons = root / "coupons.csv"
            bills = root / "bills.csv"
            write_rows_csv(coupons, self.coupons)
            write_rows_csv(bills, self.bills)

            code, payload, stderr = self.run_cli(coupons, bills)

        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("success", payload["status"])
        result = payload["result"]
        self.assertEqual([], result["supported_reasons"])
        evidence = {item["input"]: item for item in result["input_evidence"]}
        self.assertEqual("unknown", evidence["coupons"]["completeness"])
        self.assertEqual("unknown", evidence["bill_details"]["completeness"])

    def test_incomplete_query_artifact_returns_partial_without_supported_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coupons = root / "coupons.csv"
            bills = root / "bills.csv"
            write_rows_csv(coupons, self.coupons)
            write_rows_csv(bills, self.bills)
            write_metadata(coupons, complete=False)
            write_metadata(bills, complete=True)

            code, payload, stderr = self.run_cli(coupons, bills)

        self.assertEqual((6, ""), (code, stderr))
        self.assertEqual("partial", payload["status"])
        result = payload["result"]
        self.assertEqual([], result["supported_reasons"])
        evidence = {item["input"]: item for item in result["input_evidence"]}
        self.assertEqual("partial", evidence["coupons"]["completeness"])
        self.assertEqual("complete", evidence["bill_details"]["completeness"])

    def test_complete_query_artifacts_keep_supported_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coupons = root / "coupons.csv"
            bills = root / "bills.csv"
            write_rows_csv(coupons, self.coupons)
            write_rows_csv(bills, self.bills)
            write_metadata(coupons, complete=True)
            write_metadata(bills, complete=True)

            code, payload, stderr = self.run_cli(coupons, bills)

        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("success", payload["status"])
        result = payload["result"]
        self.assertTrue(result["supported_reasons"])
        self.assertEqual(
            {"coupons": "complete", "bill_details": "complete"},
            {item["input"]: item["completeness"] for item in result["input_evidence"]},
        )

    def test_complete_usage_artifact_adds_verified_coupon_redemption_decline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coupons = root / "coupons.csv"
            bills = root / "bills.csv"
            usage = root / "usage.csv"
            write_rows_csv(coupons, self.coupons)
            write_rows_csv(bills, self.bills)
            write_rows_csv(usage, self.usage_records)
            for path in (coupons, bills, usage):
                write_metadata(path, complete=True)

            code, payload, stderr = self.run_cli(coupons, bills, [usage])

        self.assertEqual((0, ""), (code, stderr))
        result = payload["result"]
        reasons = {item["reason_type"] for item in result["supported_reasons"]}
        self.assertIn("coupon_redemption_declined", reasons)
        self.assertEqual(2, result["summary"]["coupon_usage_record_count"])
        self.assertEqual(
            "complete",
            next(item for item in result["input_evidence"] if item["input"] == "usage_records_1")["completeness"],
        )

    def test_bill_decline_is_separate_from_expired_coupon_and_candidate_ids(self) -> None:
        result = self.analyze()
        reasons = {item["reason_type"]: item for item in result["supported_reasons"]}
        self.assertEqual({"coupon_expired"}, set(reasons))
        expired = reasons["coupon_expired"]
        self.assertEqual("cpn-tos-expired", expired["coupon"]["CouponID"])
        self.assertTrue(expired["scope_match"]["product"])
        self.assertTrue(expired["scope_match"]["configuration"])
        self.assertTrue(expired["scope_match"]["charge_item"])
        self.assertEqual("expired", expired["time_match"]["reason"])
        self.assertEqual(1, len(result["bill_observations"]))
        decline = result["bill_observations"][0]["evidence"]
        self.assertEqual("500.00", decline["comparison_period_coupon_amount"])
        self.assertEqual("0.00", decline["analysis_period_coupon_amount"])
        self.assertNotIn("coupon_ids", result["bill_observations"][0])
        self.assertEqual(
            {"cpn-tos-expired"},
            {item["coupon"]["CouponID"] for item in result["follow_up_candidates"]},
        )

    def test_usage_records_prove_coupon_level_decline_and_keep_returns_separate(self) -> None:
        result = self.analyze(usage_records=self.usage_records)
        reasons = {item["reason_type"]: item for item in result["supported_reasons"]}
        decline = reasons["coupon_redemption_declined"]
        self.assertEqual("500.0", decline["evidence"]["comparison_period_redeemed_amount"])
        self.assertEqual("0", decline["evidence"]["analysis_period_redeemed_amount"])
        self.assertFalse(decline["target_bill_redemption_verified"])
        summary = next(
            item for item in result["coupon_usage_summaries"]
            if item["coupon"]["CouponID"] == "cpn-tos-expired"
        )
        self.assertEqual("20.0", summary["periods"]["2026-09"]["returned_amount"])
        links = summary["target_bill_links"]
        self.assertEqual({"bill-detail-aug", "bill-detail-sep"}, {item["affected_bill"]["BillDetailId"] for item in links})
        self.assertEqual({True, False}, {item["target_bill_redemption_verified"] for item in links})

    def test_postpaid_redemption_links_to_target_bill_by_bill_detail_id(self) -> None:
        records = [
            {
                "CouponID": "cpn-tos-expired",
                "ProductCode": "TOS",
                "ChangeAmount": "100.000001",
                "CreatedTime": "2026-09-05T01:00:00+08:00",
                "PayType": "post",
                "SubBusinessID": "bill-detail-sep",
                "ChangeType": 2,
                "BillingCycle": "2026-09",
            },
            *self.usage_records[:1],
        ]
        result = self.analyze(usage_records=records)
        summary = next(
            item for item in result["coupon_usage_summaries"]
            if item["coupon"]["CouponID"] == "cpn-tos-expired"
        )
        current_link = next(
            item for item in summary["target_bill_links"]
            if item["affected_bill"]["BillDetailId"] == "bill-detail-sep"
        )
        self.assertTrue(current_link["target_bill_redemption_verified"])
        self.assertTrue(current_link["target_bill_link_verified"])
        self.assertEqual("BillDetailId", current_link["link_field"])
        self.assertEqual("redemption", current_link["event_type"])
        self.assertEqual("100.000001", summary["periods"]["2026-09"]["redeemed_amount"])

    def test_prepaid_redemption_links_sub_business_id_to_prepaid_bill_id(self) -> None:
        coupon = dict(self.coupons[0], PayTypeLimit="pre")
        bill = dict(
            self.bills[1],
            BillID="order-pre-001",
            BillDetailId="bill-detail-pre-001",
            BillingMode="1",
        )
        record = {
            "CouponID": "cpn-tos-expired",
            "ProductCode": "TOS",
            "ChangeAmount": "88.000001",
            "CreatedTime": "2026-09-05T01:00:00+08:00",
            "PayType": "pre",
            "SubBusinessID": "order-pre-001",
            "ChangeType": 2,
            "BillingCycle": "2026-09",
        }
        result = analyze_coupon_attribution(
            coupons=[coupon],
            usage_records=[record],
            bill_details=[bill],
            analysis_period="2026-09",
        )
        summary = result["coupon_usage_summaries"][0]
        self.assertEqual(1, len(summary["target_bill_links"]))
        link = summary["target_bill_links"][0]
        self.assertEqual("BillID", link["link_field"])
        self.assertEqual("order-pre-001", link["affected_bill"]["BillID"])
        self.assertTrue(link["target_bill_link_verified"])
        self.assertTrue(link["target_bill_redemption_verified"])

    def test_usage_record_does_not_cross_match_pre_and_post_identifiers(self) -> None:
        prepaid_bill = dict(
            self.bills[1],
            BillID="order-pre-001",
            BillDetailId="detail-pre-001",
            BillingMode="1",
        )
        cases = (
            ("pre", "detail-pre-001"),
            ("post", "order-pre-001"),
        )
        for pay_type, sub_business_id in cases:
            with self.subTest(pay_type=pay_type):
                record = {
                    "CouponID": "cpn-tos-expired",
                    "ChangeAmount": "1.00",
                    "PayType": pay_type,
                    "SubBusinessID": sub_business_id,
                    "ChangeType": 2,
                    "BillingCycle": "2026-09",
                }
                result = analyze_coupon_attribution(
                    coupons=[self.coupons[0]],
                    usage_records=[record],
                    bill_details=[prepaid_bill],
                    analysis_period="2026-09",
                )
                self.assertEqual([], result["coupon_usage_summaries"][0]["target_bill_links"])

        postpaid_bill = dict(prepaid_bill, BillingMode="2")
        prepaid_record = {
            "CouponID": "cpn-tos-expired",
            "ChangeAmount": "1.00",
            "PayType": "pre",
            "SubBusinessID": "order-pre-001",
            "ChangeType": 2,
            "BillingCycle": "2026-09",
        }
        result = analyze_coupon_attribution(
            coupons=[self.coupons[0]],
            usage_records=[prepaid_record],
            bill_details=[postpaid_bill],
            analysis_period="2026-09",
        )
        self.assertEqual([], result["coupon_usage_summaries"][0]["target_bill_links"])

    def test_negative_usage_amount_does_not_support_coupon_decline(self) -> None:
        records = [dict(self.usage_records[0], ChangeAmount="-500.00")]
        result = self.analyze(usage_records=records)
        self.assertFalse(
            any(item["reason_type"] == "coupon_redemption_declined" for item in result["supported_reasons"])
        )
        self.assertTrue(
            any(
                "non_negative_finite_ChangeAmount" in item.get("missing_evidence", [])
                for item in result["insufficient_evidence"]
            )
        )

    def test_unqueried_scope_matching_candidate_remains_insufficient(self) -> None:
        result = self.analyze(usage_records=[])
        self.assertTrue(
            any(
                item.get("coupon_id") == "cpn-tos-expired"
                for item in result["insufficient_evidence"]
            )
        )

    def test_complete_empty_usage_scope_proves_zero_only_for_queried_coupon(self) -> None:
        result = analyze_coupon_attribution(
            coupons=self.coupons,
            usage_records=[],
            usage_record_coupon_ids=["cpn-tos-expired"],
            bill_details=self.bills,
            analysis_period="2026-09",
            comparison_period="2026-08",
        )
        self.assertEqual(1, len(result["coupon_usage_summaries"]))
        summary = result["coupon_usage_summaries"][0]
        self.assertEqual("cpn-tos-expired", summary["coupon"]["CouponID"])
        self.assertEqual("0", summary["periods"]["2026-09"]["redeemed_amount"])
        self.assertNotIn(
            "cpn-ecs-active",
            {item["coupon"]["CouponID"] for item in result["coupon_usage_summaries"]},
        )

    def test_used_up_requires_zero_balance_scope_match_and_bill_decline(self) -> None:
        coupon = dict(self.coupons[0])
        coupon.update(Status=4, RemainingAmount=0.0, ExpiredTime="2026-12-31T23:59:59+08:00")
        reasons = {item["reason_type"] for item in self.analyze(coupons=[coupon])["supported_reasons"]}
        self.assertIn("coupon_used_up", reasons)

    def test_not_effective_uses_bill_consumption_time(self) -> None:
        coupon = dict(self.coupons[0])
        coupon.update(Status=1, BeginTime="2026-10-01T00:00:00+08:00", ExpiredTime="2026-12-31T23:59:59+08:00")
        result = self.analyze(coupons=[coupon])
        reasons = {item["reason_type"]: item for item in result["supported_reasons"]}
        self.assertIn("coupon_not_effective", reasons)
        self.assertEqual("not_effective", reasons["coupon_not_effective"]["time_match"]["reason"])

    def test_not_effective_does_not_require_comparison_period(self) -> None:
        coupon = dict(self.coupons[0])
        coupon.update(Status=1, BeginTime="2026-07-01T00:00:00+08:00", ExpiredTime="2026-07-31T23:59:59+08:00")
        bill = dict(self.bills[1])
        bill.update(
            BillPeriod="2026-07",
            ExpenseBeginTime="2026-06-30T23:30:00+08:00",
            ExpenseEndTime="2026-07-01T00:00:00+08:00",
            CouponAmount="0.00",
            PayableAmount="300.00",
            DiscountBillAmount="300.00",
        )
        result = analyze_coupon_attribution(
            coupons=[coupon],
            bill_details=[bill],
            analysis_period="2026-07",
        )
        reasons = {item["reason_type"]: item for item in result["supported_reasons"]}
        self.assertEqual({"coupon_not_effective"}, set(reasons))
        self.assertEqual("2026-06-30T15:30:00+00:00", reasons["coupon_not_effective"]["time_match"]["consumption_time"])

    def test_explicit_nonapplicable_coupon_reports_product_mismatch(self) -> None:
        coupon = self.coupons[1]
        result = self.analyze(coupons=[coupon], candidates=["cpn-ecs-active"])
        reasons = {item["reason_type"]: item for item in result["supported_reasons"]}
        self.assertIn("coupon_not_applicable", reasons)
        self.assertFalse(reasons["coupon_not_applicable"]["scope_match"]["product"])

    def test_unmatched_inventory_keeps_bill_decline_insufficient(self) -> None:
        result = self.analyze(coupons=[self.coupons[1]])
        self.assertEqual([], result["supported_reasons"])
        self.assertTrue(result["insufficient_evidence"])
        self.assertEqual(1, len(result["bill_observations"]))

    def test_configuration_and_charge_item_wildcards_do_not_require_codes(self) -> None:
        result = self.analyze(coupons=[self.coupons[0]])
        expired = next(item for item in result["supported_reasons"] if item["reason_type"] == "coupon_expired")
        self.assertTrue(expired["scope_match"]["configuration"])
        self.assertTrue(expired["scope_match"]["charge_item"])
        self.assertEqual("", expired["scope_match"]["scope"]["ConfigurationCode"])
        self.assertEqual("", expired["scope_match"]["scope"]["ChargeItemCode"])

    def declines(self, bills: list[dict]) -> list[dict]:
        return [
            item for item in self.analyze(bills=bills)["bill_observations"]
            if item["observation_type"] == "coupon_deduction_declined"
        ]

    def test_bill_period_totals_and_result_do_not_depend_on_row_order(self) -> None:
        previous = dict(self.bills[0], CouponAmount="50.00", PayableAmount="100.00")
        previous_other = dict(previous, CouponAmount="0.00", PayableAmount="100.00")
        current = dict(self.bills[1], CouponAmount="25.00", PayableAmount="150.00")
        bills = [previous, previous_other, current]
        self.assertEqual([], self.declines(bills))  # Total payable fell from 200 to 150.
        self.assertEqual(self.analyze(bills=bills), self.analyze(bills=list(reversed(bills))))

    def test_multiple_current_and_previous_rows_are_summed_once(self) -> None:
        previous = dict(self.bills[0], CouponAmount="250.00", PayableAmount="350.00")
        current = dict(self.bills[1], CouponAmount="0.00", PayableAmount="600.00")
        bills = [previous, current, dict(previous), dict(current)]
        reasons = self.declines(bills)
        self.assertEqual(1, len(reasons))
        evidence = reasons[0]["evidence"]
        self.assertEqual("500.00", evidence["comparison_period_coupon_amount"])
        self.assertEqual("700.00", evidence["comparison_period_payable_amount"])
        self.assertEqual("1200.00", evidence["analysis_period_payable_amount"])
        self.assertEqual(2, evidence["analysis_period_row_count"])
        self.assertEqual(2, evidence["comparison_period_row_count"])
        self.assertEqual("BillPeriod", evidence["comparison_axis"])

    def test_missing_comparison_identity_is_not_a_wildcard(self) -> None:
        for field in ("Product", "ConfigName", "InstanceNo", "ElementCode", "BillingMode", "Currency"):
            for index in (0, 1):
                with self.subTest(field=field, index=index):
                    bills = [dict(row) for row in self.bills]
                    bills[index].pop(field)
                    result = self.analyze(bills=bills)
                    self.assertEqual([], result["bill_observations"])
                    self.assertTrue(any(field in str(item["missing_evidence"]) for item in result["insufficient_evidence"]))

    def test_missing_amount_in_one_row_blocks_the_whole_comparison_group(self) -> None:
        for field in ("CouponAmount", "PayableAmount"):
            for value in (None, "", "bad", "NaN", "Infinity"):
                with self.subTest(field=field, value=value):
                    bills = [*self.bills, dict(self.bills[0], **{field: value})]
                    self.assertEqual([], self.declines(bills))

    def test_unidentified_extra_row_blocks_a_potentially_matching_group(self) -> None:
        unidentified = dict(self.bills[0], InstanceNo="", PayableAmount="10000.00")
        self.assertEqual([], self.declines([*self.bills, unidentified]))

    def test_instances_with_the_same_charge_item_keep_separate_reasons(self) -> None:
        other = [dict(row, InstanceNo="bucket-other") for row in self.bills]
        reasons = self.declines([*self.bills, *other])
        self.assertEqual({"bucket-photo", "bucket-other"}, {item["affected_bill"]["InstanceNo"] for item in reasons})
        self.assertEqual(2, len(reasons))

    def test_region_and_unit_when_present_are_comparison_dimensions(self) -> None:
        for field in ("Region", "Unit", "Zone"):
            with self.subTest(field=field):
                previous = dict(self.bills[0], **{field: "a"})
                current = dict(self.bills[1], **{field: "b"})
                self.assertEqual([], self.declines([previous, current]))
                current.pop(field)
                self.assertEqual([], self.declines([previous, current]))

    def test_same_period_cannot_be_used_as_its_own_comparison(self) -> None:
        with self.assertRaisesRegex(ValueError, "不同账期"):
            analyze_coupon_attribution(coupons=self.coupons, bill_details=self.bills, analysis_period="2026-09", comparison_period="2026-09")

    def test_positive_attribution_is_independent_of_bill_and_coupon_order(self) -> None:
        self.assertEqual(
            self.analyze(),
            self.analyze(coupons=list(reversed(self.coupons)), bills=list(reversed(self.bills))),
        )

    def test_large_decimal_totals_keep_source_precision(self) -> None:
        previous = dict(self.bills[0], CouponAmount="500.01", PayableAmount="1234567890123456789012345678.23")
        current = dict(self.bills[1], CouponAmount="0.00", PayableAmount="1234567890123456789012345678.24")
        evidence = self.declines([previous, dict(previous), current, dict(current)])[0]["evidence"]
        self.assertEqual("2469135780246913578024691356.46", evidence["comparison_period_payable_amount"])
        self.assertEqual("2469135780246913578024691356.48", evidence["analysis_period_payable_amount"])


if __name__ == "__main__":
    unittest.main()
