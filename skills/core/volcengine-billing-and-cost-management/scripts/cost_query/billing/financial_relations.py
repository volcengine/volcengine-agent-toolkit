"""Match financial relation roles to an identity verified with the same client."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .client import BillingClient
from ..common.errors import BillingQueryError


def _account_id(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    return text if text.isascii() and text.isdigit() and int(text) > 0 else None


def verify_financial_relation_identity(
    client: BillingClient,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not rows:
        return {"status": "not_needed", "reason": "no_relations"}
    unknown: dict[str, Any] = {"status": "unknown", "reason": "identity_unavailable"}
    try:
        response = client.get_caller_identity()
    except BillingQueryError as exc:
        return {**unknown, "reason": "identity_query_failed", "error_code": exc.code.value}
    except Exception:
        return {**unknown, "reason": "identity_query_failed"}
    if not isinstance(response, Mapping):
        return unknown
    metadata = response.get("ResponseMetadata")
    if isinstance(metadata, Mapping) and metadata.get("Error"):
        return {**unknown, "reason": "identity_query_failed"}
    result = response.get("Result")
    account_id = _account_id(result.get("AccountId")) if isinstance(result, Mapping) else None
    if account_id is None:
        return {**unknown, "reason": "account_id_missing_or_invalid"}
    roles = []
    for index, row in enumerate(rows, 1):
        major = account_id == _account_id(row.get("MajorAccountID"))
        sub = account_id == _account_id(row.get("SubAccountID"))
        role = "ambiguous" if major and sub else "major" if major else "sub" if sub else "unknown"
        roles.append({"row": index, "relation_id": row.get("RelationID"), "role": role})
    return {
        "status": "verified", "source": "sts.GetCallerIdentity",
        "account_id": account_id, "relations": roles,
    }


def financial_identity_message(evidence: Mapping[str, Any]) -> str:
    if evidence.get("status") == "not_needed":
        return ""
    if evidence.get("status") != "verified":
        return (
            "当前查询身份未核验，无法确认当前账号是主账号还是子账号。"
            "Filiation/FiliationDesc 是主子相对视角，不能单独据此判断当前账号角色。"
        )
    message = f"同一查询凭证经 STS 核验，当前账号 ID 为 {evidence['account_id']}。"
    roles = evidence.get("relations") or []
    labels = {
        "major": "当前账号是主账号（匹配 MajorAccountID）",
        "sub": "当前账号是子账号（匹配 SubAccountID）",
        "unknown": "当前账号未匹配该关系的主子账号，角色无法确认",
        "ambiguous": "当前账号同时匹配主子账号，角色无法确认",
    }
    for role in roles[:5]:
        message += f"第 {role['row']} 条关系中，{labels[role['role']]}。"
    if len(roles) > 5:
        message += "其余关系按已核验账号 ID 与各行 MajorAccountID/SubAccountID 匹配。"
    return message
