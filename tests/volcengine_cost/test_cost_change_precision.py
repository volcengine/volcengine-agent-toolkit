from __future__ import annotations

import contextlib
import csv
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2] / "skills" / "core" / "volcengine-cost"
sys.path.insert(0, str(ROOT / "scripts"))

from cost_query.billing.client import VeBillingClient
from cost_query.billing.cost_change import validate_cost_change_result
from cost_query.billing.contracts.registry import UPSTREAM_ACTION_CONTRACTS
from cost_query.common.json_output import dumps
from cost_query.common.errors import BillingQueryError
from query_billing import main


class CostChangePrecisionTest(unittest.TestCase):
    def cases(self):
        periods = {"CurrentPeriod": "2026-06-01", "BasePeriod": "2026-05-01", "Metric": 3}
        return (
            ("QueryCostChangeDimensions", {**periods, "CandidateDimensions": ["product"]}),
            ("QueryCostChangeAmountComponents", {**periods, "Filters": {"charge_item_code": "ci"}}),
            ("QueryCostChangeDrivers", {"current_period": "2026-06-01", "base_period": "2026-05-01",
                                        "Metric": "original_bill_amount", "filters": {"charge_item_code": "ci"}}),
        )

    def raw_response(self, action):
        if action.endswith("Drivers"):
            return ('{"Result":{"total_diff":9007199254740992.01,"base_amount":0,"current_amount":9007199254740992.01,'
                    '"contributions":[{"dimension":"usage","contribution":9007199254740992.01,'
                    '"base_amount":0,"current_amount":9007199254740992.01}]}}')
        return ('{"Result":{"totalDiff":9007199254740992.01,"baseAmount":0,"currentAmount":9007199254740992.01,'
                '"candidates":[{"dimension":"product","coverageRatio":0.1234567890123456789,'
                '"values":[{"valueKey":"item","valueName":"item","deltaAmount":9007199254740992.01,'
                '"baseAmount":0,"currentAmount":9007199254740992.01,"contributionRatio":0.1234567890123456789}]}]}}')

    def test_real_client_preserves_decimal_tokens_in_both_json_parser_paths(self):
        for action, body in self.cases():
            for prefix in ("", "CLI notice\n"):
                with self.subTest(action=action, prefix=prefix):
                    def runner(command, **kwargs):
                        return subprocess.CompletedProcess(command, 0, prefix + self.raw_response(action), "")
                    client = VeBillingClient(region="cn-beijing", profile=None, timeout_seconds=None,
                                             executable=sys.executable, runner=runner)
                    actual = client.query(action, body)["Result"]
                    expected = json.loads(self.raw_response(action), parse_float=Decimal)["Result"]
                    self.assertEqual(expected, actual)
                    key = "total_diff" if action.endswith("Drivers") else "totalDiff"
                    self.assertIsInstance(actual[key], Decimal)

    def test_other_action_preserves_decimal_tokens(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, '{"Result":{"extra":1.25}}', "")
        client = VeBillingClient(region="cn-beijing", profile=None, timeout_seconds=None,
                                 executable=sys.executable, runner=runner)
        actual = client.query("QueryBalanceAcct", {})["Result"]["extra"]
        self.assertIsInstance(actual, Decimal)
        self.assertEqual(Decimal("1.25"), actual)

    def test_decimal_response_validation_keeps_finite_values_without_float_conversion(self):
        action = "QueryCostChangeDrivers"
        for number in (Decimal("9007199254740992.01"), Decimal("1e1000"), Decimal("1e-1000")):
            with self.subTest(number=number):
                validate_cost_change_result(action, {"total_diff": number, "base_amount": 0,
                                                     "current_amount": number, "contributions": []})
        for number in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
            with self.subTest(number=number), self.assertRaises(BillingQueryError):
                validate_cost_change_result(action, {"total_diff": number, "base_amount": 0,
                                                     "current_amount": number, "contributions": []})

    def test_development_contract_does_not_cast_decimal_response_to_float(self):
        for action, _ in self.cases():
            expected = json.loads(self.raw_response(action), parse_float=Decimal)["Result"]
            model = UPSTREAM_ACTION_CONTRACTS[action].response_model.model_validate(expected)
            actual = model.model_dump(by_alias=True, exclude_none=True)
            self.assertEqual(expected, actual)

    def test_cli_inline_explicit_and_automatic_csv_preserve_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for action, body in self.cases():
                for mode in ("inline", "csv", "automatic"):
                    with self.subTest(action=action, mode=mode):
                        raw = self.raw_response(action)
                        if mode == "automatic":
                            raw = raw[:-2] + ',"large_note":' + json.dumps("large-" * 12000) + '}}'
                        (root / f"{action}.json").write_text(raw)
                        expected = json.loads(raw, parse_float=Decimal)["Result"]
                        args = ["--action", action, "--body", json.dumps(body), "--fixture-dir", directory]
                        if mode == "csv":
                            args.extend(["--out", str(root / f"{action}.csv")])
                        output = io.StringIO()
                        with patch("query_billing.tempfile.gettempdir", return_value=directory), contextlib.redirect_stdout(output):
                            code = main(args)
                        self.assertEqual(0, code, output.getvalue())
                        payload = json.loads(output.getvalue(), parse_float=Decimal)
                        key = "total_diff" if action.endswith("Drivers") else "totalDiff"
                        if mode == "inline":
                            row = {k: v for k, v in payload["result"][0].items() if not k.startswith("_")}
                            self.assertEqual(expected, row)
                            self.assertIsInstance(row[key], Decimal)
                        else:
                            with Path(payload["result"]["file"]).open(newline="") as file:
                                row = next(csv.DictReader(file))
                            self.assertEqual("9007199254740992.01", row[key])
                            nested = "contributions" if action.endswith("Drivers") else "candidates"
                            self.assertEqual(expected[nested], json.loads(row[nested], parse_float=Decimal))

    def test_json_decimal_remains_number_and_existing_types_keep_standard_format(self):
        value = {"amount": Decimal("9007199254740992.0100"), "nested": [Decimal("1e-1000"), "123", True, None]}
        for compact in (True, False):
            raw = dumps(value, compact=compact)
            self.assertEqual(value, json.loads(raw, parse_float=Decimal))
            self.assertNotIn('"9007199254740992.0100"', raw)
            ordinary = {"中文": [1.25, 42, "text", True, None]}
            kwargs = {"separators": (",", ":")} if compact else {"indent": 2}
            self.assertEqual(json.dumps(ordinary, ensure_ascii=False, allow_nan=False, **kwargs), dumps(ordinary, compact=compact))
        for number in (Decimal("NaN"), Decimal("Infinity")):
            with self.assertRaises(ValueError):
                dumps({"amount": number})

    def test_copied_skill_preserves_precision_without_site_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installed = root / "installed" / "volcengine-cost"
            shutil.copytree(ROOT, installed, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for action, body in self.cases():
                with self.subTest(action=action):
                    raw = self.raw_response(action)
                    (root / f"{action}.json").write_text(raw)
                    completed = subprocess.run(
                        [sys.executable, "-S", "scripts/cost.py", "query", "--action", action,
                         "--body", json.dumps(body), "--fixture-dir", directory],
                        cwd=installed, capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
                    payload = json.loads(completed.stdout, parse_float=Decimal)
                    expected = json.loads(raw, parse_float=Decimal)["Result"]
                    row = {k: v for k, v in payload["result"][0].items() if not k.startswith("_")}
                    self.assertEqual(expected, row)


if __name__ == "__main__":
    unittest.main()
