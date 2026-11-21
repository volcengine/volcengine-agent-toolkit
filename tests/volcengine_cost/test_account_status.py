from __future__ import annotations

import copy
import sys
import unittest
from decimal import localcontext
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "core" / "volcengine-cost" / "scripts"))

from cost_query.billing.account_status import account_snapshot_projection, evaluate_account_status  # noqa: E402
from cost_query.common.errors import BillingQueryError, ErrorCode  # noqa: E402


def snapshot(**changes):
    row = {
        "AvailableBalance": "-328.500000",
        "CashBalance": "0.000000",
        "CreditLimit": "0.000000",
        "FreezeAmount": "0.000000",
        "ArrearsBalance": "328.500000",
        "Currency": "CNY",
    }
    row.update(changes)
    return row


class AccountStatusTest(unittest.TestCase):
    def test_arrears_does_not_override_nonnegative_available_balance(self):
        result = evaluate_account_status([snapshot(AvailableBalance="50", CashBalance="150", ArrearsBalance="100")])
        self.assertEqual("not_in_arrears", result["status"])
        self.assertEqual("pass", result["balance_check"]["status"])

    def test_zero_and_signed_zero_are_not_in_arrears(self):
        for available in ("0", "-0.000000"):
            with self.subTest(available=available):
                result = evaluate_account_status([snapshot(AvailableBalance=available, ArrearsBalance="0")])
                self.assertEqual("not_in_arrears", result["status"])
                self.assertEqual("pass", result["balance_check"]["status"])

    def test_missing_or_invalid_available_balance_does_not_fall_back(self):
        for value in (None, "", "   ", "bad", "NaN", "sNaN", "Infinity", "-Infinity", True, -1.5):
            with self.subTest(value=value):
                result = evaluate_account_status([snapshot(AvailableBalance=value)])
                self.assertEqual("unknown", result["status"])
                self.assertEqual("not_checked", result["balance_check"]["status"])
                self.assertIn("AvailableBalance", result["balance_check"]["missing_fields"] + result["balance_check"]["invalid_fields"])
                self.assertIsNone(result["credit_covered"])

    def test_inconsistent_formula_overrides_available_balance_sign(self):
        result = evaluate_account_status([snapshot(AvailableBalance="5", CashBalance="10", ArrearsBalance="20")])
        self.assertEqual("unknown", result["status"])
        self.assertEqual("balance_formula_mismatch", result["reason"])
        self.assertEqual("fail", result["balance_check"]["status"])
        self.assertEqual("-10.000000", result["balance_check"]["expected_available_balance"])
        self.assertEqual("15.000000", result["balance_check"]["difference"])

    def test_missing_components_skip_formula_without_filling_zero(self):
        row = snapshot()
        del row["CashBalance"]
        result = evaluate_account_status([row])
        self.assertEqual("in_arrears", result["status"])
        self.assertEqual("not_checked", result["balance_check"]["status"])
        self.assertEqual(["CashBalance"], result["balance_check"]["missing_fields"])
        self.assertNotIn("expected_available_balance", result["balance_check"])

    def test_invalid_component_is_reported_without_formula_result(self):
        result = evaluate_account_status([snapshot(FreezeAmount="NaN")])
        self.assertEqual("in_arrears", result["status"])
        self.assertEqual(["FreezeAmount"], result["balance_check"]["invalid_fields"])
        self.assertEqual("not_checked", result["balance_check"]["status"])

    def test_formula_preserves_precision_during_large_cancellation(self):
        row = snapshot(
            CashBalance="10000000000000000000000000000.000000000000000001",
            FreezeAmount="10000000000000000000000000000",
            ArrearsBalance="0.000000000000000002",
            AvailableBalance="-0.000000000000000001",
        )
        with localcontext() as context:
            context.prec = 4
            result = evaluate_account_status([row])
        self.assertEqual("in_arrears", result["status"])
        self.assertEqual("pass", result["balance_check"]["status"])
        self.assertEqual("-1E-18", result["balance_check"]["expected_available_balance"])

    def test_negative_component_keeps_its_sign(self):
        result = evaluate_account_status([snapshot(AvailableBalance="1.25", ArrearsBalance="-1.25")])
        self.assertEqual("not_in_arrears", result["status"])
        self.assertEqual("pass", result["balance_check"]["status"])

    def test_credit_coverage_is_derived_without_changing_status(self):
        result = evaluate_account_status([snapshot(AvailableBalance="50", CashBalance="-50", CreditLimit="100", ArrearsBalance="0")])
        self.assertEqual("not_in_arrears", result["status"])
        self.assertTrue(result["credit_covered"])
        row = snapshot()
        del row["CreditLimit"]
        self.assertIsNone(evaluate_account_status([row])["credit_covered"])

    def test_empty_multiple_and_incomplete_snapshots_are_unknown(self):
        for rows, complete, reason in (
            ([], True, "empty_snapshot"),
            ([snapshot(), snapshot()], True, "unexpected_snapshot_count"),
            ([snapshot()], False, "incomplete_query"),
        ):
            with self.subTest(reason=reason):
                result = evaluate_account_status(rows, query_complete=complete)
                self.assertEqual("unknown", result["status"])
                self.assertEqual(reason, result["reason"])

    def test_source_fields_are_preserved_and_no_query_time_is_added(self):
        row = snapshot()
        original = copy.deepcopy(row)
        result = evaluate_account_status([row])
        self.assertEqual(original, row)
        self.assertNotIn("queried_at", result)
        self.assertNotIn("time_source", result)

    def test_projection_preserves_original_fields_and_reports_the_check_result(self):
        row = snapshot(AvailableBalance="0", CashBalance="0", CreditLimit="0", FreezeAmount="0", ArrearsBalance="0")
        row["AccountID"] = 2100000000
        result, _, meta = account_snapshot_projection([row])
        self.assertEqual(row, result)
        self.assertEqual("not_in_arrears", meta["account_status"])
        self.assertEqual({"status": "pass"}, meta["balance_check"])
        self.assertNotIn("credit_covered", meta)

    def test_projection_explains_missing_and_inconsistent_amounts(self):
        for row, expected_status, expected_check in (
            (snapshot(AvailableBalance=None), "unknown", "not_checked"),
            (snapshot(CashBalance=None), "in_arrears", "not_checked"),
            (snapshot(AvailableBalance="5", CashBalance="10", ArrearsBalance="20"), "unknown", "fail"),
        ):
            with self.subTest(row=row):
                _, _, meta = account_snapshot_projection([row])
                self.assertEqual(expected_status, meta["account_status"])
                self.assertEqual(expected_check, meta["balance_check"]["status"])
                self.assertNotIn("invalid_fields", meta["balance_check"])

    def test_projection_rejects_invalid_amount_contract(self):
        with self.assertRaises(BillingQueryError) as raised:
            account_snapshot_projection([snapshot(AvailableBalance="NaN")])
        self.assertEqual(ErrorCode.RESPONSE_INVALID, raised.exception.code)

    def test_projection_does_not_invent_currency_time_or_zero_values(self):
        row = snapshot()
        del row["Currency"]
        result, _, meta = account_snapshot_projection([row])
        self.assertNotIn("Currency", result)
        self.assertTrue({"queried_at", "snapshot_time"}.isdisjoint(meta))
        empty, _, empty_meta = account_snapshot_projection([])
        self.assertEqual({}, empty)
        self.assertEqual("unknown", empty_meta["account_status"])


if __name__ == "__main__":
    unittest.main()
