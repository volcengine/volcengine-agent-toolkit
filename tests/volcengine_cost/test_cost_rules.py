from __future__ import annotations

import contextlib
import csv
import importlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "skills" / "core" / "volcengine-cost"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from cost import main as cost_main  # noqa: E402
from cost_query.common import parse_decimal as exported_parse_decimal  # noqa: E402
from cost_query.common.cost_rules import (  # noqa: E402
    FieldResolver,
    ensure_money_grouping,
    evidence_from_metadata,
    format_decimal,
    load_cost_csv,
    load_cost_metadata,
    parse_decimal,
    require_registered_money_metric,
    resolve_money_currency,
)
from cost_query.common.errors import BillingQueryError  # noqa: E402


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class CostRulesTest(unittest.TestCase):
    def _run_cost(self, arguments: list[str]) -> tuple[int, dict, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cost_main(arguments)
        return code, json.loads(stdout.getvalue()) if stdout.getvalue() else {}, stderr.getvalue()

    def test_parse_decimal_preserves_empty_negative_and_precision_semantics(self) -> None:
        self.assertIsNone(parse_decimal("", "PayableAmount", allow_empty=True))
        self.assertIsNone(parse_decimal(None, "PayableAmount", allow_empty=True))
        self.assertEqual("-1.23", str(parse_decimal("-1.23", "PayableAmount")))
        self.assertEqual("0.012091", format_decimal(parse_decimal("0.012091", "OriginalBillAmount")))
        self.assertEqual("2.50", str(exported_parse_decimal("2.50", "PayableAmount")))
        with self.assertRaisesRegex(BillingQueryError, "非 Decimal"):
            parse_decimal("not-a-number", "PayableAmount")

    def test_registered_money_metric_and_currency_are_required(self) -> None:
        resolver = FieldResolver(
            ["PayableAmount", "Currency", "Count"],
            [{"PayableAmount": "10", "Currency": "CNY", "Count": "2"}],
        )
        require_registered_money_metric(resolver.resolve("payable_amount"), "sum")
        self.assertEqual(
            "Currency",
            resolve_money_currency(resolver, resolver.resolve("PayableAmount")).column,
        )
        with self.assertRaisesRegex(BillingQueryError, "明确注册的金额字段"):
            require_registered_money_metric(resolver.resolve("Count"), "sum")

    def test_metadata_evidence_preserves_partial_and_current_period_scope(self) -> None:
        partial = evidence_from_metadata(
            {
                "action": "ListBill",
                "coverage": {"is_complete": False, "failed_queries": [{"query_id": "2026-07"}]},
                "freshness": {"partial_period": True},
            }
        )
        self.assertEqual("partial_dataset", partial["claim_scope"])
        self.assertEqual("partial", partial["coverage_status"])
        self.assertEqual([{"query_id": "2026-07"}], partial["failed_queries"])

        current = evidence_from_metadata(
            {
                "action": "ListBillDetail",
                "coverage": {"is_complete": False, "is_provisional": True, "failed_queries": []},
                "freshness": {"partial_period": True},
            }
        )
        self.assertEqual("provisional_current_period", current["claim_scope"])
        self.assertEqual("provisional", current["coverage_status"])

    def test_loaders_discover_metadata_and_keep_named_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.csv"
            write_csv(
                source,
                ["Product", "PayableAmount", "Currency"],
                [{"Product": "ECS", "PayableAmount": "1.25", "Currency": "CNY"}],
            )
            metadata = source.with_suffix(".meta.json")
            metadata.write_text(
                json.dumps(
                    {
                        "output_protocol_version": "1.0",
                        "action": "ListBill",
                        "coverage": {"is_complete": True, "failed_queries": []},
                        "freshness": {"partial_period": False},
                    }
                ),
                encoding="utf-8",
            )
            loaded_csv = load_cost_csv(source)
            loaded_metadata = load_cost_metadata(source)

        self.assertEqual(["Product", "PayableAmount", "Currency"], loaded_csv.columns)
        self.assertEqual("1.25", loaded_csv.rows[0]["PayableAmount"])
        self.assertEqual(metadata, loaded_metadata.path)
        self.assertEqual("ListBill", loaded_metadata.metadata["action"])

    def test_money_grouping_adds_currency_without_duplicating_it(self) -> None:
        resolver = FieldResolver(
            ["Product", "PayableAmount", "Currency"],
            [{"Product": "ECS", "PayableAmount": "1.00", "Currency": "CNY"}],
        )
        metric = resolver.resolve("PayableAmount")
        grouping = ensure_money_grouping(resolver, [metric], [resolver.resolve("Product")])
        self.assertEqual(["Product", "Currency"], [ref.column for ref in grouping.group_refs])
        self.assertEqual(["Currency"], [ref.column for ref in grouping.implicit_currency_refs])

        explicit = ensure_money_grouping(
            resolver,
            [metric],
            [resolver.resolve("Product"), resolver.resolve("Currency")],
        )
        self.assertEqual(["Product", "Currency"], [ref.column for ref in explicit.group_refs])
        self.assertEqual([], explicit.implicit_currency_refs)

    def test_cost_rules_contract_has_one_public_source(self) -> None:
        rules = importlib.import_module("cost_query.common.cost_rules")
        common = importlib.import_module("cost_query.common")
        code, payload, stderr = self._run_cost(["schema", "--section", "cost_rules"])
        self.assertEqual((0, ""), (code, stderr))
        contract_symbols = {item["name"] for key in ("helpers", "types") for item in payload[key]}
        self.assertEqual(set(rules.__all__), contract_symbols)
        self.assertEqual(set(rules.__all__), set(common.__all__) - {"BillingQueryError", "ErrorCode", "ExitCode"})

    def test_cost_rules_schema_filters_fields_and_errors_use_stdout_envelope(self) -> None:
        code, payload, stderr = self._run_cost(
            ["schema", "--section", "cost_rules", "--field", "require_decimal"]
        )
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual(["require_decimal"], [helper["name"] for helper in payload["helpers"]])

        code, payload, stderr = self._run_cost(
            ["schema", "--section", "cost_rules", "--field", "made_up_helper"]
        )
        self.assertEqual((2, ""), (code, stderr))
        self.assertEqual("error", payload["status"])
        self.assertEqual("UNSUPPORTED_FIELD", payload["_meta"]["error"]["code"])

    def test_cost_rules_contract_examples_execute(self) -> None:
        columns = ["Product", "PayableAmount", "Currency"]
        rows = [{"Product": "ECS", "PayableAmount": "1.25", "Currency": "CNY"}]
        code, payload, stderr = self._run_cost(
            ["schema", "--section", "cost_rules", "--field", "FieldRef"]
        )
        self.assertEqual((0, ""), (code, stderr))
        example = next(item for item in payload["examples"] if item["name"] == "resolve_and_read_field")
        namespace = {"columns": columns, "rows": rows, "row": rows[0], "group_by": ["Product"]}
        exec(example["code"], namespace)
        self.assertEqual("1.25", str(namespace["value"]))


if __name__ == "__main__":
    unittest.main()
