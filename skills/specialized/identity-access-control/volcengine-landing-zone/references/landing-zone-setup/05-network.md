---
stage_id: 05-network
stage_type: landing-zone-setup
user_step_name: 网络底座搭建
user_goal: 完成网络账号中的中转路由器、VPC、子网、连接、共享以及公网出向能力配置
user_progress_text: 正在补齐网络底座
user_completion_text: 网络底座已完成
user_intro_why_now: 前面的组织、权限和日志基础完成后，需要把统一网络底座搭起来，后续业务账号接入才有标准入口
user_intro_value: 帮用户提前建立跨账号可扩展的网络承载能力，减少后续业务接入的重复建设
user_intro_outcome: 完成后会得到可复用且可跨账号接入的网络底座，并具备统一公网出口，便于后续业务 VPC 接入和互通规划
purpose: Provide a reusable network foundation, a network-owned shared TR entrypoint, and a shared public-egress path for later workload-account onboarding and cross-account connectivity
---

# Phase 5: Network Foundation (05-network)

**Target directory**: `./volcengine-landing-zone-workspace/blueprints/landing-zone-setup/05-network/`

## Phase Goal

- Create the TR, VPC, dual-AZ subnets, and VPC attachment inside the network account
- Prepare a reusable TR resource share in the network account for later member-account onboarding
- Create the shared public-egress NAT, bound EIP, and baseline SNAT rule inside the network account
- Pre-create the shared TR route-table skeleton in the network account for later account-factory onboarding
- Ensure `ServiceRoleForNatGateway` is ready before creating the NAT gateway
- Ensure `ServiceRoleForTransitRouter` is ready before creating the VPC attachment

## Minimum Input

- The standard path passes the absolute `${WORKSPACE_ROOT}/landing-zone-context.json`. Resolve `management_account_id` from `execution_scope.management_account_id` and the network target from `phase_inputs.network.account_id`
- If `phase_inputs.network.enabled` is false, mark this phase skipped. If it is true but the target is empty, stop and require a `network` role binding; never guess by name
- `management_account_id` and `network_account_id` are legacy inputs only. If supplied with a context, they must match exactly
- Ask for `prefix` only when it is missing, because it is used for default naming of network-foundation resources
- Ask for `network_vpc_cidr`, `network_subnet_cidr_az_a`, and `network_subnet_cidr_az_b` only when address planning is still missing
- Ask for `network_availability_zone_a` and `network_availability_zone_b` only when the default `<region>-a` / `<region>-b` placement does not match the account's enabled AZs or the customer's landing-zone design
- Default the public-egress inputs from the approved baseline: create NAT by default, use `internet` NAT type, `Small` spec, `BGP` EIP, `billing_type = 2`, `bandwidth = 1`, `period = 1`, and `snat_source_cidr = 172.16.0.0/12`
- Ask for NAT/EIP names only when the customer naming standard should override the default `<prefix>-nat`, `<prefix>-nat-eip`, and `<prefix>-default-snat`
- When asking about CIDRs, remind the user directly to avoid conflicts with existing networks. If defaults already exist, explain those defaults first and let the user decide whether to override them

## Execution Conventions

- This is a cross-account phase; follow the "Cross-account execution model" in [guidebook.md](guidebook.md). Provider-supported objects (TR/VPC/NAT/attachment, `volcenginecc_iam_role` service-linked roles, Resource Share associations) go through Terraform `assume_role`; the organization-admin CLI writes below are the enumerated exceptions. Check AssumeRole readiness right before this phase and stop for the user to fix identity if it fails.
- Validate the confirmed architecture digest, prefix, region, management account, and target network account before G2. Rebinding an already deployed network foundation is `migration_required`
- Before any organization-admin CLI write in this phase, first run `ve sts GetCallerIdentity` and confirm the returned account ID matches `management_account_id`; if not, stop instead of executing against the wrong organization context
- Include delegated-administrator registration and organization sharing enablement in the Phase 05 impact summary. After G2 confirmation, run both writes in the organization-admin context, then create or reconcile the reusable TR resource share in the network account
- `05-network` only creates the share container and associates the TR resource. Do not associate the whole organization or any member account principal in this phase
- When reconciling the TR resource share by name, prefer the newest `ACTIVE` record. Ignore same-name `DELETED` tombstone records and create a new share when no `ACTIVE` record remains. Treat other non-`ACTIVE` statuses as blockers that need investigation
- Use the network baseline subnet in AZ A as the default NAT placement, and create the public-egress resources only in the network account
- In this iteration, do not add ALB resources or listener/rule logic into `05-network`; keep the scope to shared outbound internet egress
- In the network account, manage the shared TR route-table skeleton for account-factory with `volcenginecc_transitrouter_transit_router_route_table`: `RT_DMZ_Public` and `RT_Egress_To_Internal`
- Treat the network baseline VPC attachment as the shared public-egress / DMZ-facing attachment: manage its association to `RT_DMZ_Public`, propagation into `RT_Egress_To_Internal`, and default route `0.0.0.0/0 -> network attachment` with `volcenginecc` TR route resources
- Before creating the NAT gateway, ensure that `ServiceRoleForNatGateway` is managed by `volcenginecc_iam_role` through the `network_account` provider
- Before creating the TR VPC attachment, ensure that `ServiceRoleForTransitRouter` is managed by `volcenginecc_iam_role` through the `network_account` provider
- These service-linked roles must be created in the network-account context through provider `assume_role`, not through management-account direct credentials or CLI profile fallback
- If either service-linked role already exists outside Terraform state, import it into the phase state instead of adding a `local-exec` fallback
- After the share is created or reconciled, verify that the TR resource is associated into the share. Member-account principals are added later by account-factory

## Result Requirements

- After the phase completes, record at least the TR, TR resource TRN, TR resource-share name, VPC, subnets, VPC attachment, NAT gateway, NAT EIP, SNAT rule, and the result of the delegated-administrator / service-linked-role checks
- Record the shared TR route-table names and IDs created for account-factory consumption
- In the result summary, state clearly whether the network foundation is complete, which resources were created successfully, whether the reusable TR share is ready, whether the shared public-egress path is ready, that no workload accounts have been granted access yet, whether any manual follow-up items remain, and whether the next recommended step is to start creating workload accounts
