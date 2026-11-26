# scope-report — Seedance 2.x 效果问题上报（badcase report）

> 这是 [`arkcli-doctor`](../GUIDE.md) 的 **report scope reference**。只有两种情况读这里：① `doctor model` / `doctor infer-endpoint` 已返回 `report_suggestion`，确认是 Seedance 2.x 效果类问题，需要向用户询问是否上报；② 用户已经明确要求“直接上报 / 提交 badcase / 反馈到方舟”，**没有同时要求检查、诊断、排查或分析原因**，且上下文确认是 Seedance 2.x 效果类问题。**只描述效果差，或同时要求先诊断再上报时，不得直接进入本 scope，必须先走 model / infer-endpoint 诊断。**
>
> **CRITICAL — 开始前 MUST 先用 Read 工具读取**：
> - [`../../arkcli-shared/GUIDE.md`](../../arkcli-shared/GUIDE.md)（认证闸门、命令选择顺序）
> - [`../GUIDE.md`](../GUIDE.md)（doctor 总入口与路径决策表）

## 它解决什么

火山方舟 Seedance 2.x 家族（当前家族包括 `doubao-seedance-2-0-260128` / `doubao-seedance-2-0-fast-260128` 等已知版本，具体清单以服务端为准）在生视频时可能命中效果类问题：角色 ID 漂移、字幕生成错、水印、风格漂移、闪烁、拼接跳变、角色重复、音频尾部杂音、中文发音错、音色参考错等。方舟平台为这些**效果类问题**（不是错误码 / 生成失败）提供了**badcase 上报**接口，把 task_id 送到排障平台异步分析。

`arkcli doctor report` 就是这一步的执行入口。

| 用户场景                                                        | Agent 跑什么                                                                                       |
|----------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| 「我这次 seedance 2.x 生成的视频角色脸变形了 / 字幕拼错了」     | **未明确说上报，不直达 report**；有模型名走 `doctor model`，有 ep-id 走 `doctor infer-endpoint`        |
| 「先检查这次 seedance 2.x 字幕错的原因，再帮我上报」           | **诊断意图优先**；先走 `doctor model` / `doctor infer-endpoint`，完成后按 Path A 询问并上报             |
| 「帮我上报下这次 seedance 2.x 字幕错的 badcase / 提交到方舟」   | **明确上报**；确认家族 + 效果类门槛后，按 Path B 参数收集并直达 `doctor report`                       |
| 「刚跑完 doctor model seedance-2-0，看到 report_suggestion」    | 按 Path A 二次分流；确认是效果类后询问用户，用户同意才进入 `doctor report`                            |
| 「seedream-4-0 生图效果不对，能上报吗」                          | ❌ **不属于本 reference** —— 只覆盖 seedance 2.x 家族视频，生图 / 1.x seedance 一律不能上报，转告用户 |
| 「seedance 生视频报了 60002 / 429 / expired」                    | ❌ **不属于本 reference** —— 错误码类走 [`error-codes.md`](error-codes.md)，不走 badcase 通道       |

> 边界：**只覆盖 Seedance 2.x 家族**（客户端按前缀 `doubao-seedance-2-` 匹配触发建议），家族内某个具体版本受不受理由服务端 60002 判定；家族外的 task 提交会被服务端 60002 拒绝。

## 触发条件

`doctor report` 只有以下两个合法入口。无论哪条入口，**执行 report 时都必须已经有用户明确的上报意图**：Path A 的意图来自诊断后的询问与用户确认；Path B 的意图来自用户原始请求。**诊断意图始终优先于上报意图**：用户同时要求“检查 / 诊断 / 排查 / 分析原因 / 看健康 / 看指标”和“上报”时，必须先走 Path A 的上游诊断，不得直达 Path B。

**Path A — 上游 doctor 诊断完成后的上报确认（保留 model / infer-endpoint 检查链路）**

跑 `arkcli doctor model doubao-seedance-2-0-260128` 或 `arkcli doctor infer-endpoint <ep-id>`（endpoint 关联的 model 命中 seedance 2.x 家族前缀）时，输出 JSON 里会浮出：

```json
{
  "report_suggestion": {
    "model_supported": true,
    "reason": "doubao-seedance-2-0-260128 落在 seedance 2.x 家族内, 可尝试 badcase 上报; 具体 task_id 是否可受理由服务端校验",
    "model_name": "doubao-seedance-2-0-260128",
    "supported_models": ["doubao-seedance-2-*"],
    "docs": "https://www.volcengine.com/docs/82379/2389900",
    "report_command": "arkcli doctor report --task-id <cgt-xxx> --feedback \"<问题现象描述>\" [--badcase-type <enum>]"
  }
}
```

Path A **必须以真实执行过 model / infer-endpoint 诊断并拿到上述字段为前提**，不得根据用户一句“效果不好”自行虚构 `report_suggestion` 或跳过诊断。`model_supported=true` 只表示诊断到的模型落在客户端已知的 seedance 2.x 家族前缀内；`supported_models` 是 pattern 提示（如 `doubao-seedance-2-*`），**不是穷举白名单**；家族内某个具体版本是否受理、以及具体 `task_id` 的存在性 / 账号归属 / 完成状态 / 重复提交，**全部由服务端校验**（见 `reason` 字段）。**不得把 `model_supported=true` 解释成某个具体 task 已通过资格校验。** 是否建议上报仍由 agent 二次分流：

1. **判定问题类别**（agent 结合用户原始诉求 + 诊断输出的 error_rate / errors 分布）
   - ✅ **效果类**：角色 ID 漂移 / 字幕生成错 / 水印 / 风格漂移 / 闪烁 / 拼接跳变 / 角色重复 / 音频尾部杂音 / 中文发音错 / 音色参考错 —— 走本 reference
   - ❌ **错误码 / 运行类**：task 失败 / 429 / ModelAccessDenied / ContentRiskBlocked / expired / 状态异常 / 错误率高 —— 走 [`error-codes.md`](error-codes.md)，**不要**提上报
   - ❓ **未知**：用户没描述具体现象 —— 先看诊断输出，可以追问用户"是效果不对还是接口报错"，**不要**主动提上报

2. **判定为效果类后，用一句话告知用户此通道**（意向探询，不是仪式感的确认门）：

   > "这类效果类问题可以上报到方舟让排障团队分析，需要我帮你上报吗？"

   用户表达意向后即可进入下一步；如果用户没兴趣说"算了"，自然结束。**不要**在这一步做仪式感的"确认要上报吗 [y/N]"式反复追问 —— 决定性确认由 CLI 层完成。

3. **进入参数收集**（自然对话，不算确认）：agent 从用户上下文里做**参数意图识别**（见下方"参数意图识别契约"段），能识别到的字段直接带上；必填字段（task_id / feedback）识别不到才向用户追问，可选字段识别不到就**不带**、**不问**。参数齐后**告知用户即将执行的命令**（预告，让用户知道 CLI 还会弹一次结构化确认让他核对参数），然后直接跑 `arkcli doctor report`。

4. **CLI 层弹出结构化确认**（唯一决定性确认）：CLI 会打印合规声明 + 本次实际外发的参数列表 + 是否上报？[y/N]，由**用户点头**才真发请求。**Agent 不需要模拟或预知 CLI 输出**——拼好命令跑就行，实际文案见运行结果。**不要**替用户擅自上报，也不要伪造 task_id。

> 为什么把决策集中到 CLI 层：case-platform 只处理"生成成功但效果差"的 case，服务端会异步拉视频 / 输入帧做效果分析。对失败 task（task 未 completed）上报会被 40004 拒；对非 seedance 2.0 会被 60002 拒。错误码 / 运行类问题走上报是浪费用户时间。Agent 层做一次意向探询 + 参数收集，让 CLI 结构化 prompt 承担唯一决定性确认，避免重复问同一个问题。

**Path B — 用户只要求直接上报且没有诊断意图（唯一允许跳过 model / infer-endpoint 诊断的直达路径）**

用户直接说"这次 seedance 2.0 效果不对，帮我上报"、"提个 badcase"、"上报到方舟"，且没有要求先检查、诊断、排查或分析原因时，才可能进入 Path B。若用户说“先检查为什么字幕错并上报”或任何同义混合请求，必须先走 `doctor model` / `doctor infer-endpoint`，完成诊断后按 Path A 处理。进入 Path B 后，agent **不能只凭意图关键词就抽参数跑命令**；必须先从对话上下文里确认两个门槛条件，缺哪个哪个追问，明显不符合的直接拒绝并转告边界：

1. **家族门槛 —— 模型是 seedance 2.x 家族**（`doubao-seedance-2-*` 前缀，含 fast 变体）：
   - 用户明说 seedance 2.x / 2.0 / 2.1 / `doubao-seedance-2-*` 系列模型 → 门槛过
   - 用户没提模型 / 只给 task_id → **追问**："这个 task 是哪个模型跑的？（本通道只覆盖 seedance 2.x 家族）"
   - 用户明说 1.x / seedream / 其他视频模型 → **拒绝**："这条通道只覆盖 seedance 2.x 家族视频；你这个是 xxx，走 `arkcli doctor model` / 反馈原路径"
2. **效果类门槛 —— 问题是效果类**（角色漂移 / 字幕错 / 水印 / 风格漂移 / 闪烁 / 拼接跳变 / 角色重复 / 音频尾部杂音 / 中文发音错 / 音色参考错等）：
   - 用户描述里明显是效果类现象 → 门槛过
   - 用户没描述具体现象 / 只说"上报 badcase" → **追问**："具体是效果不对（比如角色变形、字幕拼错）还是接口报错（比如 429 / task expired）？"
   - 用户描述是错误码 / 运行类（生成失败 / 429 / expired / ContentRiskBlocked 等） → **拒绝**："错误码类不走 badcase 通道，请走 `arkcli doctor error <code>` 或 [`error-codes.md`](error-codes.md)"

两个门槛都过后，才进入下方"参数意图识别契约"抽 task_id + feedback + 可选字段，跑 `arkcli doctor report`。**agent 不能靠"上报"关键词单独触发** —— 意图 + 家族 + 效果类三个信号都得凑齐，缺哪个追问哪个，明显不符的直接拒绝转告。

> 为什么不再"信任意图直接提交": 之前设计相信"服务端 60002 兜底"就够, 但会把用户带进"我要上报 → 提交 → 被 60002 拒 → 才知道通道不覆盖"的绕行, 浪费一次交互。前置两门槛让 agent 提前告知用户边界, 用户少走弯路。同时 CLI 层不做客户端家族闸门 —— 门槛只在 agent 层, 服务端仍是最终权威。

## 参数意图识别契约

Agent 应从用户自然语言 / 命令上下文里对 **6 个 CLI 参数**全部做意图识别，识别到就带上；用户明确指定了值（直接写 flag 或明确说"用 xxx"）以用户为准。缺失时按下表处理：

| CLI flag | 必填? | 用户可能的表达 | 未识别到时的行为 |
|----------|-------|---------------|-----------------|
| `--task-id` | **是** | `cgt-*` 格式 id、"任务 id 是 xxx"、"这次生成的 task"（从对话历史里的 `+gen` / `gen list` 输出提取） | **询问用户**："能给我这次生成的 task_id 吗？可以从 `arkcli gen list` 拿" |
| `--feedback` | **是** | 用户对现象的描述（"主角脸变形"、"字幕拼错"、"续写接缝跳变"）—— 直接摘用户原话 | **询问用户**："能描述下具体是哪里效果不对吗？" |
| `--badcase-type` | 否 | 用户明说"这是角色漂移" / 或 agent 从 feedback 推断出某个枚举 | 不追问；如推断出候选枚举可**主动推荐 + 等用户确认**再带上 |
| `--contact-info` | 否 | "留邮箱 xxx@yy"、"回访电话 138xxx"、"联系方式 xxx"—— **只在用户主动提供时提取** | **绝不主动问**（PII，避免过度收集） |
| `--source` | 否 | 用户明说"来源 huoshan / huosu / qianzhi / case_import" | 不追问，走服务端默认 |
| `--account-id` | 否 | 用户明说"上报到 account xxx"（罕见） | 不追问，Bearer 路径服务端自动反查 |

**核心原则**：

- **必填缺失 → 主动追问**（不能编、不能猜、不能跳过）
- **可选缺失 → 不带、不问**（不做过度收集，尤其 PII）
- **用户明确指定 → 以用户为准**（不要 agent 覆盖或"修正"用户传的值，比如用户说 `--source huoshan`，就用 huoshan，不要改成 case_import）
- **带上的可选字段 → CLI confirm prompt 会展示**（视觉透明，让用户知道所有外发内容）

## 命令用法

```bash
arkcli doctor report \
  --task-id cgt-20260501132104-tfm9v \      # 必填, 1-50 个, 可 --task-id 多次或用逗号 / 空格 / 换行分隔
  --feedback "人物手部扭曲, 且嘴型和中文配音对不上" \  # 必填, 1-2000 字符
  --badcase-type character_id_drift \       # 可选, 见下方枚举
  --contact-info "user@example.com" \       # 可选, 联系方式, ≤255 字符
  --source case_import                      # 可选, 默认 case_import
```

`--dry-run` 会打印完整请求预览而不真正上报——排查参数拼写的推荐方式。

## `--badcase-type` 枚举（可选，但强烈建议填）

| 枚举值 | 中文含义 | 典型现象 |
|--------|----------|----------|
| `character_id_drift` | 角色 ID 漂移 | 主角脸/身份在片子里逐渐变形，或跟输入图不一致 |
| `subtitle_generation_error` | 字幕生成错误 | 视频里自动生成的字幕拼写、格式、位置有问题 |
| `logo_watermark_generated` | 生成 logo / 水印 | 画面里冒出了不该有的品牌 logo、水印 |
| `style_drift` | 风格漂移 | 前后帧的画风、色调、光影出现明显跳变 |
| `regular_flickering` | 规律性闪烁 | 出现规律的闪烁、明暗跳变 |
| `extended_video_joint_jump` | 续写视频接缝跳变 | 使用视频续写能力时接缝处画面跳变 |
| `duplicate_character_appearance` | 角色重复出现 | 同一角色在同一帧出现多次 |
| `audio_end_noise` | 尾部音频杂音 | 音频结尾出现杂音 / 爆音 / 静默 |
| `chinese_pronunciation_error` | 中文发音错误 | 生成的中文语音发音有误 |
| `voice_tone_reference_error` | 音色参考错误 | 生成音色与参考音频不符 |
| `other` | 其他 | 上述都不适用 |

**Agent 应主动帮用户匹配**：读到 feedback 描述后可以推荐一个 `--badcase-type`，但**要等用户确认**才加上。

## 鉴权

**只支持 Ark API Key (Bearer) 鉴权**。

- 缺 API Key 时命令会明确报错并引导 `arkcli auth apikey`。
- 不需要子账号挂 `CasePlatformAccess` 策略（那是 AKSK 路径的要求，一期不做）。
- API Key 只负责 Bearer 鉴权，不能代替 project scope。`ProjectName` 由 transport
  从当前 profile 解析，作为 URL query 公共参数发送；
  **绝不能放进 JSON body**，否则 CasePlatform 的 Pydantic `extra_forbid` 校验会拒绝。
- 当前 scope 是「账号全部资源」时省略 `ProjectName`；具体 project（包括
  `default`）按 query 发送。业务 service 不读、不保存 project。

## 二次确认门（HeadlessConfirm）

上报会导致方舟平台异步拉取视频 / 输入帧用于排障——属于**用户数据外发**，走高危二次确认门：

- **TTY 交互**：默认弹 Y/N 提示（`--yes` 可跳过）。
- **非交互 / Agent / CI**：`--yes` 被无视，必须显式设 `ARKCLI_ALLOW_HEADLESS_REPORT=1` 才放行。这是 arkcli 对**用户数据外发类操作**的通用护栏（参考 delete / open service 同款做法），防止 agent 反射性静默上报。

Agent 在 headless 环境下**必须先展示 prompt 内容给用户确认**再设 env，不要自作主张把 env 塞进 shell。

## 服务端错误码翻译（`arkcli doctor report` 自带 hint）

| Code | 含义 | 处理 |
|------|------|------|
| `40002` | task_id 不存在或不属于当前账号 | 确认 task_id 拼写 + 当前 profile 与 task 所属账号一致 |
| `40003` | task_id 已经上报过 badcase | 不要重复上报 |
| `40004` | task 仍在生成中 | 等任务 completed 后再来 |
| `40005` | 单请求内重复 task_id | 去重 |
| `60002` | 不在 seedance 2.x 上报支持范围内 | 覆盖方舟 Seedance 2.x 家族的部分版本；具体清单以服务端为准，文档 `https://www.volcengine.com/docs/82379/2389900` |
| `60003` | 请求 ModelId 与 task_id 反查模型不一致 | 检查 task_id 是否对应 seedance 2.x 家族的正确版本 |
| `40006` | AccountId 缺失（AKSK 路径） | Bearer 路径不会撞这个；撞了说明 APIKey 未生效 |
| `40007-40011` | 各种字段前置校验 | 按 hint 补齐 |

## Output schema

```json
{
  "submission_id": "badcase-sub-...",
  "total": 2,
  "accepted": [
    {"task_id": "cgt-a", "case_id": "instance-...", "message": "Success"}
  ],
  "rejected": [
    {"task_id": "cgt-b", "code": "40003", "reason": "task_id 已经提交过 badcase", "hint": "..."}
  ],
  "processing_hint": "case 已进入 processing 状态; 后台异步转存视频与输入帧, 完成后 case 翻成 completed",
  "request_id": "..."
}
```

Agent 拿到之后应把 `accepted` 的 case_id 展示给用户，`rejected` 里的每条把 `reason` + `hint` 展示（不用重复原始错误码）。

## 反例（不要做）

- ❌ 用户只描述 Seedance 2.x 字幕错 / 角色漂移等效果问题，Agent 跳过 `doctor model` / `doctor infer-endpoint` 直接跑 report。**不能**；用户未明确说要上报时必须先诊断。
- ❌ 用户说“先检查 / 诊断 / 排查这个 Seedance 2.x 效果问题并上报”，Agent 因为看见“上报”就直达 report。**不能**；混合意图必须先完成 `doctor model` / `doctor infer-endpoint`，再按 Path A 询问并上报。
- ❌ Agent 读到 `report_suggestion` 后不询问用户，直接跑 report。**不能**；Path A 必须等用户明确同意上报。
- ❌ 用户没说要上报、Agent 也没读到真实诊断返回的 `report_suggestion` → 主动跑 report。**不能**。
- ❌ 用户只说"帮我上报 badcase"但没提模型 / 没描述现象 → agent 直接抽 task_id 就跑命令。**不能**，Path B 有家族门槛和效果类门槛,缺哪个追问哪个,不许无脑靠意图关键词触发。
- ❌ 用户明说是 1.x / seedream / 其他视频模型 → 硬走上报路径想让服务端 60002 兜底。**不能**,agent 层就要拒绝并转告边界,不要浪费用户一次交互。
- ❌ 把 `model_supported=true` 当作具体 task 已通过资格校验 → 它只表示模型落在家族前缀内；具体 task 必须由 report 服务端校验。
- ❌ **在 agent 层做一次"确认要上报吗 [y/N]"式仪式门，跑 CLI 后用户又被 CLI 层弹的 prompt 问一次相同的事** → 两次问同一个问题冗余。Agent 层只做一句话意向探询 + 参数收集，决定性确认交给 CLI 层的结构化 prompt。
- ❌ 用户反馈"生成失败 / 报错 / task expired / 429" → agent 建议上报 badcase。**不能**，那是运行类问题，服务端 40004 / 60002 会拒；错误码类走 error / doctor error 路径。
- ❌ 用户 task_id 不清楚 → agent 编一个 fake 走 dry-run 之外的路径。**不能**。
- ❌ 必填参数（task_id / feedback）缺失时**不追问**、瞎猜 / 编 / 用占位符跑命令。**必填未识别到 MUST 询问用户**。
- ❌ **主动询问用户 contact-info**（"给我你的邮箱吧") → 违反过度收集原则。仅在用户主动提供联系方式时才提取并带上。
- ❌ 用户明确说"用 `--source huoshan`" agent 又擅自改成 case_import。**以用户为准**。
- ❌ 用 1.x 或 seedance 家族外的 task_id 提交，然后忽略 60002 拒绝。**要转告用户**。家族前缀匹配只是发现提示，具体 task 由服务端判。
- ❌ headless 环境替用户静默设 `ARKCLI_ALLOW_HEADLESS_REPORT=1`。**不能**，先向用户展示要上报的内容。

## 给用户看的话术

Agent 拿到 `arkcli doctor report` 输出后按以下模板回信，**不复述完整 JSON、不重复原始错误码**：

1. **全部 accepted**（happy path）：
   > "已上报，方舟排障平台会异步分析。case_id：`instance-xxx`（可留作后续跟进）。分析完成后 case 会翻到 completed。"

2. **部分 accepted / 部分 rejected**：
   - 先说 accepted 的 case_id
   - 逐条说 rejected：`task_id + reason + hint`（hint 已由 CLI 翻译成人类可读中文，直接展示）
   > "上报了 3 个 task：`cgt-a` 已受理（case_id: instance-1）；`cgt-b` 被拒——已经上报过 badcase，不用重复提；`cgt-c` 被拒——task 还在生成中，等 completed 后再上报。"

3. **全部 rejected**：
   > "全部被拒。原因："逐条列 `reason + hint`；给出下一步（等 completed / 换正确 task_id / 别重复上报）。

4. **未定案 case**（Accepted 里 `processing_hint` 非空）：
   - 转告 processing 语义："case 已进入 processing 状态，后台异步转存视频与输入帧，完成后翻成 completed"
   - **不承诺**具体完成时间

**触发上报前**（Path A 意向探询后 / Path B 参数收集完成后）也有话术：
- Path A 意向探询："这类效果类问题可以上报到方舟让排障团队分析，需要我帮你上报吗？"
- 参数缺失追问：见"参数意图识别契约"表最后一列

## 何时 _不_ 用本 reference

- 用户跑的是 **seedream / 1.x seedance / 其他生视频模型** 的 task → **不支持上报**，直接转告用户并转 [`scope-model.md`](scope-model.md) 或 [`error-codes.md`](error-codes.md)
- 用户反馈是 **task 生成失败 / expired / 429 / ContentRiskBlocked / ModelAccessDenied** → 错误码 / 运行类问题，走 [`error-codes.md`](error-codes.md) 或 `doctor error <code>`
- 用户想看**模型整体健康度 / 错误率分布 / 用量** → [`scope-model.md`](scope-model.md)
- 用户想看**单接入点状态 / 用量 / 配额** → [`scope-infer-endpoint.md`](scope-infer-endpoint.md)
- 用户想**看视频结果 / 下载 mp4 / 查任务状态** → 不是诊断问题，走 `arkcli gen get <task_id>` / `arkcli gen list`
- 用户问 **`--contact-info` / API Key 是什么** → 认证类走 [`../../arkcli-auth/GUIDE.md`](../../arkcli-auth/GUIDE.md)

## 参考

- 接口文档：[火山方舟 CasePlatformV1BadcaseReport](https://www.volcengine.com/docs/82379/2389900)
- 上级：[`../GUIDE.md`](../GUIDE.md)
- 相邻 domain：[`scope-model.md`](scope-model.md)（`doctor model` 会输出 `report_suggestion` 触发本 domain）
- 相邻 domain：[`scope-infer-endpoint.md`](scope-infer-endpoint.md)（`doctor infer-endpoint` 同样会触发）
