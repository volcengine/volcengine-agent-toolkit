from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "skills" / "core" / "volcengine-cost"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from describe_billing_api import describe_action, find_field, list_actions  # noqa: E402
from cost_query.billing.json_schema import schema_contract  # noqa: E402
from cost_query.billing.schema import ACTION_SCHEMAS  # noqa: E402
from cost_query.common.version import VERSION  # noqa: E402


SCRIPT = SCRIPTS / "describe_billing_api.py"
COST_SCRIPT = SCRIPTS / "cost.py"


class DescribeBillingApiTest(unittest.TestCase):
    def test_list_is_an_agent_action_selection_catalog(self) -> None:
        result = list_actions()
        self.assertEqual("describe_billing_api", result["tool"])
        self.assertEqual(VERSION, result["tool_version"])
        self.assertEqual(
            set(ACTION_SCHEMAS),
            {item["action"] for item in result["actions"]},
        )
        self.assertTrue(all("query_shape" not in item for item in result["actions"]))
        analysis = next(
            item
            for item in result["actions"]
            if item["action"] == "ListCostAnalysisOpenApi"
        )
        self.assertEqual("aggregated_time_series", analysis["result_kind"])
        self.assertTrue(analysis["use_when"])
        self.assertTrue(analysis["avoid_when"])
        filter_info = next(
            item
            for item in result["actions"]
            if item["action"] == "GetFilterInfoForCostAnalysis"
        )
        self.assertEqual("structured_json_stdout", filter_info["preferred_output"])
        balance = next(
            item for item in result["actions"]
            if item["action"] == "QueryBalanceAcct"
        )
        self.assertEqual("account_balance_snapshot", balance["result_kind"])
        self.assertEqual("structured_json_stdout", balance["preferred_output"])

    def test_default_list_contains_action_decision_guidance(self) -> None:
        result = list_actions()
        self.assertTrue(all("purpose" in item for item in result["actions"]))
        self.assertTrue(all("use_when" in item for item in result["actions"]))
        self.assertTrue(all("avoid_when" in item for item in result["actions"]))
        self.assertTrue(all("important_limits" in item for item in result["actions"]))

    def test_action_guidance_distinguishes_bill_usage_period_from_amortized_cost(self) -> None:
        actions = {item["action"]: item for item in list_actions()["actions"]}
        bill_limits = " ".join(actions["ListBillDetail"]["important_limits"])
        daily = actions["ListAmortizedCostBillDaily"]
        self.assertIn("BillPeriod 决定账单归属", bill_limits)
        self.assertIn("可能晚于出账账期甚至位于未来", bill_limits)
        self.assertIn("不改变账期归属", bill_limits)
        self.assertTrue(any("每日分摊趋势" in item for item in daily["use_when"]))
        self.assertIn("实际使用周期", daily["purpose"])
        self.assertIn("AmortizedDay/AmortizedMonth", " ".join(daily["important_limits"]))

        bill_interpretation = describe_action(
            "ListBillDetail", section="response",
        )["response"]["interpretation"]["interpretation_rules"]
        self.assertTrue(any("不能据此从账期合计中排除" in item for item in bill_interpretation))
        self.assertTrue(any("不要根据 ExpenseBeginTime/ExpenseEndTime 手工分配" in item for item in bill_interpretation))

        cost_interpretation = describe_action(
            "ListAmortizedCostBillDaily", section="response",
        )["response"]["interpretation"]["interpretation_rules"]
        self.assertTrue(any("实际使用周期" in item and "AmortizedMonth" in item for item in cost_interpretation))
        self.assertTrue(any("BillPeriod 表示原始账务账期" in item for item in cost_interpretation))

    def test_time_fields_expose_action_specific_interpretation(self) -> None:
        bill_begin = describe_action(
            "ListBillDetail", section="response", field_query="ExpenseBeginTime",
        )["response"]["fields"][0]["agent_guidance"]
        self.assertEqual("实例实际开始使用时间。", bill_begin["summary"])
        self.assertTrue(any("仍计入 BillPeriod" in note for note in bill_begin["notes"]))

        amortized_day = describe_action(
            "ListAmortizedCostBillDaily", section="response", field_query="AmortizedDay",
        )["response"]["fields"][0]["agent_guidance"]
        self.assertIn("实际使用周期", amortized_day["summary"])
        amortized_bill_period = describe_action(
            "ListAmortizedCostBillDaily", section="response", field_query="BillPeriod",
        )["response"]["fields"][0]["agent_guidance"]
        self.assertIn("不决定成本的分摊日期", amortized_bill_period["summary"])

    def test_balance_contract_exposes_empty_request_and_response_shape(self) -> None:
        request = describe_action("QueryBalanceAcct", section="request")["request"]
        self.assertEqual([], request["fields"])
        self.assertEqual([], request["overview"]["required_fields"])
        self.assertEqual([], request["overview"]["optional_fields"])

        response = describe_action("QueryBalanceAcct", section="response")["response"]
        fields = {item["path"]: item for item in response["fields"]}
        self.assertEqual(
            {
                "ArrearsBalance",
                "AvailableBalance",
                "CashBalance",
                "CreditLimit",
                "FreezeAmount",
                "Currency",
            },
            set(fields),
        )
        self.assertNotIn("AccountID", fields)
        interpretation = response["interpretation"]
        self.assertEqual("Result", interpretation["records_path"])

    def test_bill_detail_group_period_field_has_minimal_decision_card(self) -> None:
        result = describe_action("ListBillDetail", section="request", field_query="GroupPeriod")
        self.assertNotIn("overview", result["request"])
        decision = result["request"]["field_decisions"]["GroupPeriod"]
        self.assertEqual({"0", "1", "2"}, set(decision["values"]))
        self.assertIn("GroupTerm", decision["related_request_fields"])
        self.assertNotIn("details_command", decision)
        self.assertIn(2, {item["value"] for item in decision["choose"]})
        text = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("preaggregation_guidance", text)
        self.assertNotIn("recommended_combinations", text)
        self.assertLess(len(text), 1800)

    def test_bill_detail_request_overview_can_include_preaggregation_guidance_explicitly(self) -> None:
        result = describe_action(
            "ListBillDetail",
            section="request",
            field_query="GroupPeriod",
            include_overview=True,
        )
        guidance = result["request"]["overview"]["preaggregation_guidance"]
        self.assertEqual("advisory", guidance["kind"])
        self.assertEqual("retention_guidance_not_response_guarantee", guidance["field_semantics"])
        self.assertEqual(4, len(guidance["recommended_combinations"]))
        self.assertEqual(
            {"GroupPeriod": 2, "GroupTerm": 0},
            guidance["recommended_combinations"][0]["request_patch"],
        )

    def test_preaggregation_guidance_only_appears_in_bill_detail_request_overview(self) -> None:
        self.assertIn(
            "preaggregation_guidance",
            describe_action("ListBillDetail", section="request")["request"]["overview"],
        )
        self.assertNotIn(
            "preaggregation_guidance",
            describe_action("ListBill", section="request")["request"]["overview"],
        )

    def test_request_field_has_structured_agent_guidance(self) -> None:
        result = describe_action(
            "ListBill",
            section="request",
            field_query="BillingMode",
            include_overview=True,
        )
        self.assertEqual(VERSION, result["tool_version"])
        field = result["request"]["fields"][0]
        self.assertNotIn("description", field)
        self.assertNotIn("raw_description", field)
        self.assertEqual("string[]", field["type"])
        self.assertFalse(field["required"])
        accepted = field["agent_guidance"]["accepted_values"]
        self.assertEqual({"1", "2", "3", "4", "5"}, {item["value"] for item in accepted})
        overview = result["request"]["overview"]
        self.assertEqual(["BillingMode"], overview["optional_fields"])
        self.assertNotIn("capability", result)
        self.assertLess(len(json.dumps(result, ensure_ascii=False)), 2000)

    def test_cost_analysis_field_extracts_enum_and_condition(self) -> None:
        cost_type = describe_action(
            "ListCostAnalysisOpenApi",
            section="request",
            field_query="CostType",
        )["request"]["fields"][0]
        accepted_cost_types = {item["value"] for item in cost_type["agent_guidance"]["accepted_values"]}
        self.assertEqual({"0", "1", "2", "4", "5", "6"}, set(accepted_cost_types))
        self.assertNotIn("3", accepted_cost_types)
        self.assertNotIn("7", accepted_cost_types)
        dimension = describe_action(
            "ListCostAnalysisOpenApi",
            section="request",
            field_query="ClassifyDimension",
        )["request"]["fields"][0]
        accepted = dimension["agent_guidance"]["accepted_values"]
        self.assertIn("3", {item["value"] for item in accepted})
        value = describe_action(
            "ListCostAnalysisOpenApi",
            section="request",
            field_query="ClassifyDimensionValue",
        )["request"]["fields"][0]
        self.assertEqual(
            {
                "ClassifyDimension=10",
                "ClassifyDimension=11",
                "ClassifyDimension=15",
            },
            set(value["agent_guidance"]["conditionally_required_when"]),
        )
        overview = describe_action(
            "ListCostAnalysisOpenApi",
            section="request",
            field_query="ClassifyDimensionValue",
            include_overview=True,
        )["request"]["overview"]
        self.assertIn("CostType", overview["required_fields"])
        self.assertIn("Limit", overview["required_fields"])
        self.assertIn("ClassifyDimensionValue", overview["optional_fields"])
        self.assertTrue(overview["conditional_rules"])

    def test_date_format_is_machine_readable(self) -> None:
        field = describe_action(
            "ListCostAnalysisOpenApi",
            section="request",
            field_query="BeginTimeStr",
        )["request"]["fields"][0]
        self.assertEqual(
            {
                "TimeGranularity=0": "YYYY-MM-01",
                "TimeGranularity=1": "YYYY-MM-DD",
            },
            field["agent_guidance"]["format_by_condition"],
        )
        self.assertEqual("YYYY-MM-DD", field["constraints"]["date_format"])
        self.assertEqual(24, field["constraints"]["max_age_months"])
        self.assertEqual(
            {"max_age_months": 24},
            field["agent_guidance"]["date_range"],
        )

    def test_month_range_constraints_are_machine_readable(self) -> None:
        bill_period = describe_action(
            "ListBill",
            section="request",
            field_query="BillPeriod",
        )["request"]["fields"][0]
        self.assertEqual("YYYY-MM", bill_period["constraints"]["date_format"])
        self.assertEqual(24, bill_period["constraints"]["max_age_months"])
        self.assertEqual(
            {"max_age_months": 24},
            bill_period["agent_guidance"]["date_range"],
        )

        amortized_month = describe_action(
            "ListAmortizedCostBillMonthly",
            section="request",
            field_query="AmortizedMonth",
        )["request"]["fields"][0]
        self.assertEqual("YYYY-MM", amortized_month["constraints"]["date_format"])
        self.assertEqual("2023-04", amortized_month["constraints"]["min_month"])
        self.assertEqual(24, amortized_month["constraints"]["max_age_months"])
        self.assertEqual(
            {"min_month": "2023-04", "max_age_months": 24},
            amortized_month["agent_guidance"]["date_range"],
        )

        amortized_bill_period = describe_action(
            "ListAmortizedCostBillMonthly",
            section="request",
            field_query="BillPeriod",
        )["request"]["fields"][0]
        self.assertEqual("2023-04", amortized_bill_period["constraints"]["min_month"])
        self.assertEqual(24, amortized_bill_period["constraints"]["max_age_months"])

        amortized_day = describe_action(
            "ListAmortizedCostBillDetail",
            section="request",
            field_query="AmortizedDay",
        )["request"]["fields"][0]
        self.assertEqual("YYYY-MM-DD", amortized_day["constraints"]["date_format"])
        self.assertEqual("2023-04-01", amortized_day["constraints"]["min_date"])
        self.assertEqual(24, amortized_day["constraints"]["max_age_months"])

    def test_response_includes_interpretation_in_compact_mode(self) -> None:
        response = describe_action(
            "ListBill",
            section="response",
        )["response"]
        list_field = next(
            item for item in response["fields"] if item["path"] == "List"
        )
        self.assertGreater(list_field["child_count"], 0)
        self.assertEqual(
            "Result.List",
            response["interpretation"]["records_path"],
        )
        self.assertIsNotNone(response["interpretation"]["pagination"])

    def test_cost_analysis_response_nested_fields_expand_for_agent(self) -> None:
        response = describe_action(
            "ListCostAnalysisOpenApi",
            section="response",
            field_query="CostData",
            expand=True,
        )["response"]
        paths = [field["path"] for field in response["fields"]]
        self.assertIn("CostData[].Costs[].TimeStr", paths)
        self.assertIn("CostData[].Costs[].Amount", paths)
        amount = next(
            field
            for field in response["fields"]
            if field["path"] == "CostData[].Costs[].Amount"
        )
        self.assertTrue(amount["agent_guidance"])

        costs = describe_action(
            "ListCostAnalysisOpenApi",
            section="response",
            field_query="CostData.Costs",
            expand=True,
        )["response"]
        self.assertEqual(
            [
                "CostData[].Costs",
                "CostData[].Costs[].TimeStr",
                "CostData[].Costs[].Amount",
            ],
            [field["path"] for field in costs["fields"]],
        )

    def test_cost_analysis_response_interpretation_explains_flattening(self) -> None:
        interpretation = describe_action(
            "ListCostAnalysisOpenApi",
            section="response",
        )["response"]["interpretation"]
        self.assertEqual("Result.CostData", interpretation["records_path"])
        flattening = interpretation["flattening"]
        self.assertEqual("cost_data_costs", flattening["strategy"])
        self.assertEqual("Result.CostData[].Costs[]", flattening["source_path"])
        self.assertEqual(["ClassifyDimension", "ClassifyItem"], flattening["parent_fields_carried"])
        self.assertEqual(["TimeStr", "Amount"], flattening["child_fields"])
        self.assertEqual("TimeStr", flattening["time_field"])
        self.assertEqual("Amount", flattening["amount_field"])

    def test_reconciliation_fields_are_exposed_by_bill_actions(self) -> None:
        blocked_roots = ("PaidAmount", "UnpaidAmount", "CreditCarriedAmount")
        bill_actions = {
            "ListBill",
            "ListBillOverviewByProd",
            "ListBillOverviewByCategory",
        }
        for action_name, action in ACTION_SCHEMAS.items():
            names: list[str] = []

            def collect(elements):
                for element in elements:
                    names.append(element.name)
                    collect(element.children)

            collect(action.response_elements)
            matching = [
                name
                for name in names
                if any(name == root or name.endswith(root) for root in blocked_roots)
            ]
            with self.subTest(action=action_name):
                if action_name in bill_actions:
                    self.assertEqual(set(blocked_roots), set(matching))
                else:
                    self.assertEqual([], matching)
        paid_matches = find_field("PaidAmount", "response")["matches"]
        unpaid_matches = find_field("UnpaidAmount", "response")["matches"]
        credit_matches = find_field("CreditCarriedAmount", "response")["matches"]
        self.assertEqual(bill_actions, {item["action"] for item in paid_matches})
        self.assertEqual(bill_actions, {item["action"] for item in unpaid_matches})
        self.assertEqual(bill_actions, {item["action"] for item in credit_matches})
        overview = describe_action(
            "ListBillOverviewByProd",
            section="response",
            field_query="PaidAmount",
        )["response"]["fields"][0]
        self.assertEqual("List[].PaidAmount", overview["path"])

    def test_describe_accepts_multiple_response_fields(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "describe",
                "ListBillOverviewByProd",
                "--section",
                "response",
                "--field",
                "ProductZh",
                "--field",
                "PayableAmount",
                "--field",
                "OriginalBillAmount",
                "--field",
                "DiscountBillAmount",
                "--field",
                "PaidAmount",
                "--expand",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        response = json.loads(completed.stdout)["response"]
        self.assertEqual(
            ["ProductZh", "PayableAmount", "OriginalBillAmount", "DiscountBillAmount", "PaidAmount"],
            response["requested_fields"],
        )
        self.assertEqual(
            {
                "List[].ProductZh",
                "List[].PayableAmount",
                "List[].OriginalBillAmount",
                "List[].DiscountBillAmount",
                "List[].PaidAmount",
            },
            {field["path"] for field in response["fields"]},
        )

    def test_cli_field_query_uses_minimal_payload_unless_overview_included(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "describe",
                "ListBillDetail",
                "--section",
                "request",
                "--field",
                "GroupPeriod",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        request = payload["request"]
        self.assertNotIn("overview", request)
        self.assertIn("field_decisions", request)
        self.assertNotIn("preaggregation_guidance", completed.stdout)
        self.assertNotIn("recommended_combinations", completed.stdout)
        self.assertLess(len(completed.stdout), 1800)

        expanded = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "describe",
                "ListBillDetail",
                "--section",
                "request",
                "--field",
                "GroupPeriod",
                "--include",
                "overview",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        request_with_overview = json.loads(expanded.stdout)["request"]
        self.assertIn(
            "preaggregation_guidance",
            request_with_overview["overview"],
        )

    def test_cost_schema_outputs_json_schema_with_agent_decisions(self) -> None:
        payload = schema_contract(
            "ListBillDetail",
            section="request",
            field_queries=["GroupPeriod"],
        )
        request_schema = payload["request_json_schema"]
        self.assertEqual("object", request_schema["type"])
        self.assertEqual(["GroupPeriod"], list(request_schema["properties"]))
        self.assertEqual([0, 1, 2], request_schema["properties"]["GroupPeriod"]["enum"])
        decision = payload["agent_decisions"]["GroupPeriod"]
        self.assertIn("2", decision["values"])
        self.assertNotIn("business_constraints", payload)

        completed = subprocess.run(
            [
                sys.executable,
                str(COST_SCRIPT),
                "schema",
                "--action",
                "ListBillDetail",
                "--section",
                "request",
                "--field",
                "GroupPeriod",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        cli_payload = json.loads(completed.stdout)
        self.assertEqual(["GroupPeriod"], list(cli_payload["request_json_schema"]["properties"]))
        self.assertIn("agent_decisions", cli_payload)
        self.assertLess(len(completed.stdout), 1800)

    def test_cost_schema_list_actions_rejects_action_contract_options(self) -> None:
        for options in (
            ["--action", "NoSuchAction", "--field", "NoSuchField"],
            ["--action", "ListBillDetail"],
            ["--field", "GroupPeriod"],
            ["--section", "both"],
            ["--include-guidance"],
        ):
            with self.subTest(options=options):
                completed = subprocess.run(
                    [sys.executable, str(COST_SCRIPT), "schema", "--list-actions", *options],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(2, completed.returncode)
                self.assertEqual("", completed.stderr)
                envelope = json.loads(completed.stdout)
                error = envelope["_meta"]["error"]
                self.assertEqual("INVALID_ARGUMENT", error["code"])

    def test_cost_schema_can_include_business_constraints_explicitly(self) -> None:
        payload = schema_contract(
            "ListBillDetail",
            section="request",
            field_queries=["GroupPeriod"],
            include_guidance=True,
        )
        self.assertTrue(payload["business_constraints"])
        self.assertIn("preaggregation_guidance", payload)
        self.assertIn("field_grain_guidance", payload)
        self.assertEqual(
            {"GroupPeriod": 2, "GroupTerm": 0},
            payload["preaggregation_guidance"]["recommended_combinations"][0]["request_patch"],
        )

        completed = subprocess.run(
            [
                sys.executable,
                str(COST_SCRIPT),
                "schema",
                "--action",
                "ListBillDetail",
                "--section",
                "request",
                "--field",
                "GroupPeriod",
                "--include-guidance",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        cli_payload = json.loads(completed.stdout)
        self.assertIn("preaggregation_guidance", cli_payload)
        self.assertIn("field_grain_guidance", cli_payload)

    def test_cost_schema_response_field_exposes_grain_decision_before_query(self) -> None:
        expected = {
            "Count": {"GroupTerm": 0},
            "BillDetailId": {"GroupPeriod": 2, "GroupTerm": 0},
            "InstanceNo": {"GroupTerm": 0},
        }
        for field_name, required_request in expected.items():
            with self.subTest(field=field_name):
                payload = schema_contract(
                    "ListBillDetail",
                    section="response",
                    field_queries=[field_name],
                )
                decision = payload["response_field_decisions"][field_name]
                self.assertEqual(required_request, decision["required_request"])
                self.assertNotIn("preaggregation_guidance", payload)
                self.assertNotIn("field_grain_guidance", payload)

        instance = schema_contract(
            "ListBillDetail",
            section="response",
            field_queries=["InstanceNo"],
        )["response_field_decisions"]["InstanceNo"]
        self.assertEqual({"GroupTerm": [0, 1]}, instance["available_request_values"])

    def test_response_field_without_registered_grain_rule_keeps_schema_without_decision(self) -> None:
        payload = schema_contract(
            "ListBillDetail",
            section="response",
            field_queries=["PayableAmount", "Product"],
        )
        properties = payload["response_json_schema"]["properties"]["List"]["items"]["properties"]
        self.assertEqual({"PayableAmount", "Product"}, set(properties))
        self.assertNotIn("response_field_decisions", payload)

    def test_public_cost_cli_exposes_response_field_grain_decision(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(COST_SCRIPT),
                "schema",
                "--action",
                "ListSplitBillDetail",
                "--section",
                "response",
                "--field",
                "SplitItemID",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        decision = json.loads(completed.stdout)["response_field_decisions"]["SplitItemID"]
        self.assertEqual({"GroupPeriod": 2}, decision["required_request"])

    def test_public_cost_cli_accepts_comma_separated_fields(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(COST_SCRIPT),
                "schema",
                "--action",
                "ListBillDetail",
                "--section",
                "response",
                "--field",
                "BillID, BillPeriod,InstanceNo",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        properties = payload["response_json_schema"]["properties"]["List"]["items"]["properties"]
        self.assertEqual({"BillID", "BillPeriod", "InstanceNo"}, set(properties))
        self.assertEqual({"BillID", "InstanceNo"}, set(payload["response_field_decisions"]))

    def test_multiple_fields_report_all_missing_names(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "describe",
                "ListBillOverviewByProd",
                "--section",
                "response",
                "--field",
                "ProductName",
                "--field",
                "OriginalAmount",
                "--field",
                "DiscountAmount",
                "--field",
                "PaidAmount",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, completed.returncode)
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "describe",
                "ListBillDetail",
                "--section",
                "response",
                "--field",
                "PaidAmount",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, completed.returncode)

    def test_settlement_type_uses_complete_shared_response_semantics(self) -> None:
        detail = describe_action(
            "ListBillDetail",
            section="response",
            field_query="SettlementType",
        )["response"]["fields"][0]
        accepted = detail["agent_guidance"]["accepted_values"]
        self.assertEqual(
            {
                "非结算": "non-settle",
                "结算": "settle",
                "Quota结算": "quota-settle",
            },
            {item["value"]: item["request_value"] for item in accepted},
        )
        self.assertEqual("response_value", detail["agent_guidance"]["value_for_csv_filter"])
        self.assertEqual(
            {"非结算", "结算", "Quota结算"},
            {item["response_value"] for item in accepted},
        )
        self.assertEqual(
            {"service_or_cli"},
            {item["localized_by"] for item in accepted},
        )
        matches = find_field("SettlementType", "response")["matches"]
        self.assertTrue(
            all(
                len(match["agent_guidance"]["accepted_values"]) == 3
                for match in matches
            )
        )

    def test_response_enum_guidance_uses_csv_values_and_keeps_request_values(self) -> None:
        response = describe_action(
            "ListBill",
            section="response",
            field_query=["PayStatus", "BusinessMode", "SettlementType", "BillCategoryParent"],
        )["response"]["fields"]
        fields = {field["path"].rsplit(".", 1)[-1]: field["agent_guidance"] for field in response}
        self.assertEqual(
            {
                "已结清": "CompletedSettle",
                "未结清": "PartSettle",
                "未结算": "Unsettle",
            },
            {item["value"]: item["request_value"] for item in fields["PayStatus"]["accepted_values"]},
        )
        self.assertEqual(
            {
                "财务托管": "1",
                "代销业务": "2",
            },
            {
                item["value"]: item["request_value"]
                for item in fields["BusinessMode"]["accepted_values"]
                if item["value"] in {"财务托管", "代销业务"}
            },
        )
        self.assertEqual(
            "response_value",
            fields["PayStatus"]["value_for_csv_filter"],
        )
        self.assertEqual(
            {
                "消费": "consume",
                "退款": "refund",
                "调账": "transfer",
            },
            {item["value"]: item["request_value"] for item in fields["BillCategoryParent"]["accepted_values"]},
        )
        for guidance in fields.values():
            self.assertEqual(
                {item["value"] for item in guidance["accepted_values"]},
                {item["response_value"] for item in guidance["accepted_values"]},
            )

    def test_bill_category_response_guidance_uses_localized_csv_values(self) -> None:
        response = describe_action(
            "ListBillDetail",
            section="response",
            field_query="BillCategory",
        )["response"]["fields"][0]
        guidance = response["agent_guidance"]
        accepted = {
            item["value"]: item["request_value"]
            for item in guidance["accepted_values"]
        }
        self.assertEqual("response_value", guidance["value_for_csv_filter"])
        self.assertEqual("consume-use", accepted["消费-使用"])
        self.assertEqual("consume-TempUpgrade", accepted["消费-临时升配"])
        self.assertEqual("refund-DeliveryFailed", accepted["退款-交付失败"])
        self.assertEqual("consume-Commitment", accepted["消费-承诺消费"])
        self.assertNotIn("consume-use", accepted)

    def test_action_scoped_response_enum_keeps_code_when_service_returns_code(self) -> None:
        bill_mode = describe_action(
            "ListBill",
            section="response",
            field_query="BillingMode",
        )["response"]["fields"][0]["agent_guidance"]
        detail_mode = describe_action(
            "ListBillDetail",
            section="response",
            field_query="BillingMode",
        )["response"]["fields"][0]["agent_guidance"]
        self.assertNotIn("value_for_csv_filter", bill_mode)
        self.assertEqual(
            {"1": "1", "2": "2", "3": "3", "4": "4", "5": "5"},
            {item["value"]: item["request_value"] for item in bill_mode["accepted_values"]},
        )
        self.assertEqual("response_value", detail_mode["value_for_csv_filter"])
        self.assertEqual(
            {"包年包月": "1", "按量计费": "2", "承诺消费": "5"},
            {
                item["value"]: item["request_value"]
                for item in detail_mode["accepted_values"]
                if item["value"] in {"包年包月", "按量计费", "承诺消费"}
            },
        )

    def test_business_mode_response_enum_mapping(self) -> None:
        response = describe_action(
            "ListBillDetail",
            section="response",
            field_query=[
                "BusinessMode",
            ],
        )["response"]["fields"]
        fields = {field["path"].rsplit(".", 1)[-1]: field for field in response}
        business_mode = fields["BusinessMode"]["agent_guidance"]
        self.assertEqual(
            {
                "普通业务": "0",
                "财务托管": "1",
                "代销业务": "2",
                "代售业务": "3",
                "财务管理": "4",
                "代买业务": "5",
            },
            {item["value"]: item["request_value"] for item in business_mode["accepted_values"]},
        )
        self.assertEqual("response_value", business_mode["value_for_csv_filter"])

    def test_bill_detail_contract_exposes_unsupported_detail_grain_combinations(self) -> None:
        group_term = describe_action(
            "ListBillDetail",
            section="request",
            field_query="GroupTerm",
        )["request"]["fields"][0]
        guidance = group_term["agent_guidance"]
        self.assertEqual(
            [
                {"GroupPeriod": 2, "GroupTerm": 2},
                {"GroupPeriod": 2, "GroupTerm": 3},
            ],
            [
                {key: value for key, value in item.items() if key != "reason"}
                for item in guidance["unsupported_combinations"]
            ],
        )
        overview = describe_action(
            "ListBillDetail",
            section="request",
        )["request"]["overview"]
        self.assertIn("preaggregation_guidance", overview)

    def test_complex_filter_value_formats_are_structured(self) -> None:
        field = describe_action(
            "ListCostAnalysisOpenApi",
            section="request",
            field_query="FilterValue",
        )["request"]["fields"][0]
        guidance = field["agent_guidance"]
        formats = guidance["format_by_condition"]
        self.assertTrue({"FilterKey=5", "FilterKey=7", "FilterKey=10"} <= set(formats))
        details = {
            tuple(item["filter_keys"]): item
            for item in guidance["format_details"]
        }
        self.assertEqual(
            ['{"sms":["BE000383"]}', '{"ark_bd":["BE150994"]}'],
            details[(5,)]["example"],
        )
        self.assertEqual(
            ['{"":[""]}', '{"R000017":["ZoneA"]}'],
            details[(7,)]["example"],
        )
        self.assertEqual(
            [{"voKey2": ["v2", "v3"], "voKey1": ["v1", "v11"]}],
            details[(10,)]["example"],
        )
        self.assertEqual(["adjust_code"], details[(16,)]["example"])
        self.assertEqual(["aaa"], details[(17,)]["example"])

    def test_zero_minimum_constraint_is_preserved(self) -> None:
        field = describe_action(
            "ListBill",
            section="request",
            field_query="Offset",
        )["request"]["fields"][0]
        self.assertEqual("0", field["constraints"]["minimum"])

    def test_non_list_action_has_safe_empty_row_fields(self) -> None:
        self.assertEqual({}, ACTION_SCHEMAS["ListCostAnalysisOpenApi"].row_fields)

    def test_split_detail_identifier_fields_require_detail_grain(self) -> None:
        for field_name in ("BillID", "BillDetailId", "SplitBillDetailId", "SplitItemID"):
            with self.subTest(field=field_name):
                field = describe_action(
                    "ListSplitBillDetail",
                    section="response",
                    field_query=field_name,
                )["response"]["fields"][0]
                grain = field["agent_guidance"]["grain_availability"]
                self.assertEqual({"GroupPeriod": 2}, grain["required_request"])

        request = describe_action(
            "ListSplitBillDetail",
            section="request",
            field_query="GroupPeriod",
            include_overview=True,
        )["request"]["overview"]
        matrix = request["field_grain_guidance"]
        self.assertEqual(
            ["BillID", "BillDetailId", "SplitBillDetailId", "SplitItemID"],
            matrix["detail_identifier_fields"],
        )
        self.assertEqual({"GroupPeriod": 2}, matrix["detail_request_patch"])

    def test_bill_detail_field_grain_guidance_covers_high_risk_fields(self) -> None:
        expected = {
            "Count": {"GroupTerm": 0},
            "Price": {"GroupTerm": 0},
            "PriceUnit": {"GroupTerm": 0},
            "BillID": {"GroupPeriod": 2, "GroupTerm": 0},
            "BillDetailId": {"GroupPeriod": 2, "GroupTerm": 0},
            "InstanceNo": {"GroupTerm": 0},
        }
        for field_name, required_request in expected.items():
            with self.subTest(field=field_name):
                field = describe_action(
                    "ListBillDetail",
                    section="response",
                    field_query=field_name,
                )["response"]["fields"][0]
                grain = field["agent_guidance"]["grain_availability"]
                self.assertEqual(required_request, grain["required_request"])
        instance = describe_action(
            "ListBillDetail", section="response", field_query="InstanceNo"
        )["response"]["fields"][0]["agent_guidance"]["grain_availability"]
        self.assertEqual({"GroupTerm": [0, 1]}, instance["available_request_values"])

        request = describe_action(
            "ListBillDetail",
            section="request",
            field_query="GroupTerm",
            include_overview=True,
        )["request"]["overview"]
        self.assertIn("field_grain_guidance", request)

    def test_include_raw_is_opt_in(self) -> None:
        compact = describe_action(
            "ListBill",
            section="request",
            field_query="BillingMode",
        )["request"]["fields"][0]
        raw = describe_action(
            "ListBill",
            section="request",
            field_query="BillingMode",
            include_raw=True,
        )["request"]["fields"][0]
        self.assertNotIn("raw_description", compact)
        self.assertTrue(raw["raw_description"])

    def test_find_compares_action_local_contracts(self) -> None:
        result = find_field("BillingMode", "request")
        self.assertEqual(VERSION, result["tool_version"])
        self.assertTrue(result["matches"])
        self.assertTrue(result["uniform_in_current_contracts"])

    def test_unknown_action_returns_structured_nonzero_error(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "describe", "UnknownAction"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, completed.returncode)
        error = json.loads(completed.stderr)
        self.assertEqual("error", error["status"])


if __name__ == "__main__":
    unittest.main()
