from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2] / "skills" / "core" / "volcengine-cost"
sys.path.insert(0, str(ROOT / "scripts"))

from cost_query.billing.client import BillingClient, FixtureBillingClient, VeBillingClient
from cost_query.billing.field_catalog import build_field_catalog
from cost_query.billing.fetch import FetchConfig, collect_query
from cost_query.billing.json_schema import schema_contract
from cost_query.billing.validation import validate_request_body
from cost_query.common.errors import BillingQueryError, ErrorCode, ExitCode
from describe_billing_api import describe_action, list_actions
from query_billing import main


ACTION = "ListFinancialRelation"


def relation_row(**overrides):
    return {
        "RelationID": "relation-001",
        "RelationDesc": "财务托管",
        "MajorAccountID": 2000000000,
        "MajorAccountName": "测试主账号",
        "SubAccountID": 2000000001,
        "SubAccountName": "测试子账号",
        **overrides,
    }


def response(rows, *, total, offset=0, limit=100):
    return {"Result": {"List": rows, "Total": total, "Offset": offset, "Limit": limit}}


class SequenceClient(BillingClient):
    def __init__(self, outcomes, identity=None):
        self.outcomes = list(outcomes)
        self.calls = []
        self.identity = identity
        self.identity_calls = 0

    def get_caller_identity(self):
        self.identity_calls += 1
        if isinstance(self.identity, Exception):
            raise self.identity
        return self.identity

    def query(self, action, body):
        self.calls.append((action, dict(body)))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FinancialRelationTest(unittest.TestCase):
    def run_query(self, client, *arguments):
        stdout = io.StringIO()
        with patch("query_billing.VeBillingClient", return_value=client):
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["--action", ACTION, "--body", "{}", *arguments])
        return exit_code, json.loads(stdout.getvalue())

    def test_query_defaults_to_legal_page_size_and_keeps_unknown_codes(self):
        row = relation_row(Relation=999, Status=998, Filiation=997)
        client = SequenceClient([response([row], total=1)])
        code, payload = self.run_query(client, "--pagination", "full")
        self.assertEqual(0, code)
        self.assertEqual("success", payload["status"])
        self.assertEqual((ACTION, {"Limit": 100, "Offset": 0}), client.calls[0])
        self.assertEqual(999, payload["result"][0]["Relation"])
        self.assertEqual(998, payload["result"][0]["Status"])
        self.assertNotIn("account_status", payload["_meta"])

    def test_full_reads_second_page_preserves_filter_and_excludes_auth_details(self):
        first = relation_row(AuthInfo=[{"AuthType": "test-only"}])
        second = relation_row(RelationID="relation-002", RelationDesc="财务管理")
        client = SequenceClient([
            response([first], total=2, limit=1),
            response([second], total=2, offset=1, limit=1),
        ])
        result = collect_query(
            client=client, action=ACTION, query_id="relations",
            base_body={"AccountIDSearchList": ["002000000001"]},
            config=FetchConfig(page_size=1),
        )
        self.assertTrue(result.is_complete)
        self.assertEqual(2, len(result.rows))
        self.assertEqual([0, 1], [body["Offset"] for _, body in client.calls])
        self.assertTrue(all(body["AccountIDSearchList"] == ["002000000001"] for _, body in client.calls))
        self.assertTrue(all("NeedRecordNum" not in body for _, body in client.calls))
        self.assertNotIn("AuthInfo", result.rows[0])
        self.assertEqual("财务管理", result.rows[1]["RelationDesc"])

    def test_denied_later_page_delivers_partial_rows(self):
        client = SequenceClient([
            response([relation_row()], total=2, limit=1),
            BillingQueryError(ErrorCode.PERMISSION_DENIED, "test denied", ExitCode.QUERY_FAILED),
        ])
        code, payload = self.run_query(client, "--pagination", "full", "--page-size", "1")
        self.assertEqual(ExitCode.PARTIAL_RESULT, code)
        self.assertEqual("partial", payload["status"])
        self.assertEqual("relation-001", payload["result"][0]["RelationID"])
        self.assertEqual(2, len(client.calls))

    def test_empty_relationship_query_does_not_decide_balance_or_consumption(self):
        code, payload = self.run_query(SequenceClient([response([], total=0)]), "--pagination", "full")
        self.assertEqual(0, code)
        self.assertEqual([], payload["result"])
        self.assertNotIn("account_status", payload["_meta"])
        self.assertNotIn("没有消费", payload["message"])
        self.assertIn("当前账号没有财务关系", payload["message"])
        self.assertNotIn("无法确认", payload["message"])

    def test_live_response_minus_one_offset_is_usable_in_both_modes(self):
        # Shape captured on 2026-11-04; account identifiers/names are synthetic.
        raw = response([
            relation_row(
                AccountAlias="子账号", AuthInfo=[], Filiation=1, FiliationDesc="主",
                Relation=1, Status=200, StatusDesc="关系已建立",
                UpdateTime="2023-03-27 20:00:50",
            )
        ], total=1, offset=-1)
        raw["Result"]["BaseResp"] = {
            "ErrorCode": "", "HTTPStatusCode": 0, "StatusCode": 0, "StatusMessage": "",
        }
        for mode in ("page", "full"):
            with self.subTest(mode=mode):
                client = SequenceClient([raw])
                code, payload = self.run_query(client, "--pagination", mode)
                self.assertEqual(0, code)
                self.assertEqual("success", payload["status"])
                self.assertEqual("财务托管", payload["result"][0]["RelationDesc"])
                self.assertEqual(1, len(client.calls))
                self.assertEqual(-1, raw["Result"]["Offset"])

    def test_minus_one_echo_full_advances_using_requested_offsets(self):
        client = SequenceClient([
            response([relation_row()], total=2, offset=-1, limit=1),
            response([relation_row(RelationID="relation-002")], total=2, offset=-1, limit=1),
        ])
        result = collect_query(
            client=client, action=ACTION, query_id="relations", base_body={},
            config=FetchConfig(page_size=1),
        )
        self.assertTrue(result.is_complete)
        self.assertEqual(2, len(result.rows))
        self.assertEqual([0, 1], [body["Offset"] for _, body in client.calls])
        self.assertEqual(1, len(result.warnings))

    def test_empty_minus_one_echo_succeeds_without_fabricating_relations(self):
        for mode in ("page", "full"):
            with self.subTest(mode=mode):
                code, payload = self.run_query(
                    SequenceClient([response([], total=0, offset=-1)]), "--pagination", mode,
                )
                self.assertEqual(0, code)
                self.assertEqual([], payload["result"])
                self.assertNotIn("account_status", payload["_meta"])

    def test_minus_one_echo_does_not_disable_repeat_total_or_early_end_checks(self):
        for scenario, outcomes in (
            ("repeat", [
                response([relation_row()], total=2, offset=-1, limit=1),
                response([relation_row()], total=2, offset=-1, limit=1),
            ]),
            ("total_drift", [
                response([relation_row()], total=2, offset=-1, limit=1),
                response([relation_row(RelationID="relation-002")], total=3, offset=-1, limit=1),
            ]),
            ("early_end", [response([], total=1, offset=-1, limit=1)]),
        ):
            with self.subTest(scenario=scenario):
                result = collect_query(
                    client=SequenceClient(outcomes), action=ACTION, query_id="relations",
                    base_body={}, config=FetchConfig(page_size=1),
                )
                self.assertFalse(result.is_complete)
                self.assertEqual("PAGINATION_INCOMPLETE", result.error["code"])

    def test_other_offset_mismatches_still_fail_and_include_actual_values(self):
        for returned in (-2, 9):
            with self.subTest(returned=returned):
                result = collect_query(
                    client=SequenceClient([response([relation_row()], total=1, offset=returned)]),
                    action=ACTION, query_id="relations", base_body={}, config=FetchConfig(page_size=100),
                )
                self.assertEqual("PAGINATION_INCOMPLETE", result.error["code"])
                self.assertEqual(0, result.error["details"]["requested_offset"])
                self.assertEqual(returned, result.error["details"]["returned_offset"])
                self.assertEqual([], result.rows)

    def test_minus_one_offset_is_not_accepted_for_bill_actions(self):
        result = collect_query(
            client=SequenceClient([response([], total=0, offset=-1)]),
            action="ListBill", query_id="2026-10", base_body={"BillPeriod": "2026-10"},
            config=FetchConfig(page_size=100),
        )
        self.assertFalse(result.is_complete)
        self.assertEqual("PAGINATION_INCOMPLETE", result.error["code"])

    def test_missing_or_null_offset_echo_remains_supported(self):
        for include_null in (False, True):
            raw = response([relation_row()], total=1)
            if include_null:
                raw["Result"]["Offset"] = None
            else:
                del raw["Result"]["Offset"]
            with self.subTest(include_null=include_null):
                result = collect_query(
                    client=SequenceClient([raw]), action=ACTION, query_id="relations", base_body={},
                    config=FetchConfig(page_size=100),
                )
                self.assertTrue(result.is_complete)
                self.assertIsNone(result.error)

    def test_invalid_page_size_and_billing_parameters_are_rejected(self):
        for body in ({"Limit": 101}, {"Limit": 0}, {"Offset": -1}, {"BillPeriod": "2026-10"}, {"NeedRecordNum": 1}):
            with self.subTest(body=body), self.assertRaises(BillingQueryError):
                validate_request_body(ACTION, body)

    def test_request_filters_keep_string_codes_and_account_ids(self):
        body = {"AccountIDSearchList": ["002000000001"], "Relation": ["999"], "Status": ["998"]}
        self.assertEqual(body, validate_request_body(ACTION, body))
        for field in ("AccountIDSearchList", "Relation", "Status"):
            with self.subTest(field=field), self.assertRaises(BillingQueryError):
                validate_request_body(ACTION, {field: [1]})

    def test_discovery_explains_role_status_and_separate_settlement(self):
        action = next(item for item in list_actions()["actions"] if item["action"] == ACTION)
        self.assertEqual("financial_relation", action["result_kind"])
        self.assertIn("财务管理", " ".join(action["important_limits"]))
        described = describe_action(ACTION, section="response", expand=True)
        guidance = json.dumps(described, ensure_ascii=False)
        self.assertIn("主子相对视角", guidance)
        self.assertIn("已核验账号 ID", guidance)
        self.assertIn("不能复用代金券或资源包状态枚举", guidance)
        properties = schema_contract(ACTION, section="request")["request_json_schema"]["properties"]
        self.assertEqual(100, properties["Limit"]["maximum"])

    def test_relationship_identifiers_and_codes_are_not_money_metrics(self):
        catalog = build_field_catalog(
            action=ACTION, columns=list(relation_row(Relation=999, Status=998, Filiation=997)),
            source_csv=Path("relations.csv"), source_metadata=None,
        )
        fields = {item["field"]: item for item in catalog["fields"]}
        self.assertEqual("identifier", fields["MajorAccountID"]["role"])
        self.assertEqual("attribute", fields["Status"]["role"])
        self.assertEqual([], fields["Status"]["aggregations"])

    def test_same_identity_proves_sub_role_despite_filiation_saying_major(self):
        client = SequenceClient(
            [response([relation_row(Filiation=1, FiliationDesc="主")], total=1, offset=-1)],
            identity={"Result": {"AccountId": 2000000001, "IdentityType": "User", "Trn": "not-for-output"}},
        )
        code, payload = self.run_query(client, "--pagination", "full")
        self.assertEqual(0, code)
        self.assertIn("当前账号是子账号（匹配 SubAccountID）", payload["message"])
        self.assertNotIn("当前账号是主账号", payload["message"])
        self.assertEqual("主", payload["result"][0]["FiliationDesc"])
        evidence = payload["_meta"]["identity_verification"]
        self.assertEqual("sub", evidence["relations"][0]["role"])
        self.assertEqual(1, client.identity_calls)
        self.assertNotIn("not-for-output", json.dumps(payload))

    def test_major_role_requires_actual_account_id_match(self):
        client = SequenceClient(
            [response([relation_row(FiliationDesc="子")], total=1)],
            identity={"Result": {"AccountId": "2000000000"}},
        )
        code, payload = self.run_query(client, "--pagination", "page")
        self.assertEqual(0, code)
        self.assertIn("当前账号是主账号（匹配 MajorAccountID）", payload["message"])
        self.assertEqual("major", payload["_meta"]["identity_verification"]["relations"][0]["role"])

    def test_missing_failed_invalid_identity_keeps_relations_and_unknown_role(self):
        for identity in (
            None, {"Result": {}}, {"Result": {"AccountId": True}},
            {"Result": {"AccountId": 2000000001.0}},
            {"ResponseMetadata": {"Error": {"Code": "AccessDenied"}}, "Result": {"AccountId": 2000000001}},
            BillingQueryError(ErrorCode.PERMISSION_DENIED, "identity denied", ExitCode.QUERY_FAILED),
        ):
            with self.subTest(identity=type(identity).__name__):
                client = SequenceClient([response([relation_row(FiliationDesc="主")], total=1)], identity=identity)
                code, payload = self.run_query(client, "--pagination", "full")
                self.assertEqual(0, code)
                self.assertEqual(1, len(payload["result"]))
                self.assertIn("无法确认当前账号是主账号还是子账号", payload["message"])
                self.assertEqual("unknown", payload["_meta"]["identity_verification"]["status"])

    def test_empty_relations_do_not_trigger_identity_query(self):
        client = SequenceClient([response([], total=0, offset=-1)])
        code, payload = self.run_query(client, "--pagination", "full")
        self.assertEqual(0, code)
        self.assertEqual(0, client.identity_calls)
        self.assertEqual("not_needed", payload["_meta"]["identity_verification"]["status"])

    def test_filtered_empty_query_names_its_scope_without_denial_of_all_relations(self):
        with patch("query_billing.VeBillingClient", return_value=SequenceClient([response([], total=0)])):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main([
                    "--action", ACTION, "--body", '{"AccountIDSearchList":["2000000001"]}',
                    "--pagination", "full",
                ])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, code)
        self.assertIn("指定条件或页范围内没有财务关系记录", payload["message"])
        self.assertNotIn("当前账号没有财务关系", payload["message"])
        self.assertNotIn("无法确认", payload["message"])

    def test_identity_matching_both_or_neither_account_is_not_a_major_role(self):
        for major, sub in ((2000000001, 2000000001), (2000000000, 2000000002)):
            client = SequenceClient(
                [response([relation_row(MajorAccountID=major, SubAccountID=sub)], total=1)],
                identity={"Result": {"AccountId": 2000000001}},
            )
            code, payload = self.run_query(client, "--pagination", "full")
            self.assertEqual(0, code)
            self.assertIn("角色无法确认", payload["message"])
            self.assertNotIn("当前账号是主账号", payload["message"])

    def test_identity_query_uses_billing_client_profile_and_region(self):
        commands = []
        def runner(command, **kwargs):
            commands.append(command)
            payload = response([relation_row()], total=1) if command[1] == "billing" else {"Result": {"AccountId": 2000000001}}
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        with patch("cost_query.billing.client.shutil.which", return_value="ve"):
            client = VeBillingClient(region="cn-beijing", profile="selected", timeout_seconds=7, runner=runner)
        client.query(ACTION, {"Limit": 100, "Offset": 0})
        client.get_caller_identity()
        self.assertEqual(["ve", "sts", "GetCallerIdentity"], commands[1][:3])
        self.assertTrue(all(command[-2:] == ["---profile", "selected"] for command in commands))
        self.assertTrue(all(command[command.index("---region") + 1] == "cn-beijing" for command in commands))
        self.assertNotIn("--body", commands[1])

    def test_export_retains_identity_evidence_without_altering_wire_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "relations.csv"
            client = SequenceClient(
                [response([relation_row(FiliationDesc="主")], total=1, offset=-1)],
                identity={"Result": {"AccountId": 2000000001}},
            )
            code, payload = self.run_query(client, "--pagination", "full", "--out", str(path))
            self.assertEqual(0, code)
            metadata = json.loads(Path(payload["result"]["metadata"]).read_text())
            self.assertEqual("sub", metadata["identity_verification"]["relations"][0]["role"])
            self.assertIn("当前账号是子账号", payload["message"])
            self.assertNotIn("CurrentAccountRole", path.read_text())

    def test_fixture_identity_is_local_and_missing_fixture_stays_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FixtureBillingClient(Path(directory))
            self.assertIsNone(client.get_caller_identity())
            (Path(directory) / "GetCallerIdentity.json").write_text('{"Result":{"AccountId":2000000001}}')
            self.assertEqual(2000000001, client.get_caller_identity()["Result"]["AccountId"])


if __name__ == "__main__":
    unittest.main()
