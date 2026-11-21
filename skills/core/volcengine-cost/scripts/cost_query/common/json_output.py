"""公开 CLI 共享的 JSON 序列化。"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any


def _encode_decimal_json(value: Any, *, compact: bool, sort_keys: bool, level: int, markers: set[int]) -> str:
    """标准库不支持 Decimal；仅在需要时将有限 Decimal 写为原精度 JSON number。"""
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Out of range Decimal values are not JSON compliant")
        return str(value)
    if not isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    marker = id(value)
    if marker in markers:
        raise ValueError("Circular reference detected")
    markers.add(marker)
    try:
        parts = []
        is_object = isinstance(value, dict)
        entries = sorted(value.items()) if is_object and sort_keys else value.items() if is_object else value
        for entry in entries:
            if is_object:
                key, child = entry
                if not isinstance(key, str):
                    if key is None or isinstance(key, (bool, int, float)):
                        key = json.dumps(key, allow_nan=False)
                    else:
                        raise TypeError("JSON object keys must be str, int, float, bool or None")
                prefix = json.dumps(key, ensure_ascii=False) + (":" if compact else ": ")
            else:
                child, prefix = entry, ""
            parts.append(prefix + _encode_decimal_json(
                child, compact=compact, sort_keys=sort_keys, level=level + 1, markers=markers,
            ))
        opening, closing = ("{", "}") if is_object else ("[", "]")
        if not parts:
            return opening + closing
        if compact:
            return opening + ",".join(parts) + closing
        padding = "  " * (level + 1)
        return opening + "\n" + padding + (",\n" + padding).join(parts) + "\n" + "  " * level + closing
    finally:
        markers.remove(marker)


def dumps(value: Any, *, compact: bool = True, sort_keys: bool = False) -> str:
    options = {"separators": (",", ":")} if compact else {"indent": 2}
    try:
        # 普通接口与现有类型继续使用标准库，保持原序列化行为。
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=sort_keys, **options)
    except TypeError:
        return _encode_decimal_json(value, compact=compact, sort_keys=sort_keys, level=0, markers=set())
