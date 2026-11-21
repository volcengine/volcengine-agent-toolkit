from __future__ import annotations

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "core" / "volcengine-cost" / "scripts"))

from cost_query.billing.contracts import build_static_contract_payload
from cost_query.billing.contracts.registry import UPSTREAM_ACTION_CONTRACTS


class CostChangeContractTest(unittest.TestCase):
    def contract(self, action):
        self.assertIn(action, UPSTREAM_ACTION_CONTRACTS, "归因接口尚未登记")
        return UPSTREAM_ACTION_CONTRACTS[action]

    def cases(self):
        return (
            ("QueryCostChangeDimensions", {
                "CurrentPeriod": "2026-06-01", "BasePeriod": "2026-05-01",
                "CandidateDimensions": ["product"], "Metric": 3,
                "Filters": {"project": "p1"},
            }),
            ("QueryCostChangeAmountComponents", {
                "CurrentPeriod": "2026-06-01", "BasePeriod": "2026-05-01",
                "Metric": 3, "Filters": {"product": "ML", "charge_item_code": "ci"},
            }),
            ("QueryCostChangeDrivers", {
                "current_period": "2026-06-01", "base_period": "2026-05-01",
                "Metric": "original_bill_amount",
                "filters": {"instance_no": "i1", "charge_item_code": "ci"},
            }),
        )

    def test_wire_requests_preserve_casing_metric_and_scope(self):
        for action, body in self.cases():
            with self.subTest(action=action):
                model = self.contract(action).request_model.model_validate(body)
                self.assertEqual(body, model.model_dump(by_alias=True, exclude_none=True))

    def test_rejects_missing_charge_item_and_identity_injection(self):
        for action, body in self.cases():
            with self.subTest(action=action):
                model = self.contract(action).request_model
                with self.assertRaises(ValidationError):
                    model.model_validate({**body, "AccountID": "123"})
                key = "filters" if action.endswith("Drivers") else "Filters"
                with self.assertRaises(ValidationError):
                    model.model_validate({**body, key: {**body[key], "token": "secret"}})
                if not action.endswith("Dimensions"):
                    for filters in ({}, {"charge_item_code": ""}, {"charge_item_code": "  "}):
                        with self.assertRaises(ValidationError):
                            model.model_validate({**body, key: filters})

    def test_optional_scope_filters_reject_explicit_null(self):
        for action, body in self.cases():
            model = self.contract(action).request_model
            key = "filters" if action.endswith("Drivers") else "Filters"
            for field in ("product", "project", "region_code", "instance_no"):
                with self.subTest(action=action, field=field), self.assertRaises(ValidationError):
                    model.model_validate({**body, key: {**body[key], field: None}})

    def test_dimensions_accepts_exactly_one_supported_dimension(self):
        action, body = self.cases()[0]
        model = self.contract(action).request_model
        for dimensions in ([], ["product", "project"], ["unknown"]):
            with self.subTest(dimensions=dimensions), self.assertRaises(ValidationError):
                model.model_validate({**body, "CandidateDimensions": dimensions})

    def test_rejects_invalid_periods_and_wrong_metric(self):
        for action, body in self.cases():
            with self.subTest(action=action):
                model = self.contract(action).request_model
                key = "current_period" if action.endswith("Drivers") else "CurrentPeriod"
                for period in ("2026-13-01", "2026-06-02", "0000-06-01"):
                    with self.assertRaises(ValidationError):
                        model.model_validate({**body, key: period})
                with self.assertRaises(ValidationError):
                    model.model_validate({**body, "Metric": 2})

    def test_nested_responses_preserve_negative_amounts_and_factor_names(self):
        candidate_result = {
            "totalDiff": -20, "baseAmount": 100, "currentAmount": 80,
            "candidates": [{"dimension": "amount_component", "coverageRatio": 1,
                            "values": [{"valueKey": "refund", "valueName": "退款",
                                        "deltaAmount": -20, "baseAmount": 0,
                                        "currentAmount": -20, "contributionRatio": 1}]}],
        }
        driver_result = {
            "total_diff": -20, "base_amount": 100, "current_amount": 80,
            "contributions": [{"dimension": "usage", "dimension_name": "用量",
                               "contribution": -20, "base_amount": 100, "current_amount": 80}],
        }
        for action, _ in self.cases():
            with self.subTest(action=action):
                body = driver_result if action.endswith("Drivers") else candidate_result
                model = self.contract(action).response_model.model_validate(body)
                self.assertEqual(body, model.model_dump(by_alias=True, exclude_none=True))

    def test_static_discovery_retains_nested_request_and_response_fields(self):
        payload = build_static_contract_payload()["actions"]
        for action, _ in self.cases():
            with self.subTest(action=action):
                self.contract(action)
                fields = {item["name"]: item for item in payload[action]["request_params"]}
                key = "filters" if action.endswith("Drivers") else "Filters"
                filters = {item["name"]: item for item in fields[key]["children"]}
                self.assertEqual({"product", "project", "instance_no", "region_code", "charge_item_code"}, set(filters))
                self.assertEqual(not action.endswith("Dimensions"), filters["charge_item_code"]["is_required"])
                response = {item["name"]: item for item in payload[action]["response_elements"]}
                nested = response["contributions" if action.endswith("Drivers") else "candidates"]
                self.assertTrue(nested["is_array"])
                self.assertTrue(nested["children"])


if __name__ == "__main__":
    unittest.main()
