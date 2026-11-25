"""把完整采集结果稳定写入 CSV、字段目录和 metadata。"""

from __future__ import annotations

import csv
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..common.errors import BillingQueryError, ErrorCode, ExitCode
from ..common.execution_output import OUTPUT_PROTOCOL_VERSION
from ..common.json_output import dumps as json_dumps
from .field_catalog import build_field_catalog
from .field_grain import field_grain_warnings
from .fetch import (
    ANALYSIS_DEFAULT_CURRENCY,
    QueryResult,
    aggregate_coverage,
    request_includes_current_period,
)


PROVENANCE_COLUMNS = ("_action", "_query_id")


def _cell(value: Any) -> str | int | float | bool:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (Mapping, list, tuple)):
        return json_dumps(value, sort_keys=True)
    return value


def _columns(results: Sequence[QueryResult]) -> list[str]:
    seen: set[str] = set()
    for result in results:
        for row in result.rows:
            seen.update(row)
    return [*PROVENANCE_COLUMNS, *sorted(seen)]


def result_records(results: Sequence[QueryResult]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for result in results:
        for row in result.rows:
            record = {"_action": result.action, "_query_id": result.query_id}
            record.update(dict(row))
            records.append(record)
    return records


def query_result_context(action: str, results: Sequence[QueryResult]) -> dict[str, Any]:
    """Return warnings, freshness, and domain evidence for envelope projection."""
    records = result_records(results)
    warnings = list(
        dict.fromkeys(
            warning
            for result in results
            for warning in result.warnings
        )
    )
    warnings.extend(
        field_grain_warnings(
            action,
            _columns(results),
            [result.request_body for result in results],
            records,
        )
    )
    context: dict[str, Any] = {
        "warnings": list(dict.fromkeys(warnings)),
        "freshness": freshness(action, results),
    }
    analysis_summary = _analysis_summary(results) if action == "ListCostAnalysisOpenApi" else None
    if analysis_summary is not None:
        context["analysis_summary"] = analysis_summary
        context["warnings"].append(
            "ListCostAnalysisOpenApi 的“总费用”服务端合计行保留在机器证据中，未放入明细结果。"
        )
    return context


def _analysis_summary(results: Sequence[QueryResult]) -> dict[str, Any] | None:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in results:
        for row in result.analysis_summary_rows:
            record = {"_action": result.action, "_query_id": result.query_id}
            record.update(dict(row))
            signature = json_dumps(record, sort_keys=True)
            if signature in seen:
                continue
            seen.add(signature)
            rows.append({key: _cell(value) for key, value in record.items()})
    if not rows:
        return None
    return {
        "kind": "service_synthetic_total",
        "row_count": len(rows),
        "currency": ANALYSIS_DEFAULT_CURRENCY,
        "rows": rows,
        "note": "ListCostAnalysisOpenApi 的“总费用”是服务端合计行，已从 CSV 明细行剥离，避免 TopN 和贡献率重复计入。",
    }


def _derived_fields(action: str, columns: Sequence[str]) -> list[dict[str, Any]]:
    if action != "ListCostAnalysisOpenApi" or "Currency" not in columns:
        return []
    return [
        {
            "field": "Currency",
            "value": ANALYSIS_DEFAULT_CURRENCY,
            "source": "derived_contract_default",
            "original_response_field": False,
            "note": "ListCostAnalysisOpenApi 不返回币种；按该接口固定 CNY 口径补充。",
        }
    ]


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(text)
        os.replace(name, path)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def _atomic_csv(path: Path, results: Sequence[QueryResult]) -> tuple[list[str], int]:
    columns = _columns(results)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    count = 0
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            for result in results:
                for row in result.rows:
                    record = {"_action": result.action, "_query_id": result.query_id}
                    record.update({key: _cell(value) for key, value in row.items()})
                    writer.writerow(record)
                    count += 1
        os.replace(name, path)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise
    return columns, count


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_text(path, json_dumps(payload, compact=False) + "\n")


def freshness(action: str, results: Sequence[QueryResult]) -> dict[str, Any]:
    notes: list[str] = []
    partial_period = any(
        request_includes_current_period(result.request_body)
        for result in results
    )
    if partial_period:
        notes.append("查询包含当前月，数据尚未完结。")
    if action == "ListCostAnalysisOpenApi":
        notes.append("费用分析在账单明细出具后 T+2 日更新，不代表最新账单明细。")
    if action == "ListSplitBillDetail":
        notes.append("分账账单通常比账单明细延迟约 2 天，项目和标签最晚还可能延迟约 12 小时。")
    if action.startswith("ListAmortizedCostBill"):
        notes.append("成本账单通常比账单明细延迟约 2 天，且使用分摊时间轴。")
    return {
        "partial_period": partial_period,
        "notes": list(dict.fromkeys(notes)),
    }


def output_artifact_paths(
    output: Path,
) -> tuple[Path, Path, Path]:
    """Resolve and validate the complete output set before any remote query."""
    if output.suffix.lower() != ".csv":
        raise BillingQueryError(
            ErrorCode.OUTPUT_FAILED,
            "结果文件必须使用 .csv 扩展名",
            ExitCode.OUTPUT_FAILED,
        )
    metadata = output.with_name(f"{output.stem}.meta.json")
    fields_artifact = output.with_name(f"{output.stem}.fields.json")
    return output, metadata, fields_artifact


def preflight_output(
    *,
    output: Path,
    overwrite: bool,
    remote_call_attempted: bool = False,
) -> tuple[Path | None, Path | None, Path | None]:
    """Reject output collisions before querying; repeat at commit for race safety."""
    paths = output_artifact_paths(output)
    existing = [str(path) for path in paths if path.exists()]
    if existing and not overwrite:
        phase = "output_commit_check" if remote_call_attempted else "output_preflight"
        raise BillingQueryError(
            ErrorCode.OUTPUT_EXISTS,
            f"输出文件已存在：{existing[0]}",
            ExitCode.OUTPUT_FAILED,
            {
                "phase": phase,
                "remote_call_attempted": remote_call_attempted,
                "paths": existing,
                "recovery_options": [
                    {
                        "action": "choose_new_output_path",
                        "description": "改用本轮任务专属且尚不存在的输出路径。",
                    },
                    {
                        "action": "retry_with_overwrite",
                        "argument": "--overwrite",
                        "allowed_when": "已确认所有冲突文件均属于本轮任务并且允许替换",
                    },
                ],
                "retry_policy": "只调整输出策略；不要重新规划或扩大 Billing 查询。",
            },
        )
    return paths


def write_outputs(
    *,
    action: str,
    results: Sequence[QueryResult],
    output: Path,
    overwrite: bool,
    backend: str,
    required_fields: Sequence[str] = (),
    execution_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    output, metadata, fields_artifact = preflight_output(
        output=output,
        overwrite=overwrite,
        remote_call_attempted=True,
    )
    try:
        records = result_records(results)
        row_count = len(records)
        coverage = aggregate_coverage(results)
        analysis_summary = _analysis_summary(results) if action == "ListCostAnalysisOpenApi" else None
        warnings = list(
            dict.fromkeys(
                warning
                for result in results
                for warning in result.warnings
            )
        )
        if analysis_summary is not None:
            warnings.append("ListCostAnalysisOpenApi 的“总费用”服务端合计行已写入 metadata.analysis_summary，未写入 CSV 明细行。")
        columns = _columns(results)
        warnings.extend(
            field_grain_warnings(
                action,
                columns,
                [result.request_body for result in results],
                records,
            )
        )
        warnings = list(dict.fromkeys(warnings))
        columns, row_count = _atomic_csv(output, results)
        artifacts: dict[str, str] = {"csv": str(output.resolve())}
        catalog = build_field_catalog(
            action=action,
            columns=columns,
            source_csv=output,
            source_metadata=metadata,
            request_bodies=[result.request_body for result in results],
        )
        _atomic_json(fields_artifact, catalog)
        artifacts["fields"] = str(fields_artifact.resolve())
        artifacts["metadata"] = str(metadata.resolve())
        meta = {
            "output_protocol_version": OUTPUT_PROTOCOL_VERSION,
            "schema_version": "1.0",
            **(
                {}
                if action == "QueryBalanceAcct"
                else {"generated_at": datetime.now(timezone.utc).isoformat()}
            ),
            "action": action,
            "backend": backend,
            "columns": columns,
            "row_count": row_count,
            "coverage": coverage,
            "freshness": freshness(action, results),
            "warnings": warnings,
            "derived_fields": _derived_fields(action, columns),
            "required_response_fields": list(required_fields),
            **dict(execution_evidence or {}),
            **({"analysis_summary": analysis_summary} if analysis_summary is not None else {}),
            "queries": [
                {
                    "query_id": result.query_id,
                    "request_body": result.request_body,
                    "coverage": result.coverage(),
                }
                for result in results
            ],
            "artifacts": artifacts,
        }
        _atomic_text(metadata, json_dumps(meta, compact=False) + "\n")
    except BillingQueryError:
        raise
    except OSError as exc:
        raise BillingQueryError(
            ErrorCode.OUTPUT_FAILED,
            f"写入结果失败：{exc}",
            ExitCode.OUTPUT_FAILED,
        ) from exc
    return meta
