#!/usr/bin/env python3
"""Runtime helpers for analysis_state v0.3.

The LLM still owns RCA reasoning and semantic stop decisions. This module only
keeps the state shape valid, performs deterministic task transitions, dedupes
candidate tasks, builds tool arguments, and applies runtime guardrails.
"""

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set


SCHEMA_VERSION = "analysis-state-v0.3"
TOP_LEVEL_FIELDS = {
    "schema_version",
    "question",
    "context",
    "fsm",
    "current_task",
    "pending_tasks",
    "completed_tasks",
    "failed_tasks",
    "findings",
    "scheduler",
    "progress_signals",
    "stop_condition",
    "dedup",
}
TASK_TYPES = {
    "locate_product",
    "locate_charge_item",
    "locate_instance",
    "locate_region",
    "locate_project",
    "locate_amount",
    "decompose_charge_item",
}
TASK_REQUIRED_FIELDS = {
    "locate_product": ["current_period", "base_period"],
    "locate_charge_item": ["current_period", "base_period"],
    "locate_instance": ["current_period", "base_period"],
    "locate_region": ["current_period", "base_period"],
    "locate_project": ["current_period", "base_period"],
    "locate_amount": ["current_period", "base_period", "charge_item_code"],
    "decompose_charge_item": ["current_period", "base_period", "charge_item_code"],
}
ALLOWED_SCOPE_FIELDS = {"product", "instance_no", "charge_item_code", "project", "region_code"}
DIMENSION_BY_TASK_TYPE = {
    "locate_product": "product",
    "locate_charge_item": "charge_item_code",
    "locate_instance": "instance_no",
    "locate_region": "region_code",
    "locate_project": "project",
}
QUESTION_TYPES = {"dimension_locate", "amount_breakdown", "driver_decompose", "generic_rca"}
ANALYSIS_GOALS = {"locate_main_dimension", "explain_amount_change", "explain_driver_change", "explain_cost_increase"}
FSM_STATES = {"initialized", "running", "waiting_for_tool", "interpreting_result", "ready_to_answer", "blocked", "stopped"}
ANSWER_READINESS = {"not_ready", "partially_ready", "ready", "ready_with_limitations"}
FINDING_TYPES = {"dimension_locate", "amount_breakdown", "driver_decompose", "anomaly_detected", "insufficient_signal"}
ANSWERABLE_FINDING_TYPES_BY_QUESTION_TYPE = {
    "dimension_locate": {"dimension_locate", "amount_breakdown", "driver_decompose"},
    "amount_breakdown": {"amount_breakdown", "driver_decompose"},
    "driver_decompose": {"driver_decompose"},
    "generic_rca": {"amount_breakdown", "driver_decompose"},
}
PRIMARY_CHARGE_ITEM_FINDING_TYPES = {"dimension_locate", "amount_breakdown", "driver_decompose"}
CONFIDENCE_VALUES = {"high", "medium", "low", "unknown"}
RUNTIME_GUARDRAIL_REASONS = {
    None,
    "missing_required_context",
    "max_steps_reached",
    "no_executable_task",
    "tool_error_retry_exceeded",
    "invalid_state",
}
PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-01$")
PROGRESS_SIGNAL_FIELDS = {
    "has_primary_dimension",
    "has_primary_charge_item",
    "has_driver_explanation",
    "has_answerable_finding",
    "has_user_requested_scope_resolved",
    "has_unresolved_required_task",
}


class AnalysisStateError(ValueError):
    """Raised when the analysis state violates the v0.3 contract."""


def _copy_state(state: Dict[str, Any]) -> Dict[str, Any]:
    return deepcopy(state)


def _normalize_period(value: Any) -> Any:
    if isinstance(value, str) and len(value) == 7 and value[4] == "-":
        return value + "-01"
    return value


def _known_context_and_scope(state: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
    context = state.get("context", {})
    known = dict(context)
    known.update(context.get("global_filters") or {})
    known.update(task.get("scope") or {})
    return known


def _required_fields_for_task(task: Dict[str, Any]) -> List[str]:
    task_type = task.get("task_type")
    required: List[str] = []
    for field in list(TASK_REQUIRED_FIELDS.get(task_type, [])) + list(task.get("requires", [])):
        if field not in required:
            required.append(field)
    return required


def _next_numbered_id(items: Iterable[Dict[str, Any]], field: str, prefix: str) -> str:
    max_seen = 0
    for item in items:
        value = str(item.get(field, ""))
        if value.startswith(f"{prefix}_"):
            suffix = value[len(prefix) + 1:]
            if suffix.isdigit():
                max_seen = max(max_seen, int(suffix))
    return f"{prefix}_{max_seen + 1:03d}"


def _all_tasks(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    if state.get("current_task"):
        tasks.append(state["current_task"])
    tasks.extend(state.get("pending_tasks", []))
    tasks.extend(state.get("completed_tasks", []))
    tasks.extend(state.get("failed_tasks", []))
    return tasks


def _existing_task_keys(state: Dict[str, Any]) -> Set[str]:
    keys = {str(task.get("task_key")) for task in _all_tasks(state) if task.get("task_key")}
    keys.update(str(key) for key in state.get("dedup", {}).get("visited_task_keys", []) if key)
    return keys


def _make_task(
    state: Dict[str, Any],
    task_type: str,
    scope: Optional[Dict[str, Any]] = None,
    requires: Optional[List[str]] = None,
    priority: int = 100,
    parent_task_id: Optional[str] = None,
    reason: Optional[str] = None,
    evidence_summary: Optional[str] = None,
    retry_count: int = 0,
) -> Dict[str, Any]:
    scope = dict(scope or {})
    task_requires: List[str] = []
    for field in list(TASK_REQUIRED_FIELDS.get(task_type, [])) + list(requires or []):
        if field not in task_requires:
            task_requires.append(field)
    task_key = generate_task_key(task_type, scope)
    next_id = _next_numbered_id(_all_tasks(state), "task_id", "task")
    task = {
        "task_id": next_id,
        "task_key": task_key,
        "task_type": task_type,
        "scope": scope,
        "requires": task_requires,
        "priority": priority,
        "parent_task_id": parent_task_id,
        "reason": reason or _default_reason(task_type, scope),
    }
    if evidence_summary:
        task["evidence_summary"] = evidence_summary
    if retry_count:
        task["retry_count"] = retry_count
    return task


def _default_reason(task_type: str, scope: Dict[str, Any]) -> str:
    if task_type == "locate_product":
        return "整体费用上涨归因先从产品维度定位"
    if task_type == "locate_charge_item" and scope.get("product"):
        return f"用户或上游结果已限定产品 {scope['product']}，需要定位其下主要计费项"
    if task_type == "decompose_charge_item":
        return "已定位计费项，需要拆解驱动因素"
    return f"执行 {task_type} 以补齐回答所需信息"


def default_analysis_goal_for_question_type(question_type: str) -> str:
    return {
        "dimension_locate": "locate_main_dimension",
        "amount_breakdown": "explain_amount_change",
        "driver_decompose": "explain_driver_change",
        "generic_rca": "explain_cost_increase",
    }.get(question_type, "explain_cost_increase")


def infer_analysis_goal(question_type: str) -> str:
    """Backward-compatible alias for the stable enum mapping."""
    return default_analysis_goal_for_question_type(question_type)


def initialize_analysis_state(user_query: str, parsed_context: Dict[str, Any]) -> Dict[str, Any]:
    """Create a complete analysis_state v0.3 object."""
    global_filters = dict(parsed_context.get("global_filters") or parsed_context.get("filters") or {})
    for key in ALLOWED_SCOPE_FIELDS:
        if key in parsed_context and key not in global_filters:
            global_filters[key] = parsed_context[key]
    context = {
        "current_period": _normalize_period(parsed_context.get("current_period") or parsed_context.get("CurrentPeriod")),
        "base_period": _normalize_period(parsed_context.get("base_period") or parsed_context.get("BasePeriod")),
        "global_filters": global_filters,
    }
    question_type = str(parsed_context.get("question_type") or "generic_rca")
    if question_type not in QUESTION_TYPES:
        question_type = "generic_rca"
    analysis_goal = str(parsed_context.get("analysis_goal") or default_analysis_goal_for_question_type(question_type))
    if analysis_goal not in ANALYSIS_GOALS:
        analysis_goal = default_analysis_goal_for_question_type(question_type)
    state: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "question": {
            "raw_user_query": user_query,
            "question_type": question_type,
            "analysis_goal": analysis_goal,
        },
        "context": context,
        "fsm": {"state": "running", "step": 0, "last_transition": None},
        "current_task": None,
        "pending_tasks": [],
        "completed_tasks": [],
        "failed_tasks": [],
        "findings": [],
        "scheduler": {
            "mode": "llm_guided",
            "max_steps": int(parsed_context.get("max_steps", 8)),
            "max_retry": int(parsed_context.get("max_retry", 1)),
            "selection_policy": "llm_selects_task_runtime_validates",
        },
        "progress_signals": {
            "has_primary_dimension": False,
            "has_primary_charge_item": False,
            "has_driver_explanation": False,
            "has_answerable_finding": False,
            "has_user_requested_scope_resolved": False,
            "has_unresolved_required_task": True,
        },
        "stop_condition": {
            "llm_decision": {
                "should_stop": False,
                "answer_readiness": "not_ready",
                "reason": "analysis just initialized",
                "next_required_task_id": "task_001",
            },
            "runtime_guardrail": {"must_stop": False, "reason": None},
            "final": {"should_stop": False, "reason": "llm_requires_more_analysis"},
        },
        "dedup": {"visited_task_keys": []},
    }

    initial_task_warnings: List[str] = []
    missing_required_context = not context.get("current_period") or not context.get("base_period")
    if not missing_required_context:
        initial_tasks = _materialize_initial_tasks(state, parsed_context.get("initial_tasks") or [], initial_task_warnings)
        if initial_tasks:
            state["pending_tasks"].extend(initial_tasks)
        elif global_filters.get("charge_item_code") and question_type == "amount_breakdown":
            initial = _make_task(
                state,
                "locate_amount",
                {"charge_item_code": global_filters["charge_item_code"]},
                reason="用户已指定计费项，直接分析金额构成变化",
            )
            state["pending_tasks"].append(initial)
        elif global_filters.get("charge_item_code"):
            initial = _make_task(
                state,
                "decompose_charge_item",
                {"charge_item_code": global_filters["charge_item_code"]},
                reason="用户已指定计费项，直接拆解驱动因素",
            )
            state["pending_tasks"].append(initial)
        elif global_filters.get("product"):
            initial = _make_task(
                state,
                "locate_charge_item",
                {"product": global_filters["product"]},
                reason=f"用户已指定产品 {global_filters['product']}，直接定位其下主要计费项",
            )
            state["pending_tasks"].append(initial)
        else:
            initial = _make_task(state, "locate_product", {})
            state["pending_tasks"].append(initial)
    state = update_runtime_guardrail(state)
    if state["stop_condition"]["runtime_guardrail"]["reason"] == "missing_required_context":
        state["pending_tasks"] = []
        state["current_task"] = None
        state["stop_condition"]["llm_decision"].update({
            "should_stop": False,
            "answer_readiness": "not_ready",
            "reason": "missing required context; ask user for current_period/base_period before tool execution",
            "next_required_task_id": None,
        })
        state["progress_signals"]["has_unresolved_required_task"] = False
    state = finalize_stop_condition(state)
    if state["stop_condition"]["runtime_guardrail"]["must_stop"]:
        state["fsm"]["last_transition"] = {
            "from_state": "running",
            "to_state": "blocked",
            "reason": state["stop_condition"]["final"]["reason"],
        }
        if initial_task_warnings:
            state["fsm"]["last_transition"]["skipped_initial_tasks"] = initial_task_warnings
        state["fsm"]["state"] = "blocked"
    elif initial_task_warnings:
        state["fsm"]["last_transition"] = {
            "from_state": "initialized",
            "to_state": "running",
            "reason": "initial_tasks_filtered_before_runtime_fallback",
            "skipped_initial_tasks": initial_task_warnings,
        }
    state["progress_signals"] = _derive_progress_signals(state.get("findings", []), state.get("progress_signals", {}), state)
    validate_analysis_state(state)
    return state


def _materialize_initial_tasks(state: Dict[str, Any], candidates: List[Dict[str, Any]], warnings: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    accepted: List[Dict[str, Any]] = []
    shadow = _copy_state(state)
    for candidate in candidates:
        task_type = candidate.get("task_type")
        if task_type not in TASK_TYPES:
            if warnings is not None:
                warnings.append(f"unsupported task_type: {task_type}")
            continue
        task = _make_task(
            shadow,
            task_type,
            dict(candidate.get("scope") or {}),
            list(candidate.get("requires") or []),
            int(candidate.get("priority", 100)),
            candidate.get("parent_task_id"),
            candidate.get("reason"),
            candidate.get("evidence_summary"),
            int(candidate.get("retry_count", 0)),
        )
        if not _requires_satisfied(shadow, task):
            if warnings is not None:
                missing = [field for field in task.get("requires", []) if not _known_context_and_scope(shadow, task).get(field)]
                warnings.append(f"{task_type} requires missing context: {', '.join(missing)}")
            continue
        accepted.append(task)
        shadow.setdefault("pending_tasks", []).append(task)
    return _dedup_tasks_by_key(state, accepted)


def validate_analysis_state(state: Dict[str, Any]) -> None:
    missing = TOP_LEVEL_FIELDS - set(state.keys())
    extra = set(state.keys()) - TOP_LEVEL_FIELDS
    if missing:
        raise AnalysisStateError(f"analysis_state missing top-level fields: {sorted(missing)}")
    if extra:
        raise AnalysisStateError(f"analysis_state has unsupported top-level fields: {sorted(extra)}")
    if state.get("schema_version") != SCHEMA_VERSION:
        raise AnalysisStateError(f"unsupported schema_version: {state.get('schema_version')}")
    question = state.get("question") or {}
    if question.get("question_type") not in QUESTION_TYPES:
        raise AnalysisStateError(f"unsupported question_type: {question.get('question_type')}")
    if question.get("analysis_goal") not in ANALYSIS_GOALS:
        raise AnalysisStateError(f"unsupported analysis_goal: {question.get('analysis_goal')}")
    context = state.get("context") or {}
    allow_incomplete_context = _allows_incomplete_context(state)
    for field in ("current_period", "base_period"):
        value = context.get(field)
        if value in (None, "") and allow_incomplete_context:
            continue
        if not isinstance(value, str) or not PERIOD_PATTERN.match(value):
            raise AnalysisStateError(f"context.{field} must match YYYY-MM-01")
    if not isinstance(context.get("global_filters"), dict):
        raise AnalysisStateError("context.global_filters must be an object")
    _validate_scope_fields(context.get("global_filters") or {}, "context.global_filters")
    fsm = state.get("fsm") or {}
    if fsm.get("state") not in FSM_STATES:
        raise AnalysisStateError(f"unsupported fsm.state: {fsm.get('state')}")
    if not isinstance(fsm.get("step"), int) or fsm.get("step") < 0:
        raise AnalysisStateError("fsm.step must be a non-negative integer")
    scheduler = state.get("scheduler") or {}
    if not isinstance(scheduler.get("max_steps"), int) or scheduler.get("max_steps") <= 0:
        raise AnalysisStateError("scheduler.max_steps must be a positive integer")
    if "max_retry" in scheduler and (not isinstance(scheduler.get("max_retry"), int) or scheduler.get("max_retry") < 0):
        raise AnalysisStateError("scheduler.max_retry must be a non-negative integer")
    stop_condition = state.get("stop_condition") or {}
    llm_decision = stop_condition.get("llm_decision") or {}
    if llm_decision.get("answer_readiness") not in ANSWER_READINESS:
        raise AnalysisStateError(f"unsupported answer_readiness: {llm_decision.get('answer_readiness')}")
    guardrail = stop_condition.get("runtime_guardrail") or {}
    if guardrail.get("reason") not in RUNTIME_GUARDRAIL_REASONS:
        raise AnalysisStateError(f"unsupported runtime_guardrail.reason: {guardrail.get('reason')}")
    final = stop_condition.get("final") or {}
    if not isinstance(final.get("should_stop"), bool):
        raise AnalysisStateError("stop_condition.final.should_stop must be a boolean")
    progress_signals = state.get("progress_signals") or {}
    missing_progress_signals = PROGRESS_SIGNAL_FIELDS - set(progress_signals.keys())
    if missing_progress_signals:
        raise AnalysisStateError(f"progress_signals missing fields: {sorted(missing_progress_signals)}")
    extra_progress_signals = set(progress_signals.keys()) - PROGRESS_SIGNAL_FIELDS
    if extra_progress_signals:
        raise AnalysisStateError(f"progress_signals has unsupported fields: {sorted(extra_progress_signals)}")
    for field in PROGRESS_SIGNAL_FIELDS:
        if not isinstance(progress_signals.get(field), bool):
            raise AnalysisStateError(f"progress_signals.{field} must be a boolean")
    dedup = state.get("dedup") or {}
    if not isinstance(dedup.get("visited_task_keys"), list):
        raise AnalysisStateError("dedup.visited_task_keys must be a list")
    if state.get("current_task") is not None:
        _validate_task(state["current_task"])
    for list_name in ("pending_tasks", "completed_tasks", "failed_tasks", "findings"):
        if not isinstance(state.get(list_name), list):
            raise AnalysisStateError(f"{list_name} must be a list")
    for task in state.get("pending_tasks", []):
        _validate_task(task)
    for task in state.get("completed_tasks", []):
        _validate_completed_task(task)
    for task in state.get("failed_tasks", []):
        _validate_failed_task(task)
    for finding in state.get("findings", []):
        _validate_finding(finding)


def _allows_incomplete_context(state: Dict[str, Any]) -> bool:
    stop_condition = state.get("stop_condition") or {}
    guardrail = stop_condition.get("runtime_guardrail") or {}
    final = stop_condition.get("final") or {}
    return (
        guardrail.get("must_stop") is True
        and guardrail.get("reason") == "missing_required_context"
        and final.get("should_stop") is True
    )


def _validate_scope_fields(scope: Dict[str, Any], label: str) -> None:
    invalid = sorted(set(scope.keys()) - ALLOWED_SCOPE_FIELDS)
    if invalid:
        raise AnalysisStateError(f"{label} has unsupported scope fields: {invalid}")


def _validate_task(task: Dict[str, Any]) -> None:
    for field in ("task_id", "task_key", "task_type", "scope", "requires", "priority"):
        if field not in task:
            raise AnalysisStateError(f"task missing required field: {field}")
    if task["task_type"] not in TASK_TYPES:
        raise AnalysisStateError(f"unsupported task_type: {task['task_type']}")
    if not isinstance(task.get("scope"), dict):
        raise AnalysisStateError("task.scope must be an object")
    _validate_scope_fields(task.get("scope") or {}, "task.scope")
    if not isinstance(task.get("requires"), list):
        raise AnalysisStateError("task.requires must be a list")


def _validate_completed_task(task: Dict[str, Any]) -> None:
    for field in ("task_id", "task_key", "task_type", "scope", "result_summary", "generated_task_ids", "completed_at_step"):
        if field not in task:
            raise AnalysisStateError(f"completed task missing required field: {field}")
    if task["task_type"] not in TASK_TYPES:
        raise AnalysisStateError(f"unsupported completed task_type: {task['task_type']}")
    if not isinstance(task.get("scope"), dict):
        raise AnalysisStateError("completed task.scope must be an object")
    _validate_scope_fields(task.get("scope") or {}, "completed task.scope")
    if not isinstance(task.get("generated_task_ids"), list):
        raise AnalysisStateError("completed task.generated_task_ids must be a list")


def _validate_failed_task(task: Dict[str, Any]) -> None:
    for field in ("task_id", "task_key", "task_type", "scope", "failure_reason", "retryable", "retry_count", "failed_at_step"):
        if field not in task:
            raise AnalysisStateError(f"failed task missing required field: {field}")
    if task["task_type"] not in TASK_TYPES:
        raise AnalysisStateError(f"unsupported failed task_type: {task['task_type']}")
    if not isinstance(task.get("scope"), dict):
        raise AnalysisStateError("failed task.scope must be an object")
    _validate_scope_fields(task.get("scope") or {}, "failed task.scope")
    if not isinstance(task.get("retry_count"), int) or task.get("retry_count") < 0:
        raise AnalysisStateError("failed task.retry_count must be a non-negative integer")


def _validate_finding(finding: Dict[str, Any]) -> None:
    for field in ("finding_id", "finding_type", "scope", "summary", "confidence", "source_task_id"):
        if field not in finding:
            raise AnalysisStateError(f"finding missing required field: {field}")
    if finding.get("finding_type") not in FINDING_TYPES:
        raise AnalysisStateError(f"unsupported finding_type: {finding.get('finding_type')}")
    if finding.get("confidence") not in CONFIDENCE_VALUES:
        raise AnalysisStateError(f"unsupported confidence: {finding.get('confidence')}")
    if not isinstance(finding.get("scope"), dict):
        raise AnalysisStateError("finding.scope must be an object")
    _validate_scope_fields(finding.get("scope") or {}, "finding.scope")


def select_task_by_llm(state: Dict[str, Any], llm_decision: Dict[str, Any]) -> Dict[str, Any]:
    updated = _copy_state(state)
    validate_analysis_state(updated)
    if updated["fsm"]["state"] != "running" or updated.get("current_task") is not None:
        raise AnalysisStateError("task can only be selected when fsm.state=running and current_task=null")
    if updated["stop_condition"]["final"].get("should_stop"):
        raise AnalysisStateError("cannot select task when final.should_stop=true")
    if int(updated["fsm"]["step"]) >= int(updated["scheduler"]["max_steps"]):
        updated = update_runtime_guardrail(updated)
        updated = finalize_stop_condition(updated)
        updated["fsm"]["last_transition"] = {
            "from_state": "running",
            "to_state": "blocked",
            "selected_task_id": llm_decision.get("selected_task_id"),
            "reason": updated["stop_condition"]["final"]["reason"],
        }
        updated["fsm"]["state"] = "blocked"
        validate_analysis_state(updated)
        return updated

    selected_task_id = llm_decision.get("selected_task_id")
    selected = None
    remaining = []
    for task in updated.get("pending_tasks", []):
        if task.get("task_id") == selected_task_id:
            selected = task
        else:
            remaining.append(task)
    if selected is None:
        raise AnalysisStateError(f"selected_task_id not found in pending_tasks: {selected_task_id}")
    _assert_requires_satisfied(updated, selected)
    is_retry = int(selected.get("retry_count", 0)) > 0
    if selected["task_key"] in updated.get("dedup", {}).get("visited_task_keys", []) and not is_retry:
        raise AnalysisStateError(f"task already visited: {selected['task_key']}")

    updated["pending_tasks"] = remaining
    updated["current_task"] = selected
    if selected["task_key"] not in updated["dedup"].setdefault("visited_task_keys", []):
        updated["dedup"]["visited_task_keys"].append(selected["task_key"])
    updated["fsm"]["state"] = "waiting_for_tool"
    updated["fsm"]["step"] = int(updated["fsm"].get("step", 0)) + 1
    updated["fsm"]["last_transition"] = {
        "from_state": "running",
        "to_state": "waiting_for_tool",
        "selected_task_id": selected["task_id"],
        "reason": llm_decision.get("decision_reason"),
    }
    validate_analysis_state(updated)
    return updated


def _assert_requires_satisfied(state: Dict[str, Any], task: Dict[str, Any]) -> None:
    known = _known_context_and_scope(state, task)
    missing = [field for field in _required_fields_for_task(task) if not known.get(field)]
    if missing:
        raise AnalysisStateError(f"task requires missing context: {', '.join(missing)}")


def _requires_satisfied(state: Dict[str, Any], task: Dict[str, Any]) -> bool:
    known = _known_context_and_scope(state, task)
    return all(known.get(field) for field in _required_fields_for_task(task))


def build_tool_args(state: Dict[str, Any]) -> Dict[str, Any]:
    validate_analysis_state(state)
    task = state.get("current_task")
    if not task:
        raise AnalysisStateError("current_task is required to build tool args")
    _assert_requires_satisfied(state, task)
    context = state.get("context", {})
    scope = dict(context.get("global_filters") or {})
    scope.update(task.get("scope") or {})
    base_args = {
        "current_period": context.get("current_period"),
        "base_period": context.get("base_period"),
    }
    task_type = task["task_type"]
    if task_type in DIMENSION_BY_TASK_TYPE:
        return {
            "action": "QueryCostChangeDimensions",
            "model_args": {**base_args, "dimension": DIMENSION_BY_TASK_TYPE[task_type], "filters": scope},
        }
    if task_type == "locate_amount":
        charge_item_code = scope.pop("charge_item_code", None)
        if not charge_item_code:
            raise AnalysisStateError("charge_item_code is required to build QueryCostChangeAmountComponents args")
        return {"action": "QueryCostChangeAmountComponents", "model_args": {**base_args, "charge_item_code": charge_item_code, "filters": scope}}
    if task_type == "decompose_charge_item":
        charge_item_code = scope.pop("charge_item_code", None)
        if not charge_item_code:
            raise AnalysisStateError("charge_item_code is required to build QueryCostChangeDrivers args")
        return {"action": "QueryCostChangeDrivers", "model_args": {**base_args, "charge_item_code": charge_item_code, "filters": scope}}
    raise AnalysisStateError(f"cannot build tool args for task_type: {task_type}")


def _task_summary(task: Dict[str, Any]) -> Dict[str, Any]:
    summary = {
        "task_id": task.get("task_id"),
        "task_key": task.get("task_key"),
        "task_type": task.get("task_type"),
        "scope": deepcopy(task.get("scope") or {}),
    }
    for key in ("result_summary", "failure_reason", "error_code", "error_message", "retryable", "retry_count"):
        if key in task:
            summary[key] = deepcopy(task.get(key))
    return summary


def build_llm_view(state: Dict[str, Any]) -> Dict[str, Any]:
    """Project the canonical state into the smaller view used by the LLM.

    This is a deterministic field selection, not a business summary. The full
    state remains authoritative in the workflow state file.
    """
    validate_analysis_state(state)
    return {
        "question": {
            "raw_user_query": (state.get("question") or {}).get("raw_user_query"),
            "question_type": (state.get("question") or {}).get("question_type"),
            "analysis_goal": (state.get("question") or {}).get("analysis_goal"),
        },
        "context": deepcopy(state.get("context") or {}),
        "fsm": {
            "state": (state.get("fsm") or {}).get("state"),
            "step": (state.get("fsm") or {}).get("step"),
            "last_transition": deepcopy((state.get("fsm") or {}).get("last_transition")),
        },
        "current_task": deepcopy(state.get("current_task")),
        "available_next_tasks": deepcopy(state.get("pending_tasks") or []),
        "findings": deepcopy(state.get("findings") or []),
        "progress_signals": deepcopy(state.get("progress_signals") or {}),
        "stop_condition": deepcopy(state.get("stop_condition") or {}),
        "completed_tasks_summary": [_task_summary(task) for task in state.get("completed_tasks", [])],
        "failed_tasks_summary": [_task_summary(task) for task in state.get("failed_tasks", [])],
    }


def normalize_llm_delta(llm_delta: Dict[str, Any]) -> Dict[str, Any]:
    """Convert append/update delta into the existing interpretation shape.

    The public delta is intentionally small and action-oriented. Runtime keeps
    the merge rules deterministic and then reuses apply_tool_success/failure for
    the canonical state transition.
    """
    delta = dict(llm_delta or {})
    current_task_result = delta.get("current_task_result") or {}
    stop_update = delta.get("stop_condition_update") or {}
    interpretation = {
        "result_summary": (
            current_task_result.get("result_summary")
            or delta.get("result_summary")
            or "tool result interpreted by LLM"
        ),
        "findings": deepcopy(delta.get("findings_append") or delta.get("new_findings") or delta.get("findings") or []),
        "candidate_tasks": deepcopy(delta.get("pending_tasks_append") or delta.get("candidate_tasks") or []),
        "progress_signals": deepcopy(delta.get("progress_signals_update") or delta.get("progress_signals") or {}),
        "llm_decision": deepcopy(stop_update.get("llm_decision") or delta.get("llm_decision") or {}),
    }
    for key in ("evidence_refs", "next_task_decision"):
        if key in delta:
            interpretation[key] = deepcopy(delta[key])
    return interpretation


def apply_result(
    state: Dict[str, Any],
    tool_result: Optional[Dict[str, Any]] = None,
    error: Optional[Dict[str, Any]] = None,
    llm_delta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply one tool result and return the updated business state and stop decision."""
    interpretation = normalize_llm_delta(llm_delta or {})
    if error is not None:
        updated = apply_tool_failure(state, error or {}, interpretation)
    else:
        updated = apply_tool_success(state, tool_result or {}, interpretation)
    return {
        "analysis_state": deepcopy(updated),
        "should_stop": bool(updated.get("stop_condition", {}).get("final", {}).get("should_stop")),
    }


def _select_task_decision_from_next_step(state: Dict[str, Any], next_task_decision: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not state.get("pending_tasks"):
        return None
    decision = dict(next_task_decision or {})
    selected_task_id = decision.get("selected_task_id")
    task_key_or_type = decision.get("task_key_or_type") or decision.get("task_key") or decision.get("task_type")
    selected = None
    if selected_task_id:
        selected = next((task for task in state.get("pending_tasks", []) if task.get("task_id") == selected_task_id), None)
    if selected is None and task_key_or_type:
        selected = next(
            (
                task
                for task in state.get("pending_tasks", [])
                if task.get("task_key") == task_key_or_type or task.get("task_type") == task_key_or_type
            ),
            None,
        )
    if selected is None:
        selected = sorted(
            state.get("pending_tasks", []),
            key=lambda task: (-int(task.get("priority", 0)), str(task.get("task_id") or "")),
        )[0]
    return {
        "selected_task_id": selected.get("task_id"),
        "decision_reason": decision.get("decision_reason") or selected.get("reason") or "runtime selected the highest priority available task",
    }


def next_step(state: Dict[str, Any], next_task_decision: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Select the next task and build tool args using runtime-controlled state."""
    validate_analysis_state(state)
    if state.get("stop_condition", {}).get("final", {}).get("should_stop"):
        return {"should_stop": True, "analysis_state": deepcopy(state), "reason": state["stop_condition"]["final"].get("reason")}
    fsm_state = state.get("fsm", {}).get("state")
    if fsm_state != "running":
        raise AnalysisStateError(
            f"next_step requires fsm.state=running, got {fsm_state}; "
            "did you call next_step twice without applying the result?"
        )
    decision = _select_task_decision_from_next_step(state, next_task_decision)
    if decision is None:
        guarded = finalize_stop_condition(update_runtime_guardrail(state))
        return {
            "should_stop": bool(guarded.get("stop_condition", {}).get("final", {}).get("should_stop")),
            "analysis_state": deepcopy(guarded),
            "reason": guarded.get("stop_condition", {}).get("final", {}).get("reason"),
        }
    selected = select_task_by_llm(state, decision)
    tool_args = build_tool_args(selected)
    return {
        "should_stop": False,
        "analysis_state": deepcopy(selected),
        "tool_args": tool_args,
    }


def apply_tool_success(
    state: Dict[str, Any],
    tool_result: Dict[str, Any],
    llm_interpretation: Dict[str, Any],
) -> Dict[str, Any]:
    if not llm_interpretation:
        raise AnalysisStateError("llm_interpretation is required for success transition")
    updated = _copy_state(state)
    task = updated.get("current_task")
    if not task:
        raise AnalysisStateError("current_task is required for success transition")
    if updated["fsm"]["state"] != "waiting_for_tool":
        raise AnalysisStateError("tool result can only be applied when fsm.state=waiting_for_tool")
    from_state = updated["fsm"]["state"]
    updated["fsm"]["state"] = "interpreting_result"

    new_findings = []
    evidence_refs = llm_interpretation.get("evidence_refs")
    for finding in llm_interpretation.get("findings", []):
        item = dict(finding)
        item.setdefault("finding_id", _next_numbered_id(updated.get("findings", []) + new_findings, "finding_id", "finding"))
        item.setdefault("source_task_id", task["task_id"])
        item.setdefault("scope", deepcopy(task.get("scope", {})))
        item.setdefault("confidence", "unknown")
        item.setdefault("summary", llm_interpretation.get("result_summary") or "tool result interpreted by LLM")
        if evidence_refs and "evidence_refs" not in item:
            item["evidence_refs"] = deepcopy(evidence_refs)
        new_findings.append(item)
    updated["findings"].extend(new_findings)

    candidate_task_warnings: List[str] = []
    candidate_tasks = _materialize_candidate_tasks(updated, llm_interpretation.get("candidate_tasks", []), task["task_id"], candidate_task_warnings)
    generated_task_ids = [candidate["task_id"] for candidate in candidate_tasks]
    completed = {
        "task_id": task["task_id"],
        "task_key": task["task_key"],
        "task_type": task["task_type"],
        "scope": task.get("scope", {}),
        "result_summary": llm_interpretation.get("result_summary") or _summarize_tool_result(tool_result),
        "generated_task_ids": generated_task_ids,
        "completed_at_step": updated["fsm"].get("step"),
    }
    if evidence_refs:
        completed["evidence_refs"] = deepcopy(evidence_refs)
    updated["completed_tasks"].append(completed)
    updated["pending_tasks"].extend(candidate_tasks)
    updated["current_task"] = None
    _merge_progress_signals(updated["progress_signals"], llm_interpretation.get("progress_signals", {}))
    updated["progress_signals"] = _derive_progress_signals(updated.get("findings", []), updated.get("progress_signals", {}), updated)
    llm_decision_warnings = _llm_decision_warnings(llm_interpretation)
    _merge_llm_decision(updated, llm_interpretation)
    updated = update_runtime_guardrail(updated)
    updated = finalize_stop_condition(updated)
    updated["progress_signals"] = _derive_progress_signals(updated.get("findings", []), updated.get("progress_signals", {}), updated)
    final_state = "ready_to_answer" if updated["stop_condition"]["final"]["should_stop"] else "running"
    updated["fsm"]["last_transition"] = {
        "from_state": from_state,
        "to_state": final_state,
        "consumed_task_id": task["task_id"],
        "generated_task_ids": generated_task_ids,
        "transition_reason": completed["result_summary"],
    }
    if llm_decision_warnings:
        updated["fsm"]["last_transition"]["warnings"] = llm_decision_warnings
    if candidate_task_warnings:
        updated["fsm"]["last_transition"]["skipped_candidate_tasks"] = candidate_task_warnings
    updated["fsm"]["state"] = final_state
    validate_analysis_state(updated)
    return updated


def apply_tool_failure(
    state: Dict[str, Any],
    error: Dict[str, Any],
    llm_interpretation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    llm_interpretation = llm_interpretation or {}
    updated = _copy_state(state)
    task = updated.get("current_task")
    if not task:
        raise AnalysisStateError("current_task is required for failure transition")
    if updated["fsm"]["state"] != "waiting_for_tool":
        raise AnalysisStateError("tool result can only be applied when fsm.state=waiting_for_tool")
    retry_count = int(task.get("retry_count", 0))
    failed = {
        "task_id": task["task_id"],
        "task_key": task["task_key"],
        "task_type": task["task_type"],
        "scope": task.get("scope", {}),
        "failure_reason": error.get("failure_reason") or "tool_error",
        "error_code": error.get("error_code"),
        "error_message": error.get("error_message"),
        "retryable": bool(error.get("retryable", False)),
        "retry_count": retry_count,
        "failed_at_step": updated["fsm"].get("step"),
    }
    updated["failed_tasks"].append(failed)
    updated["current_task"] = None
    retry_task = _make_retry_task(updated, task, failed)
    generated_task_ids = []
    if retry_task:
        updated["pending_tasks"].append(retry_task)
        generated_task_ids.append(retry_task["task_id"])
    llm_decision_warnings = _llm_decision_warnings(llm_interpretation) if llm_interpretation else []
    _merge_llm_decision(updated, llm_interpretation)
    updated = update_runtime_guardrail(updated)
    updated = finalize_stop_condition(updated)
    final_state = "ready_to_answer" if updated["stop_condition"]["final"]["should_stop"] else "running"
    updated["fsm"]["last_transition"] = {
        "from_state": "waiting_for_tool",
        "to_state": final_state,
        "consumed_task_id": task["task_id"],
        "generated_task_ids": generated_task_ids,
        "transition_reason": failed["failure_reason"],
    }
    if llm_decision_warnings:
        updated["fsm"]["last_transition"]["warnings"] = llm_decision_warnings
    updated["fsm"]["state"] = final_state
    validate_analysis_state(updated)
    return updated


def _merge_progress_signals(current: Dict[str, Any], llm_progress: Dict[str, Any]) -> None:
    for key, value in (llm_progress or {}).items():
        if key in PROGRESS_SIGNAL_FIELDS and isinstance(value, bool):
            current[key] = value


def _llm_decision_warnings(llm_interpretation: Dict[str, Any]) -> List[str]:
    llm_decision = llm_interpretation.get("llm_decision")
    if not isinstance(llm_decision, dict) or not llm_decision:
        return ["llm_interpretation_missing_llm_decision", "llm_interpretation_missing_stop_reason"]
    warnings: List[str] = []
    for field in ("should_stop", "answer_readiness"):
        if field not in llm_decision:
            warnings.append(f"llm_interpretation_missing_{field}")
    if llm_decision.get("should_stop") is True and llm_decision.get("answer_readiness") in {"not_ready", "partially_ready"}:
        warnings.append("inconsistent_llm_stop_decision")
    if not llm_decision.get("reason"):
        warnings.append("llm_interpretation_missing_stop_reason")
    return warnings


def _merge_llm_decision(state: Dict[str, Any], llm_interpretation: Dict[str, Any]) -> None:
    llm_decision = llm_interpretation.get("llm_decision") if isinstance(llm_interpretation, dict) else None
    target = state["stop_condition"].setdefault("llm_decision", {})
    if not isinstance(llm_decision, dict) or not llm_decision:
        target.update({
            "should_stop": False,
            "answer_readiness": "not_ready",
            "reason": "llm_decision_missing_in_current_interpretation",
            "next_required_task_id": None,
        })
        return
    target.update(llm_decision)
    if "should_stop" not in llm_decision:
        target["should_stop"] = False
    if "answer_readiness" not in llm_decision:
        target["answer_readiness"] = "not_ready"
    if not llm_decision.get("reason"):
        target["reason"] = "llm_decision_missing_in_current_interpretation"


def _make_retry_task(state: Dict[str, Any], original_task: Dict[str, Any], failed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not failed.get("retryable"):
        return None
    next_retry_count = int(failed.get("retry_count", 0)) + 1
    max_retry = int(state.get("scheduler", {}).get("max_retry", 1))
    if next_retry_count > max_retry:
        return None
    retry_task = deepcopy(original_task)
    retry_task["task_id"] = _next_numbered_id(_all_tasks(state), "task_id", "task")
    retry_task["retry_count"] = next_retry_count
    retry_task["priority"] = max(0, int(original_task.get("priority", 50)) - 20)
    retry_task["reason"] = original_task.get("reason") or _default_reason(original_task["task_type"], original_task.get("scope", {}))
    retry_task["reason"] = f"{retry_task['reason']}（第 {next_retry_count} 次重试）"
    retry_task["last_failure_reason"] = failed.get("failure_reason") or "tool_error"
    retry_task["evidence_summary"] = f"retry after previous failure: {retry_task['last_failure_reason']}"
    return retry_task


def _derive_progress_signals(findings: List[Dict[str, Any]], progress_signals: Dict[str, Any], state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    derived = {key: bool(progress_signals.get(key, False)) for key in PROGRESS_SIGNAL_FIELDS}
    derived["has_primary_charge_item"] = False
    derived["has_answerable_finding"] = False
    if any(finding.get("finding_type") == "dimension_locate" for finding in findings):
        derived["has_primary_dimension"] = True
    if any(
        finding.get("finding_type") in PRIMARY_CHARGE_ITEM_FINDING_TYPES
        and (finding.get("scope") or {}).get("charge_item_code")
        for finding in findings
    ):
        derived["has_primary_charge_item"] = True
    if any(finding.get("finding_type") == "driver_decompose" for finding in findings):
        derived["has_driver_explanation"] = True
    question_type = "generic_rca"
    if state is not None:
        question_type = (state.get("question") or {}).get("question_type") or "generic_rca"
    answerable_types = ANSWERABLE_FINDING_TYPES_BY_QUESTION_TYPE.get(question_type, {"amount_breakdown", "driver_decompose"})
    if any(finding.get("finding_type") in answerable_types for finding in findings):
        derived["has_answerable_finding"] = True
    if state is not None:
        final_should_stop = bool(state.get("stop_condition", {}).get("final", {}).get("should_stop"))
        derived["has_unresolved_required_task"] = bool((state.get("pending_tasks") or state.get("current_task")) and not final_should_stop)
    return derived


def _materialize_candidate_tasks(
    state: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    parent_task_id: Optional[str],
    warnings: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    accepted: List[Dict[str, Any]] = []
    shadow = _copy_state(state)
    existing = _existing_task_keys(shadow)
    for candidate in candidates:
        task_type = candidate.get("task_type")
        if task_type not in TASK_TYPES:
            if warnings is not None:
                warnings.append(f"unsupported task_type: {task_type}")
            continue
        scope = dict(candidate.get("scope") or {})
        task_key = generate_task_key(task_type, scope)
        if task_key in existing:
            continue
        task = _make_task(
            shadow,
            task_type,
            scope,
            list(candidate.get("requires") or []),
            int(candidate.get("priority", 50)),
            candidate.get("parent_task_id", parent_task_id),
            candidate.get("reason"),
            candidate.get("evidence_summary"),
        )
        if not _requires_satisfied(shadow, task):
            if warnings is not None:
                missing = [field for field in _required_fields_for_task(task) if not _known_context_and_scope(shadow, task).get(field)]
                warnings.append(f"{task_type} requires missing context: {', '.join(missing)}")
            continue
        accepted.append(task)
        shadow.setdefault("pending_tasks", []).append(task)
        existing.add(task["task_key"])
    return accepted


def _summarize_tool_result(tool_result: Dict[str, Any]) -> str:
    if isinstance(tool_result, dict) and tool_result.get("summary"):
        return str(tool_result["summary"])
    return "tool completed and result interpreted by LLM"


def generate_task_key(task_type: str, scope: Optional[Dict[str, Any]] = None) -> str:
    parts = [task_type]
    for key in sorted((scope or {}).keys()):
        value = (scope or {})[key]
        if value is not None and value != "":
            parts.append(f"{key}={value}")
    return "|".join(parts)


def _dedup_tasks_by_key(state: Dict[str, Any], candidate_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    existing = _existing_task_keys(state)
    deduped = []
    for task in candidate_tasks:
        task_key = task.get("task_key") or generate_task_key(task.get("task_type"), task.get("scope", {}))
        if task_key in existing:
            continue
        task = dict(task)
        task["task_key"] = task_key
        deduped.append(task)
        existing.add(task_key)
    return deduped


def dedup_tasks(state: Dict[str, Any], candidate_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Backward-compatible alias that only de-duplicates by task_key.

    Callers that need complete task objects should use the materialization helpers
    instead of passing hand-written partial task dictionaries here.
    """
    return _dedup_tasks_by_key(state, candidate_tasks)


def materialize_candidate_tasks(
    state: Dict[str, Any],
    candidate_tasks: List[Dict[str, Any]],
    parent_task_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return complete, validated task objects from partial LLM candidates.

    This is the public helper for callers that need task_id/task_key/requires and
    task_key de-duplication. Unsupported or unsatisfied candidates are skipped,
    matching the runtime transition behavior.
    """
    updated = _copy_state(state)
    validate_analysis_state(updated)
    return _materialize_candidate_tasks(updated, candidate_tasks, parent_task_id)


def update_runtime_guardrail(state: Dict[str, Any]) -> Dict[str, Any]:
    updated = _copy_state(state)
    reason = None
    must_stop = False
    context = updated.get("context", {})
    llm_should_stop = bool(updated.get("stop_condition", {}).get("llm_decision", {}).get("should_stop"))
    if not context.get("current_period") or not context.get("base_period"):
        must_stop = True
        reason = "missing_required_context"
    elif _has_retry_exceeded(updated) and not llm_should_stop:
        must_stop = True
        reason = "tool_error_retry_exceeded"
    elif int(updated.get("fsm", {}).get("step", 0)) >= int(updated.get("scheduler", {}).get("max_steps", 8)) and not llm_should_stop:
        must_stop = True
        reason = "max_steps_reached"
    elif not updated.get("pending_tasks") and not updated.get("current_task") and not llm_should_stop:
        must_stop = True
        reason = "no_executable_task"
    updated["stop_condition"]["runtime_guardrail"] = {"must_stop": must_stop, "reason": reason}
    return updated


def _has_retry_exceeded(state: Dict[str, Any]) -> bool:
    if state.get("pending_tasks") or state.get("current_task"):
        return False
    failed_tasks = state.get("failed_tasks") or []
    if not failed_tasks:
        return False
    max_retry = int(state.get("scheduler", {}).get("max_retry", 1))
    return any(bool(failed.get("retryable")) and int(failed.get("retry_count", 0)) >= max_retry for failed in failed_tasks)


def finalize_stop_condition(state: Dict[str, Any]) -> Dict[str, Any]:
    updated = _copy_state(state)
    guardrail = updated["stop_condition"].get("runtime_guardrail", {})
    llm_decision = updated["stop_condition"].get("llm_decision", {})
    if guardrail.get("must_stop"):
        reason = guardrail.get("reason") or "invalid_state"
        updated["stop_condition"]["final"] = {
            "should_stop": True,
            "reason": f"runtime_guardrail_{reason}",
        }
    else:
        should_stop = bool(llm_decision.get("should_stop", False))
        readiness = llm_decision.get("answer_readiness")
        if should_stop and readiness in {"not_ready", "partially_ready"}:
            warnings = list(llm_decision.get("warnings") or [])
            if "inconsistent_llm_stop_decision" not in warnings:
                warnings.append("inconsistent_llm_stop_decision")
            updated["stop_condition"]["llm_decision"]["warnings"] = warnings
            reason = "llm_stop_decision_inconsistent"
        elif should_stop and readiness == "ready_with_limitations":
            reason = "llm_answer_ready_with_limitations"
        elif should_stop:
            reason = "llm_answer_ready"
        else:
            reason = "llm_requires_more_analysis"
        updated["stop_condition"]["final"] = {"should_stop": should_stop, "reason": reason}
    validate_analysis_state(updated)
    return updated


def _load_json_arg(value: Optional[str], file_path: Optional[str]) -> Dict[str, Any]:
    if file_path:
        return json.loads(Path(file_path).read_text(encoding="utf-8"))
    if value:
        return json.loads(value)
    return {}


def _load_state(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_output(data: Dict[str, Any], output_file: Optional[str]) -> None:
    if output_file:
        Path(output_file).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cli_main(argv: Optional[List[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description="Runtime helper CLI for analysis_state v0.3")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--input-json")
    init_parser.add_argument("--input-file")
    init_parser.add_argument("--output-file")

    select_parser = subparsers.add_parser("select-task")
    select_parser.add_argument("--state-file", required=True)
    select_parser.add_argument("--decision-json")
    select_parser.add_argument("--decision-file")
    select_parser.add_argument("--output-file")

    llm_view_parser = subparsers.add_parser("build-llm-view")
    llm_view_parser.add_argument("--state-file", required=True)
    llm_view_parser.add_argument("--output-file")

    next_step_parser = subparsers.add_parser("next-step")
    next_step_parser.add_argument("--state-file", required=True)
    next_step_parser.add_argument("--next-task-decision-json")
    next_step_parser.add_argument("--next-task-decision-file")
    next_step_parser.add_argument("--output-file")

    build_parser = subparsers.add_parser("build-tool-args")
    build_parser.add_argument("--state-file", required=True)
    build_parser.add_argument("--output-file")

    success_parser = subparsers.add_parser("apply-success")
    success_parser.add_argument("--state-file", required=True)
    success_parser.add_argument("--tool-result-json")
    success_parser.add_argument("--tool-result-file")
    success_parser.add_argument("--llm-interpretation-json")
    success_parser.add_argument("--llm-interpretation-file")
    success_parser.add_argument("--output-file")

    failure_parser = subparsers.add_parser("apply-failure")
    failure_parser.add_argument("--state-file", required=True)
    failure_parser.add_argument("--error-json")
    failure_parser.add_argument("--error-file")
    failure_parser.add_argument("--llm-interpretation-json")
    failure_parser.add_argument("--llm-interpretation-file")
    failure_parser.add_argument("--output-file")

    apply_result_parser = subparsers.add_parser("apply-result")
    apply_result_parser.add_argument("--state-file", required=True)
    apply_result_parser.add_argument("--tool-result-json")
    apply_result_parser.add_argument("--tool-result-file")
    apply_result_parser.add_argument("--error-json")
    apply_result_parser.add_argument("--error-file")
    apply_result_parser.add_argument("--llm-delta-json")
    apply_result_parser.add_argument("--llm-delta-file")
    apply_result_parser.add_argument("--output-file")

    args = parser.parse_args(argv)
    if args.command == "init":
        payload = _load_json_arg(args.input_json, args.input_file)
        result = initialize_analysis_state(str(payload.get("user_query") or payload.get("raw_user_query") or ""), payload.get("parsed_context") or payload)
    elif args.command == "select-task":
        result = select_task_by_llm(_load_state(args.state_file), _load_json_arg(args.decision_json, args.decision_file))
    elif args.command == "build-llm-view":
        result = build_llm_view(_load_state(args.state_file))
    elif args.command == "next-step":
        result = next_step(_load_state(args.state_file), _load_json_arg(args.next_task_decision_json, args.next_task_decision_file))
    elif args.command == "build-tool-args":
        result = build_tool_args(_load_state(args.state_file))
    elif args.command == "apply-success":
        result = apply_tool_success(
            _load_state(args.state_file),
            _load_json_arg(args.tool_result_json, args.tool_result_file),
            _load_json_arg(args.llm_interpretation_json, args.llm_interpretation_file),
        )
    elif args.command == "apply-failure":
        result = apply_tool_failure(
            _load_state(args.state_file),
            _load_json_arg(args.error_json, args.error_file),
            _load_json_arg(args.llm_interpretation_json, args.llm_interpretation_file),
        )
    elif args.command == "apply-result":
        result = apply_result(
            _load_state(args.state_file),
            _load_json_arg(args.tool_result_json, args.tool_result_file),
            _load_json_arg(args.error_json, args.error_file) if (args.error_json or args.error_file) else None,
            _load_json_arg(args.llm_delta_json, args.llm_delta_file),
        )
    else:
        raise AnalysisStateError(f"unsupported command: {args.command}")
    _write_output(result, getattr(args, "output_file", None))
    return result


def main() -> None:
    try:
        print(json.dumps(cli_main(), ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
