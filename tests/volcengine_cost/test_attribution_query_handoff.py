"""Exercise real query deliveries as inputs to both attribution CLIs."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2] / "skills/core/volcengine-cost"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(ROOT / "scripts"))

from cost import main  # noqa: E402
from cost_query.arrears.input_evidence import load_attribution_input  # noqa: E402


class AttributionQueryHandoffTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_cli(self, arguments: list[str], expected: int = 0) -> dict:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(arguments)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(expected, code, payload)
        return payload

    def prepare(self, kind: str) -> Path:
        original = FIXTURES / ("coupon/expired" if kind == "coupon" else "resource_package/used_up")
        fixture = self.root / kind
        fixture.mkdir()
        for path in original.glob("*.json"):
            shutil.copyfile(path, fixture / path.name)
        bills = json.loads((original / "bill-details.json").read_text())["rows"]
        for period in ("2026-08", "2026-09"):
            rows = [row for row in bills if row["BillPeriod"] == period]
            (fixture / f"ListBillDetail__period-{period}__offset-0.json").write_text(json.dumps(
                {"Result": {"List": rows, "Total": len(rows), "Limit": 300, "Offset": 0}}))
        return fixture

    def query(self, fixture: Path, action: str, body: dict, name: str, *, periods: bool = False,
              inline: bool = False) -> tuple[Path, Path, dict]:
        csv_path = self.root / f"{name}.csv"
        args = ["query", "--action", action, "--body", json.dumps(body),
                "--pagination", "full", "--fixture-dir", str(fixture)]
        if action in ("ListCoupons", "ListCouponUsageRecords"):
            args += ["--page-size", "1"]
        if periods:
            args += ["--period", "2026-08", "--period", "2026-09"]
        if not inline:
            args += ["--out", str(csv_path)]
        payload = self.run_cli(args)
        envelope_path = self.root / f"{name}.json"
        envelope_path.write_text(json.dumps(payload))
        return csv_path, envelope_path, payload

    def inputs(self, kind: str) -> tuple[list[str], list[tuple[str, Path, Path]]]:
        fixture = self.prepare(kind)
        bills, bills_json, _ = self.query(fixture, "ListBillDetail", {"GroupPeriod": 2, "GroupTerm": 0},
                                         f"{kind}-bills", periods=True)
        if kind == "coupon":
            inventory, inventory_json, _ = self.query(fixture, "ListCoupons", {}, "coupons")
            usage, usage_json, _ = self.query(fixture, "ListCouponUsageRecords",
                                              {"CouponID": "cpn-tos-expired"}, "coupon-usage")
            options = [("--coupons", inventory, inventory_json), ("--usage-records", usage, usage_json)]
        else:
            inventory, inventory_json, _ = self.query(fixture, "ListResourcePackages",
                                                      {"ResourceType": "Package"}, "packages")
            usage, usage_json, _ = self.query(fixture, "ListPackageUsageDetails", {
                "ResourceType": "Package", "DeductBeginTime": "2026-08-01T00:00:00Z",
                "DeductEndTime": "2026-09-30T23:59:59Z"}, "package-usage")
            options = [("--packages", inventory, inventory_json), ("--usage-details", usage, usage_json)]
        options.append(("--bill-details", bills, bills_json))
        args = [kind, "--analysis-period", "2026-09", "--comparison-period", "2026-08"]
        for flag, csv_path, _ in options:
            args += [flag, str(csv_path)]
        return args, options

    def test_all_file_envelope_input_slots_match_csv_attribution(self) -> None:
        for kind in ("coupon", "resource-package"):
            with self.subTest(kind=kind):
                args, inputs = self.inputs(kind)
                baseline = self.run_cli(args)
                self.assertTrue(baseline["result"]["supported_reasons"])
                for flag, _, envelope in inputs:
                    with self.subTest(input=flag):
                        handoff = list(args)
                        handoff[handoff.index(flag) + 1] = str(envelope)
                        payload = self.run_cli(handoff)
                        self.assertEqual(baseline["result"]["supported_reasons"], payload["result"]["supported_reasons"])
                        self.assertTrue(all(item["completeness"] == "complete" for item in payload["result"]["input_evidence"]))

    def test_partial_outer_envelope_keeps_limits_with_complete_sidecar(self) -> None:
        args, inputs = self.inputs("coupon")
        flag, _, envelope = inputs[0]
        payload = json.loads(envelope.read_text())
        payload["status"] = "partial"
        envelope.write_text(json.dumps(payload))
        args[args.index(flag) + 1] = str(envelope)
        result = self.run_cli(args, expected=6)
        self.assertEqual("partial", result["status"])
        self.assertEqual([], result["result"]["supported_reasons"])

    def test_unknown_protocol_is_not_upgraded_by_a_complete_sidecar(self) -> None:
        _, inputs = self.inputs("coupon")
        envelope = inputs[0][2]
        payload = json.loads(envelope.read_text())
        payload["_meta"]["output_protocol_version"] = "unsupported"
        envelope.write_text(json.dumps(payload))
        self.assertEqual("unknown", load_attribution_input(envelope, input_name="coupons").completeness)

    def test_current_period_outer_evidence_keeps_limits_without_inline_coverage(self) -> None:
        _, inputs = self.inputs("coupon")
        envelope = inputs[0][2]
        payload = json.loads(envelope.read_text())
        payload["_meta"]["freshness"] = {"partial_period": True}
        envelope.write_text(json.dumps(payload))
        self.assertEqual("partial", load_attribution_input(envelope, input_name="coupons").completeness)

    def test_legacy_file_shape_uses_the_same_complete_sidecar(self) -> None:
        _, inputs = self.inputs("coupon")
        envelope = inputs[0][2]
        payload = json.loads(envelope.read_text())
        payload["result"] = {"file": payload["result"]["file"]}
        envelope.write_text(json.dumps(payload))
        self.assertEqual("complete", load_attribution_input(envelope, input_name="coupons").completeness)

    def test_cross_query_file_bindings_are_rejected(self) -> None:
        args, inputs = self.inputs("coupon")
        flag, _, envelope = inputs[0]
        payload = json.loads(envelope.read_text())
        payload["result"]["metadata"] = json.loads(inputs[1][2].read_text())["result"]["metadata"]
        envelope.write_text(json.dumps(payload))
        args[args.index(flag) + 1] = str(envelope)
        result = self.run_cli(args, expected=2)
        self.assertEqual("RESPONSE_INVALID", result["_meta"]["error"]["code"])

    def test_complete_empty_inline_usage_keeps_queried_coupon_identity(self) -> None:
        args, inputs = self.inputs("coupon")
        fixture = self.root / "coupon"
        original = json.loads((fixture / "ListCouponUsageRecords__offset-0.json").read_text())
        result = original.get("Result", original)
        result.update(List=[], Total=0)
        (fixture / "ListCouponUsageRecords__offset-0.json").write_text(json.dumps(original))
        _, inline, payload = self.query(fixture, "ListCouponUsageRecords", {"CouponID": "cpn-tos-expired"},
                                        "empty-inline", inline=True)
        csv_path, _, _ = self.query(fixture, "ListCouponUsageRecords", {"CouponID": "cpn-tos-expired"}, "empty-file")
        self.assertEqual([], payload["result"])
        self.assertEqual(["cpn-tos-expired"], payload["_meta"]["queried_coupon_ids"])
        args[args.index("--usage-records") + 1] = str(inline)
        from_inline = self.run_cli(args)
        args[args.index("--usage-records") + 1] = str(csv_path)
        from_csv = self.run_cli(args)
        self.assertEqual(from_csv["result"]["coupon_usage_summaries"], from_inline["result"]["coupon_usage_summaries"])
        self.assertEqual(1, len(from_inline["result"]["coupon_usage_summaries"]))

    def test_automatic_file_delivery_is_a_supported_handoff(self) -> None:
        fixture = self.prepare("coupon")
        with mock.patch("query_billing.AUTO_STDOUT_BYTE_LIMIT", 1), mock.patch(
            "query_billing._create_automatic_output_path", return_value=self.root / "automatic.csv",
        ):
            _, envelope, payload = self.query(fixture, "ListCoupons", {}, "automatic", inline=True)
        self.assertIsInstance(payload["result"], dict)
        self.assertEqual("complete", load_attribution_input(envelope, input_name="coupons").completeness)


if __name__ == "__main__":
    unittest.main()
