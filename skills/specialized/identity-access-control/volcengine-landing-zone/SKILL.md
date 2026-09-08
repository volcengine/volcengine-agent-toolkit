---
name: volcengine-landing-zone
description: Use when the user asks to analyze, consult, setup, manage, configure, or design a Volcengine Landing Zone, including organization, accounts, finance, identity, cloudtrail, or network infrastructure.
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

Use the resolved absolute paths for all later reads and writes. Do not rely on process cwd.

## Local File Display

Whenever a local file must be placed in front of the user, such as a solution confirmation HTML file, login information, initial passwords, or a summary report, follow the protocol in [display-protocol.md](references/display-protocol.md): copy into the workspace, then **open the file for the user first**; if opening is unavailable or fails, degrade to delivering its absolute path plus one short guidance line; in the worst case, retell the plan in chat as an explicitly marked degraded fallback. Keep the safety boundary, then stop and wait. G1, G4, STEP 0, and STEP 3 all reference that protocol.

> Hard rule: **display means delivering the file itself in an openable form, not paraphrasing or summarizing its contents in chat.**
> The priority is mandatory: **open the file first (the default must-do action); only if opening is unavailable or fails, degrade to delivering the absolute path plus one short guidance line; only when neither is possible, retell the plan in chat as an explicitly marked degraded fallback**. Do not read the file first and convert the body into a chat summary.

## Entry Routing (Intent Router)

Once `volcengine-landing-zone` is activated, it **must automatically route into the main path that matches the user's intent**. Do not start by asking the user to choose a path. Ask a follow-up only when multiple paths truly match at the same time, or when the minimum information required to continue is missing.

| Trigger semantics | Route into |
|---|---|
| `landing zone` 的方案/理念/最佳实践/阶段价值/实施顺序/组织设计建议/账号规划建议/是否值得做/怎么落地 | `Consulting and Solution Design` |
| `landing zone`、`首次搭建`、`组织`、`OU`、`核心账号`、`网络底座` | `Initial Landing Zone Setup` |
| `新增账号`、`开账号`、`创建账号`、`baseline`、`应用 baseline`、`设置基线`、`创建 baseline` | `Account Creation and Baseline Setup` |
| `失败恢复`、`失败重试`、`修复失败执行`、`上次执行报错` | `Failure Recovery` |

Handling principles:

- The user does not need to understand directory layout, phase numbers, or blueprint structure first. The agent should directly take ownership of the goal and do the necessary reference reading and execution preparation.
- `Create baseline` and `apply baseline` are not listed as a separate first-screen path, but if the user asks for them directly, take the request as-is and do not push them back into path selection.
- **Exception for Initial Landing Zone Setup**: once routed into `Initial Landing Zone Setup`, "execution preparation" does **not** include preflight, credential setup, reading phase blueprints for warm-up, init, plan, or any write action. The only allowed first step is to display the solution confirmation file under G1 and stop. Before the user explicitly confirms the solution, do not pre-read phase blueprints and do not start any real execution.

## Hard Gates Before Any Real Execution

> Violating the literal wording of a hard gate also violates its intent. If any gate below is triggered, stop immediately no matter how simple the task feels, how urgent the user is, or whether some earlier step was already confirmed.

### G1. Solution Confirmation (Initial Landing Zone Setup)
**Trigger**: the user has entered the real execution path for initial setup, and the solution confirmation file has not yet been displayed in this run.
**Action**: before any preflight, credential setup, Terraform, or write action, the first thing you do must be to follow [display-protocol.md](references/display-protocol.md) and put the solution confirmation file `./skills/volcengine-landing-zone/assets/html/landing-zone-solution-plan.html` in front of the user: **open it for the user first**; only if opening is unavailable or fails, degrade to delivering its workspace absolute path plus a short guidance line; only when neither is possible, retell the plan in chat as an explicitly marked degraded fallback. Ask the user to confirm the solution or request changes, then stop and wait. The only allowed outward wording is one short guidance line such as "I have opened the solution confirmation file, please review it in the browser and confirm whether we should proceed". **Do not output a body summary, section-by-section explanation, or key-point rewrite before the file is in front of the user.**
**Forbidden**: before the user explicitly confirms, do not start preflight, do not run init/plan/apply, do not "prepare things in the background first", and do not assume consent just because the user previously said they wanted a landing zone. **Never treat a chat summary or paraphrase of the solution HTML as if the file had been displayed.** The openable HTML file itself must be delivered.
**Self-check**: have I delivered the solution HTML according to the display protocol, rather than merely retelling it in chat, and obtained explicit confirmation from the user? If not, stop now.

#### G1 Output Contract (Must Follow Literally)

For a direct setup request such as `帮我搭建火山引擎landingzone`, your first user-facing turn in `STEP 0` must follow this shape and nothing else:

1. put `landing-zone-solution-plan.html` in front of the user (open it first; degrade to its workspace absolute path if opening is unavailable or fails)
2. say one short guidance line asking the user to review the file
3. ask one confirmation question
4. stop and wait

The same turn must **not** contain any of the following before the user confirms:

- a solution summary
- a phase overview
- an explanation of organization / finance / identity / log / network design
- a proposed implementation sequence
- any preflight or credential-setup language

Bad pattern:

`I have reviewed the solution and here is the plan: ...`

Good pattern:

`Please review the solution confirmation HTML file I just opened for you. Do you want me to proceed with this plan, or would you like any changes first?`

### G2. Phase Confirmation (Every Deployment Task / Phase)
**Trigger**: you are about to enter a deployment phase. For `01-organization` through `05-network`, each phase is separate. For account factory, `create account` and `apply baseline` are separate phases.
**Action**: before the phase starts, present the overall impact summary for that phase and get a dedicated confirmation. After confirmation, all write actions inside the phase run continuously without prompting for each individual write.
**Forbidden**: do not ask the user to confirm each individual Terraform apply or CLI write action one by one. The user does not care about implementation granularity. Do not reuse a previous phase confirmation as a substitute for this phase.
**Self-check**: do I have explicit confirmation for **this phase**? If not, stop.

### G3. Workspace Isolation
**Trigger**: any Terraform or write action.
**Action**: real execution happens only inside `${WORKSPACE_ROOT}/` (that is, `./volcengine-landing-zone-workspace/`). See the path anchors above.
**Forbidden**: do not execute from or write back into `${SKILL_ROOT}/assets/blueprints/`. Built-in blueprint sources are always read-only.
**Self-check**: am I running from a workspace copy under `${WORKSPACE_ROOT}`, rather than from the built-in blueprint source? If not, stop.

### G4. File Review Pause
**Trigger**: a phase produces a local file that the user needs to view, such as an initial password, login information, or a summary report.
**Action**: deliver the file according to [display-protocol.md](references/display-protocol.md), tell the user to review it, and pause there waiting for the next instruction.
**Forbidden**: do not skip the pause because you want to show multiple files later together. G2 does not exempt this pause. Do not echo the full initial password in chat, and do not replace file delivery with a text restatement.
**Self-check**: after producing a sensitive or user-review file, have I opened or delivered it according to the display protocol and then stopped? If not, stop.

### G5. Consulting Is Read-Only
**Trigger**: the user intent is consulting, design, evaluation, or learning about concepts, ordering, or value.
**Action**: provide explanation and recommendations only.
**Forbidden**: do not run preflight, do not start credential setup, do not run Terraform, and do not perform any write action, even if it would be convenient.
**Self-check**: has the user clearly asked for real execution? If not, explain only and do not act.

### G6. Authorization Does Not Carry Forward
**Trigger**: the workflow spans multiple steps and something earlier was already confirmed.
**Action**: phases must be re-confirmed between steps.
**Forbidden**: the existence of a checklist, an earlier path selection, or a previous phase confirmation does not mean later write actions are already authorized.
**Self-check**: does the exact next step I want to run have its own authorization? If not, stop.

## Danger Signals
- "The user already agreed earlier, so I don't need to confirm this step again" -> violates G2/G6
- "I'll prepare things in the background and confirm later" -> violates G1/G2
- "The solution is small enough, let's just do it" -> violates G1
- "The file is generated, I'll show it together with the next one later" -> violates G4
- "The user was only asking, but I executed it anyway" -> violates G5

> Always design and implement against the official Volcengine Landing Zone methodology.

## Paths

### Consulting and Solution Design

- Use this path when the user wants to understand concepts, phase value, rollout order, organization design suggestions, or a practical landing path before real execution.

### Initial Landing Zone Setup

> The step order in this path is mandatory. **Until STEP 0 is complete, meaning the user has explicitly confirmed the solution, do not enter STEP 1 or anything later**, including preflight, credential setup, reading phase blueprints for execution prep, init, plan, or apply.

- **STEP 0. Display the Solution and Stop (G1, mandatory and the only allowed first step)**: after entering this path, the first thing you do is automatically put the solution confirmation document `./skills/volcengine-landing-zone/assets/html/landing-zone-solution-plan.html` in front of the user per [display-protocol.md](references/display-protocol.md) (**open it first**; degrade to its workspace absolute path plus one guidance line if opening is unavailable or fails; retell in chat only as an explicitly marked last-resort fallback), ask the user to confirm the solution or request adjustments, then **stop and wait**. This step only allows "put the file in front of the user (open / degrade to path) + one guidance line + one confirmation question". **Do not summarize the HTML content before sending it to the user.** Before explicit confirmation arrives, do nothing else.
- **STEP 0 response budget is intentionally tiny**: treat this as a file-delivery checkpoint, not a discussion turn. If your first reply contains any concrete solution details from the HTML body, you have already violated G1.
- **STEP 1. Preflight Checks**: after the user confirms the solution, run [preflight-checks.md](references/preflight-checks.md).
- **STEP 2. Execute Phase by Phase**: the overall workflow is in [guidebook.md](references/landing-zone-setup/guidebook.md). Before each phase, follow G2 and obtain a dedicated confirmation. Phase documents:
  - [01-organization.md](references/landing-zone-setup/01-organization.md)
  - [02-finance.md](references/landing-zone-setup/02-finance.md)
  - [03-identity.md](references/landing-zone-setup/03-identity.md)
  - [04-log.md](references/landing-zone-setup/04-log.md)
  - [05-network.md](references/landing-zone-setup/05-network.md)
- **STEP 3. Summary Report**: after execution, generate the summary report using the template `./skills/volcengine-landing-zone/assets/html/landing-zone-setup-report-template.html`.

### Account Creation and Baseline Setup

- The overall execution flow is in [guidebook.md](references/account-factory/guidebook.md).
- Treat the agent as the Terraform operator. Do not introduce a separate runner, control-plane service, or central baseline orchestrator root for account factory.
- `account create` and `baseline apply` are separate tasks under G2/G6. Never auto-carry authorization from one into the other.
- For `account create`, resolve or create a dedicated `run_id`, copy the package into `account-factory/runs/<run_id>/account-create/terraform/`, write the resolved inputs, and execute Terraform inside that isolated run directory.
- For `baseline apply`, read the selected `*.baseline.json` files, resolve baseline packages by name, copy each package into `account-factory/runs/<run_id>/baselines/<baseline-name>/terraform/`, write `terraform.tfvars.json`, and execute Terraform serially inside those isolated run directories.
- Built-in and workspace baselines are the same execution unit: both are Terraform packages resolved by name, with workspace `account-factory/baselines/` overriding built-in `assets/blueprints/account-factory/baselines/` when names collide.
- `run.json`, `context.json`, `account-create/status.json`, and `baselines/<baseline-name>/status.json` are recovery artifacts for the agent to resume, inspect, and summarize the current run. They are not a separate orchestration layer.

### Failure Recovery

- The recovery flow is in [failure-recovery.md](references/failure-recovery.md).
- Use this path for recovery of `landing-zone-setup`, `account-factory account create`, and `account-factory baseline apply` failures.

## Reference Files

> **Soft vs. hard layering**: all hard execution requirements such as solution confirmation, phase confirmation, workspace isolation, file pause, read-only consulting, and non-carrying authorization are defined **only** by G1-G6 above. The reference files below contain only path-specific details. `interaction-contract.md` covers outward communication and result style only. Each `guidebook.md` contains only path-specific flow details and should reference hard-gate numbers instead of restating the rules.

- Outward communication and result conventions: [interaction-contract.md](references/interaction-contract.md)
- Mechanical preflight checks: [preflight-checks.md](references/preflight-checks.md)
- Landing Zone setup: [guidebook.md](references/landing-zone-setup/guidebook.md)
- Account factory workflow: [guidebook.md](references/account-factory/guidebook.md)
- Failure recovery: [failure-recovery.md](references/failure-recovery.md)
