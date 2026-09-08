# 合规推荐：从官方内置基线里推荐该开启什么

合规推荐（`compliance.py recommend`）根据用户诉求，从火山引擎**官方内置的合规包模板**里挑出
该开启的合规基线，并标出哪些已经开过。本 reference 讲这套内置基线是什么、怎么识别、怎么选。

## 内置基线的组成

- **合规包模板（Conformance Pack Template）**：一组规则模板的集合，对应一套合规标准/最佳
  实践基线（如等保、安全最佳实践）。模板带 `Labels`，取值：
  - `Law`：法规 / 合规要求（映射为「法规合规」类别）。
  - `BestPractice`：最佳实践（映射为「最佳实践」类别）。

  这是推荐的顶层单位——「该开哪套基线」。
- **规则模板（Rule Template）**：单条检查项，带 `Source`（`BuiltIn` / `Custom`）、
  `RiskLevel`、`Scope.ResourceTypes`（查哪类资源）、`Parameters`（可配参数）、
  `AllowedEffects`（`Audit` / `Modify`）、`PolicyRule`（策略本体）。

一个合规包模板包含多个规则模板；开启一套基线 = 把整套检查项部署为一个合规包。

## 怎么识别「官方内置」基线

`compliance.py recommend` 只推荐**官方内置**基线，判据：

1. 模板由 `ListConformancePackTemplates` 返回且状态为 `Released`。
2. 模板 `Labels` 含 `Law` 或 `BestPractice`（官方合规基线才会打这类标签；用户自建模板
   通常没有）。

> 底层还有个更硬的信号：内置模板的 `AccountID == 0`（不属于任何用户账号）。CLI 层已把
> 「内置 + 当前账号可见」的模板一起返回，所以这里用 `Law/BestPractice` 标签作为「官方
> 合规基线」的实用判据。

## 怎么按诉求推荐

- **按合规标准**：`recommend --standard Law` 只看法规类（如等保）；`--standard BestPractice`
  只看最佳实践类。
- **按关键词**：`recommend --keyword 对象存储` 按名称/描述模糊匹配，聚焦某类资源/主题。
- **按风险等级**：`recommend --risk-level High` 只看高风险基线，快速聚焦。
- **看覆盖面**：结果里 `RuleTemplateCount` = 基线含多少检查项，规模越大覆盖越广、部署后
  产生的规则也越多（注意规则配额）。

## 「已开启」标注怎么来的

`recommend` 会拉取账号已部署合规包（`ListConformancePacks`），凡是引用了某官方模板的，
就把该模板标 `AlreadyEnabled=true`。输出里**未开启的排前**，便于优先推荐补齐未覆盖的基线，
避免重复部署同一套。

## 推荐话术建议

- 用户说「想过等保」→ 优先 `--standard Law` 且名称匹配等保的基线。
- 用户说「做个安全体检 / 看看有什么最佳实践没做」→ `--standard BestPractice`。
- 先推**未开启 + 高风险**的基线，再逐步补齐其余覆盖面。
- 推荐 ≠ 部署：选定后走 [apply.md](apply.md) 的确认门控写流程真正开启。

## 单账号 vs 账号组

- 模板列表有单账号版（`ListConformancePackTemplates`）与账号组版
  （`ListAccountGroupConformancePackTemplates`），官方内置模板对两者都可见。
- 账号组场景的部署与权限差异见 [apply.md](apply.md)。
