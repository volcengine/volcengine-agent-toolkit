from __future__ import annotations

import ast
import sys
import unittest
from collections import defaultdict
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "skills" / "core" / "volcengine-cost"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from cost_query.common.errors import BillingQueryError, ErrorCode  # noqa: E402
from cost_query.utils.arguments import BillingArgumentParser  # noqa: E402
from cost_query.utils.billing import ISO8601_UTC_PATTERN, TOKEN_PAGE_SIZE_LIMITS  # noqa: E402
from cost_query.utils.datetimes import parse_iso_datetime_utc  # noqa: E402
from cost_query.utils.decimals import decimal_value, exact_sum, format_decimal  # noqa: E402
from cost_query.utils.errors import invalid_argument  # noqa: E402
from cost_query.utils.rows import row_decimal, row_text  # noqa: E402
from cost_query.utils.text import normalize_field_path  # noqa: E402


class SharedUtilsBehaviorTest(unittest.TestCase):
    def test_row_decimal_and_datetime_helpers_preserve_existing_semantics(self) -> None:
        self.assertEqual("1.20", row_text({"amount": " 1.20 "}, "amount"))
        self.assertEqual("", row_text({}, "amount"))
        self.assertEqual(Decimal("1.20"), row_decimal({"amount": "1.20"}, "amount"))
        self.assertIsNone(row_decimal({"amount": "NaN"}, "amount"))
        self.assertEqual(
            "+00:00",
            parse_iso_datetime_utc("2026-01-01T00:00:00Z").strftime("%z")[:3] + ":00",
        )
        self.assertIsNone(parse_iso_datetime_utc("not-a-time"))

    def test_decimal_text_and_billing_constants_are_shared(self) -> None:
        self.assertEqual(Decimal("3.30"), exact_sum([Decimal("1.10"), Decimal("2.20")]))
        self.assertEqual("3.30", format_decimal(Decimal("3.30")))
        self.assertEqual(Decimal("0.000001"), decimal_value("0.000001"))
        self.assertEqual("list.couponamount", normalize_field_path("List[].CouponAmount"))
        self.assertEqual(
            {"ListResourcePackages": 20, "ListPackageUsageDetails": 50},
            TOKEN_PAGE_SIZE_LIMITS,
        )
        self.assertRegex("2026-01-01T00:00:00Z", ISO8601_UTC_PATTERN)

    def test_shared_argument_and_error_helpers_use_standard_error_contract(self) -> None:
        parser = BillingArgumentParser(add_help=False)
        parser.add_argument("--required", required=True)
        with self.assertRaises(BillingQueryError) as context:
            parser.parse_args([])
        self.assertEqual(ErrorCode.INVALID_ARGUMENT, context.exception.code)
        self.assertIn("参数无效", str(context.exception))

        error = invalid_argument("invalid", field="Amount")
        self.assertEqual(ErrorCode.INVALID_ARGUMENT, error.code)
        self.assertEqual({"field": "Amount"}, error.details)


class SharedUtilsStructureTest(unittest.TestCase):
    def test_scripts_have_no_identical_function_class_or_top_level_declaration(self) -> None:
        functions: defaultdict[str, list[str]] = defaultdict(list)
        classes: defaultdict[str, list[str]] = defaultdict(list)
        declarations: defaultdict[str, list[str]] = defaultdict(list)

        for path in sorted(SCRIPTS.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            relative = path.relative_to(SCRIPTS)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    clone = ast.parse(ast.unparse(node)).body[0]
                    clone.name = "_shared_name"
                    functions[ast.dump(clone, include_attributes=False)].append(
                        f"{relative}:{node.lineno}:{node.name}"
                    )
                elif isinstance(node, ast.ClassDef):
                    clone = ast.parse(ast.unparse(node)).body[0]
                    clone.name = "_SharedName"
                    classes[ast.dump(clone, include_attributes=False)].append(
                        f"{relative}:{node.lineno}:{node.name}"
                    )
            for node in tree.body:
                if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names = [target.id for target in targets if isinstance(target, ast.Name)]
                if names:
                    declarations[ast.dump(node.value, include_attributes=False)].append(
                        f"{relative}:{node.lineno}:{','.join(names)}"
                    )

        duplicates = [
            items
            for groups in (functions, classes, declarations)
            for items in groups.values()
            if len(items) > 1
        ]
        self.assertEqual([], duplicates)


if __name__ == "__main__":
    unittest.main()
