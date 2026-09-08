---
stage_id: 01-organization
stage_type: landing-zone-setup
user_step_name: 组织和核心账号准备
user_goal: 完成企业组织初始化、OU 结构搭建和核心账号创建
user_progress_text: 正在完成组织和核心账号准备
user_completion_text: 组织和核心账号准备已完成
user_intro_why_now: 先把组织结构和核心账号准备好，后续财务、身份、日志和网络配置才有统一落点
user_intro_value: 帮用户先建立可治理、可分层承载的基础组织框架
user_intro_outcome: 完成后会得到可复用的 OU 结构和核心账号，为后续阶段减少重复决策
purpose: Provide the base organization structure and core accounts required by later finance, identity, logging, and networking phases
---

# Phase 1: Organization and Accounts (01-organization)

**Target directory**: `./volcengine-landing-zone-workspace/blueprints/landing-zone-setup/01-organization/`

## Phase Goal

- Reuse or create the top-level OUs `Platform`, `Applications`, and `SandBox`
- Under `Applications`, reuse or create `Dev`, `Staging`, and `Prod`
- Create the five core accounts `LogArchive`, `Security`, `SharedService`, `Network`, and `SandBoxTest`

## Minimum Input

- Prefer read-only lookup for `root_ou_id` and do not ask the user for it first
- When an enterprise organization already exists, auto-scan the standard OUs first and inject detected IDs into `existing_*_ou_id`
- Ask for `prefix` only when it is missing. It affects OUs, core accounts, and later default naming
- Ask for `region` only when it is missing. Prefer `VOLCENGINE_REGION`, otherwise default to `cn-beijing`
- Do not ask early in this phase for finance, identity, logging, or networking variables

## Phase-Specific Branches

- Run `ve organization DescribeOrganization` first
- If the organization exists, continue by fetching the root OU and scanning the standard OUs
- If it returns `RecordNotExists` or a similar `organization not exists`, treat it as the normal initial state for first-time setup and continue with organization creation
- If `CreateOrganization` returns `NoPermissionOnVerificationError`, recognize it as missing enterprise real-name verification rather than a generic permission issue
- When standard OUs already exist, prefer reuse and create only the missing ones. Ask the user for OU IDs only when auto-detection fails or the structure is ambiguous

## Output and Recovery

- After the phase completes, record at least the key IDs for the top-level OUs, Applications child OUs, and core accounts so later phases can reuse them
- If `ConcurrentException` or partial success occurs, reconcile first and regenerate a plan later instead of calling it a total failure immediately
- Existing accounts that are not yet enrolled into the enterprise organization are not handled by the default automation path. Handle them separately only if the user asks explicitly
