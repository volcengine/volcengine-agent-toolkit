"""Load attribution inputs without losing query completeness evidence."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from ..common.execution_output import OUTPUT_PROTOCOL_VERSION


Completeness = Literal["complete", "partial", "unknown"]


@dataclass(frozen=True)
class AttributionInput:
    input_name: str
    path: Path
    rows: list[dict[str, Any]]
    completeness: Completeness
    source: Literal["csv", "json"]
    reason: str
    status: str | None = None
    metadata_path: Path | None = None
    queried_coupon_ids: tuple[str, ...] = ()

    def evidence(self) -> dict[str, Any]:
        return {
            "input": self.input_name,
            "path": str(self.path.resolve()),
            "source": self.source,
            "completeness": self.completeness,
            "reason": self.reason,
            **({"status": self.status} if self.status else {}),
            **(
                {"metadata": str(self.metadata_path.resolve())}
                if self.metadata_path
                else {}
            ),
        }


def _coverage_completeness(
    coverage: Mapping[str, Any],
    freshness: Mapping[str, Any] | None = None,
) -> tuple[Completeness, str]:
    failed_queries = coverage.get("failed_queries")
    partial_period = bool(freshness and freshness.get("partial_period") is True)
    if (
        coverage.get("is_complete") is True
        and (failed_queries is None or failed_queries == [])
        and not partial_period
    ):
        return "complete", "coverage_complete"
    return "partial", "coverage_incomplete"


def _read_metadata(path: Path | None) -> Mapping[str, Any]:
    if path is None:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, Mapping) else {}


def _coupon_scope(metadata: Mapping[str, Any]) -> tuple[str, ...]:
    if metadata.get("action") != "ListCouponUsageRecords":
        return ()
    ids = metadata.get("queried_coupon_ids")
    values = list(ids) if isinstance(ids, list) else []
    for query in metadata.get("queries") or []:
        if isinstance(query, Mapping) and isinstance(query.get("request_body"), Mapping):
            values.append(query["request_body"].get("CouponID"))
    return tuple(dict.fromkeys(value for value in values if isinstance(value, str) and value.strip()))


def _check_binding(value: Any, actual: Path, csv_path: Path) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value:
        raise ValueError("CSV、metadata 和 fields 的来源引用无效")
    expected = Path(value)
    if not expected.is_absolute():
        expected = actual.parent / expected
    matches = expected.resolve() == actual.resolve()
    if not matches and not expected.exists() and expected.name == actual.name:
        matches = actual.parent.resolve() == csv_path.parent.resolve()
    if not matches:
        raise ValueError("CSV、metadata 和 fields 来源不一致")


def _csv_evidence(
    path: Path, metadata_path: Path | None = None, fields_path: Path | None = None,
) -> tuple[Completeness, str, Path | None]:
    metadata_path = metadata_path or path.with_suffix(".meta.json")
    if not metadata_path.is_file():
        return "unknown", "metadata_missing", None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unknown", "metadata_invalid", metadata_path
    if not isinstance(metadata, Mapping) or not isinstance(
        metadata.get("coverage"), Mapping
    ):
        return "unknown", "metadata_invalid", metadata_path
    if metadata.get("output_protocol_version") != OUTPUT_PROTOCOL_VERSION:
        return "unknown", "output_protocol_version_missing_or_unsupported", metadata_path
    declared = metadata.get("artifacts")
    declared = declared if isinstance(declared, Mapping) else {}
    _check_binding(declared.get("csv"), path, path)
    _check_binding(declared.get("metadata"), metadata_path, path)
    if fields_path is not None or declared.get("fields"):
        fields_path = fields_path or path.with_suffix(".fields.json")
        _check_binding(declared.get("fields"), fields_path, path)
        fields = _read_metadata(fields_path)
        if not fields:
            return "unknown", "fields_missing_or_invalid", metadata_path
        _check_binding(fields.get("source_csv"), path, path)
        _check_binding(fields.get("source_metadata"), metadata_path, path)
        if fields.get("source_action") and fields["source_action"] != metadata.get("action"):
            raise ValueError("fields.source_action 与 metadata.action 不一致")
    completeness, reason = _coverage_completeness(
        metadata["coverage"],
        (
            metadata.get("freshness")
            if isinstance(metadata.get("freshness"), Mapping)
            else None
        ),
    )
    return completeness, reason, metadata_path


def _json_evidence(payload: Mapping[str, Any]) -> tuple[Completeness, str, str | None]:
    status_value = payload.get("status")
    status = status_value if isinstance(status_value, str) else None
    meta = payload.get("_meta")
    if not isinstance(meta, Mapping):
        return "unknown", "machine_evidence_missing", status
    if meta.get("output_protocol_version") != OUTPUT_PROTOCOL_VERSION:
        return "unknown", "output_protocol_version_missing_or_unsupported", status
    if status in ("partial", "error"):
        return "partial", f"query_status_{status}", status
    if status != "success":
        return "unknown", "query_status_missing_or_invalid", status
    if isinstance(meta.get("freshness"), Mapping) and meta["freshness"].get("partial_period") is True:
        return "partial", "coverage_incomplete", status
    coverage = meta.get("coverage")
    if isinstance(coverage, Mapping):
        completeness, reason = _coverage_completeness(
            coverage,
            (
                meta.get("freshness")
                if isinstance(meta.get("freshness"), Mapping)
                else None
            ),
        )
        if status == "partial":
            return "partial", f"query_status_{status}", status
        if status == "error":
            return "partial", "query_status_error", status
        return completeness, reason, status
    if status == "partial":
        return "partial", "query_status_partial", status
    return "unknown", "coverage_missing", status


def _resolve_result_file(envelope_path: Path, value: Any) -> Path | None:
    if not isinstance(value, Mapping) or "file" not in value:
        return None
    file_value = value.get("file")
    if not isinstance(file_value, str) or not file_value:
        raise ValueError(f"{envelope_path} 的 result.file 必须是非空字符串")
    result_path = Path(file_value)
    if not result_path.is_absolute():
        raise ValueError(f"{envelope_path} 的 result.file 必须是绝对路径")
    return result_path


def load_attribution_input(
    path: Path, *, input_name: str,
    metadata_path: Path | None = None, fields_path: Path | None = None,
) -> AttributionInput:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as file:
            rows = [dict(row) for row in csv.DictReader(file)]
        completeness, reason, metadata_path = _csv_evidence(path, metadata_path, fields_path)
        metadata = _read_metadata(metadata_path)
        row_actions = {row.get("_action") for row in rows if row.get("_action")}
        if metadata.get("action") and row_actions and row_actions != {metadata["action"]}:
            raise ValueError("CSV _action 与 metadata.action 不一致")
        return AttributionInput(
            input_name=input_name,
            path=path,
            rows=rows,
            completeness=completeness,
            source="csv",
            reason=reason,
            metadata_path=metadata_path,
            queried_coupon_ids=_coupon_scope(metadata),
        )

    payload = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    if isinstance(payload, list):
        rows = payload
        completeness: Completeness = "unknown"
        reason = "query_status_missing"
        status = None
    elif isinstance(payload, Mapping) and {"status", "message", "result", "_meta"} <= set(payload):
        completeness, reason, status = _json_evidence(payload)
        result_file = _resolve_result_file(path, payload.get("result"))
        if result_file is not None:
            pointers = payload["result"]
            metadata_file = _resolve_result_file(path, {"file": pointers["metadata"]}) if "metadata" in pointers else None
            fields_file = _resolve_result_file(path, {"file": pointers["fields"]}) if "fields" in pointers else None
            if result_file.suffix.lower() != ".csv":
                raise ValueError("归因文件结果必须指向 CSV")
            loaded = load_attribution_input(
                result_file, input_name=input_name, metadata_path=metadata_file, fields_path=fields_file,
            )
            source_metadata = _read_metadata(loaded.metadata_path)
            meta = payload["_meta"]
            if isinstance(meta, Mapping) and meta.get("action") and source_metadata.get("action"):
                if meta["action"] != source_metadata["action"]:
                    raise ValueError("查询结果 action 与 metadata.action 不一致")
            if status == "success" and reason == "coverage_missing":
                completeness, reason = loaded.completeness, loaded.reason
            return AttributionInput(
                input_name=input_name,
                path=loaded.path,
                rows=loaded.rows,
                completeness=(
                    "partial"
                    if completeness == "partial" or loaded.completeness == "partial"
                    else "unknown"
                    if completeness == "unknown" or loaded.completeness == "unknown"
                    else "complete"
                ),
                source=loaded.source,
                reason=(reason if completeness != "complete" else loaded.reason),
                status=status,
                metadata_path=loaded.metadata_path,
                queried_coupon_ids=loaded.queried_coupon_ids,
            )
        rows = payload.get("result")
    elif isinstance(payload, Mapping):
        rows = payload.get("rows")
        completeness = "unknown"
        reason = "manual_json_without_execution_evidence"
        status = None
    else:
        rows = None
        completeness = "unknown"
        reason = "query_status_missing"
        status = None
    if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
        raise ValueError(
            f"{path} 必须是 CSV、JSON rows 数组或 cost.py query inline JSON"
        )
    return AttributionInput(
        input_name=input_name,
        path=path,
        rows=[dict(row) for row in rows],
        completeness=completeness,
        source="json",
        reason=reason,
        status=status,
        queried_coupon_ids=(
            _coupon_scope(payload["_meta"])
            if isinstance(payload, Mapping) and isinstance(payload.get("_meta"), Mapping)
            else ()
        ),
    )


def apply_input_evidence_policy(
    result: Mapping[str, Any],
    inputs: Sequence[AttributionInput],
) -> tuple[dict[str, Any], Literal["success", "partial"]]:
    output = dict(result)
    output.pop("status", None)
    output["input_evidence"] = [item.evidence() for item in inputs]
    incomplete = [item for item in inputs if item.completeness == "partial"]
    unknown = [item for item in inputs if item.completeness == "unknown"]
    if not incomplete and not unknown:
        return output, "success"

    claim_fields = (
        "supported_reasons",
        "bill_observations",
        "follow_up_candidates",
        "coupon_usage_summaries",
    )
    supported = output.get("supported_reasons")
    discarded_supported_reason_count = len(supported) if isinstance(supported, list) else 0
    discarded_claim_count = 0
    for field in claim_fields:
        claims = output.get(field)
        if isinstance(claims, list):
            discarded_claim_count += len(claims)
            output[field] = []
    existing = output.get("insufficient_evidence")
    insufficient = list(existing) if isinstance(existing, list) else []
    affected = [*incomplete, *unknown]
    insufficient.append(
        {
            "candidate": "input_completeness",
            "inputs": [item.input_name for item in affected],
            "missing_evidence": [
                f"{item.input_name}:{item.reason}" for item in affected
            ],
            "discarded_supported_reason_count": discarded_supported_reason_count,
            "discarded_claim_count": discarded_claim_count,
        }
    )
    output["insufficient_evidence"] = insufficient
    summary = dict(output.get("summary") or {})
    summary["supported_reason_count"] = 0
    summary["insufficient_candidate_count"] = len(insufficient)
    output["summary"] = summary
    return output, "partial" if incomplete else "success"
