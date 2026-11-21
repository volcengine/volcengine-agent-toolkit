from __future__ import annotations

import contextlib
import csv
import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2] / "skills" / "core" / "volcengine-cost"
SCRIPTS = ROOT / "scripts"
BALANCE_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "query_balance_acct"
sys.path.insert(0, str(SCRIPTS))

from cost_query.billing.client import BillingClient  # noqa: E402
from cost_query.billing.client import VeBillingClient  # noqa: E402
from cost_query.common.errors import BillingQueryError, ErrorCode, ExitCode  # noqa: E402
from cost_query.billing.fetch import FetchConfig, aggregate_coverage, collect_query  # noqa: E402
from cost_query.billing.field_catalog import build_field_catalog, output_field_names  # noqa: E402
from cost_query.billing.field_grain import validate_required_response_fields  # noqa: E402
from cost_query.billing.query_contract import CONTRACT_SECTIONS, describe_query  # noqa: E402
from cost_query.common.execution_output import OUTPUT_PROTOCOL_VERSION  # noqa: E402
from query_billing import build_parser, main  # noqa: E402
from cost_query.billing.validation import validate_request_body  # noqa: E402


def bill_row(index: int) -> dict:
    return {
        "BillID": f"bill-{index}",
        "BillPeriod": "2026-07",
        "Product": "ECS" if index % 2 else "TOS",
        "ProductZh": "云服务器" if index % 2 else "对象存储",
        "PayableAmount": str(index),
        "Currency": "CNY",
    }


def bill_response(rows, *, total: int, limit: int, offset: int, warning: str = "") -> dict:
    result = {"List": rows, "Total": total, "Limit": limit, "Offset": offset}
    if warning:
        result["Warning"] = warning
    return {"ResponseMetadata": {"Error": None}, "Result": result}


def detail_response(rows, *, total: int, limit: int, offset: int, warning: str = "") -> dict:
    return {
        "ResponseMetadata": {"Error": None},
        "Result": {
            "Warning": warning,
            "List": rows,
            "Total": total,
            "Limit": limit,
            "Offset": offset,
        },
    }


def cost_analysis_response(cost_data, *, total: int, limit: int, offset: int, warning: str = "") -> dict:
    result = {"CostData": cost_data, "Total": total, "Limit": limit, "Offset": offset}
    if warning:
        result["Warning"] = warning
    return {"ResponseMetadata": {"Error": None}, "Result": result}


def filter_info_response(payload: dict) -> dict:
    return {"ResponseMetadata": {"Error": None}, "Result": payload}


def category_response(rows) -> dict:
    return {
        "ResponseMetadata": {"Error": None},
        "Result": {
            "List": [
                {
                    "PayerID": "payer-1",
                    "OwnerID": "owner-1",
                    "List": rows,
                }
            ]
        },
    }


def balance_response(**overrides) -> dict:
    result = {
        "AccountID": 2100000000,
        "ArrearsBalance": "328.500000",
        "AvailableBalance": "-328.500000",
        "CashBalance": "0.000000",
        "CreditLimit": "0.000000",
        "FreezeAmount": "0.000000",
        "Currency": "CNY",
    }
    result.update(overrides)
    return {
        "ResponseMetadata": {"Error": None, "RequestId": "request-balance-1"},
        "Result": result,
    }


def write_fixture(root: Path, action: str, period: str, offset: int, payload: dict) -> None:
    (root / f"{action}__period-{period}__offset-{offset}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def envelope_rows(payload: dict) -> list[dict]:
    result = payload["result"]
    if isinstance(result, list):
        return result
    if isinstance(result, dict) and "file" in result:
        with Path(result["file"]).open(encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))
    raise AssertionError(f"expected row result, got {result!r}")


def envelope_error(payload: dict) -> dict:
    return payload["_meta"]["error"]


def file_result(path: Path) -> dict[str, str]:
    return {
        "file": str(path.resolve()),
        "metadata": str(path.with_name(f"{path.stem}.meta.json").resolve()),
        "fields": str(path.with_name(f"{path.stem}.fields.json").resolve()),
    }


class SequenceClient(BillingClient):
    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls = []

    def query(self, action, body):
        self.calls.append(dict(body))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RequestContractCompatibilityTest(unittest.TestCase):
    VALID_REQUESTS = {
        "ListFinancialRelation": {},
        "QueryBalanceAcct": {},
        "ListResourcePackages": {"ResourceType": "Package", "MaxResults": "20"},
        "ListPackageUsageDetails": {
            "ResourceType": "Package",
            "DeductBeginTime": "2026-08-01T00:00:00Z",
            "DeductEndTime": "2026-10-01T00:00:00Z",
            "MaxResults": "50",
        },
        "ListCoupons": {},
        "ListCouponUsageRecords": {"CouponID": "coupon-1"},
        "ListCostAnalysisOpenApi": {
            "CostType": 2,
            "TimeGranularity": 0,
            "BeginTimeStr": "2026-08-01",
            "EndTimeStr": "2026-08-01",
            "ClassifyDimension": 3,
            "Limit": 300,
            "Offset": 0,
        },
        "GetFilterInfoForCostAnalysis": {
            "TimeGranularity": 0,
            "BeginTimeStr": "2026-08-01",
            "EndTimeStr": "2026-08-01",
        },
        "ListBillOverviewByCategory": {"BillPeriod": "2026-08"},
        "ListBillOverviewByProd": {"BillPeriod": "2026-08", "Limit": 300},
        "ListBill": {"BillPeriod": "2026-08", "Limit": 300},
        "ListAmortizedCostBillDetail": {"AmortizedMonth": "2026-08", "Limit": 300},
        "ListAmortizedCostBillDaily": {"AmortizedMonth": "2026-08", "Limit": 300},
        "ListAmortizedCostBillMonthly": {"AmortizedMonth": "2026-08", "Limit": 300},
        "ListSplitBillDetail": {"BillPeriod": "2026-08", "Limit": 300},
        "ListBillDetail": {"BillPeriod": "2026-08", "Limit": 300},
    }

    def _validation_errors(self, action: str, body: dict) -> list[dict]:
        with self.assertRaises(BillingQueryError) as context:
            validate_request_body(action, body)
        error = context.exception
        self.assertEqual(ErrorCode.INVALID_ARGUMENT, error.code)
        self.assertEqual(ExitCode.INVALID_ARGUMENT, error.exit_code)
        return error.details["validation_errors"]

    def test_every_action_accepts_its_minimal_valid_request_without_coercion(self) -> None:
        self.assertEqual(16, len(self.VALID_REQUESTS))
        for action, body in self.VALID_REQUESTS.items():
            with self.subTest(action=action):
                self.assertEqual(body, validate_request_body(action, body))

    def test_token_page_size_accepts_json_integer_and_normalizes_to_api_string(self) -> None:
        cases = (
            (
                "ListResourcePackages",
                {"ResourceType": "Package", "MaxResults": 20},
                {"ResourceType": "Package", "MaxResults": "20"},
            ),
            (
                "ListPackageUsageDetails",
                {
                    "ResourceType": "Package",
                    "DeductBeginTime": "2026-08-01T00:00:00Z",
                    "DeductEndTime": "2026-10-01T00:00:00Z",
                    "MaxResults": 50,
                },
                {
                    "ResourceType": "Package",
                    "DeductBeginTime": "2026-08-01T00:00:00Z",
                    "DeductEndTime": "2026-10-01T00:00:00Z",
                    "MaxResults": "50",
                },
            ),
        )
        for action, body, expected in cases:
            with self.subTest(action=action):
                self.assertEqual(expected, validate_request_body(action, body))

    def test_token_page_size_does_not_coerce_boolean_or_float(self) -> None:
        for value in (True, 20.0):
            with self.subTest(value=value):
                errors = self._validation_errors(
                    "ListResourcePackages",
                    {"ResourceType": "Package", "MaxResults": value},
                )
                self.assertEqual("MaxResults", errors[0]["path"])
                self.assertEqual("string_type", errors[0]["type"])

    def test_every_action_rejects_a_missing_required_field_with_stable_error_shape(self) -> None:
        for action, valid in self.VALID_REQUESTS.items():
            with self.subTest(action=action):
                if not valid:
                    continue
                body = dict(valid)
                missing = next(iter(body))
                body.pop(missing)
                errors = self._validation_errors(action, body)
                self.assertEqual(
                    [{"path": missing, "type": "missing", "message": "Field required"}],
                    errors,
                )

    def test_every_action_rejects_unknown_top_level_fields(self) -> None:
        for action, valid in self.VALID_REQUESTS.items():
            with self.subTest(action=action):
                errors = self._validation_errors(action, {**valid, "UnknownField": True})
                self.assertEqual(
                    [{
                        "path": "UnknownField",
                        "type": "extra_forbidden",
                        "message": "Extra inputs are not permitted",
                    }],
                    errors,
                )

    def test_strict_scalar_and_array_item_types_are_not_coerced(self) -> None:
        cases = (
            ("ListBill", {"BillPeriod": "2026-08", "Limit": "300"}, "Limit", "int_type", "integer"),
            ("ListBill", {"BillPeriod": "2026-08", "Limit": True}, "Limit", "int_type", "integer"),
            ("ListBill", {"BillPeriod": 202608, "Limit": 300}, "BillPeriod", "string_type", "string"),
            ("ListBill", {"BillPeriod": "2026-08", "Limit": 300, "PayerID": ["1"]}, "PayerID.0", "int_type", "integer"),
            ("ListBillDetail", {"BillPeriod": "2026-08", "Limit": 300, "Product": [1]}, "Product.0", "string_type", "string"),
        )
        for action, body, path, error_type, type_name in cases:
            with self.subTest(action=action, path=path):
                self.assertEqual(
                    [{"path": path, "type": error_type, "message": f"Input should be a valid {type_name}"}],
                    self._validation_errors(action, body),
                )

    def test_nested_validation_paths_and_errors_are_stable(self) -> None:
        base = dict(self.VALID_REQUESTS["ListCostAnalysisOpenApi"])
        cases = (
            (
                {"Operator": 1, "FilterKey": 3, "FilterValue": [1]},
                {"path": "Filters.0.FilterValue.0", "type": "string_type", "message": "Input should be a valid string"},
            ),
            (
                {"Operator": 1, "FilterKey": 3, "FilterValue": ["ECS"], "Extra": 1},
                {"path": "Filters.0.Extra", "type": "extra_forbidden", "message": "Extra inputs are not permitted"},
            ),
        )
        for item, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    [expected],
                    self._validation_errors("ListCostAnalysisOpenApi", {**base, "Filters": [item]}),
                )

    def test_internal_names_remain_accepted_and_normalized_to_api_aliases(self) -> None:
        result = validate_request_body(
            "ListBill",
            {"bill_period": "2026-08", "limit": 300, "pay_status": "Unsettle"},
        )
        self.assertEqual(
            {"BillPeriod": "2026-08", "Limit": 300, "PayStatus": "Unsettle"},
            result,
        )

    def test_api_alias_and_internal_name_together_reject_the_internal_duplicate(self) -> None:
        errors = self._validation_errors(
            "ListBill",
            {"BillPeriod": "2026-08", "bill_period": "2026-07", "Limit": 300},
        )
        self.assertEqual(
            [{"path": "bill_period", "type": "extra_forbidden", "message": "Extra inputs are not permitted"}],
            errors,
        )

    def test_enum_and_literal_validation_preserve_pydantic_behavior(self) -> None:
        enum_errors = self._validation_errors(
            "ListBill",
            {"BillPeriod": "2026-08", "Limit": 300, "BillingMode": [1]},
        )
        self.assertEqual(
            [{
                "path": "BillingMode.0",
                "type": "enum",
                "message": "Input should be '1', '2', '3', '4' or '5'",
            }],
            enum_errors,
        )
        self.assertEqual(
            {"BillPeriod": "2026-08", "Limit": 300, "NeedRecordNum": 1},
            validate_request_body(
                "ListBill",
                {"BillPeriod": "2026-08", "Limit": 300, "NeedRecordNum": True},
            ),
        )
        literal_errors = self._validation_errors(
            "ListBillDetail",
            {"BillPeriod": "2026-08", "Limit": 300, "GroupPeriod": "1"},
        )
        self.assertEqual(
            [{"path": "GroupPeriod", "type": "literal_error", "message": "Input should be 0, 1 or 2"}],
            literal_errors,
        )

    def test_invalid_parameters_include_only_local_action_contracts(self) -> None:
        with self.assertRaises(BillingQueryError) as context:
            validate_request_body(
                "ListBillDetail",
                {"BillPeriod": "2026-08", "Limit": "300", "GroupPeriod": 9},
            )
        invalid = context.exception.details["invalid_parameters"]
        self.assertEqual(["Limit", "GroupPeriod"], [item["path"] for item in invalid])
        self.assertEqual("300", invalid[0]["actual"])
        self.assertEqual("integer", invalid[0]["contract"]["type"])
        self.assertEqual([0, 1, 2], invalid[1]["contract"]["enum"])
        self.assertNotIn("next_action", context.exception.details)

    def test_relational_error_returns_contracts_for_each_involved_parameter(self) -> None:
        with self.assertRaises(BillingQueryError) as context:
            validate_request_body(
                "ListPackageUsageDetails",
                {
                    "ResourceType": "Package",
                    "DeductBeginTime": "2026-10-01T00:00:00Z",
                    "DeductEndTime": "2026-09-01T00:00:00Z",
                    "MaxResults": "50",
                },
            )
        invalid = context.exception.details["invalid_parameters"]
        self.assertEqual(
            ["DeductBeginTime", "DeductEndTime"],
            [item["path"] for item in invalid],
        )
        self.assertTrue(all(item["contract"]["type"] == "string" for item in invalid))


class QueryBillingTest(unittest.TestCase):
    def _run(self, arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_balance_snapshot_uses_unified_envelope(self) -> None:
        code, stdout, stderr = self._run(
            [
                "--action", "QueryBalanceAcct",
                "--body", "{}",
                "--fixture-dir", str(BALANCE_FIXTURES / "current_arrears"),
            ]
        )
        payload = json.loads(stdout)
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual({"status", "message", "result", "_meta"}, set(payload))
        self.assertEqual("success", payload["status"])
        self.assertEqual("-328.500000", payload["result"]["AvailableBalance"])
        self.assertEqual("328.500000", payload["result"]["ArrearsBalance"])
        self.assertEqual("in_arrears", payload["_meta"]["account_status"])
        self.assertEqual(OUTPUT_PROTOCOL_VERSION, payload["_meta"]["output_protocol_version"])
        self.assertTrue({"queried_at", "snapshot_time"}.isdisjoint(payload["_meta"]))
        self.assertTrue({"row_count", "coverage", "queries", "failed_queries"}.isdisjoint(payload["_meta"]))
        self.assertEqual({"status": "pass"}, payload["_meta"]["balance_check"])
        self.assertNotIn("credit_covered", payload["_meta"])

    def test_balance_message_and_raw_fields_are_consistent_when_exported(self) -> None:
        cases = (
            ("current_arrears", "in_arrears", "pass"),
            ("nonnegative_with_arrears", "not_in_arrears", "pass"),
            ("missing_available", "unknown", "not_checked"),
            ("formula_mismatch", "unknown", "fail"),
        )
        with tempfile.TemporaryDirectory() as directory:
            for fixture, account_status, balance_status in cases:
                with self.subTest(fixture=fixture):
                    arguments = [
                        "--action", "QueryBalanceAcct", "--body", "{}",
                        "--fixture-dir", str(BALANCE_FIXTURES / fixture),
                    ]
                    code, stdout, stderr = self._run(arguments)
                    self.assertEqual((0, ""), (code, stderr))
                    snapshot = json.loads(stdout)
                    output = Path(directory) / f"{fixture}.csv"
                    code, stdout, stderr = self._run([*arguments, "--out", str(output)])
                    self.assertEqual((0, ""), (code, stderr))
                    artifact = json.loads(stdout)
                    metadata = json.loads(Path(artifact["_meta"]["evidence_file"]).read_text())
                    self.assertEqual(account_status, snapshot["_meta"]["account_status"])
                    self.assertEqual(balance_status, snapshot["_meta"]["balance_check"]["status"])
                    self.assertEqual("success", artifact["status"])
                    self.assertEqual(file_result(output), artifact["result"])
                    with Path(artifact["result"]["file"]).open(encoding="utf-8", newline="") as file:
                        exported = next(csv.DictReader(file))
                    comparable = {key: value for key, value in exported.items() if key not in {"_action", "_query_id"}}
                    expected = {key: str(value) for key, value in snapshot["result"].items()}
                    self.assertEqual(expected, comparable)
                    self.assertNotIn("tool_hint", metadata)
                    self.assertNotIn("generated_at", metadata)
                    self.assertTrue({"queried_at", "snapshot_time"}.isdisjoint(artifact["_meta"]))
                    self.assertTrue(Path(artifact["_meta"]["evidence_file"]).is_file())
                    self.assertTrue(Path(artifact["_meta"]["field_catalog"]).is_file())
                    self.assertTrue({"row_count", "coverage", "queries", "failed_queries"}.isdisjoint(artifact["_meta"]))
                    if fixture == "missing_available":
                        self.assertNotIn("AvailableBalance", snapshot["result"])

    def test_balance_permission_fixture_fails_without_business_rows(self) -> None:
        code, stdout, stderr = self._run(
            [
                "--action", "QueryBalanceAcct",
                "--body", "{}",
                "--fixture-dir", str(BALANCE_FIXTURES / "permission_denied"),
                "--retry-count", "0",
            ]
        )
        payload = json.loads(stdout)
        self.assertEqual(5, code)
        self.assertEqual("", stderr)
        self.assertEqual("error", payload["status"])
        self.assertIsNone(payload["result"])
        self.assertEqual("PERMISSION_DENIED", envelope_error(payload)["code"])

    def test_balance_snapshot_rejects_non_string_amounts(self) -> None:
        client = SequenceClient([balance_response(AvailableBalance=-328.5)])
        result = collect_query(
            client=client,
            action="QueryBalanceAcct",
            query_id="current",
            base_body={},
            config=FetchConfig(pagination="none"),
        )
        self.assertEqual("RESPONSE_INVALID", result.error["code"])

    def test_balance_snapshot_fields_are_decimal_but_not_aggregatable(self) -> None:
        catalog = build_field_catalog(
            action="QueryBalanceAcct",
            columns=[
                "AccountID",
                "ArrearsBalance",
                "AvailableBalance",
                "CashBalance",
                "CreditLimit",
                "FreezeAmount",
                "Currency",
            ],
            source_csv=Path("balance.csv"),
            source_metadata=None,
        )
        fields = {item["field"]: item for item in catalog["fields"]}
        for name in (
            "ArrearsBalance",
            "AvailableBalance",
            "CashBalance",
            "CreditLimit",
            "FreezeAmount",
        ):
            with self.subTest(name=name):
                self.assertEqual("decimal", fields[name]["type"])
                self.assertEqual("attribute", fields[name]["role"])
                self.assertEqual([], fields[name]["aggregations"])
                self.assertEqual("Currency", fields[name]["currency_field"])
        self.assertNotIn("AccountID", fields)
        self.assertEqual("currency", fields["Currency"]["role"])

    def test_default_output_inlines_by_compact_size_without_writing_artifacts(self) -> None:
        cases = (
            (
                "more_than_twenty_rows",
                [
                    {
                        "BillCategoryParent": f"category-{index}",
                        "PayableAmount": str(index),
                        "Currency": "CNY",
                    }
                    for index in range(25)
                ],
            ),
            (
                "above_old_32_kib_limit",
                [{
                    "BillCategoryParent": "consume",
                    "PayableAmount": "1",
                    "Currency": "CNY",
                    "OwnerCustomerName": "x" * (40 * 1024),
                }],
            ),
        )
        for name, rows in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "ListBillOverviewByCategory.json").write_text(
                    json.dumps(category_response(rows)),
                    encoding="utf-8",
                )
                automatic_output = root / "auto" / "result.csv"
                with mock.patch(
                    "query_billing._create_automatic_output_path",
                    return_value=automatic_output,
                ) as create_output:
                    code, stdout, stderr = self._run(
                        [
                            "--action", "ListBillOverviewByCategory",
                            "--body", '{"BillPeriod":"2026-07"}',
                            "--fixture-dir", str(root),
                        ]
                    )
                payload = json.loads(stdout)

                self.assertEqual((0, ""), (code, stderr))
                self.assertEqual("success", payload["status"])
                self.assertEqual(len(rows), payload["_meta"]["row_count"])
                self.assertEqual(len(rows), len(payload["result"]))
                self.assertNotIn("file", payload["result"] if isinstance(payload["result"], dict) else {})
                create_output.assert_not_called()
                self.assertFalse(automatic_output.parent.exists())

    def test_default_output_uses_artifact_above_utf8_byte_limit(self) -> None:
        cases = (
            ("ascii", "x" * (64 * 1024)),
            ("multibyte", "云" * 22_000),
        )
        for name, value in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                rows = [{
                    "BillCategoryParent": "consume",
                    "PayableAmount": "1",
                    "Currency": "CNY",
                    "OwnerCustomerName": value,
                }]
                (root / "ListBillOverviewByCategory.json").write_text(
                    json.dumps(category_response(rows)),
                    encoding="utf-8",
                )
                automatic_output = root / "auto" / "result.csv"
                with mock.patch(
                    "query_billing._create_automatic_output_path",
                    return_value=automatic_output,
                ):
                    code, stdout, stderr = self._run(
                        [
                            "--action", "ListBillOverviewByCategory",
                            "--body", '{"BillPeriod":"2026-07"}',
                            "--fixture-dir", str(root),
                        ]
                    )
                payload = json.loads(stdout)

                self.assertEqual((0, ""), (code, stderr))
                self.assertEqual("success", payload["status"])
                self.assertEqual(file_result(automatic_output), payload["result"])
                self.assertTrue(automatic_output.is_file())

    def test_explicit_output_uses_artifact_for_small_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ListBillOverviewByCategory.json").write_text(
                json.dumps(
                    category_response(
                        [{"BillCategoryParent": "consume", "PayableAmount": "1", "Currency": "CNY"}]
                    )
                ),
                encoding="utf-8",
            )
            output = root / "category.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBillOverviewByCategory",
                    "--body", '{"BillPeriod":"2026-07"}',
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
            output_exists = output.is_file()
            metadata_exists = output.with_name("category.meta.json").is_file()
            fields_exists = output.with_name("category.fields.json").is_file()

        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("success", payload["status"])
        self.assertEqual(file_result(output), payload["result"])
        self.assertTrue(output_exists)
        self.assertTrue(metadata_exists)
        self.assertTrue(fields_exists)
        self.assertNotIn("preview", payload)

    def test_product_overview_preserves_distinct_amount_fields_and_source_precision(self) -> None:
        row = {
            "Product": "CloudKMS",
            "ProductZh": "密钥管理系统",
            "OriginalBillAmount": "0.012091",
            "DiscountBillAmount": "0.012091",
            "RoundBillAmount": "0.002091",
            "PayableAmount": "0.01",
            "Currency": "CNY",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(
                root,
                "ListBillOverviewByProd",
                "2026-07",
                0,
                bill_response([row], total=1, limit=1, offset=0),
            )
            output = root / "product.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBillOverviewByProd",
                    "--body", '{"BillPeriod":"2026-07"}',
                    "--pagination", "full",
                    "--page-size", "1",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
            with output.open(encoding="utf-8") as file:
                csv_row = next(csv.DictReader(file))

        self.assertEqual((0, ""), (code, stderr))
        expected = {
            "OriginalBillAmount": "0.012091",
            "DiscountBillAmount": "0.012091",
            "RoundBillAmount": "0.002091",
            "PayableAmount": "0.01",
        }
        self.assertEqual(file_result(output), payload["result"])
        self.assertEqual(expected, {key: csv_row[key] for key in expected})

    def test_default_output_does_not_create_automatic_artifacts_when_all_queries_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(
                root,
                "ListBill",
                "2026-07",
                0,
                {"__error__": {"code": "PERMISSION_DENIED", "message": "denied"}},
            )
            with mock.patch("query_billing._create_automatic_output_path") as create_output:
                code, stdout, stderr = self._run(
                    [
                        "--action", "ListBill",
                        "--body", '{"BillPeriod":"2026-07"}',
                        "--pagination", "full",
                        "--fixture-dir", str(root),
                    ]
                )

        self.assertEqual(5, code)
        self.assertEqual("", stderr)
        self.assertEqual("PERMISSION_DENIED", envelope_error(json.loads(stdout))["code"])
        create_output.assert_not_called()

    def test_output_collisions_are_rejected_before_client_creation(self) -> None:
        for conflicting_name in ("bill.csv", "bill.meta.json", "bill.fields.json"):
            with self.subTest(conflicting_name=conflicting_name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / conflicting_name).write_text("existing", encoding="utf-8")
                output = root / "bill.csv"
                with mock.patch("query_billing.FixtureBillingClient") as client_class:
                    code, stdout, stderr = self._run(
                        [
                            "--action", "ListBill",
                            "--body", '{"BillPeriod":"2026-07"}',
                            "--pagination", "full",
                            "--fixture-dir", str(root),
                            "--out", str(output),
                        ]
                    )
                payload = json.loads(stdout)
                client_class.assert_not_called()
                self.assertEqual(7, code)
                self.assertEqual("", stderr)
                error = envelope_error(payload)
                self.assertEqual("OUTPUT_EXISTS", error["code"])
                details = error["details"]
                self.assertEqual("output_preflight", details["phase"])
                self.assertFalse(details["remote_call_attempted"])
                self.assertEqual([str(root / conflicting_name)], details["paths"])
                self.assertEqual(
                    ["choose_new_output_path", "retry_with_overwrite"],
                    [item["action"] for item in details["recovery_options"]],
                )

    def test_overwrite_queries_once_and_replaces_owned_output_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "bill.csv"
            for path in (output, root / "bill.meta.json", root / "bill.fields.json"):
                path.write_text("owned-by-current-task", encoding="utf-8")
            client = SequenceClient([
                bill_response([bill_row(1)], total=1, limit=300, offset=0),
            ])
            with mock.patch("query_billing.FixtureBillingClient", return_value=client):
                code, stdout, stderr = self._run(
                    [
                        "--action", "ListBill",
                        "--body", '{"BillPeriod":"2026-07"}',
                        "--pagination", "full",
                        "--fixture-dir", str(root),
                        "--out", str(output),
                        "--overwrite",
                    ]
                )
            payload = json.loads(stdout)
            metadata = json.loads((root / "bill.meta.json").read_text(encoding="utf-8"))
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual("success", payload["status"])
        self.assertEqual(1, len(client.calls))
        self.assertEqual(1, metadata["row_count"])

    def test_agent_cli_fetches_all_pages_and_writes_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root, "ListBill", "2026-07", 0, bill_response([bill_row(1), bill_row(2)], total=3, limit=2, offset=0))
            write_fixture(root, "ListBill", "2026-07", 2, bill_response([bill_row(3)], total=3, limit=2, offset=2))
            output = root / "bill.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBill",
                    "--body", '{"BillPeriod":"2026-07"}',
                    "--pagination", "full",
                    "--page-size", "2",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
            with output.open(encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
            metadata = json.loads((root / "bill.meta.json").read_text())
            fields = json.loads((root / "bill.fields.json").read_text())
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual("success", payload["status"])
        self.assertEqual(3, len(rows))
        self.assertEqual(["bill-1", "bill-2", "bill-3"], [row["BillID"] for row in rows])
        self.assertTrue(metadata["coverage"]["is_complete"])
        self.assertEqual(2, metadata["coverage"]["pages_fetched"])
        self.assertEqual(str((root / "bill.fields.json").resolve()), payload["_meta"]["field_catalog"])
        self.assertEqual(payload["_meta"]["field_catalog"], metadata["artifacts"]["fields"])
        product = next(item for item in fields["fields"] if item["field"] == "Product")
        payable = next(item for item in fields["fields"] if item["field"] == "PayableAmount")
        serialized_fields = json.dumps(fields, ensure_ascii=False)
        self.assertNotIn('"canonical"', serialized_fields)
        self.assertNotIn('"column"', serialized_fields)
        self.assertEqual("Product", product["field"])
        self.assertEqual("PayableAmount", payable["field"])
        self.assertEqual("dimension", product["role"])
        self.assertEqual(["sum", "avg", "count"], payable["aggregations"])
        self.assertEqual("Currency", payable["currency_field"])

    def test_multi_period_failure_continues_and_outputs_partial_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root, "ListBill", "2026-06", 0, {"__error__": {"code": "PERMISSION_DENIED", "message": "denied"}})
            write_fixture(root, "ListBill", "2026-07", 0, bill_response([bill_row(1)], total=1, limit=2, offset=0))
            output = root / "bill.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBill",
                    "--body", "{}",
                    "--period", "2026-06",
                    "--period", "2026-07",
                    "--pagination", "full",
                    "--page-size", "2",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
            metadata = json.loads((root / "bill.meta.json").read_text())
        self.assertEqual(6, code)
        self.assertEqual("", stderr)
        self.assertEqual("partial", payload["status"])
        self.assertEqual(1, payload["_meta"]["row_count"])
        self.assertEqual(1, len(metadata["coverage"]["failed_queries"]))
        self.assertEqual("2026-06", metadata["coverage"]["failed_queries"][0]["query_id"])

    def test_small_partial_result_remains_inline_with_machine_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root, "ListBill", "2026-06", 0, {"__error__": {"code": "PERMISSION_DENIED", "message": "denied"}})
            write_fixture(root, "ListBill", "2026-07", 0, bill_response([bill_row(1)], total=1, limit=2, offset=0))
            automatic_output = root / "auto" / "result.csv"
            with mock.patch(
                "query_billing._create_automatic_output_path",
                return_value=automatic_output,
            ) as create_output:
                code, stdout, stderr = self._run(
                    [
                        "--action", "ListBill",
                        "--body", "{}",
                        "--period", "2026-06",
                        "--period", "2026-07",
                        "--pagination", "full",
                        "--page-size", "2",
                        "--fixture-dir", str(root),
                    ]
                )
            payload = json.loads(stdout)
        self.assertEqual((6, ""), (code, stderr))
        self.assertEqual("partial", payload["status"])
        self.assertEqual(1, len(payload["result"]))
        self.assertEqual(1, len(payload["_meta"]["coverage"]["failed_queries"]))
        create_output.assert_not_called()

    def test_multi_period_empty_success_and_failure_returns_partial(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root, "ListBill", "2026-06", 0, bill_response([], total=0, limit=2, offset=0))
            write_fixture(root, "ListBill", "2026-07", 0, {"__error__": {"code": "PERMISSION_DENIED", "message": "denied"}})
            output = root / "bill.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBill",
                    "--body", "{}",
                    "--period", "2026-06",
                    "--period", "2026-07",
                    "--pagination", "full",
                    "--page-size", "2",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
            metadata = json.loads((root / "bill.meta.json").read_text())
            output_exists = output.is_file()
        self.assertEqual(6, code)
        self.assertEqual("", stderr)
        self.assertEqual("partial", payload["status"])
        self.assertEqual(0, payload["_meta"]["row_count"])
        self.assertTrue(output_exists)
        self.assertEqual("2026-06", metadata["coverage"]["queries"][0]["query_id"])
        self.assertTrue(metadata["coverage"]["queries"][0]["is_complete"])
        self.assertEqual(0, metadata["coverage"]["queries"][0]["expected_total"])
        self.assertEqual(1, len(metadata["coverage"]["failed_queries"]))
        self.assertEqual("2026-07", metadata["coverage"]["failed_queries"][0]["query_id"])

    def test_all_queries_failed_returns_error_without_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(
                root,
                "ListBill",
                "2026-07",
                0,
                {"__error__": {"code": "PERMISSION_DENIED", "message": "denied"}},
            )
            output = root / "failed.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBill",
                    "--body", '{"BillPeriod":"2026-07"}',
                    "--pagination", "full",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
            artifacts = [
                output,
                root / "failed.meta.json",
                root / "failed.fields.json",
            ]
        self.assertEqual(5, code)
        self.assertEqual("", stderr)
        self.assertEqual("error", payload["status"])
        error = envelope_error(payload)
        self.assertEqual("PERMISSION_DENIED", error["code"])
        self.assertEqual(1, error["details"]["failed_query_count"])
        self.assertFalse(error["details"]["artifacts_written"])
        self.assertTrue(all(not path.exists() for path in artifacts))

    def test_all_queries_failed_with_mixed_causes_uses_aggregate_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root, "ListBill", "2026-06", 0, {"__error__": {"code": "PERMISSION_DENIED", "message": "denied"}})
            write_fixture(root, "ListBill", "2026-07", 0, {"__error__": {"code": "TIMEOUT", "message": "timed out"}})
            output = root / "failed.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBill",
                    "--body", "{}",
                    "--period", "2026-06",
                    "--period", "2026-07",
                    "--pagination", "full",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                    "--retry-count", "0",
                ]
            )
            payload = json.loads(stdout)
        self.assertEqual(5, code)
        self.assertEqual("", stderr)
        error = envelope_error(payload)
        self.assertEqual("ALL_QUERIES_FAILED", error["code"])
        failed = error["details"]["failed_queries"]
        self.assertEqual(["2026-06", "2026-07"], [item["query_id"] for item in failed])
        self.assertEqual({"PERMISSION_DENIED", "TIMEOUT"}, {item["error"]["code"] for item in failed})
        self.assertFalse(output.exists())

    def test_zero_row_pagination_failure_returns_error_without_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(
                root,
                "ListBill",
                "2026-07",
                0,
                bill_response([], total=3, limit=2, offset=0),
            )
            output = root / "failed.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBill",
                    "--body", '{"BillPeriod":"2026-07"}',
                    "--pagination", "full",
                    "--page-size", "2",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
        self.assertEqual(5, code)
        self.assertEqual("", stderr)
        error = envelope_error(payload)
        self.assertEqual("PAGINATION_INCOMPLETE", error["code"])
        self.assertFalse(output.exists())

    def test_total_change_duplicate_and_early_end_are_incomplete(self) -> None:
        cases = (
            (
                [
                    bill_response([bill_row(1), bill_row(2)], total=4, limit=2, offset=0),
                    bill_response([bill_row(3), bill_row(4)], total=5, limit=2, offset=2),
                ],
            ),
            (
                [
                    bill_response([bill_row(1), bill_row(2)], total=5, limit=2, offset=0),
                    bill_response([bill_row(1), bill_row(2)], total=5, limit=2, offset=2),
                ],
            ),
            ([bill_response([], total=3, limit=2, offset=0)],),
        )
        for (outcomes,) in cases:
            with self.subTest(outcomes=len(outcomes)):
                result = collect_query(
                    client=SequenceClient(outcomes),
                    action="ListBill",
                    query_id="2026-07",
                    base_body={"BillPeriod": "2026-07"},
                    config=FetchConfig(page_size=2),
                    sleeper=lambda _: None,
                )
                self.assertFalse(result.is_complete)
                self.assertEqual("PAGINATION_INCOMPLETE", result.error["code"])

    def test_current_period_rows_over_first_total_are_provisional(self) -> None:
        period = date.today().strftime("%Y-%m")
        client = SequenceClient([
            bill_response([bill_row(1), bill_row(2)], total=3, limit=2, offset=0),
            bill_response([bill_row(3), bill_row(4)], total=3, limit=2, offset=2),
        ])
        result = collect_query(
            client=client,
            action="ListBill",
            query_id=period,
            base_body={"BillPeriod": period},
            config=FetchConfig(page_size=2),
            sleeper=lambda _: None,
        )
        coverage = aggregate_coverage([result])
        self.assertEqual(2, len(client.calls))
        self.assertFalse(result.is_complete)
        self.assertTrue(result.is_provisional)
        self.assertIsNone(result.error)
        self.assertEqual("rows_exceeded_first_total", result.stop_reason)
        self.assertTrue(result.initial_total_boundary_reached)
        self.assertTrue(coverage["requested_scope_fulfilled"])
        self.assertTrue(coverage["is_provisional"])
        self.assertEqual("current_period_total_drift", coverage["consistency"])
        self.assertEqual([], coverage["failed_queries"])

    def test_current_period_total_change_is_provisional_only_after_first_boundary(self) -> None:
        period = date.today().strftime("%Y-%m")
        reached = collect_query(
            client=SequenceClient([
                bill_response([bill_row(1), bill_row(2)], total=4, limit=2, offset=0),
                bill_response([bill_row(3), bill_row(4)], total=5, limit=2, offset=2),
            ]),
            action="ListBill",
            query_id=period,
            base_body={"BillPeriod": period},
            config=FetchConfig(page_size=2),
            sleeper=lambda _: None,
        )
        early = collect_query(
            client=SequenceClient([
                bill_response([bill_row(1), bill_row(2)], total=6, limit=2, offset=0),
                bill_response([bill_row(3), bill_row(4)], total=7, limit=2, offset=2),
            ]),
            action="ListBill",
            query_id=period,
            base_body={"BillPeriod": period},
            config=FetchConfig(page_size=2),
            sleeper=lambda _: None,
        )
        self.assertTrue(reached.is_provisional)
        self.assertEqual(4, len(reached.rows))
        self.assertIsNone(reached.error)
        self.assertFalse(early.is_provisional)
        self.assertEqual("PAGINATION_INCOMPLETE", early.error["code"])

    def test_closed_period_rows_over_total_remain_incomplete(self) -> None:
        result = collect_query(
            client=SequenceClient([
                bill_response([bill_row(1), bill_row(2)], total=3, limit=2, offset=0),
                bill_response([bill_row(3), bill_row(4)], total=3, limit=2, offset=2),
            ]),
            action="ListBill",
            query_id="2026-07",
            base_body={"BillPeriod": "2026-07"},
            config=FetchConfig(page_size=2),
            sleeper=lambda _: None,
        )
        self.assertFalse(result.is_provisional)
        self.assertFalse(result.is_complete)
        self.assertEqual("PAGINATION_INCOMPLETE", result.error["code"])

    def test_current_period_provisional_query_returns_success_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            period = date.today().strftime("%Y-%m")
            write_fixture(root, "ListBill", period, 0, bill_response([bill_row(1), bill_row(2)], total=3, limit=2, offset=0))
            write_fixture(root, "ListBill", period, 2, bill_response([bill_row(3), bill_row(4)], total=3, limit=2, offset=2))
            output = root / "current-bill.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBill",
                    "--body", json.dumps({"BillPeriod": period}),
                    "--pagination", "full",
                    "--page-size", "2",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
            metadata = json.loads((root / "current-bill.meta.json").read_text(encoding="utf-8"))
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual("success", payload["status"])
        self.assertEqual(4, payload["_meta"]["row_count"])
        self.assertNotIn("coverage", {key: value for key, value in payload.items() if key != "_meta"})
        self.assertTrue(metadata["coverage"]["requested_scope_fulfilled"])
        self.assertFalse(metadata["coverage"]["is_complete"])
        self.assertTrue(metadata["coverage"]["is_provisional"])
        self.assertEqual([], metadata["coverage"]["failed_queries"])
        self.assertTrue(metadata["freshness"]["partial_period"])

    def test_missing_total_completes_on_short_terminal_page(self) -> None:
        first = bill_response([bill_row(1), bill_row(2)], total=-1, limit=2, offset=0)
        second = bill_response([bill_row(3)], total=-1, limit=2, offset=2)
        result = collect_query(
            client=SequenceClient([first, second]),
            action="ListBill",
            query_id="2026-07",
            base_body={"BillPeriod": "2026-07"},
            config=FetchConfig(page_size=2),
            sleeper=lambda _: None,
        )
        self.assertTrue(result.is_complete)
        self.assertIsNone(result.expected_total)
        self.assertEqual(3, len(result.rows))

    def test_max_pages_marks_full_query_incomplete(self) -> None:
        result = collect_query(
            client=SequenceClient(
                [bill_response([bill_row(1), bill_row(2)], total=5, limit=2, offset=0)]
            ),
            action="ListBill",
            query_id="2026-07",
            base_body={"BillPeriod": "2026-07"},
            config=FetchConfig(page_size=2, max_pages=1),
            sleeper=lambda _: None,
        )
        self.assertFalse(result.is_complete)
        self.assertIsNone(result.error)
        self.assertTrue(any("max_pages" in item for item in result.warnings))

    def test_response_offset_mismatch_is_incomplete(self) -> None:
        result = collect_query(
            client=SequenceClient(
                [bill_response([bill_row(1)], total=1, limit=2, offset=9)]
            ),
            action="ListBill",
            query_id="2026-07",
            base_body={"BillPeriod": "2026-07"},
            config=FetchConfig(page_size=2),
            sleeper=lambda _: None,
        )
        self.assertFalse(result.is_complete)
        self.assertEqual("PAGINATION_INCOMPLETE", result.error["code"])

    def test_only_rate_limit_and_timeout_are_retried(self) -> None:
        for code in (ErrorCode.RATE_LIMITED, ErrorCode.TIMEOUT):
            with self.subTest(code=code):
                error = BillingQueryError(code, "retry", ExitCode.QUERY_FAILED)
                client = SequenceClient([error, bill_response([bill_row(1)], total=1, limit=2, offset=0)])
                result = collect_query(
                    client=client,
                    action="ListBill",
                    query_id="2026-07",
                    base_body={"BillPeriod": "2026-07"},
                    config=FetchConfig(page_size=2, retry_count=1, retry_backoff_seconds=0),
                    sleeper=lambda _: None,
                )
                self.assertTrue(result.is_complete)
                self.assertEqual(2, len(client.calls))
        denied = SequenceClient([BillingQueryError(ErrorCode.PERMISSION_DENIED, "denied", ExitCode.QUERY_FAILED)])
        result = collect_query(
            client=denied,
            action="ListBill",
            query_id="2026-07",
            base_body={"BillPeriod": "2026-07"},
            config=FetchConfig(page_size=2, retry_count=3, retry_backoff_seconds=0),
            sleeper=lambda _: None,
        )
        self.assertEqual(1, len(denied.calls))
        self.assertFalse(result.is_complete)

    def test_invalid_request_fails_before_client_call(self) -> None:
        client = SequenceClient([])
        with self.assertRaisesRegex(BillingQueryError, "合法月份"):
            collect_query(
                client=client,
                action="ListBill",
                query_id="bad",
                base_body={"BillPeriod": "2026-99"},
                config=FetchConfig(),
            )
        self.assertEqual([], client.calls)

    def test_bill_period_rejects_month_outside_structured_range(self) -> None:
        client = SequenceClient([])
        with self.assertRaisesRegex(BillingQueryError, "BillPeriod 超出支持的时间范围") as context:
            collect_query(
                client=client,
                action="ListBill",
                query_id="2020-01",
                base_body={"BillPeriod": "2020-01", "Limit": 300},
                config=FetchConfig(),
            )
        self.assertEqual("2020-01", context.exception.details["value"])
        self.assertEqual(24, context.exception.details["max_age_months"])
        self.assertEqual([], client.calls)

    def test_amortized_month_uses_stricter_structured_range(self) -> None:
        with self.assertRaisesRegex(BillingQueryError, "AmortizedMonth 超出支持的时间范围") as context:
            validate_request_body(
                "ListAmortizedCostBillMonthly",
                {"AmortizedMonth": "2020-01", "Limit": 300},
            )
        self.assertEqual("2020-01", context.exception.details["value"])
        self.assertEqual(24, context.exception.details["max_age_months"])

    def test_cost_analysis_dates_reject_values_outside_structured_range(self) -> None:
        with self.assertRaisesRegex(BillingQueryError, "BeginTimeStr 超出支持的时间范围") as context:
            validate_request_body(
                "ListCostAnalysisOpenApi",
                {
                    "CostType": 2,
                    "TimeGranularity": 0,
                    "BeginTimeStr": "2020-01-01",
                    "EndTimeStr": "2026-07-01",
                    "ClassifyDimension": 3,
                    "Limit": 300,
                    "Offset": 0,
                },
            )
        self.assertEqual("2020-01-01", context.exception.details["value"])
        self.assertEqual(24, context.exception.details["max_age_months"])

    def test_bill_detail_response_fields_in_body_return_recoverable_error(self) -> None:
        client = SequenceClient([])
        with self.assertRaises(BillingQueryError) as context:
            collect_query(
                client=client,
                action="ListBillDetail",
                query_id="bad-fields",
                base_body={
                    "BillPeriod": "2026-07",
                    "Usage": True,
                    "UnitPrice": True,
                },
                config=FetchConfig(),
            )
        error = context.exception
        self.assertEqual(ErrorCode.RESPONSE_FIELDS_IN_REQUEST_BODY, error.code)
        self.assertEqual(["Usage", "UnitPrice"], error.details["invalid_request_fields"])
        self.assertEqual("Count", error.details["possible_response_fields"]["Usage"]["response_field"])
        self.assertEqual("Price", error.details["possible_response_fields"]["UnitPrice"]["response_field"])
        self.assertFalse(error.details["request_projection_supported"])
        self.assertEqual([], client.calls)

    def test_bill_detail_unknown_request_field_remains_generic_validation_error(self) -> None:
        with self.assertRaises(BillingQueryError) as context:
            validate_request_body("ListBillDetail", {"BillPeriod": "2026-07", "UnknownThing": True})
        self.assertEqual(ErrorCode.INVALID_ARGUMENT, context.exception.code)
        self.assertNotEqual(ErrorCode.RESPONSE_FIELDS_IN_REQUEST_BODY, context.exception.code)

    def test_list_bill_pay_status_is_validated_as_single_string(self) -> None:
        valid = validate_request_body(
            "ListBill",
            {"BillPeriod": "2026-07", "Limit": 300, "PayStatus": "Unsettle"},
        )
        self.assertEqual("Unsettle", valid["PayStatus"])

        with self.assertRaises(BillingQueryError) as context:
            validate_request_body(
                "ListBill",
                {"BillPeriod": "2026-07", "Limit": 300, "PayStatus": "UnknownSettle"},
            )
        self.assertEqual(["UnknownSettle"], context.exception.details["invalid"])

        with self.assertRaisesRegex(BillingQueryError, "请求不符合目标 Action 契约"):
            validate_request_body(
                "ListBill",
                {"BillPeriod": "2026-07", "Limit": 300, "PayStatus": ["Unsettle"]},
            )

    def test_billing_mode_accepts_commitment_code(self) -> None:
        valid = validate_request_body(
            "ListBillDetail",
            {"BillPeriod": "2026-07", "Limit": 300, "BillingMode": ["5"]},
        )
        self.assertEqual(["5"], valid["BillingMode"])

    def test_bill_category_accepts_complete_public_code_set(self) -> None:
        valid = validate_request_body(
            "ListBillDetail",
            {
                "BillPeriod": "2026-07",
                "Limit": 300,
                "BillCategory": [
                    "consume-TempUpgrade",
                    "consume-RIAdjust",
                    "refund-DeliveryFailed",
                    "consume-Commitment",
                    "consume-transfer",
                    "refund-transfer",
                ],
            },
        )
        self.assertEqual(
            [
                "consume-TempUpgrade",
                "consume-RIAdjust",
                "refund-DeliveryFailed",
                "consume-Commitment",
                "consume-transfer",
                "refund-transfer",
            ],
            valid["BillCategory"],
        )

    def test_bill_detail_rejects_product_or_account_detail_grain_before_client_call(self) -> None:
        cases = (
            (2, "产品\\+明细"),
            (3, "账号\\+明细"),
        )
        for group_term, message in cases:
            with self.subTest(group_term=group_term):
                client = SequenceClient([])
                with self.assertRaisesRegex(BillingQueryError, message):
                    collect_query(
                        client=client,
                        action="ListBillDetail",
                        query_id="2026-07",
                        base_body={
                            "BillPeriod": "2026-07",
                            "GroupPeriod": 2,
                            "GroupTerm": group_term,
                        },
                        config=FetchConfig(),
                    )
                self.assertEqual([], client.calls)

    def test_tag_kv_requires_non_empty_key_and_value_before_client_call(self) -> None:
        cases = (
            ([{"Key": "volc-Key"}], "value_provided"),
            ([{"Value": "prod"}], "key_provided"),
            ([{"Key": "volc-Key", "Value": ""}], "value_provided"),
        )
        for tag_kv, detail_key in cases:
            with self.subTest(tag_kv=tag_kv):
                client = SequenceClient([])
                with self.assertRaisesRegex(BillingQueryError, "TagKV 每一项必须同时提供非空 Key 和 Value") as context:
                    collect_query(
                        client=client,
                        action="ListSplitBillDetail",
                        query_id="2026-07",
                        base_body={
                            "BillPeriod": "2026-07",
                            "GroupPeriod": 2,
                            "TagKV": tag_kv,
                            "TagKVFilterMode": 1,
                        },
                        config=FetchConfig(),
                    )
                self.assertFalse(context.exception.details[detail_key])
                self.assertEqual([], client.calls)

    def test_cost_analysis_filters_are_validated_after_alias_normalization(self) -> None:
        valid = validate_request_body(
            "ListCostAnalysisOpenApi",
            {
                "CostType": 2,
                "TimeGranularity": 0,
                "BeginTimeStr": "2026-07-01",
                "EndTimeStr": "2026-07-01",
                "ClassifyDimension": 3,
                "Limit": 300,
                "Offset": 0,
                "Filters": [
                    {"Operator": 1, "FilterKey": 3, "FilterValue": ["ECS"]}
                ],
            },
        )
        self.assertEqual(3, valid["Filters"][0]["FilterKey"])
        with self.assertRaisesRegex(BillingQueryError, "1 到 300"):
            validate_request_body(
                "ListCostAnalysisOpenApi",
                {**valid, "Limit": 301},
            )
        cost_scope = validate_request_body(
            "ListCostAnalysisOpenApi",
            {**valid, "CostType": 6},
        )
        self.assertEqual(6, cost_scope["CostType"])
        for disabled in (3, 7):
            with self.subTest(disabled_cost_type=disabled), self.assertRaisesRegex(BillingQueryError, "现金支付口径"):
                validate_request_body(
                    "ListCostAnalysisOpenApi",
                    {**valid, "CostType": disabled},
                )
        with self.assertRaisesRegex(BillingQueryError, "Operator"):
            validate_request_body(
                "ListCostAnalysisOpenApi",
                {
                    **valid,
                    "Filters": [
                        {"Operator": 99, "FilterKey": 3, "FilterValue": ["ECS"]}
                    ],
                },
            )

    def test_pagination_mode_is_explicitly_required(self) -> None:
        code, stdout, stderr = self._run(
            [
                "--action", "ListBill",
                "--body", '{"BillPeriod":"2026-07"}',
                "--out", "unused.csv",
            ]
        )
        self.assertEqual(2, code)
        self.assertEqual("", stderr)
        self.assertEqual("INVALID_ARGUMENT", envelope_error(json.loads(stdout))["code"])

    def test_filter_catalog_is_non_paged_structured_stdout_by_default(self) -> None:
        products = [
            {"ProductCode": f"product-{index}", "ProductName": f"产品 {index}"}
            for index in range(101)
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(
                root,
                "GetFilterInfoForCostAnalysis",
                "2026-07-01",
                0,
                filter_info_response(
                    {
                        "ProductList": products,
                        "ConfigurationCode": [{"ConfigCode": "c1", "ConfigName": "配置一"}],
                        "TagKeyList": ["team"],
                    }
                ),
            )
            code, stdout, stderr = self._run(
                [
                    "--action", "GetFilterInfoForCostAnalysis",
                    "--body", '{"TimeGranularity":0,"BeginTimeStr":"2026-07-01","EndTimeStr":"2026-07-01"}',
                    "--fixture-dir", str(root),
                ]
            )
            self.assertEqual((0, ""), (code, stderr))
            payload = json.loads(stdout)
            generated = [path.name for path in root.iterdir() if not path.name.endswith("offset-0.json")]
        self.assertEqual("success", payload["status"])
        self.assertNotIn("output_format", payload)
        self.assertNotIn("coverage", payload)
        self.assertEqual(103, payload["_meta"]["row_count"])
        self.assertEqual(103, len(payload["result"]))
        self.assertEqual(101, sum(row["Catalog"] == "ProductList" for row in payload["result"]))
        self.assertEqual(
            {"status", "message", "result", "_meta"},
            set(payload),
        )
        self.assertEqual([], generated)

    def test_filter_catalog_ignores_page_semantics_and_returns_complete_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(
                root,
                "GetFilterInfoForCostAnalysis",
                "2026-07-01",
                0,
                filter_info_response(
                    {"ProductList": [{"ProductCode": "ECS", "ProductName": "云服务器"}]}
                ),
            )
            code, stdout, stderr = self._run(
                [
                    "--action", "GetFilterInfoForCostAnalysis",
                    "--body", '{"TimeGranularity":0,"BeginTimeStr":"2026-07-01","EndTimeStr":"2026-07-01"}',
                    "--pagination", "page",
                    "--page-size", "1",
                    "--page-offset", "100",
                    "--fixture-dir", str(root),
                ]
            )
        self.assertEqual((0, ""), (code, stderr))
        payload = json.loads(stdout)
        self.assertEqual("success", payload["status"])
        self.assertNotIn("coverage", payload)
        self.assertEqual("ECS", payload["result"][0]["ProductCode"])
        self.assertTrue(payload["_meta"]["warnings"])

    def test_category_overview_ignores_full_pagination_args(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ListBillOverviewByCategory.json").write_text(
                json.dumps(
                    {
                        "ResponseMetadata": {"Error": None},
                        "Result": {
                            "List": [
                                {
                                    "PayerID": 1,
                                    "OwnerID": 2,
                                    "List": [
                                        {
                                            "BillCategoryParent": "consume",
                                            "PayableAmount": "10",
                                            "Currency": "CNY",
                                        }
                                    ],
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            output = root / "category.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBillOverviewByCategory",
                    "--body", '{"BillPeriod":"2026-07"}',
                    "--pagination", "full",
                    "--page-size", "1",
                    "--page-offset", "50",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
            metadata = json.loads((root / "category.meta.json").read_text(encoding="utf-8"))
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("success", payload["status"])
        self.assertNotIn("coverage", payload)
        self.assertEqual(1, metadata["coverage"]["pages_fetched"])
        self.assertTrue(metadata["coverage"]["is_complete"])
        self.assertTrue(metadata["warnings"])

    def test_filter_catalog_can_be_explicitly_exported_to_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(
                root,
                "GetFilterInfoForCostAnalysis",
                "2026-07-01",
                0,
                filter_info_response({"ProductList": [{"ProductCode": "ECS", "ProductName": "云服务器"}]}),
            )
            output = root / "filters.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "GetFilterInfoForCostAnalysis",
                    "--body", '{"TimeGranularity":0,"BeginTimeStr":"2026-07-01","EndTimeStr":"2026-07-01"}',
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            with output.open(encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("success", json.loads(stdout)["status"])
        self.assertEqual("ECS", rows[0]["ProductCode"])

    def test_cost_analysis_total_counts_groups_not_flattened_rows(self) -> None:
        response = cost_analysis_response(
            [
                {
                    "ClassifyDimension": 3,
                    "ClassifyItem": "ECS",
                    "Costs": [
                        {"TimeStr": "2026-06", "Amount": "1"},
                        {"TimeStr": "2026-07", "Amount": "2"},
                    ],
                }
            ],
            total=1,
            limit=300,
            offset=0,
        )
        result = collect_query(
            client=SequenceClient([response]),
            action="ListCostAnalysisOpenApi",
            query_id="analysis",
            base_body={
                "CostType": 2,
                "TimeGranularity": 0,
                "BeginTimeStr": "2026-06-01",
                "EndTimeStr": "2026-07-01",
                "ClassifyDimension": 3,
            },
            config=FetchConfig(page_size=300),
            sleeper=lambda _: None,
        )
        self.assertTrue(result.is_complete)
        self.assertEqual(1, result.items_collected)
        self.assertEqual(2, len(result.rows))

    def test_cost_analysis_inline_preserves_summary_warning_and_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cost_data = [
                {
                    "ClassifyDimension": 3,
                    "ClassifyItem": "总费用",
                    "Costs": [{"TimeStr": "2026-07", "Amount": "10.00"}],
                },
                {
                    "ClassifyDimension": 3,
                    "ClassifyItem": "ECS",
                    "Costs": [{"TimeStr": "2026-07", "Amount": "6.00"}],
                },
            ]
            write_fixture(
                root,
                "ListCostAnalysisOpenApi",
                "2026-07-01",
                0,
                cost_analysis_response(cost_data, total=1, limit=300, offset=0),
            )
            code, stdout, stderr = self._run(
                [
                    "--action", "ListCostAnalysisOpenApi",
                    "--body", json.dumps(
                        {
                            "CostType": 2,
                            "TimeGranularity": 0,
                            "BeginTimeStr": "2026-07-01",
                            "EndTimeStr": "2026-07-01",
                            "ClassifyDimension": 3,
                        },
                        ensure_ascii=False,
                    ),
                    "--pagination", "full",
                    "--fixture-dir", str(root),
                ]
            )
            payload = json.loads(stdout)
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual("success", payload["status"])
        self.assertEqual(1, payload["_meta"]["row_count"])
        self.assertEqual(["ECS"], [row["ClassifyItem"] for row in payload["result"]])
        self.assertEqual(["CNY"], [row["Currency"] for row in payload["result"]])
        summary = payload["_meta"]["analysis_summary"]
        self.assertEqual(1, summary["row_count"])
        self.assertEqual(["总费用"], [row["ClassifyItem"] for row in summary["rows"]])
        self.assertEqual(["CNY"], [row["Currency"] for row in summary["rows"]])

    def test_cost_analysis_repeated_total_rows_are_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(
                root,
                "ListCostAnalysisOpenApi",
                "2026-07-01",
                0,
                cost_analysis_response(
                    [
                        {
                            "ClassifyDimension": 3,
                            "ClassifyItem": "总费用",
                            "Costs": [{"TimeStr": "2026-07", "Amount": "30"}],
                        },
                        {
                            "ClassifyDimension": 3,
                            "ClassifyItem": "ECS",
                            "Costs": [{"TimeStr": "2026-07", "Amount": "10"}],
                        },
                    ],
                    total=2,
                    limit=1,
                    offset=0,
                ),
            )
            write_fixture(
                root,
                "ListCostAnalysisOpenApi",
                "2026-07-01",
                1,
                cost_analysis_response(
                    [
                        {
                            "ClassifyDimension": 3,
                            "ClassifyItem": "总费用",
                            "Costs": [{"TimeStr": "2026-07", "Amount": "30"}],
                        },
                        {
                            "ClassifyDimension": 3,
                            "ClassifyItem": "TOS",
                            "Costs": [{"TimeStr": "2026-07", "Amount": "20"}],
                        },
                    ],
                    total=2,
                    limit=1,
                    offset=1,
                ),
            )
            output = root / "analysis.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListCostAnalysisOpenApi",
                    "--body", '{"CostType":2,"TimeGranularity":0,"BeginTimeStr":"2026-07-01","EndTimeStr":"2026-07-01","ClassifyDimension":3}',
                    "--pagination", "full",
                    "--page-size", "1",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
            metadata = json.loads((root / "analysis.meta.json").read_text(encoding="utf-8"))
            fields = json.loads((root / "analysis.fields.json").read_text(encoding="utf-8"))
            with output.open(encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("success", payload["status"])
        self.assertEqual(2, payload["_meta"]["row_count"])
        self.assertEqual(["ECS", "TOS"], [row["ClassifyItem"] for row in rows])
        self.assertEqual(["CNY", "CNY"], [row["Currency"] for row in rows])
        self.assertEqual(2, metadata["coverage"]["expected_total"])
        self.assertEqual(2, metadata["coverage"]["queries"][0]["items_collected"])
        self.assertEqual(1, metadata["analysis_summary"]["row_count"])
        self.assertEqual("总费用", metadata["analysis_summary"]["rows"][0]["ClassifyItem"])
        amount = next(item for item in fields["fields"] if item["field"] == "Amount")
        currency = next(item for item in fields["fields"] if item["field"] == "Currency")
        self.assertEqual("Currency", amount["currency_field"])
        self.assertEqual("derived_contract_default", currency["source"])
        self.assertFalse(currency["original_response_field"])
        self.assertEqual(
            [
                {
                    "field": "Currency",
                    "value": "CNY",
                    "source": "derived_contract_default",
                    "original_response_field": False,
                    "note": "ListCostAnalysisOpenApi 不返回币种；按该接口固定 CNY 口径补充。",
                }
            ],
            metadata["derived_fields"],
        )

    def test_empty_cost_analysis_result_does_not_claim_derived_currency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(
                root,
                "ListCostAnalysisOpenApi",
                "2026-07-01",
                0,
                cost_analysis_response([], total=0, limit=300, offset=0),
            )
            output = root / "analysis.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListCostAnalysisOpenApi",
                    "--body", '{"CostType":2,"TimeGranularity":0,"BeginTimeStr":"2026-07-01","EndTimeStr":"2026-07-01","ClassifyDimension":3}',
                    "--pagination", "full",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
            metadata = json.loads((root / "analysis.meta.json").read_text(encoding="utf-8"))
            fields = json.loads((root / "analysis.fields.json").read_text(encoding="utf-8"))
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("success", payload["status"])
        self.assertEqual(["_action", "_query_id"], metadata["columns"])
        self.assertEqual([], metadata["derived_fields"])
        self.assertFalse(any(item["field"] == "Currency" for item in fields["fields"]))

    def test_cost_analysis_fields_catalog_explains_contextual_amount(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(
                root,
                "ListCostAnalysisOpenApi",
                "2026-07-01",
                0,
                cost_analysis_response(
                    [
                        {
                            "ClassifyDimension": 3,
                            "ClassifyItem": "ECS",
                            "Costs": [{"TimeStr": "2026-07", "Amount": "10.00"}],
                        }
                    ],
                    total=1,
                    limit=300,
                    offset=0,
                ),
            )
            output = root / "analysis.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListCostAnalysisOpenApi",
                    "--body", '{"CostType":2,"TimeGranularity":0,"BeginTimeStr":"2026-07-01","EndTimeStr":"2026-07-01","ClassifyDimension":3}',
                    "--pagination", "full",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            fields = json.loads((root / "analysis.fields.json").read_text(encoding="utf-8"))
            metadata = json.loads((root / "analysis.meta.json").read_text(encoding="utf-8"))
        self.assertEqual((0, ""), (code, stderr))
        amount = next(item for item in fields["fields"] if item["field"] == "Amount")
        self.assertEqual("metric", amount["role"])
        self.assertEqual("decimal", amount["type"])
        self.assertEqual("Currency", amount["currency_field"])

    def test_empty_complete_result_still_writes_header_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root, "ListBill", "2026-07", 0, bill_response([], total=0, limit=2, offset=0))
            output = root / "empty.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBill",
                    "--body", '{"BillPeriod":"2026-07"}',
                    "--pagination", "full",
                    "--page-size", "2",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            exists = output.is_file()
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual("success", json.loads(stdout)["status"])
        self.assertTrue(exists)

    def test_page_mode_fetches_exactly_one_page_without_claiming_full_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(
                root,
                "ListBill",
                "2026-07",
                2,
                bill_response([bill_row(3), bill_row(4)], total=8, limit=2, offset=2),
            )
            output = root / "page.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBill",
                    "--body", '{"BillPeriod":"2026-07"}',
                    "--pagination", "page",
                    "--page-offset", "2",
                    "--page-size", "2",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
            metadata = json.loads((root / "page.meta.json").read_text())
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual("success", payload["status"])
        self.assertNotIn("coverage", payload)
        self.assertEqual("page", metadata["coverage"]["requested_scope"])
        self.assertTrue(metadata["coverage"]["requested_scope_fulfilled"])
        self.assertFalse(metadata["coverage"]["is_complete"])
        self.assertEqual([], metadata["coverage"]["failed_queries"])
        self.assertEqual(2, metadata["queries"][0]["request_body"]["Offset"])

    def test_warning_is_exposed_in_manifest_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(
                root,
                "ListBillDetail",
                "2026-07",
                0,
                detail_response([], total=0, limit=2, offset=0, warning="tag filter degraded"),
            )
            output = root / "detail.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBillDetail",
                    "--body", '{"BillPeriod":"2026-07"}',
                    "--pagination", "full",
                    "--page-size", "2",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            payload = json.loads(stdout)
            metadata = json.loads((root / "detail.meta.json").read_text())
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertTrue(metadata["warnings"])

    def test_required_split_identifier_rejects_aggregate_grain_before_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "split.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListSplitBillDetail",
                    "--body", '{"BillPeriod":"2026-07"}',
                    "--require-field", "SplitItemID",
                    "--pagination", "full",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            error = envelope_error(json.loads(stdout))
        self.assertEqual(2, code)
        self.assertEqual("", stderr)
        self.assertEqual("RESPONSE_FIELD_NOT_PRESERVED", error["code"])
        self.assertEqual({"GroupPeriod": 2}, error["details"]["required_request"])
        self.assertEqual({"GroupPeriod": 0}, error["details"]["actual_request"])
        self.assertFalse(output.exists())

    def test_bill_detail_usage_and_price_fields_only_allow_item_dimensions(self) -> None:
        available = output_field_names("ListBillDetail")
        for field in ("Count", "Price", "PriceUnit"):
            for group_period in (0, 1, 2):
                with self.subTest(field=field, group_period=group_period, group_term=0):
                    self.assertEqual(
                        (field,),
                        validate_required_response_fields(
                            "ListBillDetail",
                            {"GroupPeriod": group_period, "GroupTerm": 0},
                            [field],
                            available,
                        ),
                    )
            for group_term in (1, 2, 3):
                with self.subTest(field=field, group_period=2, group_term=group_term):
                    with self.assertRaises(BillingQueryError) as context:
                        validate_required_response_fields(
                            "ListBillDetail",
                            {"GroupPeriod": 2, "GroupTerm": group_term},
                            [field],
                            available,
                        )
                    self.assertEqual(ErrorCode.RESPONSE_FIELD_NOT_PRESERVED, context.exception.code)
                    self.assertEqual({"GroupTerm": 0}, context.exception.details["required_request"])

    def test_bill_detail_ids_only_allow_item_detail(self) -> None:
        available = output_field_names("ListBillDetail")
        for field in ("BillID", "BillDetailId"):
            with self.subTest(field=field, valid=True):
                self.assertEqual(
                    (field,),
                    validate_required_response_fields(
                        "ListBillDetail",
                        {"GroupPeriod": 2, "GroupTerm": 0},
                        [field],
                        available,
                    ),
                )
            for body in (
                {"GroupPeriod": 0, "GroupTerm": 0},
                {"GroupPeriod": 2, "GroupTerm": 1},
            ):
                with self.subTest(field=field, body=body):
                    with self.assertRaises(BillingQueryError) as context:
                        validate_required_response_fields(
                            "ListBillDetail", body, [field], available
                        )
                    self.assertEqual(
                        {"GroupPeriod": 2, "GroupTerm": 0},
                        context.exception.details["required_request"],
                    )

    def test_bill_detail_instance_number_is_not_preserved_by_product_or_account(self) -> None:
        available = output_field_names("ListBillDetail")
        for group_term in (0, 1):
            with self.subTest(group_term=group_term, available=True):
                self.assertEqual(
                    ("InstanceNo",),
                    validate_required_response_fields(
                        "ListBillDetail",
                        {"GroupPeriod": 0, "GroupTerm": group_term},
                        ["InstanceNo"],
                        available,
                    ),
                )
        for group_term in (2, 3):
            with self.subTest(group_term=group_term, available=False):
                with self.assertRaises(BillingQueryError) as context:
                    validate_required_response_fields(
                        "ListBillDetail",
                        {"GroupPeriod": 0, "GroupTerm": group_term},
                        ["InstanceNo"],
                        available,
                    )
                self.assertEqual(ErrorCode.RESPONSE_FIELD_NOT_PRESERVED, context.exception.code)
                self.assertEqual({"GroupTerm": 0}, context.exception.details["required_request"])

    def test_require_count_rejects_instance_detail_before_client_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "detail.csv"
            with mock.patch("query_billing.FixtureBillingClient") as client_class:
                code, stdout, stderr = self._run(
                    [
                        "--action", "ListBillDetail",
                        "--body", '{"BillPeriod":"2026-07","GroupPeriod":2,"GroupTerm":1}',
                        "--require-field", "Count",
                        "--pagination", "full",
                        "--fixture-dir", str(root),
                        "--out", str(output),
                    ]
                )
            error = envelope_error(json.loads(stdout))
        self.assertEqual(2, code)
        self.assertEqual("", stderr)
        self.assertEqual("RESPONSE_FIELD_NOT_PRESERVED", error["code"])
        self.assertEqual({"GroupTerm": 0}, error["details"]["required_request"])
        client_class.assert_not_called()
        self.assertFalse(output.exists())

    def test_required_split_identifier_detail_grain_is_recorded_in_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = {
                "BillDetailId": "detail-1",
                "SplitBillDetailId": "split-detail-1",
                "SplitItemID": "split-item-1",
                "PayableAmount": "1",
                "Currency": "CNY",
            }
            write_fixture(
                root,
                "ListSplitBillDetail",
                "2026-07",
                0,
                detail_response([row], total=1, limit=300, offset=0),
            )
            output = root / "split.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListSplitBillDetail",
                    "--body", '{"BillPeriod":"2026-07","GroupPeriod":2}',
                    "--require-field", "SplitItemID",
                    "--pagination", "full",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            metadata = json.loads((root / "split.meta.json").read_text())
            fields = json.loads((root / "split.fields.json").read_text())
        self.assertEqual(0, code, stderr)
        self.assertEqual("success", json.loads(stdout)["status"])
        self.assertEqual(["SplitItemID"], metadata["required_response_fields"])
        split_item = next(item for item in fields["fields"] if item["field"] == "SplitItemID")
        self.assertEqual("available", split_item["grain_availability"]["status"])

    def test_aggregate_split_empty_identifier_is_marked_not_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = {"SplitItemID": "", "PayableAmount": "1", "Currency": "CNY"}
            write_fixture(
                root,
                "ListSplitBillDetail",
                "2026-07",
                0,
                detail_response([row], total=1, limit=300, offset=0),
            )
            output = root / "split.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListSplitBillDetail",
                    "--body", '{"BillPeriod":"2026-07"}',
                    "--pagination", "full",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            manifest = json.loads(stdout)
            metadata = json.loads((root / "split.meta.json").read_text())
            fields = json.loads((root / "split.fields.json").read_text())
        self.assertEqual(0, code, stderr)
        split_item = next(item for item in fields["fields"] if item["field"] == "SplitItemID")
        self.assertEqual("not_preserved", split_item["grain_availability"]["status"])

    def test_new_response_fields_are_silently_preserved_in_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = {
                "BillID": "bill-1",
                "BillDetailId": "detail-1",
                "PayableAmount": "1.00",
                "Currency": "CNY",
                "SpPromisePurchaseTime": "12",
                "SpPromisePurchaseTimeUnit": "Month",
            }
            payload = detail_response([row], total=1, limit=2, offset=0)
            payload["Result"]["NewTopLevelField"] = "future-value"
            write_fixture(root, "ListBillDetail", "2026-07", 0, payload)
            output = root / "detail.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBillDetail",
                    "--body", '{"BillPeriod":"2026-07"}',
                    "--pagination", "full",
                    "--page-size", "2",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            manifest = json.loads(stdout)
            metadata = json.loads((root / "detail.meta.json").read_text())
            fields = json.loads((root / "detail.fields.json").read_text())
            with output.open(encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual("success", manifest["status"])
        self.assertEqual("12", rows[0]["SpPromisePurchaseTime"])
        self.assertEqual("Month", rows[0]["SpPromisePurchaseTimeUnit"])
        self.assertEqual([], manifest["_meta"].get("warnings") or [])
        self.assertNotIn("unknown_fields", metadata)
        unknown = {item["field"]: item for item in fields["fields"] if not item["contract_known"]}
        self.assertEqual({"SpPromisePurchaseTime", "SpPromisePurchaseTimeUnit"}, set(unknown))
        self.assertTrue(all(item["role"] == "unknown" for item in unknown.values()))
        self.assertEqual(2, fields["unknown_field_count"])

    def test_reconciliation_fields_are_removed_from_csv_inline_rows_and_fields(self) -> None:
        restricted_row = {
            "BillID": "bill-1",
            "BillDetailId": "detail-1",
            "PayableAmount": "10.00",
            "PaidAmount": "8.00",
            "UnpaidAmount": "2.00",
            "CreditCarriedAmount": "1.00",
            "Currency": "CNY",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(
                root,
                "ListBillDetail",
                "2026-07",
                0,
                detail_response([restricted_row], total=1, limit=1, offset=0),
            )
            csv_output = root / "detail.csv"
            csv_code, csv_stdout, csv_stderr = self._run(
                [
                    "--action", "ListBillDetail",
                    "--body", '{"BillPeriod":"2026-07"}',
                    "--pagination", "full",
                    "--page-size", "1",
                    "--fixture-dir", str(root),
                    "--out", str(csv_output),
                ]
            )
            with csv_output.open(encoding="utf-8") as file:
                csv_rows = list(csv.DictReader(file))
            fields = json.loads((root / "detail.fields.json").read_text(encoding="utf-8"))

            inline_code, inline_stdout, inline_stderr = self._run(
                [
                    "--action", "ListBillDetail",
                    "--body", '{"BillPeriod":"2026-07"}',
                    "--pagination", "full",
                    "--page-size", "1",
                    "--fixture-dir", str(root),
                ]
            )
            inline_rows = json.loads(inline_stdout)["result"]
        self.assertEqual((0, ""), (csv_code, csv_stderr))
        self.assertEqual((0, ""), (inline_code, inline_stderr))
        blocked = {"PaidAmount", "UnpaidAmount", "CreditCarriedAmount"}
        self.assertTrue(blocked.isdisjoint(csv_rows[0]))
        self.assertTrue(blocked.isdisjoint(inline_rows[0]))
        self.assertTrue(blocked.isdisjoint({item["field"] for item in fields["fields"]}))
        self.assertTrue(blocked.isdisjoint(fields["unknown_fields"]))
        self.assertEqual([], json.loads(csv_stdout)["_meta"].get("warnings") or [])

    def test_list_bill_keeps_reconciliation_fields(self) -> None:
        result = collect_query(
            client=SequenceClient(
                [
                    bill_response(
                        [
                            {
                                **bill_row(1),
                                "PaidAmount": "8.00",
                                "UnpaidAmount": "2.00",
                                "CreditCarriedAmount": "1.00",
                            }
                        ],
                        total=1,
                        limit=1,
                        offset=0,
                    )
                ]
            ),
            action="ListBill",
            query_id="2026-07",
            base_body={"BillPeriod": "2026-07"},
            config=FetchConfig(page_size=1),
            sleeper=lambda _: None,
        )
        self.assertEqual(
            {"PaidAmount", "UnpaidAmount", "CreditCarriedAmount"},
            {key for key in result.rows[0] if key in {"PaidAmount", "UnpaidAmount", "CreditCarriedAmount"}},
        )

    def test_bill_overview_actions_keep_reconciliation_fields(self) -> None:
        fields = {
            "PaidAmount": "8.00",
            "UnpaidAmount": "2.00",
            "CreditCarriedAmount": "1.00",
        }
        prod_result = collect_query(
            client=SequenceClient(
                [
                    {
                        "ResponseMetadata": {"Error": None},
                        "Result": {
                            "List": [{"Product": "ECS", "PayableAmount": "10.00", **fields}],
                            "Total": 1,
                            "Limit": 1,
                            "Offset": 0,
                        },
                    }
                ]
            ),
            action="ListBillOverviewByProd",
            query_id="2026-07",
            base_body={"BillPeriod": "2026-07"},
            config=FetchConfig(page_size=1),
            sleeper=lambda _: None,
        )
        category_result = collect_query(
            client=SequenceClient(
                [
                    {
                        "ResponseMetadata": {"Error": None},
                        "Result": {
                            "List": [{"List": [{"BillCategoryParent": "消费", "PayableAmount": "10.00", **fields}]}]
                        },
                    }
                ]
            ),
            action="ListBillOverviewByCategory",
            query_id="2026-07",
            base_body={"BillPeriod": "2026-07"},
            config=FetchConfig(page_size=1),
            sleeper=lambda _: None,
        )
        for action, result in (
            ("ListBillOverviewByProd", prod_result),
            ("ListBillOverviewByCategory", category_result),
        ):
            with self.subTest(action=action):
                self.assertEqual(fields, {key: result.rows[0][key] for key in fields})

    def test_amortized_paid_field_family_is_removed_at_runtime(self) -> None:
        response = {
            "ResponseMetadata": {"Error": None},
            "Result": {
                "Warning": "",
                "List": [
                    {
                        "AmortizedMonth": "2026-07",
                        "PayableAmount": "10.00",
                        "PaidAmount": "8.00",
                        "DailyAmortizedPaidAmount": "1.00",
                        "BeforeAmortizedPaidAmount": "2.00",
                        "NowAmortizedPaidAmount": "3.00",
                        "UnamortizedPaidAmount": "4.00",
                        "Currency": "CNY",
                    }
                ],
                "Total": 1,
                "Limit": 1,
                "Offset": 0,
            },
        }
        result = collect_query(
            client=SequenceClient([response]),
            action="ListAmortizedCostBillMonthly",
            query_id="2026-07",
            base_body={"AmortizedMonth": "2026-07"},
            config=FetchConfig(page_size=1),
            sleeper=lambda _: None,
        )
        self.assertEqual("10.00", result.rows[0]["PayableAmount"])
        self.assertFalse(any(key.endswith("PaidAmount") for key in result.rows[0]))

    def test_known_response_field_type_error_is_still_rejected(self) -> None:
        result = collect_query(
            client=SequenceClient(
                [
                    {
                        "ResponseMetadata": {"Error": None},
                        "Result": {
                            "List": [],
                            "Total": "1",
                            "Limit": 2,
                            "Offset": 0,
                        },
                    }
                ]
            ),
            action="ListBill",
            query_id="2026-07",
            base_body={"BillPeriod": "2026-07"},
            config=FetchConfig(page_size=2),
            sleeper=lambda _: None,
        )
        self.assertFalse(result.is_complete)
        self.assertEqual("RESPONSE_INVALID", result.error["code"])

    def test_ve_client_accepts_warning_line_before_json_stdout(self) -> None:
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "open <ve-config-path>: operation not permitted\n"
                    + json.dumps(bill_response([bill_row(1)], total=1, limit=300, offset=0))
                ),
                stderr="",
            )

        client = VeBillingClient(
            region="cn-north-1",
            profile="default",
            timeout_seconds=1,
            executable=sys.executable,
            runner=runner,
        )
        response = client.query("ListBill", {"BillPeriod": "2026-07", "Limit": 300})
        self.assertEqual("bill-1", response["Result"]["List"][0]["BillID"])
        self.assertIn("---region", calls[0])
        self.assertIn("---profile", calls[0])
        self.assertNotIn("--region", calls[0])
        self.assertNotIn("--profile", calls[0])

    def test_ve_client_rejects_success_stdout_without_json_object(self) -> None:
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="open <ve-config-path>: operation not permitted\n",
                stderr="",
            )

        client = VeBillingClient(
            region="cn-north-1",
            profile=None,
            timeout_seconds=1,
            executable=sys.executable,
            runner=runner,
        )
        with self.assertRaises(BillingQueryError) as context:
            client.query("ListBill", {"BillPeriod": "2026-07", "Limit": 300})
        self.assertEqual(ErrorCode.RESPONSE_INVALID, context.exception.code)

    def test_ve_client_preserves_redacted_native_auth_error(self) -> None:
        native_stderr = (
            "failed to refresh session token. Please run 've login' to re-authenticate. "
            "refresh_token=super-secret [status 400, requestId: 20260820120031D86EDDA69272BCA74D53]"
        )

        def runner(command, **kwargs):
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr=native_stderr,
            )

        client = VeBillingClient(
            region="cn-north-1",
            profile=None,
            timeout_seconds=1,
            executable=sys.executable,
            runner=runner,
        )
        with self.assertRaises(BillingQueryError) as context:
            client.query("ListBill", {"BillPeriod": "2026-07", "Limit": 300})
        error = context.exception.error_dict()
        self.assertEqual("AUTHENTICATION_FAILED", error["code"])
        self.assertEqual(1, error["cause"]["returncode"])
        self.assertEqual("20260820120031D86EDDA69272BCA74D53", error["cause"]["request_id"])
        self.assertNotIn("super-secret", json.dumps(error))

    def test_ve_client_preserves_remote_json_error_and_request_id(self) -> None:
        response = {
            "ResponseMetadata": {
                "RequestId": "remote-request-id-1234",
                "Error": {
                    "Code": "AccessDenied",
                    "Message": "permission denied",
                },
            }
        }

        def runner(command, **kwargs):
            return subprocess.CompletedProcess(
                command,
                1,
                stdout=json.dumps(response),
                stderr="ve native diagnostic",
            )

        client = VeBillingClient(
            region="cn-north-1",
            profile=None,
            timeout_seconds=1,
            executable=sys.executable,
            runner=runner,
        )
        with self.assertRaises(BillingQueryError) as context:
            client.query("ListBill", {"BillPeriod": "2026-07", "Limit": 300})
        error = context.exception.error_dict()
        self.assertEqual("PERMISSION_DENIED", error["code"])
        self.assertEqual("AccessDenied", error["cause"]["remote_code"])
        self.assertEqual("permission denied", error["cause"]["remote_message"])
        self.assertEqual("remote-request-id-1234", error["cause"]["request_id"])

    def test_ve_native_error_redacts_json_secrets_and_reports_truncation(self) -> None:
        native_stderr = (
            '{"refresh_token":"json-secret","authorization":"Bearer bearer-secret"}'
            + "x" * 5000
        )

        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, stdout="", stderr=native_stderr)

        client = VeBillingClient(
            region="cn-north-1",
            profile=None,
            timeout_seconds=1,
            executable=sys.executable,
            runner=runner,
        )
        with self.assertRaises(BillingQueryError) as context:
            client.query("ListBill", {"BillPeriod": "2026-07", "Limit": 300})
        cause = context.exception.error_dict()["cause"]
        self.assertNotIn("json-secret", cause["raw_stderr"])
        self.assertNotIn("bearer-secret", cause["raw_stderr"])
        self.assertTrue(cause["raw_stderr_truncated"])
        self.assertGreater(cause["raw_stderr_original_length"], len(cause["raw_stderr"]))

    def test_body_pagination_fields_drive_page_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(
                root,
                "ListBill",
                "2026-07",
                4,
                bill_response([bill_row(5), bill_row(6)], total=10, limit=2, offset=4),
            )
            output = root / "page.csv"
            code, stdout, stderr = self._run(
                [
                    "--action", "ListBill",
                    "--body", '{"BillPeriod":"2026-07","Limit":2,"Offset":4,"NeedRecordNum":0}',
                    "--pagination", "page",
                    "--fixture-dir", str(root),
                    "--out", str(output),
                ]
            )
            metadata = json.loads((root / "page.meta.json").read_text())
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual("success", json.loads(stdout)["status"])
        body = metadata["queries"][0]["request_body"]
        self.assertEqual(2, body["Limit"])
        self.assertEqual(4, body["Offset"])
        self.assertEqual(0, body["NeedRecordNum"])

    def test_body_and_cli_pagination_conflict_is_rejected(self) -> None:
        code, stdout, stderr = self._run(
            [
                "--action", "ListBill",
                "--body", '{"BillPeriod":"2026-07","Limit":2,"Offset":4}',
                "--pagination", "page",
                "--page-size", "3",
                "--page-offset", "4",
                "--out", "unused.csv",
            ]
        )
        self.assertEqual(2, code)
        self.assertEqual("", stderr)
        self.assertEqual("INVALID_ARGUMENT", envelope_error(json.loads(stdout))["code"])

    def test_full_mode_rejects_nonzero_offset_and_need_record_num_zero(self) -> None:
        cases = (
            '{"BillPeriod":"2026-07","Offset":1}',
            '{"BillPeriod":"2026-07","NeedRecordNum":0}',
        )
        for body in cases:
            with self.subTest(body=body):
                code, stdout, stderr = self._run(
                    [
                        "--action", "ListBill",
                        "--body", body,
                        "--pagination", "full",
                        "--out", "unused.csv",
                    ]
                )
                self.assertEqual(2, code)
                self.assertEqual("", stderr)
                message = json.loads(stdout)["message"]
                self.assertTrue("Offset" in message or "NeedRecordNum" in message)

    def test_query_contract_is_machine_readable_and_sectioned(self) -> None:
        contract = describe_query()
        self.assertNotIn("contract_schema_version", contract)
        self.assertNotIn("tool", contract)
        self.assertNotIn("tool_version", contract)
        self.assertEqual(list(CONTRACT_SECTIONS), [key for key in contract if key in CONTRACT_SECTIONS])
        self.assertTrue(contract["summary"]["read_only"])
        self.assertEqual(
            "python3 scripts/cost.py schema --action <Action> --section request --include-guidance",
            contract["summary"]["action_contract_command"],
        )
        self.assertEqual(
            "cost.py schema --action <Action> --section request --include-guidance",
            contract["input"]["body_contract_source"],
        )
        self.assertFalse(contract["pagination"]["page"]["complete_dataset_claim"])
        self.assertEqual("coverage.is_complete=true", contract["pagination"]["full"]["success_condition"])
        dynamic_stop = contract["pagination"]["full"]["dynamic_period_stop"]
        self.assertEqual(["total_changed", "rows_exceeded_first_total"], dynamic_stop["triggers"])
        self.assertFalse(dynamic_stop["continue_after_trigger"])
        snapshot_condition = contract["pagination"]["full"]["current_period_snapshot_condition"]
        self.assertTrue(snapshot_condition["current_period"])
        self.assertTrue(snapshot_condition["initial_total_boundary_reached"])
        snapshot_claim = contract["pagination"]["full"]["current_period_snapshot_claim"]
        self.assertTrue(snapshot_claim["analysis_allowed"])
        self.assertFalse(snapshot_claim["final_period_claim_allowed"])
        self.assertEqual(["RATE_LIMITED", "TIMEOUT"], contract["retry"]["retryable_errors"])
        self.assertIn("invalid_parameters", contract["retry"]["parameter_error_observation"])
        self.assertNotIn("plan_invariants", contract["retry"])
        self.assertNotIn("repair_policy", contract["retry"])
        self.assertNotIn("local_error_policy", contract["retry"])
        json.dumps(contract, ensure_ascii=False)

        section = describe_query("pagination")
        self.assertEqual("pagination", section["section"])
        self.assertNotIn("retry", section)

    def test_query_contract_arguments_match_cli_parser(self) -> None:
        parser_arguments = {
            option
            for action in build_parser()._actions
            for option in action.option_strings
            if option not in {"-h", "--help"}
        }
        parser_arguments.discard("--compact")
        contract_arguments = {item["name"] for item in describe_query("input")["input"]["arguments"]}
        self.assertEqual(parser_arguments, contract_arguments)
        output = describe_query("output")["output"]
        self.assertEqual(["status", "message", "result"], output["public_fields"])
        self.assertEqual("_meta", output["machine_field"])
        self.assertIn("file、metadata、fields", output["result"]["file"])
        self.assertEqual(["explicit_out", "stdout_envelope_over_64_kib"], output["data_artifact"]["written_when"])
        self.assertEqual("csv", output["data_artifact"]["format"])
        self.assertEqual(["status", "message", "result", "_meta"], output["stdout"]["required_fields"])
        self.assertIn("result 中直接返回 file、metadata、fields", output["stdout"]["detailed_evidence"])
        self.assertNotIn("artifact_reuse_policy", output)
        success = output["statuses"]["success"]
        self.assertEqual(0, success["exit_code"])
        collision_policy = output["output_collision_policy"]
        self.assertEqual(["primary", "metadata", "fields"], collision_policy["preflight_targets"])
        self.assertFalse(collision_policy["remote_call_attempted"])
        self.assertEqual(
            ["choose_new_output_path", "retry_with_overwrite"],
            collision_policy["recovery_actions"],
        )
        self.assertTrue(collision_policy["overwrite_requires_task_ownership"])
        self.assertFalse(collision_policy["overwrite_default_retry"])
        self.assertFalse(collision_policy["replan_required"])
        self.assertFalse(collision_policy["query_expansion_allowed"])

    def test_query_describe_does_not_require_execution_arguments(self) -> None:
        code, stdout, stderr = self._run(["describe", "--section", "examples"])
        payload = json.loads(stdout)
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual("examples", payload["section"])
        self.assertEqual("single_page", payload["examples"][0]["id"])

    def test_non_positive_timeout_is_rejected_before_query(self) -> None:
        code, stdout, stderr = self._run(
            [
                "--action", "ListBill",
                "--body", '{"BillPeriod":"2026-07"}',
                "--pagination", "page",
                "--timeout", "0",
                "--out", "unused.csv",
            ]
        )
        self.assertEqual(2, code)
        self.assertEqual("", stderr)
        self.assertEqual("INVALID_ARGUMENT", envelope_error(json.loads(stdout))["code"])


if __name__ == "__main__":
    unittest.main()
