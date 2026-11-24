# API Key：查询、导出与注入

先读 [共享协议](../../arkcli-shared/GUIDE.md)。这里只处理用户明确要求的 Key 任务，不是所有业务命令的前置步骤；宿主对凭证与授权的限制始终优先。

## 1. 元数据查询不改变当前 Key

- “有哪些 Key / 谁的 Key / 哪把 Key 有用量”先用 `arkcli api apikey.list --params '{"PageSize":100}' --page-all --format json`，按实际 envelope 的 `Items` 读取 Id、名称、掩码、状态与 Project 等字段；检查分页完整性。
- 账户 Key 列表不是 Profile 本地库存。不要用会选 Key 并写凭证的 `auth apikey` 代替 list，也不要为只读查询自动执行 `profile apikey refresh/use`。
- `Key` 的掩码不能用作推理凭证，不能去掉星号或拼后缀“还原”。用户给名称/后缀时只在真实结果中匹配；0 个说明未找到，多个需要消歧，不取第一条。
- 普通 Key 池、个人 Agent Plan 专属池、团队席位 Key 不是同一个池；普通列表有 Key 不证明 Plan Key 已就绪。
- “最近使用哪把 Key”以本轮完整列表的 `LastAccessTime` 为依据，解析日期及其时区后比较最大值，保留并列候选；空值、无效日期与分页不完整都须明确说明。不能用第一项、名称中时间或 `CreateTime` 代替，也不能把某个候选叫作用户在外部客户端实际配置的 Key。
- `auth status` 的选中 Key 只证明当前 ArkCLI 配置；`Active` 只证明管理状态；一次获准的试调用成功只证明该次 URL、协议、Key、模型与输入组合。用户原客户端的配置未知时，分别交付已验证的组合与待核对项，不声称已证明用户故障的根因；不能为消除这种未知而自动切换/轮换 Key。
- 状态统计必须从完整结构化结果聚合；`TotalCount` 与截断输出中的若干 `Active` 项不能推出“全部启用”。完整结果留在当前运行域内，只交付数量、状态分布和相关精简元数据；读取不完整时报告已核实范围。
- 方舟 API Key 池与豆包语音 App ID / Access Token / 对应服务的 API Key 是不同身份契约。只能按具体产品、接口及官方版本说明核验适用凭证，不能从“新版支持 API Key”推导为“本账号这把方舟 Key 可直接用于语音”。

### 大列表：精简同一条记录，不手工拼字段

终端预览截断或只显示最近若干项时，读取工具已保存的完整输出，或在受控进程内重新完整查询并立即投影。先按用户指定的真实名称/用途定位数字 `Id`；同名多条要消歧，不默认选最近一条。下面的 `key_id` 必须来自已读记录，`skill_dir` 是当前安装的 `arkcli-auth` 目录绝对路径；先确认环境有 `jq`。调用前补齐共享归因环境。

```bash
set +x
# 仅查询与投影；不导出明文、不切换当前 Key。pipefail 确保 CLI 失败不会被管道掩盖。
set -o pipefail
arkcli api apikey.list --params '{"PageSize":100}' --page-all --format json |
  jq -ec --arg id "$key_id" -f "$skill_dir/scripts/key-metadata.jq"
```

该模板校验 `Result.Items` 数量等于 `TotalCount`、数字 Id 唯一且可精确表示，输出全量状态分布和目标记录的 Id/SID/Name/ProjectName/Status/LastAccessTime/AccessControlInfo；不输出 `Key`。`missing_fields` 中的字段保持未知。投影失败时检查原始非敏感错误或用支持精确整数的解析器，不能手抄截断内容补齐。

报告中的 SID、名称和权限都从这一个 `selected` 对象原样取值，不把名称中的日期与另一项 SID 后缀拼接，不从相邻 Key 或当前 Profile 补 Project/权限。`ProjectName` 是所属项目，不能单独证明访问“全部资源”；权限只按该条 `AccessControlInfo` 的实际语义说明，字段缺失就未核实。完整状态统计中存在未知或非 Active 项时不能说“全部启用”。

## 2. 用户明确需要凭证时

先确认精确目标和用途：当前 Profile 的 Key、某个账户 Key，还是注入已授权的客户端。不要从“列 Key”自动扩张成全量明文导出。

- 当前 Profile 已存的 Key 有产品入口 `arkcli profile apikey get [--profile <name>] [--plain]`；它导出持久 Profile 凭证，不代表本次 `--api-key`/环境变量 override 的值。只在明确授权的导出/注入任务中使用。
- 账户中指定 Key：list 定位真实数字 `Id`，再使用已注册 `apikey.get_raw`，请求字段为 `{"Id":123}`（示意 ID 不可实用）。返回的 `Result.ApiKey` 才是明文；不能把 `Id`、`KeyID`、`SID` 或名称混用。
- `get_raw` 若返回可选的 `Result.SID`，与同一 Id 的 list 记录交叉核对；不一致时停止交付并核查目标，缺失时不能另造 SID。仅做元数据查询时不为补 SID 调用明文接口。
- 当前 registry 提供 `apikey.get_raw` 和 `apikey.get_sid`，不要发明 `apikey.get` 作为替代。`get_sid` 是持有 ApiKey 后反查 SID/Project/状态，不是凭 Id 取明文；两者输入和返回值不同。先核对当前 `api --list`，不能用相似 Action 名碰撞。
- `get_raw` 属于敏感凭证访问，个人 Plan 可能触发协议/Access 闸门；明确拒绝或状态不可确认时停止，不改走文件、另一 Action 或另一身份绕过。
- 遵守共享“不输出完整凭证”的交付边界：明文只进入用户授权的配置/安全目标，不进入聊天、debug、临时报告、命令展示或版本库；反馈只写目标、名称/后缀和完成状态。宿主不允许导出时如实说明。
- 区分产品查询能力、当前身份权限、获准的安全交付位置与聊天披露限制；未执行或被宿主限制时说明具体边界，不把它写成“CLI没有接口/任何方式都无法读取”。安全落点尚未确定时保留元数据并确认用途，不凭空声称已经导出或向聊天贴值。
- 明确授权批量导出时仍需锁定目标清单、权限与安全落点，记录逐项成功/失败；默认串行，不自动轮换、创建、禁用或改默认 Key。

## 3. 下游注入

优先让 ArkCLI/Helper 按选定 Profile 自行消费凭证，不手工转抄。确需外部客户端时，在同一受控进程内取值并写入已授权位置，禁止 `set -x`、echo Key 或将秘密展开成可见命令；失败只报告非敏感摘要。

**交付保真。** 将捕获响应中 JSON 解码后的完整 `Result.ApiKey` 直接交给目标写入器；不让模型根据前缀、掩码、长度或记忆重写，不截取成固定长度、不补字符、不删除值内部的连字符或空白。配置写入后，在同一受控进程内按目标格式回读并解码凭证字段，与原值逐字节比较；报告只输出是否相等、长度及安全落点，不输出明文。同长度、同前缀或文件存在都不能代替完整值一致。

若不一致，交付尚未完成：在原授权目标内复用已捕获原值修复本地写入并再次比较，不重新创建 Endpoint、重新导出或轮换 Key。原值缺失、目标不可回读或宿主禁止导出时保留“未验证/未完成”，说明具体限制；不能凭日志中的片段补出一把看似完整的 Key。安全交接不等于客户端已加载或调用成功，后两者按实际证据分别报告。

导出/注入与轮换完全不同：查询失败不意味着需要重置 Key，读取明文不意味着旧 Key 失效，配置写入成功也不证明下游已加载或可调用。需按目标客户端核验，不能默默更换费用主体。

### 获准后、同一受控进程内的解析模板

仅当宿主允许导出、用户已指定 Key 与安全落点，且不能通过 Helper 直接交接时采用。下面只描述取值步骤，**不是业务调用前置检查**：

```bash
set +x
# key_id 来自已完整读取的 list；是数字 Id，不是掩码、名称或 SID
key_params=$(jq -ecn --argjson id "$key_id" 'select(($id|type)=="number" and $id>0 and ($id|floor)==$id) | {Id:$id}') || exit 1
# 实际调用前补齐共享协议要求的归因环境；不加 --debug
key_response=$(arkcli api apikey.get_raw --params "$key_params" --format json) || exit 1
resolved_key=$(printf '%s' "$key_response" | jq -er '.Result.ApiKey | select(type=="string" and length>0 and (contains("*")|not))') || exit 1
# 只在此进程内交给已经获准的客户端/配置写入器；不 echo、不列进 argv 或报告
# 按目标格式回读并精确比较完整值；不相等则仅修复本地交接，不报告成功
# 完成交接后立即清理进程变量
unset resolved_key key_response key_params
```

模板中的 handoff 步骤必须使用目标客户端真实接口，不能在清理变量后声称已注入。超出 JSON 工具可精确表达范围的数字 Id 使用支持精确整数的编码器，不能舍入后查询另一条记录。禁止用 `tr -d '"'` 代替 JSON 解码；非零退出、空值或掩码值均为失败，不暴力换 Id。

批量导出只遍历用户批准的真实 Id 清单、默认串行；每项记录 Id/成功或失败/安全落点，不能把所有明文汇总进对话。交付前核对清单完整性、未改变默认 Key、秘密未进入 Trace，失败项如实报告而不轮换重试。
