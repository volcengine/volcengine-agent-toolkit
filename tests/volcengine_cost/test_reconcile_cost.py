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
sys.path.insert(0, str(SCRIPTS))

from cost_query.reconciliation.contract import describe_reconciliation  # noqa: E402
from reconcile_cost import main  # noqa: E402


def write_query_artifact(
    root: Path,
    name: str,
    action: str,
    columns: list[str],
    rows: list[dict[str, str]],
    *,
    body: dict[str, object] | None = None,
    complete: bool = True,
    partial_period: bool = False,
    provisional: bool = False,
) -> Path:
    csv_path = root / f"{name}.csv"
    fields_path = root / f"{name}.fields.json"
    metadata_path = root / f"{name}.meta.json"
    all_columns = ["_action", "_query_id", *columns]
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=all_columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({"_action": action, "_query_id": "2026-07", **row})
    fields_path.write_text(
        json.dumps(
            {
                "output_protocol_version": "1.0",
                "schema_version": "1.0",
                "source_action": action,
                "source_csv": str(csv_path),
                "fields": [{"field": column} for column in all_columns],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    request_body = {"BillPeriod": "2026-07", "Limit": 300, "Offset": 0, "NeedRecordNum": 1, **(body or {})}
    provisional_query = {
        "query_id": "2026-07",
        "action": action,
        "is_complete": False,
        "is_provisional": True,
        "provisional_reason": "current_period_total_drift",
        "stop_reason": "total_changed",
        "initial_total_boundary_reached": True,
        "requested_scope": "full",
        "page_fetched": True,
        "error": None,
    }
    failed_queries = (
        []
        if complete or provisional
        else [{"query_id": "2026-07", "error": {"code": "PAGINATION_INCOMPLETE"}}]
    )
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "action": action,
                "coverage": {
                    "is_complete": complete,
                    "is_provisional": provisional,
                    "consistency": "current_period_total_drift" if provisional else "stable" if complete else "incomplete",
                    "requested_scope": "full",
                    "requested_scope_fulfilled": complete or provisional,
                    "provisional_queries": [provisional_query] if provisional else [],
                    "failed_queries": failed_queries,
                },
                "freshness": {
                    "partial_period": partial_period,
                    "notes": ["查询包含当前月，数据尚未完结。"] if partial_period else [],
                },
                "queries": [{"query_id": "2026-07", "request_body": request_body}],
                "artifacts": {
                    "csv": str(csv_path.resolve()),
                    "fields": str(fields_path.resolve()),
                    "metadata": str(metadata_path.resolve()),
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return csv_path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


class ReconcileCostTest(unittest.TestCase):
    def test_current_period_project_and_nested_drill_inherit_parent_limits(self) -> None:
        from datetime import date
        from cost import main as cost_main

        def run(arguments: list[str]) -> dict:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cost_main(arguments)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, code, payload)
            return payload

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            period = date.today().strftime("%Y-%m")
            common = {"Product": "ECS", "Currency": "CNY", "Element": "CPU"}
            left_rows = [{**common, "InstanceNo": "synthetic-one", "PayableAmount": "100"},
                         {**common, "InstanceNo": "synthetic-two", "PayableAmount": "40"}]
            right_rows = [{**common, "InstanceNo": "synthetic-one", "Project": "a", "PayableAmount": "60"},
                          {**common, "InstanceNo": "synthetic-one", "Project": "b", "PayableAmount": "40"},
                          {**common, "InstanceNo": "synthetic-two", "Project": "a", "PayableAmount": "40"}]
            sources = []
            for action, name, rows in (("ListBillDetail", "left", left_rows),
                                       ("ListSplitBillDetail", "right", right_rows)):
                (root / f"{action}.json").write_text(json.dumps({"Result": {
                    "List": rows, "Total": len(rows), "Limit": 300, "Offset": 0}}))
                body = {"BillPeriod": period, "GroupPeriod": 2}
                if action == "ListBillDetail":
                    body["GroupTerm"] = 0
                output = root / f"{name}.csv"
                run(["query", "--action", action, "--body", json.dumps(body), "--pagination", "full",
                     "--fixture-dir", str(root), "--out", str(output)])
                sources.extend([output, output.with_suffix(".meta.json"), output.with_suffix(".fields.json")])
            before = {path: path.read_bytes() for path in sources}
            parent, child, grandchild = root / "parent.csv", root / "project.csv", root / "instances.csv"
            parent_result = run(["reconcile", "run", "--left", str(root / "left.csv"),
                                 "--right", str(root / "right.csv"), "--group-by", "Product", "--out", str(parent)])
            child_result = run(["reconcile", "drill-down", "--from", str(parent), "--row", "Product=ECS",
                                "--row", "Currency=CNY", "--by", "Project", "--side", "right", "--out", str(child)])
            grandchild_result = run(["reconcile", "drill-down", "--from", str(child), "--row", "Product=ECS",
                                     "--row", "Currency=CNY", "--row", "Project=a", "--by", "InstanceNo",
                                     "--side", "right", "--out", str(grandchild)])
            parent_warnings = json.loads(parent.with_suffix(".meta.json").read_text())["warnings"]
            for path, payload in ((child, child_result), (grandchild, grandchild_result)):
                metadata = json.loads(path.with_suffix(".meta.json").read_text())
                self.assertEqual("provisional", payload["_meta"]["claim_scope"])
                self.assertEqual("provisional", metadata["claim_scope"])
                self.assertTrue(set(parent_warnings) <= set(metadata["warnings"]))
                self.assertEqual("matched", payload["_meta"]["conservation"]["status"])
                self.assertIn("当前", payload["message"])
            self.assertEqual("provisional", parent_result["_meta"]["claim_scope"])
            self.assertEqual(before, {path: path.read_bytes() for path in sources})

    def _run(self, arguments: list[str]) -> tuple[int, dict, dict]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(arguments)
        payload = json.loads(stdout.getvalue()) if stdout.getvalue() else {}
        if payload.get("status") == "error" and "_meta" in payload:
            return code, {}, payload["_meta"]
        return code, payload, json.loads(stderr.getvalue()) if stderr.getvalue() else {}

    def _detail_split(
        self,
        root: Path,
        *,
        partial_period: bool = False,
        complete: bool = True,
        provisional: bool = False,
    ) -> tuple[Path, Path]:
        columns = [
            "BillID", "BillDetailId", "Product", "InstanceNo", "Element", "Project",
            "PayableAmount", "OriginalBillAmount", "SavingPlanOriginalAmount",
            "PreferentialBillAmount", "DiscountBillAmount", "Currency",
        ]
        left = write_query_artifact(
            root,
            "bill-detail",
            "ListBillDetail",
            columns,
            [
                {"BillID": "b-1", "BillDetailId": "d-1", "Product": "ECS", "InstanceNo": "i-1", "Element": "CPU", "Project": "billing-project", "PayableAmount": "100", "OriginalBillAmount": "120", "SavingPlanOriginalAmount": "10", "PreferentialBillAmount": "10", "DiscountBillAmount": "110", "Currency": "CNY"},
                {"BillID": "b-2", "BillDetailId": "d-2", "Product": "ECS", "InstanceNo": "i-2", "Element": "MEM", "Project": "billing-project", "PayableAmount": "50", "OriginalBillAmount": "60", "SavingPlanOriginalAmount": "0", "PreferentialBillAmount": "10", "DiscountBillAmount": "50", "Currency": "CNY"},
                {"BillID": "b-3", "BillDetailId": "d-3", "Product": "TOS", "InstanceNo": "", "Element": "Storage", "Project": "billing-project", "PayableAmount": "20", "OriginalBillAmount": "20", "SavingPlanOriginalAmount": "0", "PreferentialBillAmount": "0", "DiscountBillAmount": "20", "Currency": "CNY"},
            ],
            complete=complete,
            partial_period=partial_period,
            provisional=provisional,
            body={"GroupPeriod": 2, "GroupTerm": 0},
        )
        right_columns = [*columns, "SplitBillDetailId", "SplitItemID", "Tag"]
        right = write_query_artifact(
            root,
            "split-detail",
            "ListSplitBillDetail",
            right_columns,
            [
                {"BillID": "b-1", "BillDetailId": "d-1", "SplitBillDetailId": "s-1", "SplitItemID": "item-1", "Product": "ECS", "InstanceNo": "i-1", "Element": "CPU", "Project": "project-a", "Tag": '{"department":"a"}', "PayableAmount": "60", "OriginalBillAmount": "70", "SavingPlanOriginalAmount": "5", "PreferentialBillAmount": "5", "DiscountBillAmount": "65", "Currency": "CNY"},
                {"BillID": "b-1", "BillDetailId": "d-1", "SplitBillDetailId": "s-2", "SplitItemID": "item-2", "Product": "ECS", "InstanceNo": "i-1", "Element": "CPU", "Project": "project-b", "Tag": '{"department":"b"}', "PayableAmount": "30", "OriginalBillAmount": "40", "SavingPlanOriginalAmount": "5", "PreferentialBillAmount": "5", "DiscountBillAmount": "35", "Currency": "CNY"},
                {"BillID": "b-2", "BillDetailId": "d-2", "SplitBillDetailId": "s-3", "SplitItemID": "item-3", "Product": "ECS", "InstanceNo": "i-2", "Element": "MEM", "Project": "project-a", "Tag": '{"department":"a"}', "PayableAmount": "50", "OriginalBillAmount": "60", "SavingPlanOriginalAmount": "0", "PreferentialBillAmount": "10", "DiscountBillAmount": "50", "Currency": "CNY"},
                {"BillID": "b-3", "BillDetailId": "d-3", "SplitBillDetailId": "s-4", "SplitItemID": "item-4", "Product": "TOS", "InstanceNo": "", "Element": "Storage", "Project": "", "Tag": "", "PayableAmount": "20", "OriginalBillAmount": "20", "SavingPlanOriginalAmount": "0", "PreferentialBillAmount": "0", "DiscountBillAmount": "20", "Currency": "CNY"},
            ],
            complete=complete,
            partial_period=partial_period,
            provisional=provisional,
            body={"GroupPeriod": 2},
        )
        return left, right

    def test_contract_registers_three_pairs_and_five_metrics(self) -> None:
        contract = describe_reconciliation()
        self.assertNotIn("contract_schema_version", contract)
        self.assertNotIn("tool", contract)
        self.assertNotIn("tool_version", contract)
        self.assertEqual(
            [
                "preflight",
                "left_filter_and_aggregation",
                "right_filter_and_aggregation",
                "normalized_key_uniqueness",
                "full_outer_join",
                "decimal_difference",
            ],
            contract["run"]["operations"],
        )
        self.assertEqual(3, len(contract["profiles"]["pairs"]))
        self.assertEqual("automatic_from_artifacts", contract["summary"]["pair_selection"]["mode"])
        self.assertEqual([], contract["summary"]["pair_selection"]["accepted_arguments"])
        self.assertEqual("automatic_from_artifacts", contract["profiles"]["selection"]["mode"])
        for pair in contract["profiles"]["pairs"]:
            self.assertEqual(5, len(pair["metrics"]))
            self.assertIn("description", pair)
            self.assertNotIn("relationship", pair)
        self.assertEqual("0", contract["summary"]["tolerance"])
        coverage_policy = contract["preflight"]["coverage_policy"]
        self.assertEqual("pass", coverage_policy["complete"]["check_status"])
        self.assertEqual("warn", coverage_policy["provisional"]["check_status"])
        self.assertTrue(coverage_policy["provisional"]["calculation_allowed"])
        self.assertFalse(coverage_policy["provisional"]["final_period_claim_allowed"])
        self.assertEqual("block", coverage_policy["otherwise"]["check_status"])

        preflight_arguments = {item["name"] for item in contract["preflight"]["arguments"]}
        run_arguments = {item["name"] for item in contract["run"]["arguments"]}
        drill_arguments = {item["name"] for item in contract["drill_down"]["arguments"]}
        self.assertNotIn("--relationship", preflight_arguments | run_arguments | drill_arguments)
        self.assertEqual(
            {"--left", "--left-result", "--right", "--right-result", "--left-metadata", "--right-metadata", "--group-by", "--metric", "--filter", "--mode"},
            preflight_arguments,
        )
        self.assertEqual(preflight_arguments | {"--out", "--overwrite"}, run_arguments)
        self.assertEqual(
            {"--from", "--row", "--by", "--side", "--out", "--overwrite"},
            drill_arguments,
        )

    def test_relationship_is_not_an_execution_argument(self) -> None:
        code, payload, error = self._run([
            "preflight", "--left", "left.csv", "--right", "right.csv",
            "--relationship", "bill_detail_to_split_detail",
        ])
        self.assertEqual(2, code)
        self.assertEqual({}, payload)
        self.assertEqual("INVALID_ARGUMENT", error["error"]["code"])

    def test_preflight_accepts_query_results_directly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = self._detail_split(root)
            left_result = json.dumps({
                "file": str(left.resolve()),
                "metadata": str(left.with_name(f"{left.stem}.meta.json").resolve()),
                "fields": str(left.with_name(f"{left.stem}.fields.json").resolve()),
            })
            right_result = json.dumps({
                "file": str(right.resolve()),
                "metadata": str(right.with_name(f"{right.stem}.meta.json").resolve()),
                "fields": str(right.with_name(f"{right.stem}.fields.json").resolve()),
            })
            code, payload, error = self._run([
                "preflight",
                "--left-result", left_result,
                "--right-result", right_result,
            ])
        self.assertEqual((0, {}), (code, error))
        self.assertEqual("pass", payload["verdict"])
        self.assertEqual(str(left.resolve()), payload["left"]["csv"])
        self.assertEqual(str(right.resolve()), payload["right"]["csv"])

    def test_removed_dimension_option_is_rejected(self) -> None:
        for arguments in (
            ["preflight", "--left", "left.csv", "--right", "right.csv"],
            ["run", "--left", "left.csv", "--right", "right.csv", "--out", "result.csv"],
            ["drill-down", "--from", "parent.csv", "--row", "Product=ECS", "--by", "Project", "--out", "child.csv"],
        ):
            with self.subTest(command=arguments[0]):
                code, payload, error = self._run([*arguments, "--allow-nonstandard-dimension"])
                self.assertEqual((2, {}), (code, payload))
                self.assertEqual("INVALID_ARGUMENT", error["error"]["code"])
                self.assertIn("unrecognized arguments: --allow-nonstandard-dimension", error["error"]["message"])

    def test_invalid_query_result_returns_its_local_contract(self) -> None:
        code, payload, error = self._run([
            "preflight",
            "--left-result", '{"file":"/tmp/left.csv"}',
            "--right", "right.csv",
        ])
        self.assertEqual((2, {}), (code, payload))
        invalid = error["error"]["details"]["invalid_parameters"]
        self.assertEqual("--left-result", invalid[0]["path"])
        self.assertEqual(["file", "metadata", "fields"], invalid[0]["contract"]["required"])
        self.assertEqual(["metadata", "fields"], invalid[0]["missing_or_invalid_fields"])

    def test_query_result_requires_declared_absolute_paths(self) -> None:
        code, payload, error = self._run([
            "preflight",
            "--left-result", '{"file":"left.csv","metadata":"left.meta.json","fields":"left.fields.json"}',
            "--right", "right.csv",
        ])
        self.assertEqual((2, {}), (code, payload))
        invalid = error["error"]["details"]["invalid_parameters"][0]
        self.assertEqual("result_contract_invalid", invalid["violation"])
        self.assertEqual(["file", "metadata", "fields"], invalid["missing_or_invalid_fields"])

    def test_invalid_artifact_explains_evidence_boundary_and_recovery(self) -> None:
        code, payload, error = self._run([
            "preflight", "--left", "missing-left.csv", "--right", "missing-right.csv",
        ])
        self.assertEqual((0, {}), (code, error))
        self.assertEqual("block", payload["verdict"])
        self.assertEqual("blocked", payload["claim_scope"])
        self.assertEqual(1, len(payload["checks"]))
        check = payload["checks"][0]
        self.assertEqual("ARTIFACT_INVALID", check["code"])
        self.assertIn("没有可用于正式对账的有效双侧输入", check["message"])
        self.assertIn("尚未执行来源关系、范围、维度或金额检查", check["message"])
        self.assertEqual(
            ["inspect_artifact_set", "regenerate_query_artifacts", "rerun_preflight"],
            [item["action"] for item in check["details"]["recovery_options"]],
        )
        self.assertIn("不要继续 reconcile run", check["details"]["retry_policy"])
        self.assertIn("不要对相同无效输入重复 reconcile run", check["details"]["retry_policy"])
        self.assertIn("不要据此判断范围不一致", check["details"]["retry_policy"])

        code, payload, error = self._run([
            "run", "--left", "missing-left.csv", "--right", "missing-right.csv",
            "--out", "unused.csv",
        ])
        self.assertEqual(2, code)
        self.assertEqual({}, payload)
        preflight = error["error"]["details"]["preflight"]
        self.assertEqual("ARTIFACT_INVALID", preflight["checks"][0]["code"])
        self.assertEqual(
            check["details"]["retry_policy"],
            preflight["checks"][0]["details"]["retry_policy"],
        )

    def test_preflight_and_reconcile_by_product_instance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = self._detail_split(root)
            code, preflight, error = self._run([
                "preflight", "--left", str(left), "--right", str(right),
                "--group-by", "Product,InstanceNo", "--metric", "PayableAmount",
            ])
            self.assertEqual((0, {}), (code, error))
            self.assertEqual("pass", preflight["verdict"])
            output = root / "reconciliation.csv"
            code, manifest, error = self._run([
                "run", "--left", str(left), "--right", str(right),
                "--group-by", "Product,InstanceNo",
                "--metric", "PayableAmount", "--metric", "OriginalBillAmount",
                "--out", str(output),
            ])
            self.assertEqual((0, {}), (code, error))
            rows = read_csv(output)
            by_instance = {row["InstanceNo"]: row for row in rows}
            self.assertEqual("-10", by_instance["i-1"]["difference_PayableAmount"] )
            self.assertEqual("mismatched", by_instance["i-1"]["status"] )
            self.assertEqual("matched", by_instance["i-2"]["status"] )
            self.assertEqual("inconclusive", by_instance["__MISSING__"]["status"] )
            self.assertEqual(["Product", "InstanceNo", "Currency"], json.loads((root / "reconciliation.meta.json").read_text())["plan"]["effective_join_keys"] )
            self.assertEqual("success", manifest["status"])
            self.assertEqual(1, manifest["_meta"]["status_counts"]["mismatched"] )

    def test_product_overview_to_bill_and_bill_to_detail_execute(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            amount_columns = ["Product", "PayableAmount", "Currency"]
            overview = write_query_artifact(
                root, "overview", "ListBillOverviewByProd", amount_columns,
                [{"Product": "ECS", "PayableAmount": "30", "Currency": "CNY"}],
            )
            bill = write_query_artifact(
                root, "bill", "ListBill", ["BillID", *amount_columns],
                [
                    {"BillID": "b-1", "Product": "ECS", "PayableAmount": "10", "Currency": "CNY"},
                    {"BillID": "b-2", "Product": "ECS", "PayableAmount": "20", "Currency": "CNY"},
                ],
            )
            overview_result = root / "overview-to-bill.csv"
            code, manifest, error = self._run([
                "run", "--left", str(overview), "--right", str(bill),
                "--group-by", "Product", "--out", str(overview_result),
            ])
            self.assertEqual((0, {}), (code, error))
            self.assertEqual({"matched": 1, "mismatched": 0, "left_only": 0, "right_only": 0, "inconclusive": 0}, manifest["_meta"]["status_counts"])

            detail = write_query_artifact(
                root, "detail", "ListBillDetail", ["BillID", *amount_columns],
                [
                    {"BillID": "b-1", "Product": "ECS", "PayableAmount": "4", "Currency": "CNY"},
                    {"BillID": "b-1", "Product": "ECS", "PayableAmount": "6", "Currency": "CNY"},
                    {"BillID": "b-2", "Product": "ECS", "PayableAmount": "20", "Currency": "CNY"},
                ],
                body={"GroupPeriod": 2, "GroupTerm": 0},
            )
            bill_detail_result = root / "bill-to-detail.csv"
            code, manifest, error = self._run([
                "run", "--left", str(bill), "--right", str(detail),
                "--group-by", "BillID", "--out", str(bill_detail_result),
            ])
            self.assertEqual((0, {}), (code, error))
            self.assertEqual(2, manifest["_meta"]["status_counts"]["matched"])

    def test_nonstandard_project_runs_and_reports_limitations_without_changing_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = self._detail_split(root)
            code, payload, _ = self._run([
                "preflight", "--left", str(left), "--right", str(right), "--group-by", "Project",
            ])
            self.assertEqual(0, code)
            self.assertEqual("warn", payload["verdict"])
            self.assertEqual("observational", payload["claim_scope"])
            self.assertEqual("reconciliation", payload["mode"])
            check = next(item for item in payload["checks"] if item["code"] == "NONSTANDARD_DIMENSION")
            self.assertEqual(["project"], check["details"]["dimensions"])
            self.assertEqual("warn", check["status"])
            output = root / "project.csv"
            code, manifest, error = self._run([
                "run", "--left", str(left), "--right", str(right), "--group-by", "Project",
                "--out", str(output),
            ])
            self.assertEqual((0, {}), (code, error))
            self.assertEqual("observational", manifest["_meta"]["claim_scope"])
            self.assertIn("来源与语义可能不同", manifest["message"])
            self.assertIn("不证明标准对账不一致或多算", manifest["message"])
            metadata = json.loads(output.with_suffix(".meta.json").read_text(encoding="utf-8"))
            self.assertEqual("reconciliation", metadata["plan"]["mode"])
            self.assertEqual("unknown", metadata["plan"]["empty_group_policy"])
            rows = {row["Project"]: row for row in read_csv(output)}
            self.assertEqual("170", rows["billing-project"]["left_PayableAmount"])
            self.assertEqual("", rows["billing-project"]["right_PayableAmount"])
            self.assertTrue(all(row["status"] in {"left_only", "right_only", "inconclusive"} for row in read_csv(output)))
            filtered = root / "project-filter.csv"
            code, manifest, error = self._run([
                "run", "--left", str(left), "--right", str(right),
                "--filter", "Project", "eq", "project-a",
                "--out", str(filtered),
            ])
            self.assertEqual((0, {}), (code, error))
            self.assertEqual("observational", manifest["_meta"]["claim_scope"])
            self.assertIn("非标准维度 project", manifest["message"])
            self.assertEqual({"60", "50"}, {row["right_PayableAmount"] for row in read_csv(filtered)})

    def test_nonstandard_tag_runs_but_missing_tag_and_incomplete_input_still_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            columns = ["Product", "Tag", "PayableAmount", "Currency"]
            inputs = [
                write_query_artifact(root, name, action, columns, [
                    {"Product": "ECS", "Tag": "team-a", "PayableAmount": amount, "Currency": "CNY"},
                ])
                for name, action, amount in [
                    ("left", "ListBillDetail", "10"), ("right", "ListSplitBillDetail", "12"),
                ]
            ]
            for options in (["--group-by", "Tag"], ["--group-by", "Product", "--filter", "Tag", "eq", "team-a"]):
                with self.subTest(options=options):
                    output = root / "tags.csv"
                    code, manifest, error = self._run([
                        "run", "--left", str(inputs[0]), "--right", str(inputs[1]),
                        *options, "--out", str(output), "--overwrite",
                    ])
                    self.assertEqual((0, {}), (code, error))
                    self.assertIn("非标准维度 tag", manifest["message"])
                    row = read_csv(output)[0]
                    self.assertEqual("2", row["difference_PayableAmount"])
                    self.assertEqual("inconclusive", row["status"])
            left, right = self._detail_split(root)
            _, payload, _ = self._run([
                "preflight", "--left", str(left), "--right", str(right), "--group-by", "Tag",
            ])
            self.assertEqual("block", payload["verdict"])
            self.assertIn("GROUP_BY_FIELD_MISSING", {item["code"] for item in payload["checks"]})
            left, right = self._detail_split(root, complete=False)
            _, payload, _ = self._run([
                "preflight", "--left", str(left), "--right", str(right), "--group-by", "Project",
            ])
            self.assertEqual("block", payload["verdict"])
            self.assertIn("COVERAGE_INCOMPLETE", {item["code"] for item in payload["checks"]})

    def test_common_filter_must_exist_on_both_sides(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = self._detail_split(root)
            code, payload, _ = self._run([
                "preflight", "--left", str(left), "--right", str(right),
                "--filter", "SplitItemID", "eq", "item-1",
            ])
            self.assertEqual(0, code)
            self.assertEqual("block", payload["verdict"])
            self.assertIn("FILTER_FIELD_MISSING", {item["code"] for item in payload["checks"]})

    def test_incomplete_coverage_blocks_and_current_period_complete_snapshot_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = self._detail_split(root, complete=False)
            _, payload, _ = self._run(["preflight", "--left", str(left), "--right", str(right)])
            self.assertEqual("block", payload["verdict"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = self._detail_split(root, partial_period=True)
            _, payload, _ = self._run(["preflight", "--left", str(left), "--right", str(right)])
            self.assertEqual("warn", payload["verdict"])
            self.assertEqual("provisional", payload["claim_scope"])

    def test_supported_current_period_provisional_coverage_warns_and_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = self._detail_split(
                root,
                complete=False,
                provisional=True,
                partial_period=True,
            )
            code, preflight, error = self._run([
                "preflight", "--left", str(left), "--right", str(right),
            ])
            self.assertEqual((0, {}), (code, error))
            self.assertEqual("warn", preflight["verdict"])
            self.assertEqual("provisional", preflight["claim_scope"])
            self.assertEqual(
                2,
                sum(check["code"] == "COVERAGE_PROVISIONAL" for check in preflight["checks"]),
            )

            output = root / "provisional-reconciliation.csv"
            code, manifest, error = self._run([
                "run", "--left", str(left), "--right", str(right), "--out", str(output),
            ])
            self.assertEqual((0, {}), (code, error))
            self.assertEqual("warn", manifest["_meta"]["verdict"])
            self.assertEqual("provisional", manifest["_meta"]["claim_scope"])
            self.assertGreater(manifest["_meta"]["row_count"], 0)
            self.assertGreater(manifest["_meta"]["status_counts"]["mismatched"], 0)
            self.assertTrue(output.is_file())
            self.assertTrue(all(row["claim_scope"] == "provisional" for row in read_csv(output)))

    def test_provisional_without_required_evidence_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = self._detail_split(root, complete=False, provisional=True)
            metadata_path = left.with_suffix(".meta.json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["coverage"]["provisional_queries"][0]["initial_total_boundary_reached"] = False
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
            _, payload, _ = self._run([
                "preflight", "--left", str(left), "--right", str(right),
            ])
            self.assertEqual("block", payload["verdict"])
            self.assertIn("COVERAGE_INCOMPLETE", {item["code"] for item in payload["checks"]})

    def test_page_coverage_blocks_even_when_the_page_contains_all_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = self._detail_split(root)
            metadata_path = left.with_suffix(".meta.json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["coverage"]["requested_scope"] = "page"
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
            _, payload, _ = self._run([
                "preflight", "--left", str(left), "--right", str(right),
            ])
            self.assertEqual("block", payload["verdict"])
            self.assertIn("COVERAGE_INCOMPLETE", {item["code"] for item in payload["checks"]})

    def test_drill_down_preserves_parent_amount_and_right_project_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = self._detail_split(root)
            parent = root / "by-product.csv"
            code, _, error = self._run([
                "run", "--left", str(left), "--right", str(right),
                "--group-by", "Product", "--out", str(parent),
            ])
            self.assertEqual((0, {}), (code, error))
            child = root / "ecs-instances.csv"
            code, manifest, error = self._run([
                "drill-down", "--from", str(parent), "--row", "Product=ECS",
                "--row", "Currency=CNY", "--by", "InstanceNo", "--out", str(child),
            ])
            self.assertEqual((0, {}), (code, error))
            self.assertEqual("matched", manifest["_meta"]["conservation"]["status"])
            self.assertEqual({"i-1", "i-2"}, {row["InstanceNo"] for row in read_csv(child)})
            project = root / "i-1-projects.csv"
            code, manifest, error = self._run([
                "drill-down", "--from", str(child), "--row", "Product=ECS",
                "--row", "InstanceNo=i-1", "--row", "Currency=CNY",
                "--by", "Project", "--side", "right", "--out", str(project),
            ])
            self.assertEqual((0, {}), (code, error))
            self.assertEqual("matched", manifest["_meta"]["conservation"]["status"])
            self.assertEqual("attribution_breakdown", manifest["_meta"]["claim_scope"])
            self.assertEqual({"project-a", "project-b"}, {row["Project"] for row in read_csv(project)})
            both_projects = root / "both-projects.csv"
            code, manifest, error = self._run([
                "drill-down", "--from", str(child), "--row", "Product=ECS",
                "--row", "InstanceNo=i-1", "--row", "Currency=CNY",
                "--by", "Project", "--out", str(both_projects),
            ])
            self.assertEqual((0, {}), (code, error))
            self.assertEqual("inconclusive", manifest["_meta"]["conservation"]["status"])
            self.assertEqual("inconclusive", manifest["_meta"]["claim_scope"])
            self.assertIn("来源与语义可能不同", manifest["message"])
            metadata = json.loads(both_projects.with_suffix(".meta.json").read_text(encoding="utf-8"))
            self.assertEqual("reconciliation", metadata["plan"]["mode"])
            self.assertEqual({"billing-project", "project-a", "project-b"}, {row["Project"] for row in read_csv(both_projects)})


    def test_original_scope_and_project_keys_are_preserved(self) -> None:
        source = Path(__file__).resolve().parent / "fixtures" / "reconciliation" / "project_scope"
        left = source / "project-left-bill-detail.csv"
        right = source / "project-right-split-detail.csv"
        before = {path: path.read_bytes() for path in source.iterdir() if path.is_file()}
        common = ["--left", str(left), "--right", str(right), "--group-by", "Project"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code, formal, _ = self._run(["preflight", *common])
            self.assertEqual(0, code)
            self.assertEqual("block", formal["verdict"])
            self.assertIn("REQUEST_SCOPE_MISMATCH", {c["code"] for c in formal["checks"] if c["status"] == "block"})
            code, _, error = self._run(["run", *common, "--out", str(root / "blocked.csv")])
            self.assertEqual(2, code)
            self.assertFalse((root / "blocked.csv").exists())
            code, observed, _ = self._run(["preflight", *common, "--mode", "observational"])
            self.assertEqual(0, code)
            self.assertEqual(("warn", "observational"), (observed["verdict"], observed["claim_scope"]))
            output = root / "comparison.csv"
            code, manifest, error = self._run(["run", *common, "--mode", "observational", "--out", str(output)])
            self.assertEqual((0, {}), (code, error))
            self.assertEqual("comparison", manifest["_meta"]["operation"])
            rows = {row["Project"]: row for row in read_csv(output)}
            self.assertEqual({"legacy-project", "project-alpha"}, set(rows))
            self.assertEqual(("88.00", "0", "-88.00", "left_only"), tuple(rows["legacy-project"][key] for key in ("left_PayableAmount", "right_PayableAmount", "difference_PayableAmount", "status")))
            self.assertEqual(("0", "100.00", "100.00", "right_only"), tuple(rows["project-alpha"][key] for key in ("left_PayableAmount", "right_PayableAmount", "difference_PayableAmount", "status")))
            metadata = json.loads(output.with_suffix(".meta.json").read_text())
            self.assertEqual(["ECS"], metadata["inputs"]["left"]["request_scopes"][0]["product"])
            self.assertEqual(["ECS", "RDS"], metadata["inputs"]["right"]["request_scopes"][0]["product"])
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_plain_csv_decimal_currency_missing_amount_and_drill_inheritance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = root / "left.csv", root / "right.csv"
            left.write_text("Project,Product,PayableAmount,Currency\np,ECS,0.1,CNY\np,ECS,0.2,CNY\np,ECS,-2,USD\nq,ECS,,CNY\nq,ECS,5,CNY\n", encoding="utf-8")
            right.write_text("Project,Product,PayableAmount,Currency\np,ECS,0.4,CNY\np,RDS,0.2,CNY\np,ECS,1,USD\nq,ECS,10,CNY\n", encoding="utf-8")
            output = root / "comparison.csv"
            code, manifest, error = self._run(["run", "--mode", "observational", "--left", str(left), "--right", str(right), "--group-by", "Project", "--out", str(output)])
            self.assertEqual((0, {}), (code, error))
            rows = {(row["Project"], row["Currency"]): row for row in read_csv(output)}
            self.assertEqual("0.3", rows[("p", "CNY")]["difference_PayableAmount"])
            self.assertEqual("3", rows[("p", "USD")]["difference_PayableAmount"])
            self.assertEqual("", rows[("q", "CNY")]["left_PayableAmount"])
            self.assertEqual("", rows[("q", "CNY")]["difference_PayableAmount"])
            self.assertTrue(all(row["status"] == "inconclusive" and row["claim_scope"] == "observational" for row in rows.values()))
            metadata = json.loads(output.with_suffix(".meta.json").read_text())
            self.assertIsNone(metadata["inputs"]["left"]["metadata"])
            self.assertFalse(any(c["code"] in {"COVERAGE_COMPLETE", "CLOSED_PERIOD", "REQUEST_SCOPE_MATCH"} for c in metadata["preflight"]["checks"]))
            child = root / "child.csv"
            code, manifest, error = self._run(["drill-down", "--from", str(output), "--row", "Project=p", "--row", "Currency=CNY", "--by", "Product", "--out", str(child)])
            self.assertEqual((0, {}), (code, error))
            self.assertEqual("observational", manifest["_meta"]["claim_scope"])
            self.assertEqual("matched", manifest["_meta"]["conservation"]["status"])
            self.assertTrue(all(row["claim_scope"] == "observational" for row in read_csv(child)))

    def test_invalid_inputs_still_block_observation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = root / "left.csv", root / "right.csv"
            right.write_text("Project,PayableAmount,Currency\np,1,CNY\n", encoding="utf-8")
            cases = [
                (None, "ARTIFACT_INVALID"),
                ("Project,PayableAmount,Currency\np,NaN,CNY\n", "AMOUNT_VALUE_INVALID"),
                ("Project,PayableAmount\np,1\n", "CURRENCY_FIELD_MISSING"),
                ("Project,PayableAmount,Currency\np,1,\n", "CURRENCY_VALUE_MISSING"),
                ("Product,PayableAmount,Currency\nECS,1,CNY\n", "GROUP_BY_FIELD_MISSING"),
            ]
            for content, expected in cases:
                with self.subTest(expected=expected):
                    if content is not None:
                        left.write_text(content, encoding="utf-8")
                    output = root / "blocked.csv"
                    code, payload, error = self._run(["run", "--mode", "observational", "--left", str(left), "--right", str(right), "--group-by", "Project", "--out", str(output)])
                    self.assertEqual((2, {}), (code, payload))
                    checks = error["error"]["details"]["preflight"]["checks"]
                    self.assertIn(expected, {c["code"] for c in checks if c["status"] == "block"})
                    self.assertFalse(output.exists())

    def test_incomplete_snapshot_and_custom_dimension_remain_observational(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = write_query_artifact(root, "left", "ListBillDetail", ["Region", "PayableAmount", "Currency"], [{"Region": "cn-a", "PayableAmount": "1", "Currency": "CNY"}], complete=False)
            right = write_query_artifact(root, "right", "ListSplitBillDetail", ["Region", "PayableAmount", "Currency"], [{"Region": "cn-a", "PayableAmount": "3", "Currency": "CNY"}])
            common = ["--left", str(left), "--right", str(right), "--group-by", "Region"]
            _, formal, _ = self._run(["preflight", *common])
            self.assertEqual("block", formal["verdict"])
            output = root / "comparison.csv"
            code, _, error = self._run(["run", *common, "--mode", "observational", "--out", str(output)])
            self.assertEqual((0, {}), (code, error))
            self.assertEqual("2", read_csv(output)[0]["difference_PayableAmount"])
            metadata = json.loads(output.with_suffix(".meta.json").read_text())
            self.assertFalse(metadata["inputs"]["left"]["source_metadata"]["coverage"]["is_complete"])
            self.assertEqual("observational", metadata["claim_scope"])
            check = next(c for c in metadata["preflight"]["checks"] if c["code"] == "COVERAGE_INCOMPLETE")
            self.assertEqual("warn", check["status"])


if __name__ == "__main__":
    unittest.main()
