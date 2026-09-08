# 落地一个具体的合规检查诉求

用户常带着一个**具体的合规检查诉求**来：「帮我检查 TOS 桶有没有对匿名用户开放写权限」「ECS 有没有开公网」……
本 reference 讲怎么把这样一个诉求落地成账号里真正生效的合规检查。

核心顺序：**先找现成的，没有再自定义**。

1. **先在系统模板里找现成的**——官方内置了大量规则模板，命中就直接推荐给用户用，别重复造轮子。
2. **找不到完全匹配、但有类似的**——参考类似模板的写法改一条。
3. **完全没有**——从零写一条 Rego 策略作为自定义规则。

后两种要写 Rego，是本技能里唯一需要「写代码」的环节。注册规则是**写操作**，按
[SKILL.md 写操作边界](../SKILL.md) 必须先请用户确认。

## 第 0 步：先找系统里有没有现成模板

不要一上来就写规则。先按诉求搜已有的规则模板（含官方内置 `BuiltIn` 与账号已有 `Custom`）：

```bash
ve config ListRuleTemplates --body '{"MaxResults": 100}'          # 列模板（含 Source 字段）
ve config DescribeRuleTemplates --body '{"TemplateIds": ["<id>"]}' # 看某模板详情（含完整 PolicyRule）
```

- `ListRuleTemplates` 返回的每条带 `Source`（`BuiltIn` = 官方内置 / `Custom` = 账号自建）、`Scope.ResourceTypes`、`RiskLevel`。
- 按诉求涉及的**资源类型**和关键词筛：比如诉求是 TOS 桶，就找 `Scope.ResourceTypes` 含 `Volcengine::TOS::Bucket` 的模板。
- 也可以用 `recommend`（见 [recommend.md](recommend.md)）从官方合规基线角度看有没有覆盖这条诉求的基线。

分三种结果处理：

| 结果 | 怎么做 |
| --- | --- |
| 找到完全匹配的模板 | 直接推荐用户用它（`recommend` 里若属某基线则连基线一起推），或用它 `CreateRule` 实例化，**不用自己写** |
| 找到类似但不完全匹配的 | `DescribeRuleTemplates` 拉它的 `PolicyRule` 作为**参考蓝本**，改成满足诉求的策略 |
| 完全没有 | 从零写一条 Rego 策略（见下） |

## 自定义规则由什么构成

若要自定义，先理解结构：

| 概念 | 是什么 | 承载 |
| --- | --- | --- |
| 规则模板 RuleTemplate | 可复用的检查项定义 | **Rego 策略本体** + `Scope`（查哪类资源）+ `Parameters`（可配参数）+ `Triggers` + `AllowedEffects` |
| 规则 Rule | 由模板实例化、真正生效评估的实体 | `Effect`（Audit/Modify）+ `InputParameters`（给参数赋值）+ `Scope` |

写规则 = 写模板里的 Rego 策略，再用模板实例化出规则去评估资源。

## 策略契约（最重要）

评估引擎用固定契约调用策略，写错任何一条都会评估失败：

- **包名固定**：`package rules`。
- **查询固定**：引擎查询 `data.rules`，要求结果是一个对象。
- **输出字段**：
  - `compliant`（**bool，必填**）：`true` 合规 / `false` 不合规。
  - `annotation`（string，可选）：不合规原因说明，会展示在评估结果里，**强烈建议写**，便于定位整改。
  - `modify`（可选）：仅 `Modify`（自动修正）类规则用；纯审计规则不用管。
- **默认不合规更安全**：`default compliant := false`，只有命中合规条件才置 `true`——避免策略漏判时误报「合规」。

### 输入长什么样

策略从 `input` 读两部分：

```rego
input.ConfigurationItem   # 被评估资源的配置快照
input.Args                # 规则实例的 InputParameters（参数化规则才用）
```

`input.ConfigurationItem` 常用字段：

| 字段 | 含义 |
| --- | --- |
| `ResourceType` | 资源类型，如 `Volcengine::TOS::Bucket` |
| `ResourceId` / `ResourceName` | 资源 ID / 名称 |
| `Region` | 地域 |
| `Tags` | 标签数组 `[{"Key":..,"Value":..}]` |
| `Configuration` | **资源属性对象**，形态随资源类型而定，是判定的主要依据 |
| `Relationships` | 关联资源 |

> `Configuration` 里各字段的确切名字和层级**因资源类型而异**，不要凭空猜——见下面「摸清字段结构」。
> 有些字段本身是 JSON 字符串（如 TOS 的 `Policy`），要先 `json.unmarshal` 再读。

### Rego 版本与可用函数

- 引擎用 **OPA v1** 语法：`if` / `contains` / `in` / `some x in xs` 都是关键字，`default compliant := false` 用 `:=`。
- **禁用**的内置函数（策略必须是纯函数、不能出网）：`http.send`、`net.lookup_ip_addr`、`opa.runtime`。
- 引擎还注册了**自定义函数** `config.check_related_resources`（用于关联资源判定）。
- 常用可用函数：`json.unmarshal` / `json.is_valid` / `object.get`（读字段带默认值，防 undefined）/
  `lower` / `upper` / `startswith` / `contains` / `substring` / `indexof` 等。

## 摸清字段结构（不要猜，拿不到就如实说）

判定逻辑依赖 `Configuration` 里的字段路径/取值，这些**因资源类型而异，必须以真实数据为准**。

**前置：先查到资源类型的准确编码**

资源类型编码（如 `Volcengine::TOS::Bucket`）不要凭记忆拼，先列出账号支持的资源类型确认：

```bash
ve config ListSupportedResourceType --body '{"MaxResults": 100}'
```

返回里每条含 `ServiceCode` / `ServiceName` / `ResourceType`（准确编码）/ `ResourceTypeName`，
按诉求涉及的服务/资源筛出准确的 `ResourceType`，后续所有接口都用它。（注意它**只**给编码，
不含配置示例。）

**拿到编码后，有三种方式了解字段结构，尽量都取、相互印证：**

**方法 A：配置项示例（`DescribeSupportedResourceTypes`，config 侧构造的样例）**

```bash
ve config DescribeSupportedResourceTypes --body '{"ResourceTypes": ["Volcengine::TOS::Bucket"]}'
```

返回的 `ConfigurationItemSample` 就是该资源类型 **`Configuration` 的样例结构**——正是策略要读的
形态，是了解字段路径/层级最直接、不依赖账号里有没有真实资源的来源。

**方法 B：真实资源快照（`GetResourceConfigHistory`，实际取值，判定的最终标准）**

```bash
ve config GetResourceConfigHistory --body '{
  "ResourceType": "Volcengine::TOS::Bucket",
  "ResourceId":   "<resource-id>",
  "Region":       "<region>"
}'
```

看 `Configuration` 的实际取值：字段是对象还是数组、是否是 JSON 字符串、枚举取值的大小写。
**最好同时找一个合规样本和一个不合规样本**，两边对比出判定依据。

**方法 C（可选）：资源类型 schema（`ve ccapi DescribeResourceType`，CloudControl 属性定义）**

需要更完整的属性/类型定义时，查 CloudControl schema：

```bash
ve ccapi DescribeResourceType --body '{"TypeName": "Volcengine::TOS::Bucket"}'
```

看返回的 `Schema.properties` 了解各属性的类型与约束。

> 三者关系：方法 A 给「长什么样的样例」、方法 B 给「真实值」（最权威）、方法 C 给「字段类型定义」。
> 能拿到真实快照（B）时以 B 为准，A/C 帮助补全字段名与类型。

> ⚠️ **拿不到就如实告诉用户，不要瞎写**：
> - 如果 `ListSupportedResourceType` 里没有该资源类型，说明账号可能不支持，**明确告知**，别硬编一个编码。
> - 如果 A/C 都拿不到 schema/示例，**明确告知**，不要凭想象编字段。
> - 如果账号里没有该类资源、方法 B 取不到真实样本，**告诉用户你是在无真实样本的情况下按 schema/示例/文档推断的**，并把不确定的字段（尤其是确切字段名、枚举大小写、标量还是数组）**显式标出来**，请用户拿真实样本复核，或提示评估结果可能不准。
> - 宁可少写、标注「待核实」，也不要给用户一条看起来能跑、实际字段路径是猜的规则。

## 写策略要点

- `default compliant := false` 起手，命中合规条件才置 `true`。
- 判定逻辑尽量正向表达「什么算合规」；复杂场景可拆成「命中风险」的辅助规则再取反。
- 不合规时给 `annotation` 写清楚**哪个字段、什么问题**。

## 本地自测

至少覆盖：合规样本、各类不合规样本、**边界形态**——字段缺失、大小写差异、标量 vs 数组
（很多云 API 字段既可能是字符串也可能是数组）、通配符、空值 / 非法值。

关于验证工具：

- 官方 `opa` CLI（`opa eval -d rule.rego -i input.json 'data.rules'`）可以校验**标准 Rego 语法**，
  但**跑不了用到 `config.check_related_resources` 的策略**——这是本平台的自定义函数，官方 CLI
  不认识，会直接报未知函数。用到该函数的策略只能靠平台侧评估验证。
- 因此最可靠的验证闸是下一步的 `CreateRuleTemplate`：它在服务端做**严格编译**（含自定义函数），
  语法/语义错误会直接报错；注册后用真实资源跑评估看判定对不对。

## 注册规则（写操作，需用户确认）

> `CreateRuleTemplate` / `CreateRule` 会在账号里落库，是**写操作**。执行前**必须**把将要创建
> 什么（模板名、资源范围、Effect=Audit 只审计）复述给用户，得到**明确同意**后再执行。

```bash
# 1) 创建规则模板（内含策略本体）。这是写操作，也会严格编译策略，编译不过直接报错。
ve config CreateRuleTemplate --body '{
  "TemplateName": "tos-no-anonymous-write",
  "Description":  "检测 TOS 桶是否向匿名用户开放写权限",
  "RiskLevel":    "High",
  "Scope":        {"ResourceTypes": ["Volcengine::TOS::Bucket"]},
  "Triggers":     [{"TriggerType": "ConfigurationItemChange"}],
  "AllowedEffects": ["Audit"],
  "PolicyRule":   "<把 Rego 策略作为字符串放这里>"
}'
# -> 返回 TemplateId

# 2) 用模板实例化出规则（默认 Effect=Audit，只审计不改资源）。这也是写操作。
ve config CreateRule --body '{
  "RuleTemplateId": "<上一步的 TemplateId>",
  "RuleName":       "tos-no-anonymous-write",
  "Description":    "检测 TOS 桶是否向匿名用户开放写权限",
  "RiskLevel":      "High",
  "Effect":         "Audit",
  "Triggers":       [{"TriggerType": "ConfigurationItemChange"}]
}'
# -> 返回 RuleId
```

**规则创建后会自动开始评估，无需手动触发**。评估是**异步**的，通常有几秒延迟，创建完立刻查
可能还没结果，稍等再看。前置条件同样是账号已启用配置记录器（见 [apply.md](apply.md)）。

查看评估结果：

```bash
ve config ListEvaluationResults --body '{"RuleId": "<RuleId>", "ComplianceTypes": ["NonCompliant"]}'
```

或用 `compliance.py overview` 汇总（见 [overview.md](overview.md)）。

## 触发器与执行频率

- `Triggers[].TriggerType`：`ConfigurationItemChange`（资源配置变更即评估）/ `Periodic`（周期评估）/ `Manual`（仅手动）。
- 周期评估用 `MaximumExecutionFrequency`：`OneHour` / `ThreeHours` / `SixHours` / `TwelveHours` / `TwentyFourHours`。
- 大多数「配置是否合规」类规则用 `ConfigurationItemChange` 即可，变更即时评估。

## 参数化规则

想让同一条模板可复用（如「端口白名单」由使用者填），用参数：

- 模板 `Parameters` 声明：`Name` / `ValueType`（String/Number/Boolean/ArrayString…）/ `IsCompulsory` / `DefaultValue` / `AllowedValues`。
- 实例化时 `CreateRule` 传 `InputParameters`（JSON 字符串）给参数赋值。
- 策略里通过 `input.Args.<ParamName>` 读取。缺省值可用的前提是模板给了 `DefaultValue`。

## 常见坑

| 坑 | 说明 |
| --- | --- |
| 不先找现成的 | 官方内置了大量模板，先 `ListRuleTemplates` / `recommend` 找，命中就别自己写 |
| 字段全靠猜 | 先 `ListSupportedResourceType` 定编码，再用 `DescribeSupportedResourceTypes`(示例) / `GetResourceConfigHistory`(真实值) / `ve ccapi DescribeResourceType`(schema) 核对字段；拿不到就如实标注、别编 |
| 标量 vs 数组 | 云 API 里 `Principal` / `Action` 等字段可能是字符串**也**可能是数组，两种都要兼容 |
| JSON 字符串字段 | 如 TOS 的 `Configuration.Policy` 是 JSON **字符串**，要 `json.unmarshal` 后再遍历 |
| 大小写 | 枚举/权限值大小写不稳定，比较前 `lower()` / `upper()` 归一 |
| 字段缺失 | 直接取不存在的键会 undefined 导致规则不成立，用 `object.get(x, "K", 默认)` 兜底 |
| 只判 Allow | 策略类判定要只看 `Effect=Allow`，别把 `Deny` 语句误判成风险 |
| 默认合规 | 忘了 `default compliant := false`，策略漏判时会静默「合规」误报 |
| 用官方 opa 验自定义函数 | 用到 `config.check_related_resources` 的策略官方 `opa` CLI 跑不了，靠平台侧编译/评估验证 |

## 完整范例：TOS 桶匿名写权限检测

合规条件：**ACL 不存在匿名写权限 AND Bucket Policy 不存在匿名写权限**。任一命中即不合规。
覆盖了标量/数组、JSON 字符串字段、大小写、通配、Deny、缺字段等边界。

```rego
package rules

# 合规当且仅当：ACL 与 Bucket Policy 均不存在向匿名用户开放的写权限。
default compliant := false
default annotation := ""

compliant if {
	not acl_has_anonymous_write
	not policy_has_anonymous_write
}

# 不合规时按命中来源给出说明，便于定位整改。
annotation := "桶 ACL 与桶策略均存在向匿名用户开放的写操作权限" if {
	acl_has_anonymous_write
	policy_has_anonymous_write
}

annotation := "桶 ACL 存在向匿名用户开放的写操作权限" if {
	acl_has_anonymous_write
	not policy_has_anonymous_write
}

annotation := "桶策略存在向匿名用户开放的写操作权限" if {
	policy_has_anonymous_write
	not acl_has_anonymous_write
}

# ===== ACL：匿名预定义组 AllUsers 拿到写权限 =====
acl_write_permissions := {"WRITE", "WRITE_ACP", "FULL_CONTROL"}

acl_has_anonymous_write if {
	some grant in input.ConfigurationItem.Configuration.ACL.Grants
	is_anonymous_grantee(grant.Grantee)
	upper(object.get(grant, "Permission", "")) in acl_write_permissions
}

is_anonymous_grantee(grantee) if {
	lower(object.get(grantee, "Type", "")) == "group"
	lower(object.get(grantee, "Canned", "")) == "allusers"
}

is_anonymous_grantee(grantee) if {
	lower(object.get(grantee, "Canned", "")) == "allusers"
}

# ===== Bucket Policy：Principal 含 "*" 且授予写操作的 Allow 语句 =====
# Policy 是 JSON 字符串，先 unmarshal 再遍历 Statement。
policy_has_anonymous_write if {
	raw := input.ConfigurationItem.Configuration.Policy
	is_string(raw)
	raw != ""
	json.is_valid(raw)
	parsed := json.unmarshal(raw)
	some stmt in parsed.Statement
	lower(object.get(stmt, "Effect", "")) == "allow"
	statement_principal_anonymous(stmt)
	statement_action_has_write(stmt)
}

statement_principal_anonymous(stmt) if { stmt.Principal == "*" }
statement_principal_anonymous(stmt) if {
	some p in principal_list(stmt.Principal)
	p == "*"
}

# Principal / Action 可能是字符串或数组，统一规整为列表。
principal_list(p) := p if is_array(p)
principal_list(p) := [p] if is_string(p)

statement_action_has_write(stmt) if {
	some a in action_list(stmt.Action)
	is_string(a)
	is_write_action(a)
}

action_list(a) := a if is_array(a)
action_list(a) := [a] if is_string(a)

is_write_action(a) if { a == "*" }
is_write_action(a) if { action_operation(a) == "*" }
is_write_action(a) if {
	op := action_operation(a)
	some verb in {"put", "delete", "abort", "restore", "rename", "create", "modify", "set", "complete", "append", "upload", "copy", "initiate"}
	startswith(op, verb)
}

# 取 Action 冒号后的操作名并小写；无冒号则取整体。
action_operation(a) := lower(substring(a, indexof(a, ":") + 1, -1)) if { contains(a, ":") }
action_operation(a) := lower(a) if { not contains(a, ":") }
```

判定要点：ACL 写权限 = `WRITE` / `WRITE_ACP` / `FULL_CONTROL`（`READ` / `READ_ACP` 只读、合规）；
策略按 `tos:` 之后的操作名前缀匹配写动词，并覆盖 `*` 与 `tos:*` 通配；只统计 `Allow`；`Policy`
为空或非法 JSON 时安全跳过。

> 说明：上面 ACL 匿名组的确切字段（`Type=Group` + `Canned=AllUsers`）若手头没有公共桶真实样本，
> 属于按文档推断，加了容错分支；正式使用前建议拿一个真实公共桶快照核对字段名。这正是「拿不到
> 真实样本要如实标注」的示例。
