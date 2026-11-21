"""Machine-readable public contract for the open cost-analysis rule library."""

from __future__ import annotations

import dataclasses
import inspect
import types
from enum import Enum
from typing import Any, Sequence, get_args, get_origin, get_type_hints, is_typeddict

from . import cost_rules
from .errors import BillingQueryError, ErrorCode, ExitCode


def _classify_public_symbols() -> tuple[tuple[str, ...], tuple[str, ...]]:
    functions: list[str] = []
    types_: list[str] = []
    for name in cost_rules.__all__:
        value = getattr(cost_rules, name)
        if inspect.isfunction(value):
            functions.append(name)
        elif inspect.isclass(value):
            types_.append(name)
        else:
            raise TypeError(f"cost_rules 公开符号类型不受支持: {name}")
    return tuple(functions), tuple(types_)


_PUBLIC_FUNCTIONS, _PUBLIC_TYPES = _classify_public_symbols()

FUNCTION_GUIDANCE: dict[str, dict[str, str]] = {
    "load_cost_csv": {
        "purpose": "读取费用 CSV，拒绝非 CSV 输入，返回带名称的 columns 和 rows。",
        "use_when": "数据处理代码需要读取当前查询产物或用户指定 CSV 时按需使用。",
    },
    "load_cost_metadata": {
        "purpose": "读取同名或显式 metadata，返回带名称的 path、metadata 和 warnings。",
        "use_when": "需要继承 coverage、freshness、failed queries 或来源证据时使用。",
    },
    "parse_decimal": {
        "purpose": "把金额或数值解析为 Decimal；空值只有显式 allow_empty 时才返回 None。",
        "use_when": "处理可为空金额，且不能把缺失金额当作 0 时使用。",
    },
    "require_decimal": {
        "purpose": "把非空数值解析为 Decimal，禁止 float。",
        "use_when": "SUM、AVG、占比、差额等数值计算前使用。",
    },
    "format_decimal": {
        "purpose": "把 Decimal 以非科学计数法稳定输出。",
        "use_when": "写入 CSV、JSON 或回答金额计算结果时使用。",
    },
    "typed_value": {
        "purpose": "根据已解析字段的类型读取字符串值，返回 Decimal、日期、账期、字符串或 None。",
        "use_when": "自定义筛选、比较或排序需要按字段类型转换当前行值时使用。",
    },
    "require_registered_money_metric": {
        "purpose": "确认聚合指标是已登记金额字段，避免把未知数字列当费用。",
        "use_when": "对 SUM、AVG、占比、TopN 等金额指标执行前使用。",
    },
    "resolve_money_currency": {
        "purpose": "找到金额字段对应的实际币种列，例如 Currency 或 CurrencySettlement。",
        "use_when": "自定义分析需要读取或显式处理金额对应币种时使用。",
    },
    "ensure_money_grouping": {
        "purpose": "为金额聚合补齐币种分组，返回最终分组字段和本次隐式加入的币种字段。",
        "use_when": "数据处理代码需要 SUM、AVG、TopN、占比等金额聚合辅助规则时按需使用。",
    },
    "evidence_from_metadata": {
        "purpose": "把查询 metadata 转为结论范围、完整性、时效和失败分片证据。",
        "use_when": "回答或分析产物需要继承查询证据时使用。",
    },
    "public_columns": {
        "purpose": "按 Action 过滤对外可用字段。",
        "use_when": "生成面向用户的输出表头，避免重新暴露被屏蔽字段。",
    },
    "public_rows": {
        "purpose": "按 Action 过滤对外可用行字段。",
        "use_when": "读取或投影 CSV 行后，输出给用户前使用。",
    },
    "atomic_write_csv": {
        "purpose": "原子写入 CSV，避免中途失败留下半文件。",
        "use_when": "正式分析、导出或可复现产物需要保存结果 CSV 时使用。",
    },
    "atomic_write_json": {
        "purpose": "原子写入 JSON。",
        "use_when": "正式分析需要保存 JSON 产物时使用。",
    },
}

FUNCTION_ERRORS: dict[str, list[dict[str, str]]] = {
    "load_cost_csv": [
        {"code": "INVALID_ARGUMENT", "when": "输入不是存在的 CSV，或 CSV 结构不可用。"},
    ],
    "load_cost_metadata": [
        {"code": "INVALID_ARGUMENT", "when": "显式 metadata 不存在、不是 JSON object 或缺少完整性证据。"},
    ],
    "parse_decimal": [
        {"code": "INVALID_ARGUMENT", "when": "值缺失但未允许为空、不是 Decimal 或不是有限数。"},
    ],
    "require_decimal": [
        {"code": "INVALID_ARGUMENT", "when": "值缺失、不是 Decimal 或不是有限数。"},
    ],
    "typed_value": [
        {"code": "INVALID_ARGUMENT", "when": "数值、日期或账期不符合已解析字段类型。"},
    ],
    "require_registered_money_metric": [
        {"code": "INVALID_ARGUMENT", "when": "字段不是已登记的可聚合金额指标。"},
    ],
    "resolve_money_currency": [
        {"code": "INVALID_ARGUMENT", "when": "金额字段匹配到多个等价币种列。"},
    ],
    "ensure_money_grouping": [
        {"code": "INVALID_ARGUMENT", "when": "金额聚合缺少对应币种列或币种列不唯一。"},
    ],
    "evidence_from_metadata": [
        {"code": "INVALID_ARGUMENT", "when": "failed_queries 不是数组或 action 不是字符串。"},
    ],
    "atomic_write_csv": [
        {"code": "INVALID_ARGUMENT", "when": "输出不是 .csv。"},
        {"code": "OUTPUT_EXISTS", "when": "目标已存在且 overwrite=False。"},
    ],
    "atomic_write_json": [
        {"code": "OUTPUT_EXISTS", "when": "目标已存在且 overwrite=False。"},
    ],
}

METHOD_ERRORS: dict[str, list[dict[str, str]]] = {
    "FieldResolver.resolve": [
        {"code": "UNSUPPORTED_FIELD", "when": "当前 CSV 不存在该字段。"},
        {"code": "INVALID_ARGUMENT", "when": "字段表达为空或匹配到多个实际列。"},
    ],
}

TYPE_GUIDANCE: dict[str, dict[str, Any]] = {
    "FieldResolver": {
        "purpose": "把用户或标准字段表达解析为当前 CSV 中唯一存在的实际字段。",
        "methods": ("resolve",),
        "constructor_errors": [
            {"code": "INVALID_ARGUMENT", "when": "输入缺少表头或包含重复列名。"},
        ],
    },
    "FieldRef": {
        "purpose": "已解析字段的公开引用；由 FieldResolver.resolve 返回，通常不直接构造。",
        "methods": ("to_dict",),
        "fields": {
            "requested": "调用者最初传入的字段表达，主要用于报错和追踪。",
            "column": "当前 CSV 的实际列名；读取 row、分组键和输出列时使用。",
            "canonical": "费用规则内部的标准化语义键；不要把它当作 CSV 列名读取 row。",
            "field_type": "字段类型枚举；把 FieldRef 传给 typed_value 等规则函数。",
            "type_source": "类型判定来源：registry 表示已登记，inferred 表示根据当前值推断。",
        },
    },
    "FieldType": {
        "purpose": "费用字段的公开类型枚举；需要序列化时使用成员的 value。",
    },
    "FieldDescriptor": {
        "purpose": "FieldRef.to_dict 生成的可序列化字段证据。",
        "fields": {
            "field": "当前 CSV 的实际列名。",
            "field_type": "FieldType.value 字符串。",
        },
    },
    "CostCsv": {
        "purpose": "load_cost_csv 返回的带名称结果；既可属性访问，也兼容 tuple 解包。",
    },
    "LoadedCostMetadata": {
        "purpose": "load_cost_metadata 返回的带名称结果；既可属性访问，也兼容 tuple 解包。",
    },
    "MoneyGrouping": {
        "purpose": "ensure_money_grouping 返回的带名称结果；既可属性访问，也兼容 tuple 解包。",
    },
    "CostEvidence": {
        "purpose": "查询证据转换后的公开结论范围；字段缺失表示来源 metadata 不提供该项。",
        "fields": {
            "claim_scope": "full_dataset、provisional_current_period、partial_dataset 或 input_file_only。",
            "coverage_status": "complete、provisional、partial 或 unknown。",
            "freshness_status": "known、partial 或 unknown。",
            "provenance_status": "known 或 unknown。",
            "failed_queries": "查询失败分片列表。",
            "source_action": "来源 Billing Action。",
        },
    },
}

INDEX_PURPOSE: dict[str, str] = {
    "load_cost_csv": "读取费用 CSV。",
    "load_cost_metadata": "读取查询证据。",
    "parse_decimal": "解析可空 Decimal。",
    "require_decimal": "解析必填 Decimal。",
    "format_decimal": "稳定格式化 Decimal。",
    "typed_value": "按字段类型读取值。",
    "require_registered_money_metric": "校验金额指标。",
    "resolve_money_currency": "解析金额对应币种。",
    "ensure_money_grouping": "补齐币种分组。",
    "evidence_from_metadata": "生成结论范围证据。",
    "public_columns": "过滤公开列。",
    "public_rows": "过滤公开行字段。",
    "atomic_write_csv": "原子写入 CSV。",
    "atomic_write_json": "原子写入 JSON。",
    "CostCsv": "CSV 列与行。",
    "CostEvidence": "结论范围与来源证据。",
    "FieldDescriptor": "可序列化字段描述。",
    "FieldRef": "已解析的实际字段引用。",
    "FieldResolver": "解析当前 CSV 字段。",
    "FieldType": "费用字段类型。",
    "LoadedCostMetadata": "已加载的查询证据。",
    "MoneyGrouping": "币种安全分组结果。",
}

EXAMPLES = (
    {
        "name": "resolve_and_read_field",
        "purpose": "解析实际列名，并按类型读取当前行；不要用 canonical 索引 row。",
        "show_for": ["FieldRef", "typed_value"],
        "symbols": ["FieldResolver", "FieldRef", "typed_value"],
        "code": (
            "from cost_query.common.cost_rules import FieldResolver, typed_value\n\n"
            "resolver = FieldResolver(columns, rows)\n"
            "amount_ref = resolver.resolve(\"PayableAmount\")\n"
            "raw = row.get(amount_ref.column, \"\")\n"
            "value = typed_value(raw, amount_ref)\n"
            "field_evidence = amount_ref.to_dict()"
        ),
    },
    {
        "name": "currency_safe_grouping",
        "purpose": "验证金额指标并把对应币种加入任意自定义聚合的分组键。",
        "show_for": ["ensure_money_grouping", "MoneyGrouping"],
        "symbols": [
            "FieldResolver",
            "require_registered_money_metric",
            "ensure_money_grouping",
            "MoneyGrouping",
        ],
        "code": (
            "from cost_query.common.cost_rules import ensure_money_grouping, require_registered_money_metric\n\n"
            "metric_ref = resolver.resolve(\"PayableAmount\")\n"
            "require_registered_money_metric(metric_ref, \"sum\")\n"
            "requested_groups = [resolver.resolve(name) for name in group_by]\n"
            "grouping = ensure_money_grouping(resolver, [metric_ref], requested_groups)\n"
            "key = tuple(row.get(ref.column, \"\") for ref in grouping.group_refs)"
        ),
    },
)


def _clean_type_text(value: str) -> str:
    cleaned = (
        value.replace("cost_query.common.cost_rules.", "")
        .replace("cost_query.common.fields.", "")
        .replace("pathlib.Path", "Path")
        .replace("decimal.Decimal", "Decimal")
        .replace("datetime.date", "date")
        .replace("typing.", "")
        .replace("NoneType", "None")
    )
    return cleaned


def _type_text(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty or annotation is inspect.Signature.empty:
        return "Any"
    return _clean_type_text(inspect.formatannotation(annotation))


def _default_value(value: Any) -> Any:
    if value is inspect.Parameter.empty:
        return None
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (tuple, list, dict)) and not value:
        return value
    return repr(value)


def _callable_details(function: Any, *, display_name: str | None = None, skip_first: bool = False) -> dict[str, Any]:
    signature = inspect.signature(function, eval_str=True)
    hints = get_type_hints(function)
    parameters: list[dict[str, Any]] = []
    signature_parameters = list(signature.parameters.values())
    if skip_first:
        signature_parameters = signature_parameters[1:]
        signature = signature.replace(parameters=signature_parameters)
    for parameter in signature_parameters:
        item = {
            "name": parameter.name,
            "type": _type_text(hints.get(parameter.name, parameter.annotation)),
            "kind": parameter.kind.name.lower(),
            "required": parameter.default is inspect.Parameter.empty,
        }
        if parameter.default is not inspect.Parameter.empty:
            item["default"] = _default_value(parameter.default)
        parameters.append(item)
    name = display_name or function.__name__
    return {
        "name": name,
        "signature": f"{name}{_clean_type_text(str(signature))}",
        "parameters": parameters,
        "returns": {"type": _type_text(hints.get("return", signature.return_annotation))},
    }


def _annotation_dependencies(annotation: Any) -> set[str]:
    result: set[str] = set()
    public_objects = {name: getattr(cost_rules, name) for name in _PUBLIC_TYPES}
    for name, value in public_objects.items():
        if annotation is value:
            result.add(name)
    origin = get_origin(annotation)
    if origin is not None and origin not in (types.UnionType,):
        result.update(_annotation_dependencies(origin))
    for argument in get_args(annotation):
        result.update(_annotation_dependencies(argument))
    return result


def _callable_dependencies(function: Any, *, skip_first: bool = False) -> set[str]:
    hints = get_type_hints(function)
    result: set[str] = set()
    for index, annotation in enumerate(hints.values()):
        if skip_first and index == 0:
            continue
        result.update(_annotation_dependencies(annotation))
    return result


def _function_contract(name: str) -> dict[str, Any]:
    item = _callable_details(getattr(cost_rules, name), display_name=name)
    item.update(FUNCTION_GUIDANCE[name])
    item["kind"] = "function"
    if name in FUNCTION_ERRORS:
        item["errors"] = FUNCTION_ERRORS[name]
    return item


def _type_fields(type_value: Any, guidance: dict[str, Any]) -> list[dict[str, Any]]:
    hints = get_type_hints(type_value)
    required_keys = getattr(type_value, "__required_keys__", frozenset(hints))
    field_guidance = guidance.get("fields", {})
    result: list[dict[str, Any]] = []
    for name, annotation in hints.items():
        item = {
            "name": name,
            "type": _type_text(annotation),
            "required": name in required_keys,
        }
        if name in field_guidance:
            item["meaning"] = field_guidance[name]
        result.append(item)
    return result


def _type_contract(name: str) -> dict[str, Any]:
    value = getattr(cost_rules, name)
    guidance = TYPE_GUIDANCE[name]
    item: dict[str, Any] = {"name": name, "purpose": guidance["purpose"]}
    if inspect.isclass(value) and issubclass(value, Enum):
        item.update({"kind": "enum", "values": [member.value for member in value]})
        return item
    if is_typeddict(value):
        item.update({"kind": "typed_dict", "fields": _type_fields(value, guidance)})
        return item
    if dataclasses.is_dataclass(value):
        item.update({"kind": "dataclass", "fields": _type_fields(value, guidance)})
    elif inspect.isclass(value) and issubclass(value, tuple) and hasattr(value, "_fields"):
        item.update({"kind": "named_tuple", "fields": _type_fields(value, guidance)})
    else:
        constructor = _callable_details(value.__init__, display_name=name, skip_first=True)
        if guidance.get("constructor_errors"):
            constructor["errors"] = guidance["constructor_errors"]
        item.update({"kind": "class", "constructor": constructor})
    methods = []
    for method_name in guidance.get("methods", ()):
        public_name = f"{name}.{method_name}"
        method = _callable_details(
            getattr(value, method_name),
            display_name=public_name,
            skip_first=True,
        )
        if public_name in METHOD_ERRORS:
            method["errors"] = METHOD_ERRORS[public_name]
        methods.append(method)
    if methods:
        item["methods"] = methods
    return item


def _type_summary(name: str, *, include_purpose: bool = True) -> dict[str, Any]:
    contract = _type_contract(name)
    result = {"name": name, "kind": contract["kind"]}
    if include_purpose:
        result["purpose"] = contract["purpose"]
    return result


def _type_dependencies(name: str) -> set[str]:
    value = getattr(cost_rules, name)
    result: set[str] = set()
    try:
        for annotation in get_type_hints(value).values():
            result.update(_annotation_dependencies(annotation))
    except TypeError:
        pass
    for method_name in TYPE_GUIDANCE[name].get("methods", ()):
        result.update(_callable_dependencies(getattr(value, method_name)))
    result.discard(name)
    return result


def _dependency_closure(initial: set[str]) -> set[str]:
    result = set(initial)
    pending = list(initial)
    while pending:
        name = pending.pop()
        dependencies: set[str] = set()
        if name in _PUBLIC_FUNCTIONS:
            dependencies = _callable_dependencies(getattr(cost_rules, name))
        elif name in _PUBLIC_TYPES:
            dependencies = _type_dependencies(name)
        for dependency in dependencies:
            if dependency not in result:
                result.add(dependency)
                pending.append(dependency)
    return result


def schema_contract(field_queries: Sequence[str]) -> dict[str, object]:
    available = list(cost_rules.__all__)
    if field_queries:
        missing = [name for name in field_queries if name not in available]
        if missing:
            raise BillingQueryError(
                ErrorCode.UNSUPPORTED_FIELD,
                f"cost_rules 中不存在公开符号: {', '.join(missing)}",
                ExitCode.INVALID_ARGUMENT,
                {"symbols": sorted(available)},
            )
        selected = _dependency_closure(set(field_queries))
        helpers = [_function_contract(name) for name in _PUBLIC_FUNCTIONS if name in selected]
        detailed_types = {name for name in field_queries if name in _PUBLIC_TYPES}
        for name in field_queries:
            if name not in _PUBLIC_FUNCTIONS:
                continue
            return_annotation = get_type_hints(getattr(cost_rules, name)).get("return")
            detailed_types.update(_annotation_dependencies(return_annotation))
        types_contract = [
            _type_contract(name) if name in detailed_types else _type_summary(name)
            for name in _PUBLIC_TYPES
            if name in selected
        ]
    else:
        selected = set(available)
        helpers = [
            {
                "name": name,
                "purpose": INDEX_PURPOSE[name],
            }
            for name in _PUBLIC_FUNCTIONS
        ]
        types_contract = [
            {"name": name, "kind": _type_summary(name, include_purpose=False)["kind"], "purpose": INDEX_PURPOSE[name]}
            for name in _PUBLIC_TYPES
        ]
    examples = []
    for example in EXAMPLES:
        if not field_queries or not set(field_queries).intersection(example["show_for"]):
            continue
        examples.append(
            {
                **{key: value for key, value in example.items() if key not in {"show_for", "symbols"}},
                "requires": example["symbols"],
            }
        )
    result: dict[str, object] = {
        "section": "cost_rules",
        "module": "cost_query.common.cost_rules",
        "helpers": helpers,
        "types": types_contract,
        "examples": examples,
    }
    if not field_queries:
        result["detail_command"] = "python3 scripts/cost.py schema --section cost_rules --field <FunctionOrType>"
    return result
