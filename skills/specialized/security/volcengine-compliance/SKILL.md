---
name: volcengine-compliance
description: >-
  火山引擎合规最佳实践助手：一是根据用户诉求（要满足的合规标准、关键词、关注的风险等级），
  从火山引擎官方内置的合规包模板里推荐该开启哪些、并标出哪些已开启；二是汇总账号当前的合规
  态势，把已生效规则/合规包（官方内置 + 用户自定义）的评估结果按类别（法规 / 最佳实践 /
  自定义）与严重度聚合成一份合规总览报告；三是当官方基线没覆盖时，指导用户写一条 Rego 策略
  作为自定义合规规则并注册评估。可在用户确认后把推荐的模板部署为合规包。Use when
  用户想做「合规检查 / 合规巡检 / 安全合规 / 合规最佳实践 / 该开哪些合规规则 / 等保合规 /
  我火山账号合规吗 / 有哪些不合规 / 帮我写条自定义合规规则」，或提到火山引擎「配置审计 /
  Config / 合规包 / conformance pack / Rego 策略」。Trigger on 火山 / 火山引擎 /
  volcengine 关键词叠加合规场景。部署合规包 / 注册自定义规则属写操作，需用户确认；合规报告
  与资源修复严格分离。
license: MIT
metadata:
  openclaw:
    requires:
      bins:
        - ve
        - python3
    install:
      - kind: node
        package: "@volcengine/cli"
        bins: [ve]
    envVars:
      - name: VOLCENGINE_ACCESS_KEY
        required: false
        description: AccessKey for AK/SK auth path (alternative to `ve login`)
      - name: VOLCENGINE_SECRET_KEY
        required: false
        description: SecretKey for AK/SK auth path
      - name: VOLCENGINE_SESSION_TOKEN
        required: false
        description: Optional STS session token for temporary credentials
      - name: VOLCENGINE_REGION
        required: false
        description: Default region; falls back to cn-beijing if unset
---

# 火山引擎合规最佳实践助手

本技能围绕火山引擎配置审计（Config）的合规能力，为用户提供三件事：

1. **合规推荐**：根据用户诉求，从火山引擎**官方内置的合规包模板**里推荐该开启哪些合规基线
   （法规 / 最佳实践），并标出哪些已经开过，避免重复部署。
2. **合规总览**：汇总账号**当前**的合规态势——把已生效规则/合规包（官方内置 + 用户自定义）
   的评估结果，按合规类别与严重度聚合成一份总览报告。
3. **落地合规检查诉求**：用户带着一个具体检查诉求来时，先在系统模板里找现成的推荐给他，没有
   现成的再参考类似模板、或从零写一条 Rego 策略自定义并注册评估（详见 [references/writing-config-rules.md](references/writing-config-rules.md)）。

合规知识既来自火山官方内置基线，也覆盖用户自建规则；总览一视同仁，推荐只针对官方基线。

## 速查

| 项目 | 说明 |
| --- | --- |
| 适用场景 | 合规检查 / 合规巡检 / 合规最佳实践推荐 / 账号合规态势总览 / 写自定义合规规则 |
| 核心能力 | 合规推荐（只读）、合规总览（只读） |
| 可选写操作 | 把推荐模板部署为合规包、注册自定义规则（需确认） |
| 底层调用 | `scripts/compliance.py` 封装 `ve config <Action>`；写自定义规则直调 `ve config` |

## 能力

| 能力 | 做什么 | 子命令 | 参考 |
| --- | --- | --- | --- |
| 合规推荐 | 按标准/关键词/风险等级，从官方内置模板里推荐该开启哪些，标注已开启 | `recommend` | [references/recommend.md](references/recommend.md) |
| 合规总览 | 汇总账号已生效规则/合规包的评估结果，按类别+严重度出总览报告 | `overview` | [references/overview.md](references/overview.md) |
| 部署合规包 | 把推荐的官方模板部署为合规包（写操作，确认门控） | `apply` | [references/apply.md](references/apply.md) |
| 写自定义规则 | 落地一个具体合规检查诉求：先在系统模板里找现成的，没有再写 Rego 策略自定义并注册评估 | 无（`ve config` 直调） | [references/writing-config-rules.md](references/writing-config-rules.md) |

## 什么时候用

- 用户问「我该开哪些合规规则 / 想满足等保 / 有没有推荐的合规最佳实践」——用合规推荐。
- 用户问「我火山账号现在合规吗 / 有哪些不合规资源 / 给我一份合规报告」——用合规总览。
- 用户带着一个具体检查诉求来（「帮我检查 TOS 桶有没有对匿名用户开放写权限」这类）——按 [references/writing-config-rules.md](references/writing-config-rules.md) 先找现成模板，没有再自定义。
- 用户消息里出现「火山 / 火山引擎 / volcengine」且属于合规检查 / 配置审计 / Config 场景。

不适用：管理单条自建规则的增删改、执行具体资源的配置修复——修复是用户确认后的独立动作。

## 前置条件

- `ve` CLI 已安装并完成鉴权（`ve configure` 或 `VOLCENGINE_ACCESS_KEY` / `SECRET_KEY`）。见 [references/auth.md](references/auth.md)。
- 合规总览要求账号已启用**配置记录器（recorder）**并已有评估结果；部署合规包同样依赖 recorder，未启用时可在确认后一并启用。
- 调用方对目标账号 / 账号组有配置审计的读写权限。

## 工作流

所有动作通过 `scripts/compliance.py` 完成（命令相对本 skill 目录根执行）。

### 合规推荐（只读）

```bash
python3 scripts/compliance.py recommend                          # 全部官方内置基线
python3 scripts/compliance.py recommend --standard Law           # 只看法规合规（如等保）
python3 scripts/compliance.py recommend --keyword 对象存储        # 按关键词过滤
python3 scripts/compliance.py recommend --risk-level High        # 只看高风险基线
```

输出候选基线（ID / 名称 / 类别 / 风险等级 / 含多少规则模板 / **是否已开启**），未开启的排前。
推荐口径与如何选基线见 [references/recommend.md](references/recommend.md)。

### 合规总览（只读）

```bash
python3 scripts/compliance.py overview                           # 全量已生效规则
python3 scripts/compliance.py overview --no-detail               # 只看规则级统计，更快
python3 scripts/compliance.py overview --conformance-pack-id <合规包ID>   # 只看某合规包
```

产出 md / csv / json 三份产物（stdout 只回摘要 + 路径），按**合规类别分节**、节内按严重度
降序，每条标注来源（BuiltIn / Custom）。定级与解读见 [references/overview.md](references/overview.md)。

### 部署合规包（写操作，需确认）

```bash
# 先 dry-run 看将要创建什么
python3 scripts/compliance.py apply --template-id <模板ID> --name my-baseline --enable-recorder
# 用户明确同意后才真正执行
python3 scripts/compliance.py apply --template-id <模板ID> --name my-baseline --enable-recorder --confirm
```

`--confirm` 才真正写入；不加只 dry-run。`--enable-recorder` 在 recorder 未启用时一并启用。
部署细节与安全边界见 [references/apply.md](references/apply.md)。

> 部署后资源评估**异步进行**，`apply` 完成不代表立刻有结果；`overview` 若显示无结果，稍等再跑。

## agent 执行流程

1. **判断诉求**：用户是想「该开哪些」（推荐）、「现在合规吗」（总览），还是「官方没覆盖、要自己写规则」（自定义规则）？单账号还是账号组？有无指定标准（等保 / 最佳实践）。
2. **检查鉴权**：`ve` 未登录按 [references/auth.md](references/auth.md) 引导，不要盲目重试。
3. **推荐场景**：`recommend` 给用户看候选基线，讲清每个覆盖什么、哪些已开启，建议先开高风险/未覆盖的。
4. **部署（可选）**：用户想开时先 `apply` dry-run 给他看，**明确同意后**才 `--confirm`。
5. **总览场景**：`overview` 后读 markdown 产物，按类别与严重度汇报，先讲 Critical/High。
6. **合规检查诉求场景**：用户带具体检查诉求来时，按 [references/writing-config-rules.md](references/writing-config-rules.md) 先用 `ListRuleTemplates` / `recommend` 找现成模板；没有再摸清资源字段结构（`ListSupportedResourceType` → `DescribeSupportedResourceTypes` / `GetResourceConfigHistory`）、写 Rego 策略、本地自测，经用户确认后注册规则（创建后自动异步评估）。
7. **给整改建议、不代执行修复**：讲清每条不合规要求什么、怎么改；具体资源修复交用户确认后另行执行。

## 优先级分级

| 优先级 | 处理建议 |
| --- | --- |
| Critical | 高危暴露，需立即整改 |
| High | 数日内处理以降低风险 |
| Medium | 排入下个迭代解决 |
| Low | 日常维护中跟踪修复 |

（严重度由规则风险等级映射：High→Critical、Medium→High、Low→Medium。）

## 写操作边界（重要）

- **只读**：`recommend` / `overview` 永远不改任何东西。
- **写操作**：`apply`（部署合规包）、`--enable-recorder`（启用记录器）会改变账号状态，
  **必须 `--confirm` 才执行**，且执行前必须让用户明确同意。不加 `--confirm` 只 dry-run。
- **注册自定义规则**：`CreateRuleTemplate` / `CreateRule` 也是写操作，会在账号里落库规则，
  同样要用户明确同意后才执行（详见 [references/writing-config-rules.md](references/writing-config-rules.md)）。
  规则创建后由平台自动触发评估（异步，有几秒延迟），本技能不手动调 `StartRuleEvaluation`。
- **修复**：改具体资源配置 / 触发自动修正**不在本技能内执行**，只作为整改建议给出，由用户
  确认后另行操作。合规「报告」与「修复」严格分离。

## 报错处理

| 现象 | 处理 |
| --- | --- |
| `ve` 未登录 / 会话过期 | 按 [references/auth.md](references/auth.md) 引导登录，不要盲目重试 |
| `SingleAccountRecorderNotEnabled` / `OrganizationRecorderNotEnabled` | recorder 未启用，用 `apply --enable-recorder`（确认后 `--confirm`） |
| `NotFound.ConformancePackTemplate` | 模板 ID 错误或不可见，重新 `recommend` 取正确 ID |
| `QuotaExceeded.Rule` | 规则配额不足，减少部署范围或清理无用规则 |
| apply 提示缺省必填参数 | 补齐 `InputParameters` 再部署 |
| `overview` 无结果 | 尚无已生效规则或评估进行中；先 `recommend` → `apply`，或稍后重试 |
| `CreateRuleTemplate` 报策略编译错 | Rego 语法/语义错误，按 [references/writing-config-rules.md](references/writing-config-rules.md) 的契约与常见坑排查 |
| 自定义规则评估结果不符预期 | 多为字段路径/大小写/标量数组假设错，用 `GetResourceConfigHistory` 核对真实快照 |

## 合规最佳实践（运营建议）

- 定期跑合规总览（周度 / 月度），跟踪不合规趋势与整改效果。
- 合规推荐优先补齐**未覆盖**的法规/最佳实践基线，再逐步收敛高风险项。
- 合规报告与修复动作分离：先出报告对齐范围，再由用户决策与执行修复。
- 报告与产物中**不得**出现 AK / SK / Authorization / 会话 token 等凭证。
- 资源 ID 对外脱敏时保留固定前缀、抽象随机段（如 `i-<id>`、`cp-<id>`、`ag-<id>`）。
