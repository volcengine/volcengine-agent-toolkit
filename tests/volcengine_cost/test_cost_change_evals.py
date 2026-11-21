"""Verify the offline comparison oracle against net-change contribution rules."""

from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("cost_eval_runner", Path(__file__).with_name("evals") / "run_evals.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class CostChangeEvalTest(unittest.TestCase):
    def compare(self, deltas: list[tuple[str, str, str]], *, group_by: tuple[str, ...] = ("Product",),
                metric: str = "PayableAmount", currency: str = "Currency") -> list[dict]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source.csv", root / "output.csv"
            rows = []
            for product, current, currency_value in deltas:
                rows.extend([
                    {"Product": product, "TimeStr": "2026-08", metric: "10", currency: currency_value},
                    {"Product": product, "TimeStr": "2026-09", metric: current, currency: currency_value},
                ])
            runner.write_csv(source, ["Product", "TimeStr", metric, currency], rows)
            runner.direct_compare_periods(source, output, period_field="TimeStr", previous="2026-08",
                                          current="2026-09", metric=metric, group_by=group_by, action="ListBill")
            with output.open(newline="", encoding="utf-8") as file:
                return list(csv.DictReader(file))

    def test_offsetting_changes_use_net_delta(self) -> None:
        rows = self.compare([("ECS", "15", "CNY"), ("TOS", "6", "CNY")])
        self.assertEqual({"ECS": "5", "TOS": "-4"}, {row["Product"]: row["delta_contribution_rate"] for row in rows})

    def test_zero_net_change_has_no_contribution_rate(self) -> None:
        rows = self.compare([("ECS", "15", "CNY"), ("TOS", "5", "CNY")])
        self.assertTrue(all(row["delta_contribution_rate"] == "" for row in rows))

    def test_net_decrease_preserves_signed_contributions(self) -> None:
        rows = self.compare([("ECS", "14", "CNY"), ("TOS", "5", "CNY")])
        self.assertEqual({"ECS": "-4", "TOS": "5"}, {row["Product"]: row["delta_contribution_rate"] for row in rows})

    def test_currencies_have_separate_denominators(self) -> None:
        rows = self.compare([("ECS", "15", "CNY"), ("TOS", "8", "USD")])
        self.assertTrue(all(row["delta_contribution_rate"] == "1" for row in rows))

    def test_explicit_currency_grouping_keeps_separate_denominators(self) -> None:
        rows = self.compare([("ECS", "15", "CNY"), ("TOS", "8", "USD")], group_by=("Product", "Currency"))
        self.assertTrue(all(row["delta_contribution_rate"] == "1" for row in rows))

    def test_settlement_amount_uses_settlement_currency(self) -> None:
        for group_by in (("Product",), ("Product", "CurrencySettlement")):
            with self.subTest(group_by=group_by):
                rows = self.compare([("ECS", "15", "CNY"), ("TOS", "8", "USD")],
                                    group_by=group_by, metric="SettlePayableAmount", currency="CurrencySettlement")
                self.assertTrue(all(row["delta_contribution_rate"] == "1" for row in rows))


if __name__ == "__main__":
    unittest.main()
