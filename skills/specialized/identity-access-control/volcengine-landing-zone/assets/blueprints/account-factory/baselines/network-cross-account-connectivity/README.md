# network-cross-account-connectivity

这个 baseline package 在新建成员账号中创建业务 VPC、两个子网，并在启用时先更新
网络账号持有的 TR 共享单元，把当前新账号加入共享范围，再把该 VPC 挂载到共享
Transit Router。

## 执行身份与凭证注入

执行身份分为两层：

- **Terraform 底座凭证（发起 provider AssumeRole 的身份）**：来自运行时环境变量
  `VOLCENGINE_ACCESS_KEY`、`VOLCENGINE_SECRET_KEY`、可选的 `VOLCENGINE_SESSION_TOKEN`、
  `VOLCENGINE_REGION`。
- **`ve` CLI 底座身份**：来自当前登录态。
- **身份切换（切到哪个成员账号）**：由 `account_id` 决定，体现在 baseline 内部。

具体行为：

- **Terraform provider（`volcenginecc.member`）**：声明
  `assume_role = { assume_role_trn = "trn:iam::${account_id}:role/OrganizationAccessControlRole", ... }`，
  配合 `endpoints = { sts = "sts.volcengineapi.com" }`。VPC、子网、TR attachment
  都用这个 provider 创建。`account_id` 注错时，AssumeRole 在 plan/apply 阶段即失败，
  绝不会在错误账号静默创建资源。
- **`local-exec`（更新共享范围 + 创建 Transit Router 服务关联角色）**：provider 的
  `assume_role` 不会传给 local-exec（`ve` CLI 是独立进程），因此脚本会按目标动作
  自行 AssumeRole：
  - 更新共享范围时，从当前登录态切到**网络账号**，查找 `05-network` 已创建的
    `transit_router_resource_share_name`，优先选取同名里最新的 `ACTIVE` 共享单元；
    同名 `DELETED` 墓碑记录会被忽略。脚本会先校验该共享单元里已经包含目标 TR，
    再把当前 `account_id` 追加为共享使用者。
  - 绑定中心 TR 路由表时，从当前登录态切到**网络账号**，查找 `05-network` 已预置的
    `transit_router_dmz_public_route_table_name` 与
      `transit_router_egress_route_table_name`，并先校验
      `RT_Egress_To_Internal` 里已经存在 `AVAILABLE` 的
      `0.0.0.0/0 -> network_vpc_attachment_id` 默认路由；只有前置探针通过后，再把当前 run 创建出来的
    `workload_vpc_attachment_id` 关联到 `RT_Egress_To_Internal`，并向
    `RT_DMZ_Public` 启用 propagation。baseline 只处理当前 attachment 的增量挂接，
    不创建或接管中心路由表本体。
  - 创建 SLR 时，从当前登录态切到**成员账号**，写入隔离临时 CLI home，并用
    `HOME=<temp_home> ve sts GetCallerIdentity --profile <temp_profile>` 做身份探针闸门，
    确认确实切到了 `account_id`，否则中止；随后显式执行
    `HOME=<temp_home> ve iam CreateServiceLinkedRole --profile <temp_profile> --ServiceName transitrouter`
    （已存在视为成功）。

## 前置条件

- Terraform 底座凭证和当前 `ve` 登录态都必须有权限 AssumeRole 到目标成员账号的
  `OrganizationAccessControlRole`
- 当前 `ve` 登录态还必须有权限 AssumeRole 到网络账号的 `OrganizationAccessControlRole`
- `05-network` 必须已经完成 `resource_share` 委派管理员注册、`EnableSharingWithOrganization`
  和初始 TR 共享单元创建
- 如果启用共享网络接入，`transit_router_id` 必须对目标成员账号可见且允许挂载

## 最低输入

- `region`
- `account_id`
- `network_account_id`
- `transit_router_id`
- `transit_router_resource_share_name`
- `transit_router_dmz_public_route_table_name`
- `transit_router_egress_route_table_name`
- `network_vpc_attachment_id`
- `workload_vpc_cidr`
- `workload_subnet_cidr_az_a`
- `workload_subnet_cidr_az_b`
- `availability_zone_a`（必填，须属于 `region`，如 `${region}-a`）
- `availability_zone_b`（必填，须属于 `region`，如 `${region}-b`）

## 输出

- `workload_vpc_id`
- `workload_subnet_az_a_id`
- `workload_subnet_az_b_id`
- `workload_vpc_attachment_id`
