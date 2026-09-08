# 部署合规包（写操作）

把 `recommend` 选中的官方内置模板部署为合规包，是本技能**唯一的写操作环节**。本 reference
讲部署链路、前置条件和安全边界。对应 `compliance.py apply`。

## 部署前置：配置记录器（recorder）

配置审计要评估资源，前提是账号已启用**配置记录器**（recorder，负责采集资源配置快照）。

- 单账号未启用 → 创建合规包会报 `SingleAccountRecorderNotEnabled`。
- 账号组未启用 → 报 `OrganizationRecorderNotEnabled`。
- `compliance.py apply --enable-recorder` 会在未启用时先 `PutConfigurationRecorder`（全量资源
  类型）+ `StartConfigurationRecorder`。
- **启用 recorder 是写操作**，同样受 `--confirm` 门禁。

## 部署链路

`CreateConformancePack (based on template)` 的契约要点（脚本已按此自动组装）：

1. **必填**：`Name`（1-100 中英数字短横线）、`Description`、`RiskLevel`（Low/Medium/High）、
   `ConformancePackTemplateId`。
2. **RuleOverrides**：合规包模板里**每一个规则模板都必须对应一条 override**。脚本自动为
   每个规则模板生成：
   - `Name` / `RiskLevel`：继承规则模板；
   - `Effect`：默认取 `Audit`（纯审计，避免部署即自动改用户资源）；仅当模板不支持 Audit
     时才用 `AllowedEffects` 的其他值；
   - `InputParameters`：用规则模板里**必填参数的 `DefaultValue`** 预填；若某必填参数无默认
     值，`apply` 会在 `MissingCompulsoryParameters` 里列出，**必须补齐后才能真正部署**。
3. **配额**：规则数按模板内规则模板数量计入账号规则配额，超了报 `QuotaExceeded.Rule`。
4. 成功返回 `ConformancePackId`；合规包初始 `Updating`，随后异步推进并开始评估资源。

## dry-run 优先

`compliance.py apply` **不加 `--confirm` 时只 dry-run**，回显将要创建的合规包摘要（名称、模板、
规则数）和 recorder 动作，不做任何写入。流程：

1. `recommend` 选定要开启的官方基线（拿到模板 ID）。
2. `apply`（无 confirm）dry-run 复核规则数、缺参、recorder 状态。
3. 向用户复述「将要创建含 N 条规则的合规包、可能启用 recorder」，得到**明确同意**。
4. `apply --confirm` 真正执行。

## Effect：默认只审计，不自动改资源

- 部署默认所有规则用 `Effect=Audit`——只评估合规性、**不触发任何自动修正**。
- `Modify`（自动修正）会真正改用户资源，风险高，本技能部署时**不默认启用**；如用户明确要
  自动修正，应作为独立决策单独处理，并再次确认。
- 这与「报告 vs 修复分离」一致：本技能负责开基线 + 出报告，改资源是用户确认后的独立动作。

## 账号组部署差异

- 账号组版用 `CreateAccountGroupConformancePack`，body 多一个 `AccountGroupId`。
- 调用方需是目标账号组**管理员**，否则 `403 AccessDenied`。
- 账号组要求组织级 recorder 已启用，且账号组状态为 `Enabled`（否则
  `OperationProhibited.AccountGroupStatus` / `AccountGroupCreating`）。

> 当前 `compliance.py apply` 走单账号版；账号组部署可按上述契约扩展，或先在单账号验证基线效果
> 再推广。
