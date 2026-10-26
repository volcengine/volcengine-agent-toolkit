#!/usr/bin/env python3
"""RCA Workflow Orchestrator (step/resume pattern).

Deterministic workflow controller for RCA analysis. The script owns the
process skeleton; LLM only answers narrow structured questions at hook points.

Usage:
  run_rca_workflow.py init --question <str> --context-json <json> --state-file <path>
  run_rca_workflow.py step --state-file <path>
  run_rca_workflow.py resume --state-file <path> --hook-response-file <path>
  run_rca_workflow.py resume --state-file <path> --tool-result-file <path>
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from analysis_state import (
    initialize_analysis_state,
    apply_result,
    next_step,
    _load_state,
    validate_analysis_state,
)
from runtime_utils import atomic_write_json
from call_openapi import add_runtime_arguments, resolve_config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HOOK_TYPES = {"choose_task", "interpret_result", "draft_answer"}
ANSWER_READINESS = {"not_ready", "partially_ready", "ready", "ready_with_limitations"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path or not os.path.isfile(path):
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _artifacts_dir(state_file: str) -> Path:
    base = Path(state_file).resolve().parent
    art = base / (Path(state_file).name + ".artifacts")
    art.mkdir(parents=True, exist_ok=True)
    return art


def _artifact_path(state_file: str, name: str) -> str:
    return str(_artifacts_dir(state_file) / name)


def _write_artifact(state_file: str, name: str, data: Dict[str, Any]) -> str:
    path = _artifact_path(state_file, name)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(Path(path), data)
    return path


def _read_state(state_file: str) -> Dict[str, Any]:
    return _load_state(state_file)


def _write_state(state_file: str, state: Dict[str, Any]) -> None:
    Path(state_file).parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(Path(state_file), state)


def _current_step(state: Dict[str, Any]) -> int:
    return int(state.get("fsm", {}).get("step", 0))


def _current_task_id(state: Dict[str, Any]) -> Optional[str]:
    task = state.get("current_task")
    return task.get("task_id") if task else None


def _findings_summary(findings: List[Dict[str, Any]]) -> List[str]:
    return [f.get("summary", "") for f in findings if f.get("summary")]


def _pending_tasks_summary(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "task_id": t.get("task_id"),
            "description": t.get("description", ""),
            "category": t.get("category", ""),
            "priority": t.get("priority", 0),
        }
        for t in state.get("pending_tasks", [])
    ]


def _completed_tasks_summary(state: Dict[str, Any]) -> List[str]:
    return [t.get("task_id", "") for t in state.get("completed_tasks", [])]


def _failed_tasks_summary(state: Dict[str, Any]) -> List[str]:
    return [t.get("task_id", "") for t in state.get("failed_tasks", [])]


def _remaining_steps(state: Dict[str, Any]) -> int:
    max_steps = int(state.get("scheduler", {}).get("max_steps", 8))
    return max(0, max_steps - _current_step(state))


# ---------------------------------------------------------------------------
# Per-step artifact naming (binds to task_id + step to avoid cross-task pollution)
# ---------------------------------------------------------------------------

ARTIFACT_NAMES = {
    "hook_request": "hook_request.json",
    "tool_result": "tool_result.json",
    "tool_args": "tool_args.json",
    "final_answer": "final_answer.json",
    "workflow_meta": "workflow_meta.json",
    "openapi_config": "openapi_config.json",
}


def _wf_meta_path(state_file: str) -> str:
    return _artifact_path(state_file, ARTIFACT_NAMES["workflow_meta"])


def _read_wf_meta(state_file: str) -> Dict[str, Any]:
    return _load_json(_wf_meta_path(state_file)) or {}


def _write_wf_meta(state_file: str, meta: Dict[str, Any]) -> None:
    _write_artifact(state_file, ARTIFACT_NAMES["workflow_meta"], meta)


def _current_tool_result(state_file: str, task_id: Optional[str], step: int) -> Optional[Dict[str, Any]]:
    """Read tool_result only if it matches current task_id and step."""
    meta = _read_wf_meta(state_file)
    tr_task = meta.get("tool_result_task_id")
    tr_step = meta.get("tool_result_step")
    if tr_task != task_id or tr_step != step:
        return None
    return _load_json(_artifact_path(state_file, ARTIFACT_NAMES["tool_result"]))


def _current_tool_args(state_file: str, task_id: Optional[str], step: int) -> Optional[Dict[str, Any]]:
    """Read tool_args only if it matches current task_id and step."""
    meta = _read_wf_meta(state_file)
    ta_task = meta.get("tool_args_task_id")
    ta_step = meta.get("tool_args_step")
    if ta_task != task_id or ta_step != step:
        return None
    return _load_json(_artifact_path(state_file, ARTIFACT_NAMES["tool_args"]))


def _pending_hook_type(state_file: str) -> Optional[str]:
    """Return the hook_type of the pending hook_request, if any."""
    meta = _read_wf_meta(state_file)
    return meta.get("pending_hook_type")


def _clear_tool_result(state_file: str) -> None:
    """Remove tool_result artifact and meta bindings."""
    meta = _read_wf_meta(state_file)
    for key in ("tool_result_task_id", "tool_result_step"):
        meta.pop(key, None)
    _write_wf_meta(state_file, meta)
    p = _artifact_path(state_file, ARTIFACT_NAMES["tool_result"])
    if os.path.isfile(p):
        os.remove(p)


def _clear_tool_args(state_file: str) -> None:
    meta = _read_wf_meta(state_file)
    for key in ("tool_args_task_id", "tool_args_step"):
        meta.pop(key, None)
    _write_wf_meta(state_file, meta)
    p = _artifact_path(state_file, ARTIFACT_NAMES["tool_args"])
    if os.path.isfile(p):
        os.remove(p)


def _clear_hook_request(state_file: str) -> None:
    meta = _read_wf_meta(state_file)
    meta.pop("pending_hook_type", None)
    meta.pop("hook_request_task_id", None)
    meta.pop("hook_request_step", None)
    _write_wf_meta(state_file, meta)
    p = _artifact_path(state_file, ARTIFACT_NAMES["hook_request"])
    if os.path.isfile(p):
        os.remove(p)


# ---------------------------------------------------------------------------
# Hook request builders
# ---------------------------------------------------------------------------


def _build_choose_task_hook(state: Dict[str, Any], state_file: str) -> Dict[str, Any]:
    hook = {
        "hook_type": "choose_task",
        "question": state.get("question", {}).get("raw_user_query", ""),
        "analysis_goal": state.get("question", {}).get("analysis_goal", ""),
        "current_findings_summary": _findings_summary(state.get("findings", [])),
        "pending_tasks": _pending_tasks_summary(state),
        "completed_tasks": _completed_tasks_summary(state),
        "failed_tasks": _failed_tasks_summary(state),
        "constraints": {
            "max_steps": state.get("scheduler", {}).get("max_steps", 8),
            "remaining_steps": _remaining_steps(state),
        },
    }
    _clear_hook_request(state_file)
    path = _write_artifact(state_file, ARTIFACT_NAMES["hook_request"], hook)
    step = _current_step(state)
    _write_wf_meta(state_file, {**_read_wf_meta(state_file), "pending_hook_type": "choose_task", "hook_request_task_id": _current_task_id(state), "hook_request_step": step})
    return {
        "action": "await_hook",
        "hook_type": "choose_task",
        "hook_request_file": path,
        "prompt_for_agent": (
            "请根据 hook_request.json 中的 pending_tasks，"
            "选择一个 task_id 执行，返回 JSON 格式的 hook_response。"
        ),
    }


def _build_interpret_result_hook(
    state: Dict[str, Any],
    state_file: str,
    tool_result: Dict[str, Any],
) -> Dict[str, Any]:
    current_task = state.get("current_task") or {}
    hook = {
        "hook_type": "interpret_result",
        "tool_name": current_task.get("category", ""),
        "tool_args": current_task.get("tool_args", {}),
        "tool_result_summary": _summarize_tool_result(tool_result),
        "current_task": {
            "task_id": current_task.get("task_id"),
            "description": current_task.get("description", ""),
        },
        "existing_findings": state.get("findings", []),
        "question": state.get("question", {}).get("raw_user_query", ""),
    }
    _clear_hook_request(state_file)
    path = _write_artifact(state_file, ARTIFACT_NAMES["hook_request"], hook)
    step = _current_step(state)
    _write_wf_meta(state_file, {**_read_wf_meta(state_file), "pending_hook_type": "interpret_result", "hook_request_task_id": _current_task_id(state), "hook_request_step": step})
    return {
        "action": "await_hook",
        "hook_type": "interpret_result",
        "hook_request_file": path,
        "prompt_for_agent": (
            "请根据 hook_request.json 中的工具执行结果，"
            "解释结果并生成 findings、candidate_tasks 和 llm_decision，"
            "返回 JSON 格式的 hook_response。"
        ),
    }


def _build_draft_answer_hook(state: Dict[str, Any], state_file: str) -> Dict[str, Any]:
    final = state.get("stop_condition", {}).get("final", {})
    hook = {
        "hook_type": "draft_answer",
        "question": state.get("question", {}).get("raw_user_query", ""),
        "analysis_goal": state.get("question", {}).get("analysis_goal", ""),
        "findings": state.get("findings", []),
        "stop_reason": final.get("reason", ""),
        "completed_tasks": _completed_tasks_summary(state),
        "failed_tasks": _failed_tasks_summary(state),
        "constraints": {
            "language": "zh-CN",
            "max_length": 2000,
        },
    }
    _clear_hook_request(state_file)
    path = _write_artifact(state_file, ARTIFACT_NAMES["hook_request"], hook)
    _write_wf_meta(state_file, {**_read_wf_meta(state_file), "pending_hook_type": "draft_answer", "hook_request_task_id": _current_task_id(state), "hook_request_step": _current_step(state)})
    return {
        "action": "await_hook",
        "hook_type": "draft_answer",
        "hook_request_file": path,
        "prompt_for_agent": (
            "请根据 hook_request.json 中的所有 findings，"
            "生成最终自然语言分析答案，返回 JSON 格式的 hook_response。"
        ),
    }


def _summarize_tool_result(tool_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract a compact summary from a tool result."""
    if tool_result.get("error"):
        return {"error": tool_result["error"], "has_error": True}
    response = tool_result.get("result")
    if isinstance(response, dict) and isinstance(response.get("Result"), dict):
        return response["Result"]
    summary = {}
    for key in ("top_items", "summary", "total_items", "drivers", "changes"):
        if key in tool_result:
            summary[key] = tool_result[key]
    if not summary:
        summary["raw_keys"] = list(tool_result.keys())
    return summary


# ---------------------------------------------------------------------------
# Hook response validation
# ---------------------------------------------------------------------------


def _validate_choose_task(response: Dict[str, Any], pending_ids: set) -> Tuple[bool, str]:
    selected = response.get("selected_task_id")
    if not selected:
        return False, "selected_task_id is required"
    if selected not in pending_ids:
        return False, f"selected_task_id '{selected}' not in pending_tasks: {sorted(pending_ids)}"
    if not response.get("decision_reason"):
        return False, "decision_reason is required"
    return True, ""


def _validate_interpret_result(response: Dict[str, Any]) -> Tuple[bool, str]:
    if not response.get("result_summary"):
        return False, "result_summary is required"
    findings = response.get("findings")
    if not isinstance(findings, list):
        return False, "findings must be a list"
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            return False, f"findings[{i}] must be an object"
        if not f.get("finding_type") and not f.get("type"):
            return False, f"findings[{i}].finding_type (or type) is required"
        if not f.get("summary"):
            return False, f"findings[{i}].summary is required"
    llm_decision = response.get("llm_decision")
    if not isinstance(llm_decision, dict):
        return False, "llm_decision is required"
    if not isinstance(llm_decision.get("should_stop"), bool):
        return False, "llm_decision.should_stop must be a boolean"
    if llm_decision.get("answer_readiness") not in ANSWER_READINESS:
        return False, f"llm_decision.answer_readiness must be one of {ANSWER_READINESS}"
    return True, ""


def _validate_draft_answer(response: Dict[str, Any]) -> Tuple[bool, str]:
    if not response.get("final_answer"):
        return False, "final_answer is required"
    return True, ""


# ---------------------------------------------------------------------------
# Hook response consumers
# ---------------------------------------------------------------------------


def _consume_choose_task(
    state: Dict[str, Any],
    state_file: str,
    response: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute next-step based on LLM's task selection. Save tool_args to artifact."""
    _clear_tool_result(state_file)
    next_task_decision = {
        "selected_task_id": response["selected_task_id"],
        "decision_reason": response["decision_reason"],
    }
    result = next_step(state, next_task_decision)
    new_state = result["analysis_state"]
    tool_args = result.get("tool_args", {})
    _write_state(state_file, new_state)

    task_id = _current_task_id(new_state)
    step = _current_step(new_state)
    _write_artifact(state_file, ARTIFACT_NAMES["tool_args"], tool_args)
    _write_wf_meta(state_file, {**_read_wf_meta(state_file), "tool_args_task_id": task_id, "tool_args_step": step})
    return new_state


def _consume_interpret_result(
    state: Dict[str, Any],
    state_file: str,
    response: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply tool result + LLM interpretation to advance state. Clean up tool_result after."""
    tool_result = _current_tool_result(state_file, _current_task_id(state), _current_step(state)) or {}

    llm_delta = {
        "result_summary": response.get("result_summary", ""),
        "findings": response.get("findings", []),
        "candidate_tasks": response.get("candidate_tasks", []),
        "llm_decision": response.get("llm_decision", {}),
        "progress_signals": response.get("progress_signals", {}),
    }

    result = apply_result(
        state,
        tool_result=tool_result if not tool_result.get("error") else None,
        error=(tool_result["error"] if isinstance(tool_result.get("error"), dict) else tool_result)
              if tool_result.get("error") else None,
        llm_delta=llm_delta,
    )
    new_state = result["analysis_state"]
    _write_state(state_file, new_state)
    _clear_tool_result(state_file)
    _clear_tool_args(state_file)
    return new_state


def _consume_draft_answer(
    state: Dict[str, Any],
    state_file: str,
    response: Dict[str, Any],
) -> Dict[str, Any]:
    """Write final answer artifact."""
    final_answer = response.get("final_answer", "")
    artifact = {"final_answer": final_answer, "generated_at": _now_iso()}
    _write_artifact(state_file, ARTIFACT_NAMES["final_answer"], artifact)
    return state


# ---------------------------------------------------------------------------
# Core dispatch
# ---------------------------------------------------------------------------


def _determine_next_action(state: Dict[str, Any], state_file: str) -> Dict[str, Any]:
    """Return the next action the agent should take based on current state."""
    fsm = state.get("fsm", {})
    fsm_state = fsm.get("state", "")
    current_task = state.get("current_task")
    pending_tasks = state.get("pending_tasks", [])
    stop_condition = state.get("stop_condition", {})
    final = stop_condition.get("final", {})
    runtime_guardrail = stop_condition.get("runtime_guardrail", {})
    task_id = _current_task_id(state)
    step = _current_step(state)

    # Check if blocked (missing required context)
    if fsm_state == "blocked" or runtime_guardrail.get("reason") == "missing_required_context":
        return {
            "action": "final",
            "final_answer": (
                "缺少必要的上下文信息（当前周期或基准周期），"
                "请向用户追问这些信息后再进行 RCA 分析。"
            ),
            "prompt_for_agent": "请向用户追问缺失的上下文信息（current_period / base_period）。",
        }

    # Check if tool was executed but not yet interpreted
    tool_result = _current_tool_result(state_file, task_id, step)
    if tool_result and current_task and fsm_state == "waiting_for_tool":
        return _build_interpret_result_hook(state, state_file, tool_result)

    # Check if we need to choose a task
    if pending_tasks and not current_task:
        return _build_choose_task_hook(state, state_file)

    # Check if we should stop
    if final.get("should_stop") or runtime_guardrail.get("must_stop"):
        return _build_draft_answer_hook(state, state_file)

    # If we have a current_task and tool hasn't been executed yet
    if current_task and fsm_state == "waiting_for_tool":
        tool_args = _current_tool_args(state_file, task_id, step)
        if not tool_args:
            return {
                "action": "error",
                "error": "no tool_args found for current task; run 'step' to re-evaluate",
            }
        return {
            "action": "execute_tool",
            "tool_args": tool_args,
            "tool_command": [sys.executable, str(Path(__file__).with_name("call_openapi.py").resolve()),
                             tool_args["action"], json.dumps(tool_args["model_args"], ensure_ascii=False),
                             "--runtime-config-file", _artifact_path(state_file, ARTIFACT_NAMES["openapi_config"])],
            "prompt_for_agent": (
                "请按 tool_command 参数数组执行 call_openapi.py。"
                "三个 Action 均由脚本使用 ve billing --force 调用；不要重拼业务参数或更换运行配置。"
                "执行完成后，将工具输出写入 tool_result.json，"
                "然后调用 run_rca_workflow.py resume --tool-result-file。"
            ),
        }

    # Fallback: should not normally reach here
    return {
        "action": "final",
        "final_answer": "分析流程出现异常，无法确定下一步动作。",
        "prompt_for_agent": "RCA workflow 状态异常，请检查 state file 和 artifacts。",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> Dict[str, Any]:
    state_file = args.state_file
    if Path(state_file).exists() or (Path(state_file).parent / (Path(state_file).name + ".artifacts")).exists():
        raise ValueError("task state or artifacts already exists; resume it or use a new task directory")
    config = resolve_config(args)
    question = args.question
    context = json.loads(args.context_json) if args.context_json else {}

    state = initialize_analysis_state(question, context)
    state_file_path = Path(state_file)
    state_file_path.parent.mkdir(parents=True, exist_ok=True)
    _write_state(state_file, state)
    _write_artifact(state_file, ARTIFACT_NAMES["openapi_config"], asdict(config))

    return _determine_next_action(state, state_file)


def cmd_step(args: argparse.Namespace) -> Dict[str, Any]:
    state_file = args.state_file
    state = _read_state(state_file)
    return _determine_next_action(state, state_file)


def cmd_resume(args: argparse.Namespace) -> Dict[str, Any]:
    state_file = args.state_file
    state = _read_state(state_file)

    if args.hook_response_file:
        return _resume_hook_response(state, state_file, args.hook_response_file)

    if args.tool_result_file:
        return _resume_tool_result(state, state_file, args.tool_result_file)

    return {
        "action": "error",
        "error": "resume requires --hook-response-file or --tool-result-file",
    }


def _resume_hook_response(
    state: Dict[str, Any],
    state_file: str,
    hook_response_file: str,
) -> Dict[str, Any]:
    response = _load_json(hook_response_file)
    if not response:
        return {"action": "error", "error": f"hook response file not found: {hook_response_file}"}

    hook_type = response.get("hook_type")
    if hook_type not in HOOK_TYPES:
        return {
            "action": "error",
            "error": f"unknown hook_type: {hook_type}. Expected one of {HOOK_TYPES}",
        }

    # Match: hook_response.hook_type must match pending hook_request
    pending = _pending_hook_type(state_file)
    if pending is None:
        return {
            "action": "error",
            "error": "no pending hook_request; run 'step' first to determine next action",
        }
    if hook_type != pending:
        return {
            "action": "error",
            "error": f"hook_type mismatch: response is '{hook_type}' but pending hook is '{pending}'",
            "hint": f"请提交 pending hook_type={pending} 的 hook_response，或重新运行 step 查看当前需要什么 hook。",
        }

    # Validate
    ok, err = _validate_hook_response(hook_type, response, state)
    if not ok:
        return {
            "action": "error",
            "error": f"hook_response validation failed: {err}",
            "hint": "请修正 hook_response.json 后重试 resume --hook-response-file",
        }

    # Consume
    if hook_type == "choose_task":
        state = _consume_choose_task(state, state_file, response)
    elif hook_type == "interpret_result":
        state = _consume_interpret_result(state, state_file, response)
    elif hook_type == "draft_answer":
        _consume_draft_answer(state, state_file, response)
        _clear_hook_request(state_file)
        final_answer = _load_json(_artifact_path(state_file, ARTIFACT_NAMES["final_answer"]))
        return {
            "action": "final",
            "final_answer": (final_answer or {}).get("final_answer", ""),
            "prompt_for_agent": (
                "RCA 分析已完成。"
                "请将 final_answer 输出给用户。"
            ),
        }

    _clear_hook_request(state_file)
    return _determine_next_action(state, state_file)


def _resume_tool_result(
    state: Dict[str, Any],
    state_file: str,
    tool_result_file: str,
) -> Dict[str, Any]:
    tool_result = _load_json(tool_result_file)
    if not tool_result:
        return {"action": "error", "error": f"tool result file not found: {tool_result_file}"}

    task_id = _current_task_id(state)
    step = _current_step(state)

    # Save tool_result as artifact (do NOT write back state)
    _write_artifact(state_file, ARTIFACT_NAMES["tool_result"], tool_result)
    _write_wf_meta(state_file, {**_read_wf_meta(state_file), "tool_result_task_id": task_id, "tool_result_step": step})

    return _determine_next_action(state, state_file)


def _validate_hook_response(
    hook_type: str,
    response: Dict[str, Any],
    state: Dict[str, Any],
) -> Tuple[bool, str]:
    if hook_type == "choose_task":
        pending_ids = {t.get("task_id", "") for t in state.get("pending_tasks", [])}
        return _validate_choose_task(response, pending_ids)
    elif hook_type == "interpret_result":
        return _validate_interpret_result(response)
    elif hook_type == "draft_answer":
        return _validate_draft_answer(response)
    return False, f"unknown hook_type: {hook_type}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def cli_main(argv: Optional[List[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(
        description="RCA Workflow Orchestrator (step/resume pattern)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--question", required=True)
    init_parser.add_argument("--context-json")
    init_parser.add_argument("--state-file", required=True)
    add_runtime_arguments(init_parser)

    step_parser = subparsers.add_parser("step")
    step_parser.add_argument("--state-file", required=True)

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--state-file", required=True)
    resume_parser.add_argument("--hook-response-file")
    resume_parser.add_argument("--tool-result-file")

    args = parser.parse_args(argv)

    if args.command == "init":
        return cmd_init(args)
    elif args.command == "step":
        return cmd_step(args)
    elif args.command == "resume":
        return cmd_resume(args)
    else:
        raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    result = cli_main()
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
