---
name: arkcli-chat
version: 1.2.6
description: "模型 API 用法、思考模式开关与强度、Chat/Responses 参数和 SDK 示例，以及 arkcli +chat 真实推理。询问如何配置时按具体模型版本与协议给最小示例；已有报错先核对原请求，不用新推理或新建凭证代替取证。明确要求真实模型输出时，支持多模态、流式、多轮与本地 dry-run；专项理解走 arkcli-understand。"
metadata:
  requires:
    bins: ["arkcli"]
  cliHelp: "arkcli +chat --help"
---

# arkcli +chat

**CRITICAL — 开始前 MUST 先用 Read 工具读取 [`../arkcli-shared/GUIDE.md`](../arkcli-shared/GUIDE.md)，其中包含认证闸门、配置排查与命令选择顺序**
**CRITICAL — `+chat` 在执行之前，务必先用 Read 工具读取 [`references/arkcli-chat.md`](references/arkcli-chat.md)，禁止直接盲目调用命令。**
**CRITICAL — 每个回答/已规划的生成分块只发起一次真实 `+chat`。首次响应不完整、strict JSON 无效或不符合内容要求时，保留并报告该次失败，不自动重试或用第二次响应替换；本地提取、保存、校验失败也只能修复本地交付。只有用户明确要求新一轮或重新生成时才重做同一块。**

## 先判断本轮任务

| 用户要完成的事 | 本轮入口与交付 |
| --- | --- |
| 询问模型 API 如何使用、关闭思考或设置参数，要求 SDK 示例 | 按具体模型版本、协议与 SDK 给最小配置示例；用法问题不要求提供错误日志，也不意味着要执行示例 |
| 排查已有请求报错 | 按错误类型核对下方请求证据与条件修复；已知模型能力可只读核对。原请求缺失时交付已知事实、适用的修复分支和待补信息，到此结束本轮诊断 |
| 明确要求调用模型生成内容、接续对话或授权复现测试 | 按后文“真实生成的执行顺序”保留原模型/路径/参数，捕获一次实际输出并交付 |
| 只要请求预览 | 只做该叶子命令支持的本地 `--dry-run`，披露 unresolved，不准备凭证、不发业务请求 |

参数解释和已有错误本身不要求新建 Key/Endpoint、获取明文 Key、切 Profile 或先发一次“你好”。缺少数据面 Key 不妨碍阅读协议契约和给出条件修复；无人回复时保留原请求未知项，不自行选择收费路径来补一份对照。

已有报错的默认交付是解释、条件修复与待核对的原请求字段。临时查询模型是取证步骤，不自动变成模型推荐任务；用户未要求选型时，不附加推荐卡片或能力排名。需要示例时优先给原协议中需要调整的最小请求片段，不擅自加入一整套 SDK 初始化代码。

### `Model only support text input`：保留两条修复路径

该错误说明服务报告当前模型只接受文本；它本身不能证明用户发了图片。先核对原请求的模型/Endpoint 绑定、协议和实际序列化后的输入类型；缺请求体就明确未核实，不把模型目录查询当成原请求证据。

- **只需文本回答**：保留原模型与协议，若实际请求含图片、音频、视频或附件，移除这些非文本内容并仅保留文本。Chat 检查 `messages[].content`，Responses 检查 `input`；这是有条件的修复建议，未执行就不称已修复。
- **确需媒体理解**：按目标输入模态和 API 支持核对候选模型，再选择已具备相应能力和准入的调用目标；图像生成能力不能证明可看图。没有原模型/请求时，两条路径都给出，不只建议换模型。

已确认线上输入只有文本时，继续核对模型绑定及客户端/网关封装，不虚构待删除的图片。原请求未知时给出需要补齐的脱敏字段即可；不为诊断新建 Endpoint/Key 或自动复测。推荐中的价格和性能比较必须有对应依据，不能凭 Lite/Pro 等名称推断成本。

### 模型 API 用法：从适用依据到最小示例

1. **先锁定适用范围。** 读取相关 reference（思考开关与强度见 [`references/caching-thinking.md`](references/caching-thinking.md)），按已有证据核对“具体模型版本 → API 路径 / SDK → 字段与本轮所需取值”。客户端枚举说明能编码什么，模型专属支持表说明其适用范围；通用文档不能补全模型表中未支持的值。缺失项标为示例条件，不假装已确认版本、协议或真实调用。
2. **给出可直接使用、适用范围明确的配置。** 已确认目标模型支持关闭思考时，先给 `thinking.type=disabled` 的 HTTP 请求片段。每段 SDK 示例标明客户端包/导入和 API 方法，不只写“Python SDK”：方舟 Python SDK 按其对应版本使用 `thinking=...`，Python `openai` 客户端则用 `extra_body={"thinking": {"type": "disabled"}}` 透传方舟扩展字段，HTTP 请求体仍是顶层 `thinking`。用户未指定 SDK 时，紧邻主示例说明这一区别；缺对应版本依据时只给已确认的 HTTP 写法，不把一个 SDK 的关键字直接套给另一个。
   **SDK 依据要成套匹配。** 安装包名、导入路径、客户端构造、API 方法与参数位置必须来自同一适用版本的文档或实际代码。不能按产品名猜模块名，也不能把一个 SDK 的导入配到另一个 SDK 的方法上。示例注明依据；缺少包/版本或调用契约依据时，仅交付已经确认的 HTTP 请求片段并说明缺项，不发明可运行的 SDK 程序，不为核实示例新增真实推理。
3. **核对完整答复，包括补充说明。** 每项取值、默认值和参数组合都须符合第一步的适用范围；代码示例正确，不能抵消后文错误地补出“另外还支持”的值。模型表只有 `enabled` / `disabled` 时，就不把通用 `auto` 列为该模型选项。请求关闭思考也不能直接保证端到端更快或省下多少 token；性能结论须有匹配模型、输入和参数的实际测量。检查已有证据和文案即可，不为补证明新增推理调用。


客户端把思考开关与强度编码为两个字段，不代表服务端行为互不相关。若匹配的模型/协议文档明确说明 `thinking.type=enabled` 配合 `minimal` 会跳过思考，可简要给出这一条件替代及字段位置：Chat 为 `reasoning_effort`，Responses 为 `reasoning.effort`；分别核对两个协议的依据，不从一边推另一边。未知或明确不支持该组合时保留 `disabled` 主方案，不作等价承诺。用户明确指定的值不擅自替换，是否更快仍须实际测量。

## 已有请求的协议与智能路由报错

用户排查 `json: unknown field`、HTTP 400 或协议字段不兼容时，先整理下面三部分，再给结论；缺项写“未提供”，不要让新测试替代原请求。

**1. 请求证据。** 在答复中区分原请求与本机对照，各自列出已知事实：

| 对象 | URL 路径 / SDK 方法与版本 | 模型或接入点 / 相关参数 | HTTP 状态、错误码、message、RequestId | 能证明什么 |
| --- | --- | --- | --- | --- |
| 用户原请求 | 按用户日志或实际抓取填写；缺失保持未知 | 保留用户原值 | 原样引用必要的非敏感字段 | 只定位这条请求 |
| 本机对照（仅有时） | 按真实工具返回填写 | 标出与原请求的差别 | 记录该次结果 | 只证明该对照路径的行为 |

用户称“Chat API”尚不能确认 URL；别的模型在 Chat 成功、在 Responses 出现同样报错，也只证明该对照的协议差异。原请求路径、模型或封装未核实，就明确“原请求尚未定位”，不写“根因已确认”“排除 SDK/版本”或未经统计的“多数情况”。SDK 默认协议或网关自动转发只能凭对应版本源码、正式文档或用户实际请求确认。

**CLI 输入与实际线上字段。** `arkcli api arkruntime.create_responses` 会经过 CLI/SDK 的请求转换。当前 Volc `decodeResponsesRequest` 只映射识别的字段：输出上限读取 `max_output_tokens`，不会把 `max_tokens` 或 `max_completion_tokens` 转成它，顶层 `response_format` 也不会自动转成 `text.format`。这些字段出现在 `--params` 或本地 Preview 中，不能证明它们发到了服务端；一次调用成功也不能证明服务端接受了被转换器丢弃的字段。按实际版本源码与已有脱敏 HTTP 请求核对；用户未授权实际测试时，不通过新增推理、导出 Key 或换模型补这个证明。

**2. 字段位置与适用范围。** 下表是协议字段位置，不是所有模型、版本和客户端的支持清单；不能从字段出现在某行反推用户必然请求了该接口。

| 协议 | 输入 | 输出长度字段（按精确模型与版本选择） | 结构化输出（须模型支持） |
| --- | --- | --- | --- |
| `/api/v3/chat/completions` | `messages` | `max_tokens` 或 `max_completion_tokens`；支持范围、默认值与可否同传查该模型文档 | `response_format` |
| `/api/v3/responses` | `input` | `max_output_tokens` | `text.format` |

客户端可编码、接口字段定义、具体模型支持是三层事实。当前 Volc Raw Chat 先将输入映射到 SDK 的 `CreateChatCompletionRequest`，分别保留 `max_tokens` 和 `max_completion_tokens`，不会互相改名；SDK 有这两个字段不等于所有模型均接受它们，也不证明可以同传。不要写“真正 Chat 不会报此字段未知”，或由同一个 `unknown field` 给 Responses、SDK、模型、网关原因排概率。该错误仅表明请求处理链的某层拒绝了字段，尚不能单凭错误文本确定是哪层。

检索文档可能针对不同模型、发布日期或 SDK。引用每条支持范围、默认值和上限时保留其适用模型/版本与明确例外；“某日期后通常支持”不能覆盖“不支持”的特例。把默认值、场景建议、最大输出量与上下文窗口分开，不能将一个模型的数值推广为全平台上限。原模型未知时，给条件和待补项；原模型已明确且有匹配依据时，给出该模型的具体结论。

**3. 条件修复。** 已确认走 Responses 才迁移为该行字段并移除 Chat 专用顶层字段；确认走 Chat 则保留原模型和路径，核查该模型版本支持的字段、原 SDK 的编码及网关实际转发，不因字段报错否定已提供的 Chat 路径。URL 只能确认路径，不能独自排除模型或客户端版本问题。原协议未知时给出这两条分支和需要补齐的原请求信息。`max_tokens` 不能修复 Responses 的 Chat 字段报错；也不凭印象断言所有 Chat 模型对它的支持或互斥规则。只有用户要求并授权实际测试成本时才新发推理请求；不自动切模型、Profile、收费路径或默认资源。

依据：[迁移至 Responses API](https://ark.volcengine.com/region:cn-beijing/docs/responses-api-migration#a9c4810b)。

用户明确在排查**智能模型路由**时，优先核对原请求是否走 Chat API、是否为 <32k tokens 的纯文本、是否与上下文缓存同用。该路由不支持 Responses API、图片/视频或上下文缓存；`top_logprobs`、`logprobs`、`logit_bias`、`stop`、`tool_choice`、`parallel_tool_calls` 会导致报错。`thinking`、`reasoning_effort`、`response_format` 会影响候选模型范围，不能一概列为非法参数。无原始错误码与请求体时按这些约束给排查顺序，不把本账号另一接入点的 ClosedEndpoint / NoAvailableModel 当作用户 400 的根因。`+chat` 默认走 Responses API，不能用它验证智能路由的 Chat API 路径；只有用户要求且授权实际推理调用时才按原协议测试。依据：[智能模型路由](https://ark.volcengine.com/region:cn-beijing/docs/intelligent-model-routing#11d90495)。

## 核心概念

- `--model` 缺省时 CLI 自动 fallback 到 active profile 的 `resources.text.default`；用户显式传入不同值时按 [`../arkcli-shared/references/profile-defaults.md`](../arkcli-shared/references/profile-defaults.md) 做漂移提示。
- `+chat` 是数据面 Responses API（`POST /responses`）的高层封装：一次请求即返回助手文本。
- 支持**多模态**：用 `--input @photo.jpg` 把本地文件随请求上传，模型可看图/看视频/听音频后回答。图片(`.jpg/.png/.webp/...`)、视频(`.mp4/.mov/...`)、音频(`.mp3/.wav/.m4a/...`)、通用文件按扩展名自动分流。
- 支持**流式**：`--stream` 模式逐段输出，先输出推理（thinking），再输出正式回答（response）。
- 支持**进度提示**：非流式调用在 5s 后开始向 stderr 输出 `arkcli +chat: still running… elapsed Xs` 心跳行（每 10s 一次），避免长调用看不到任何输出；脚本场景可用 `--no-progress` 关闭。stdout 不受影响。
- 支持**system instructions**：`--instructions "..."` 注入系统级指令。
- 支持**采样调节**：`--temperature` / `--top-p` / `--max-output-tokens`。
- 支持**思考强度**：`--reasoning-effort minimal|low|medium|high`（仅在支持 reasoning 的模型上生效）。
- 支持**多轮接续**：`--store` 持久化本次响应，下一次用 `--previous-response-id <id>` 接续。
- 支持**Tools**：`--tools web_search`（简单语法糖）或 `--tools-file tools.json`（function 等完整形态），配合 `--tool-choice auto|required|none` 与 `--max-tool-calls`。详见 [`references/tools.md`](references/tools.md)。
- 支持**对账面命令**：`arkcli chat get/delete/list-input-items <response-id>`，对 `--store` 过的 response 做 CRUD，详见 [`references/chat-meta.md`](references/chat-meta.md)。
- 支持**缓存与思考参数**：`--caching`（配 `--cache-prefix`）、`--thinking` 与 `--expire-at` 用于表达请求配置，实际取值及组合按目标模型版本核对。CLI 参数全集与回显验收见 [`references/caching-thinking.md`](references/caching-thinking.md)。
- 支持**流式事件**：`--stream --include-events` 输出原始 SDK 事件 NDJSON（每行一个 JSON），供 autotest / agent 程序化消费。详见 [`references/stream-events.md`](references/stream-events.md)。
- 支持**可验证的严格 JSON**：`--text-format json_schema --text-schema <file> --text-strict` 不只把约束传给服务端，还会在客户端确认响应完整、是直接 JSON 且符合 Schema；否则非零退出。严格流式会先缓冲，校验成功后才输出，避免泄出半截 JSON。详见 [`references/text-format.md`](references/text-format.md)。
- **输出 schema（务必先看）**：`+chat` 返回是 arkcli **扁平** schema（`{id, model, content, reasoning_content, usage, ...}`），**不是** Responses API 原生 `output[].content[].text` 嵌套；助手文本直接用 `.content` 取。`--format` 不会切换 shape。详见 [`references/arkcli-chat.md`](references/arkcli-chat.md) 的「返回值」段。
- 用户临时提供 `--api-key` / `--base-url` / Endpoint 时，MUST 读取 [`../arkcli-shared/references/execution-context.md`](../arkcli-shared/references/execution-context.md)。不要从 Key 文本猜套餐类型，也不要把临时值写入 profile。
- `--dry-run` 只在本地构造 `preview.v1` 请求摘要与无 secret 的执行上下文；不会读取在线元数据、刷新凭证、调用 Responses API、产生 token 用量或存储 response。在线依赖必须列为 `unresolved`。

## 快速决策

**用户要求真实模型输出时走 `+chat`：**
- 纯文本问答、推理，或带图/视频/音频的开放式对话；不要求一定有附件。
- 接续已有 Responses 对话，使用 `--store` / `--previous-response-id`；单轮不要求开启存储。
- 若目标是下面列出的专项理解产出，优先转 `arkcli-understand`，不能仅因带附件就选择 chat。

用户要求关闭思考、比较延迟/缓存或交付 SDK 调用代码时，先读
[`references/caching-thinking.md`](references/caching-thinking.md)，并核对具体模型与协议的组合规则；
`minimal` 是否可实现不思考按匹配文档判断，不能跨模型一概而论。参数回显不等于缓存命中，也不能据此承诺固定的速度排序。

**转 `arkcli-understand` 的判据（任一满足即转）：**
- 用户要「转写/语音转文字/语音识别/ASR」→ understand
- 用户要「字幕/打轴/SRT」→ understand
- 用户要「多人对话/标说话人/会议转写」→ understand
- 用户要「OCR/识别文字/识别图片文字/发票金额」→ understand
- 用户要「框出来/标框/bbox/视觉定位」→ understand
- 用户要「PDF 字段提取/文档提取/抽字段/合同提取」→ understand
- 用户要「视频总结/分段/章节总结」→ understand
- 用户要「视频问答/视频内容提问」→ understand

一句话：**有 @file 且有明确产出形态 → understand；带图聊天/追问/开放感想 → chat**。

- 用户要生成图片/视频（非对话）：转 [`../arkcli-gen/GUIDE.md`](../arkcli-gen/GUIDE.md)。

## 真实生成的执行顺序

先把用户要求记成可验收项：回答任务、指定模型/Profile、输入文件、输出格式、流式/多轮、
明确的参数值与交付文件。只预览请求时直接走本地 `--dry-run`，不先联网查认证或资源。

1. 用户只给 `ep-...` 且任务不明确 → `arkcli resources resolve <ep-id> --format json`；开放问答/追问才选择 `+chat`。
2. 用户给了临时 Key/Base URL/Endpoint → 按共享 execution-context 组合规则决定参数，不先切 profile。
3. 不确定认证状态且没有完整 stateless 上下文时，先看 `arkcli auth status`；未登录/无 API Key 转 [`../arkcli-auth/GUIDE.md`](../arkcli-auth/GUIDE.md)。
4. 不确定模型名时，先转 [`../arkcli-models/GUIDE.md`](../arkcli-models/GUIDE.md)。
5. 使用本次资源确认的调用 ID，不强制改成版本化名称。用户未指定模型时保留当前 text default 或省略 `--model`；合法套餐别名（如 `ark-code-latest`）不追加版本。用 `resources list --modality text` 核对 default、`invocable`、`required_overrides` 与凭证类型；可见不等于可调用。能力查询的规范 Name/Version 与计费调用 ID 分开，EP 始终保持 EP。只有未解析的模型族名才进一步查询，不凭字符串猜版本。
6. 需要流式输出时加 `--stream`；需要多模态时加 `--input @<file>`（可多次）。
7. 查模型实际支持的键、值和输入模态；不要把参数全集当成所有模型的能力。用户明确的 temperature、token 上限、thinking、store=false 等不得省略或换值；未指定时使用兼容默认，不额外开启联网、存储或工具执行。
8. 发起真实请求前先确定交付路径；要求保存时按 reference 的单次捕获流程，让调用 stdout 直接进入临时响应文件。用首次真实返回验收：普通结果取 `.content`，严格 JSON 检查完整性/Schema；多轮必须引用真实上轮 ID 并保持相同调用上下文。流式保留 NDJSON，确认成功终态后提取正式正文，不能把推理文本或 Agent 自己的回答充当模型产出。保存文件必须与该次正文逐字一致；任何本地失败都不得触发第二次模型请求。

认证准入只陈述已验证的事实：本地登录、Key 清单 Active 或资源可见均不能单独证明当前数据面请求可用。
实际调用报 401 时核对当前 lane 凭证，403/access 错误按下文只读核对能力和权限；
429 要区分限流与 quota exhausted。提醒可用候选，但不自动轮转 Key、切 Profile/收费路径或修改默认。
stored response 不存在/过期时准确报告，不能悄悄去掉 previous-response-id 重新对话后声称上下文接续成功。

## 长文与分块交付
### 研究文档的数据来源随正文交付

写论文或研究报告时，先区分用户提供的真实数据、已引用的公开资料、模拟数据与研究计划。用户没有提供调查/实验数据时，可完成文献综述、研究设计和明确标为模拟的示例分析；不能把生成的样本、日期、访谈、问卷回收数量或统计输出写成真实已经开展的研究。

分块生成时把数据来源约束放入每个相关块的提示词，合并后核对摘要、研究方法、数据收集、结果表格和结论。模拟样本及统计结果须在对应正文/表注中明确说明，最终聊天中的一句免责声明不能修正附件内的事实陈述。没有实际运行SPSS/AMOS等工具就不能写“本研究已使用该软件完成分析”；公式示例、拟采用方法和真实工具输出分开表述。发现矛盾先修正已保存正文并重新验收，不重做已完成的收费生成。

每块先保存原始响应和CLI退出码，再按实际输出模式验收。非流式 `--format json` 读取顶层 `content` 与实际 `status`；`content` 必须是非空正文，不能用 `usage`、`reasoning_content` 或函数调用代替。`status=incomplete` 即使有正文且退出码为0，也只交付已生成的部分并说明缺口；状态缺失时不虚构 `completed`。默认流式 stdout 是人类可读文本，`--stream --include-events` 才是逐行NDJSON：分别检查实际正文与退出码，事件模式还核对真实终态；不要把普通流式文本整体按JSON提取，也不把Thinking或工具参数当正文。

外层Bash完成、wc大于0或jq输出null均不证明正文成功。先检查已有响应以恢复正确字段，状态未知时保留部分内容和缺口，不为本地解析失败盲目再发一次模型请求。

### 用本地进度推进正文，不重新开始任务

长文任务只沿这条顺序推进：选题/章节 → 原始响应 → 正文校验 → 合入草稿 → 更新进度 → 下一个缺失章节 → 格式验收/交付。

- 开始时在本任务目录固定一个 `draft.md` 和简短 `progress.json`，记录用户已授权的主题选择、目标格式/文件、章节顺序、各块预算及状态，预留合并、校验与交付时间；每块关联原始响应路径、CLI退出码、实际终态和已保存正文路径。不把完整正文复制进进度文件或反复读回对话。
- 每个块结束，先按上面的输出契约记录实际终态；有有效正文就立即合入草稿，再记录该块完成或部分完成。失败块保留错误和缺口，已保存正文与进度核对后才能推进下一个可独立完成的块。正文保留原有来源标注，合并时检查顺序及重复章节。字数仅用于检查体量，不能证明事实、章节完整或实际页数。单块长时间运行时保留运行状态，不为超时等待重复提交；只有计划为上下文接续且用户允许存储时才使用真实 `--store` / `--previous-response-id`，独立章节不伪称多轮接续。
- 工具报错、任务恢复或开始重复写选型/提示词时，先读进度并核对已存文件，从第一个缺失的交付步骤继续。已有正文时下一步是核对、合并和交付已完成的部分，不重选模型、不覆盖旧提示词当作新任务、不重新生成成功段；仍运行或状态未知的段保留其状态。
- 最终回复前从草稿核对实际完成章节及剩余项，完成用户要求的格式校验；最终回复引用真实文件或本轮正文。没有交付正文时任务仍未完成，不能只返回大纲、选型JSON、占位文件或“现在开始第一章吗”。用户仅要求大纲时按大纲交付，不启动全文生成；用户已允许自选题目时直接沿用已定主题。
- 时间或输出预算不足时停止开启新章节，优先交付已有正文并说明缺口。转换、保存或提交失败只修本地文件/交付步骤，保留原始响应，不重复收费生成；已提交的文件只有真实提交回执才计为交付。



## 常见降级

- 模型名不确定：先 `models search`。
- endpoint ID 要用 `+chat`：直接传 `--model ep-xxx`（endpoint 本身已决定模态，无需额外 flag）。
- Endpoint + 显式 API Key、未给 Base URL：CLI 会读取 Endpoint region 后派生 Base URL；无法取得权威 region 时再要求用户补 `--base-url`。
- 鉴权失败：转 [`../arkcli-auth/GUIDE.md`](../arkcli-auth/GUIDE.md)。

## Responses API capability/access 错误的只读核对

用户已经给出 `model does not have access to responses api` 类错误时，本轮是排障，不是「再试一次」：

1. 若已知精确、完整的版本化模型 ID，只执行 `arkcli models get <model-id> --format json`；禁止用 `models search` 的候选摘要代替单模型详情。
2. 在 `api_support` 数组中按 `name` / `key` / `path` 定位 Responses 项，以该项的 `supported` 为模型声明事实；不从模型名、lifecycle、tool 列表或其他 capability 反推。
3. `supported=true` 但实际调用报 access 错误：说明「模型声明支持，当前 Endpoint / 账号访问路径不可用」；若用户还给了 Endpoint ID，可再只读 `resources resolve` / `infer endpoint get` 核对绑定与状态。
4. `supported=false` 才能说模型目录声明不支持；Responses 项缺失则说明元数据不足，不做猜测。

全程禁止再次执行 `+chat`、自动 `models activate`、切 profile 或修改默认资源。


## 模型能力提示（stderr warn，不阻断）

`+chat` 真实执行时会在发请求前读一次 ArkModels 元数据，把模型差异以 `warn: ` 前缀打到 **stderr**；请求照常发出。识别要点：

1. **只警告、不阻断**：出现 `warn:` 行不代表请求失败。值为 `enabled`/`disabled`、别名表、声明取值集都只是「模型声明」，服务端与 SDK 解码器才是裁决方。
2. **不要把声明集当接受集**。实测：`glm-5-2` 声明 `reasoning_effort` 为 `[none, minimal, high, max]`，但服务端**拒绝** `none`/`minimal` 而**接受** `low`/`medium`（只出现在其 `mapping_config` 别名表里）。声明集与接受集可能近乎互补。
3. **只按实际存在的元数据提示**：缺少 reasoning 元数据时不得把其他 capability 当成 reasoning 声明；模型不在 ArkModels 中（如 `kimi-k3`）或查询失败时**静默跳过**，不产生任何 warn。
4. **完整版本 ID 必须原样执行**：可以用裸模型名查对应版本元数据，但不得把用户指定的旧版本自动改写成当前主版本。
5. **stderr 变化不影响 stdout 契约**：`--format json` 的 stdout 结构不变，`warn:` 行只进 stderr。需要稳定 JSON 时只解析 stdout，同时保留并检查 stderr，不得用 `2>/dev/null` 丢弃 warning。
6. **`--dry-run` 不读元数据**：Client Preview 保持零网络，不会出现任何 `warn:` 行。

## 命令一览

| 命令 | 说明 |
|------|------|
| `arkcli +chat --model <id> "<prompt>"` | 最简用法：纯文本对话 |
| `arkcli +chat --model <id> --stream "<prompt>"` | 流式输出（thinking + response 两段） |
| `arkcli +chat --model <id> --instructions "你是简洁助手" "<prompt>"` | 系统级指令 |
| `arkcli +chat --model <id> --temperature 0.2 --max-output-tokens 256 "<prompt>"` | 采样调节 |
| `arkcli +chat --model <id> --reasoning-effort high "<prompt>"` | 提高思考强度 |
| `arkcli +chat --model <id> --input @file.jpg "<prompt>"` | 多模态（本地文件，支持图/视/音） |
| `arkcli +chat --model <id> --input @a.jpg --input @b.jpg "<prompt>"` | 多文件 |
| `arkcli +chat --model <id> --store "<prompt>"` 拿到 id 后再 `--previous-response-id <id> "<下一句>"` | 持久化 + 多轮接续 |
| `arkcli +chat --model <id> --tools web_search --tool-choice auto "<prompt>"` | Tools: 联网检索 |
| `arkcli +chat --model <id> --tools-file tools.json --tool-choice required "<prompt>"` | Tools: 自定义 function |
| `arkcli chat get <response-id>` | 拿回 store 过的 response（含 function_calls） |
| `arkcli chat list-input-items <response-id> --order desc --limit 5` | 列出输入项（多轮历史） |
| `arkcli chat delete <response-id>` | 删除 store 过的 response |
| `arkcli +chat --model <id> --caching enabled --store "<prompt>"` | 启用 prompt cache + 持久化 |
| `arkcli +chat --model <id> --thinking disabled --max-output-tokens 100 "<prompt>"` | 关思考压短输出 |
| `arkcli +chat --model <id> --text-format json_object "<prompt>"` | 强制模型出合法 JSON |
| `arkcli +chat --model <id> --text-format json_schema --text-schema schema.json --text-strict "<prompt>"` | 用 JSON Schema 强约束 shape |
| `arkcli +chat --model <id> --stream --include-events "<prompt>"` | 流式 NDJSON（每行一个 SDK 事件 JSON） |
| `arkcli +chat --model <id> --dry-run "<prompt>"` | 无副作用预演；不调用 Responses API |

## 详细文档

- `+chat` 的所有参数、返回值、错误码、多模态文件自动上传机制等见 [`references/arkcli-chat.md`](references/arkcli-chat.md)。
- `+chat` 的 Tools 能力（`--tools / --tools-file / --tool-choice / --max-tool-calls`，含 function 与 web_search）见 [`references/tools.md`](references/tools.md)。
- `chat get / chat delete / chat list-input-items` 三个对账面命令见 [`references/chat-meta.md`](references/chat-meta.md)。这些命令操作的 response 必须是 `+chat --store` 过的。
- `+chat` 的 `--caching / --cache-prefix / --thinking / --expire-at` 用法、回显字段与 autotest 对应见 [`references/caching-thinking.md`](references/caching-thinking.md)。
- `+chat` 的 `--text-format / --text-schema / --text-schema-name / --text-strict` 用法见 [`references/text-format.md`](references/text-format.md)。
- `+chat` 的 `--stream --include-events` NDJSON 流式事件输出见 [`references/stream-events.md`](references/stream-events.md)。
