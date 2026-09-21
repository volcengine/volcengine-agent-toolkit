---
name: volcengine-landing-zone
description: Use when the user asks to analyze, consult, setup, manage, configure, or design a Volcengine Landing Zone, including organization, accounts, finance, identity, cloudtrail, or network infrastructure, or to deploy a solution/blueprint.
allowed-tools: Bash, Read, Write
---

# Volcengine Landing Zone

This skill supports consulting, analysis, setup, and management tasks for a Volcengine Landing Zone, including organization design, account structure, finance relationships, identity, audit, and network foundations.

For clarity, the skill is organized as an intent router plus shared playbooks and path-specific guidebooks.

## Path Anchors (Resolve Once Before Any Real Execution)

Relative paths in this skill such as `./skills/volcengine-landing-zone/...` and
`./volcengine-landing-zone-workspace/...` are **not relative to an arbitrary current working directory**.
Resolve them through these two anchors once, then reuse them throughout the run:

- `SKILL_ROOT`: the absolute install root of this skill, which contains this `SKILL.md`. Read-only assets such as built-in blueprints, HTML templates, `tos_activate.py`, and `baseline.schema.json` live here. Any `./skills/volcengine-landing-zone/<x>` path resolves to `${SKILL_ROOT}/<x>`.
- `WORKSPACE_ROOT`: the writable runtime root for this run. By default it is `<current working directory>/volcengine-landing-zone-workspace/`, unless the user explicitly provides another writable location. Execution copies, output files, and baseline runtime state all live here. Any `./volcengine-landing-zone-workspace/<x>` path resolves to `${WORKSPACE_ROOT}/<x>`.
- `${WORKSPACE_ROOT}/confirmed-architecture.json`: the complete versioned architecture confirmed under G1. The default and custom branches both materialize this file; it is the single source of user design intent.
- `${WORKSPACE_ROOT}/landing-zone-context.json`: the filtered, non-sensitive Phase 01 hand-off contract. It is a rebuildable cache derived from the confirmed architecture and actual Phase 01 Terraform outputs, not another resource state.

Use the resolved absolute paths for all later reads and writes. Do not rely on process cwd.

## Local File Display

When a user-facing file must be delivered, choose the most appropriate method supported by the current agent client and runtime so the user can access the actual file. Keep generated or copied artifacts under `${WORKSPACE_ROOT}` and never modify read-only skill assets. Do not expose sensitive file contents in chat or start a listening service solely to display a file. G1 and G4 govern any required confirmation or pause.

## Entry Routing (Intent Router)

Once `volcengine-landing-zone` is activated, it **must automatically route into the main path that matches the user's intent**. Do not start by asking the user to choose a path. Ask a follow-up only when multiple paths truly match at the same time, or when the minimum information required to continue is missing.

| Trigger semantics | Route into |
|---|---|
| `landing zone` 的方案/理念/最佳实践/阶段价值/实施顺序/组织设计建议/账号规划建议/是否值得做/怎么落地 | `Consulting and Solution Design` |
| 明确要求`搭建/初始化/重构企业 Landing Zone 架构`，或按 Landing Zone 建立/调整`组织、OU、核心账号、财务、身份、审计、共享网络基础` | `Initial Landing Zone Setup` |
| `新增账号`、`开账号`、`创建账号`、`baseline`、`应用 baseline`、`设置基线`、`创建 baseline` | `Account Creation and Baseline Setup` |
| `部署具体解决方案/蓝图`、`部署这个 git 仓库/本地目录/内置包`、`按需求生成 IaC 并部署`、`部署网络/安全/数据/应用方案` | `Solution Deployment` |
| `失败恢复`、`失败重试`、`修复失败执行`、`上次执行报错` | `Failure Recovery` |

Handling principles:

- The user does not need to understand directory layout, phase numbers, or blueprint structure first. The agent should directly take ownership of the goal and do the necessary reference reading and execution preparation.
- `Create baseline` and `apply baseline` are not listed as a separate first-screen path, but if the user asks for them directly, take the request as-is and do not push them back into path selection.
- Route by the requested outcome, not by product or resource terms. Names such as VPC, network, identity, or logging do not by themselves imply `Initial Landing Zone Setup`.
- Enter `Initial Landing Zone Setup` only for an explicit request to establish or reconfigure the enterprise Landing Zone architecture or foundation. Enter `Solution Deployment` for a concrete deployable solution or package, even when it manages resources also used by Landing Zone phases.
- If the request could reasonably match both paths or the intended outcome is unclear, ask one clarification question before routing. Do not trigger G1 or deliver the Landing Zone setup confirmation file while the route is unresolved.

## User-Facing Communication

- Use business language and adapt the response to the current task. Default to conclusions, material impact, and the next useful action; expose commands, paths, state details, or orchestration mechanics only when the user asks or troubleshooting requires them.
- Resolve safe defaults and discoverable values from the confirmed design and live read-only state. Ask only for inputs that cannot be derived reliably and are required for the current step; group related questions instead of turning the workflow into a field-by-field interview.
- When permitted by the hard gates, keep discovery, preflight, workspace preparation, and plan generation in the background. Do not request confirmation for read-only preparation; G2 governs authorization for cloud writes.
- Use a natural response structure rather than a fixed status template. Clearly distinguish completed work, blockers, material follow-up, and the next action when those distinctions are relevant.

## Hard Gates Before Any Real Execution

These gates protect user decisions and cloud state. Keep them strict; adapt the surrounding conversation naturally.

### G1. Solution Confirmation (Initial Landing Zone Setup)
- G1 applies only after routing has conclusively selected `Initial Landing Zone Setup`; skill activation or mention of organization/network resources is not sufficient. Then deliver `${SKILL_ROOT}/assets/html/landing-zone-solution-plan.html`, ask the user to confirm the recommended architecture or request changes, and wait. Do not begin preflight or cloud operations first.
- A direct confirmation selects `recommended-v1`. Resolve only missing execution settings, materialize the complete design as `${WORKSPACE_ROOT}/confirmed-architecture.json`, validate it against [contract.schema.json](references/landing-zone-setup/contract.schema.json), and record its exact SHA-256.
- For requested changes, apply only the business differences to `recommended-v1`, generate the complete architecture JSON and its Markdown projection, deliver the Markdown, and obtain confirmation of that actual design. The user should not need to author internal keys or Terraform objects.
- Any later change to the confirmed architecture bytes invalidates G1 and requires the updated design to be displayed and confirmed again.

### G2. Phase Confirmation (Every Deployment Task / Phase)
- Before each cloud-writing phase, complete all permitted read-only discovery, reconciliation, state inspection, initialization, and planning. Present the resolved targets, target-to-identity strategy, and material create, update, replace, delete, and non-Terraform write impact, then obtain explicit confirmation.
- A confirmation authorizes only the saved plan and listed CLI/API writes for that phase. It does not carry into another phase or task. Any change to the target, inputs, blueprint revision, confirmed architecture digest, write set, or saved plan requires a new confirmation.
- After confirmation, execute all covered writes continuously without per-resource prompts. `01-organization` through `05-network` are separate phases; account creation and baseline application are separate phases; one Solution Deployment is one phase.

### G3. Workspace Isolation
**Trigger**: any Terraform or write action.
**Action**: real execution happens only inside `${WORKSPACE_ROOT}/` (that is, `./volcengine-landing-zone-workspace/`). See the path anchors above.
**Forbidden**: do not execute from or write back into `${SKILL_ROOT}/assets/blueprints/`. Built-in blueprint sources are always read-only.
**Self-check**: am I running from a workspace copy under `${WORKSPACE_ROOT}`, rather than from the built-in blueprint source? If not, stop.

### G4. File Review Pause
**Trigger**: a phase produces a local file that the user needs to view, such as an initial password, login information, or a summary report.
**Action**: deliver the actual file using the Local File Display rule above, tell the user to review it, and pause there waiting for the next instruction.
**Forbidden**: do not skip the pause because you want to show multiple files later together. G2 does not exempt this pause. Do not echo the full initial password in chat, and do not replace file delivery with a text restatement.
**Self-check**: after producing a sensitive or user-review file, have I opened or delivered it according to the display protocol and then stopped? If not, stop.

### G5. Consulting Is Read-Only
**Trigger**: the user intent is consulting, design, evaluation, or learning about concepts, ordering, or value.
**Action**: provide explanation and recommendations only.
**Forbidden**: do not run preflight, do not start credential setup, do not run Terraform, and do not perform any write action, even if it would be convenient.
**Self-check**: has the user clearly asked for real execution? If not, explain only and do not act.

> Always design and implement against the official Volcengine Landing Zone methodology.

## Paths

### Consulting and Solution Design

- Use this path when the user wants to understand concepts, phase value, rollout order, organization design suggestions, or a practical landing path before real execution.

### Initial Landing Zone Setup

- Complete G1 before following the execution flow in [guidebook.md](references/landing-zone-setup/guidebook.md). Apply G2 to each cloud-writing phase.
- Phase-specific instructions:
  - [01-organization.md](references/landing-zone-setup/01-organization.md)
  - [02-finance.md](references/landing-zone-setup/02-finance.md)
  - [03-identity.md](references/landing-zone-setup/03-identity.md)
  - [04-log.md](references/landing-zone-setup/04-log.md)
  - [05-network.md](references/landing-zone-setup/05-network.md)

### Account Creation and Baseline Setup

- The overall execution flow is in [guidebook.md](references/account-factory/guidebook.md).
- Account creation and baseline application have separate plans and G2 confirmations.

### Solution Deployment

- The overall execution flow is in [guidebook.md](references/solution-deployment/guidebook.md).
- Use this path to validate and deploy a solution package. Apply G2 after the targets, source revision, and actual impact are resolved.

### Failure Recovery

- The recovery flow is in [failure-recovery.md](references/failure-recovery.md).
- Use this path for recovery of `landing-zone-setup`, `account-factory account create`, `account-factory baseline apply`, and `solution-deployment` failures.

## Reference Files

> **Soft vs. hard layering**: all hard execution requirements such as solution confirmation, phase-scoped authorization, workspace isolation, file pause, and read-only consulting are defined **only** by G1-G5 above. The reference files below contain only path-specific details and should reference hard-gate numbers instead of restating the rules.

- Mechanical preflight checks: [preflight-checks.md](references/preflight-checks.md)
- Landing Zone setup: [guidebook.md](references/landing-zone-setup/guidebook.md)
- Account factory workflow: [guidebook.md](references/account-factory/guidebook.md)
- Solution deployment workflow: [guidebook.md](references/solution-deployment/guidebook.md)
- Failure recovery: [failure-recovery.md](references/failure-recovery.md)
- Landing Zone runtime contract: [contract.schema.json](references/landing-zone-setup/contract.schema.json)
