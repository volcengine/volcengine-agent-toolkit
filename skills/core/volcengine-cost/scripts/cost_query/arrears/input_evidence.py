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


def _csv_evidence(path: Path) -> tuple[Completeness, str, Path | None]:
    metadata_path = path.with_suffix(".meta.json")
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
    if not isinstance(value, Mapping) or set(value) != {"file"}:
        return None
    file_value = value.get("file")
    if not isinstance(file_value, str) or not file_value:
        raise ValueError(f"{envelope_path} 的 result.file 必须是非空字符串")
    result_path = Path(file_value)
    if not result_path.is_absolute():
        raise ValueError(f"{envelope_path} 的 result.file 必须是绝对路径")
    return result_path


def load_attribution_input(path: Path, *, input_name: str) -> AttributionInput:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as file:
            rows = [dict(row) for row in csv.DictReader(file)]
        completeness, reason, metadata_path = _csv_evidence(path)
        return AttributionInput(
            input_name=input_name,
            path=path,
            rows=rows,
            completeness=completeness,
            source="csv",
            reason=reason,
            metadata_path=metadata_path,
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
            loaded = load_attribution_input(result_file, input_name=input_name)
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
