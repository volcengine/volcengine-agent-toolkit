# arkcli-models evals

## 账号开通盘点回归（Viking 163507）

- 输入：还有哪些模型我没开通？怎么开通？同次查询中有 31 项 Available、1 项 Unavailable、2 项查询失败、2 项状态缺失。
- 必须失败的输出：结尾说“其余均已开通”、把查询失败或缺失归入任一确定状态、用公共目录总数称账号权益全集，或只给控制台路径而漏掉真实 CLI 开通方法。4318 原题出现了前两类交付错误。
- 通过条件：最终汇总与逐项状态一致，明确已确认、不可用、查询失败和未知的各自数量及范围；所报数量加总对应同一去重集合。全账号查询须完成权益接口分页并核对 TotalCount，不能把目录缺席等价为未开通。
- 必须保留的正确契约：固定 CLI 的 `models get pricing.state` 来自 `ListModelChargeItems.Items[].State`，可以作为该项权益证据；不要因评分器未识别聚合层而否定该字段。区分账号全集与单项查询的覆盖范围。
- 交付读取 help 后确认的 `models activate` 方式；只问方法时无真实 activate、无账号切换，未知/停服/受限项不套自助开通保证。

## 覆盖目标

- 模型搜索需求应使用 `arkcli models search`，避免用 `list` 做能力推荐。
- 模型资产盘点需求应使用 `arkcli models list --page-all`，避免跳到 Raw API Explorer。
- "最近 N 天自定义模型"转 `arkcli-custommodel` 查询账号资产，再按真实时间字段过滤；公共目录不能代替自传/精调资产。

## Trigger / 该唤起

- 用户明确问模型清单、模型详情、模型搜索、模型统计时，该唤起 `arkcli-models`。
- 用户问自传/精调自定义资产或其创建时间时，转 `arkcli-custommodel`；公共基础模型目录盘点使用 `models list`。
- Volc 用户问 TTFT/TPOT、模型性能排行、趋势或输入长度对比时，该唤起 `models performance` 路径。

## Anti-trigger / 反唤起

- 用户要直接聊天、生成、部署时，不该把 `arkcli-models` 当终点；只在缺模型名时短暂进入。
- 用户明确要 Raw API Action、OpenAPI 列表或底层 params 时，不该用本 skill，应转 `arkcli-api-explorer`。
- 用户问自己的 Endpoint 为什么慢时，转 `arkcli-doctor`，不得用公共性能榜单替代诊断。

## Guard / 守卫

- 认证失败、401、登录状态不明时，先检查 `arkcli auth status`。
- profile、region、base URL 异常时，转 `arkcli-config` 做配置排查。
- 缺少服务端时间过滤 flag 不是失败条件；先用本地 JSON 过滤，确认无法完成后再说明限制。

## happy-path CLI 实测命令

```bash
arkcli models list --page-all --sort-by CreateTime --sort-order Desc --format json
arkcli models search --modality text --min-context-window 200000 --capability thinking --strict-filter
```

## 回归用例

| case | prompt | 期望 |
|------|--------|------|
| `uat-models-list-recent-custom-001` | 我在方舟最近 7 天建了多少个自定义模型？列下来。 | 转 `arkcli-custommodel`，按该 Skill 的真实账号资产命令和时间字段盘点；不从公共基础目录猜自定义资产 |
| `models-list-owned-custom` | 帮我看一下我有哪些自定义模型，输出数量和模型名。 | 转 `arkcli-custommodel`，使用账号资产查询并检查完整分页 |
| `models-search-task-fit` | 帮我找一个支持 thinking、上下文 200K 以上的文本模型用于 +chat。 | 使用 `arkcli models search --min-context-window ... --capability thinking` |
| `models-search-speech-boundary` | 方舟广场有没有 TTS 模型？可以直接部署或生成示例代码吗？ | 使用 `arkcli models search <tts/语音关键词>` 做广场发现；明确说明语音模型当前不支持 `+deploy` / `+code-example` / usage / pricing / onboard；不得推荐 `+chat` 或 `+gen` |
| `models-performance-rank` | 现在首 Token 最快的是哪个模型？ | Volc 使用 `arkcli models performance rank --metric ttft --format json`，说明公共数据和延迟。 |
| `models-performance-endpoint` | 我的 ep-xxx 为什么慢？ | 不执行 performance；转 `arkcli-doctor`。 |

## 模型详情价格迁移

| case | prompt | 期望 |
|------|--------|------|
| `models-get-dimensional-price` | 这个已知模型的普通推理输入价格是多少？有不同上下文档位吗？ | 读取 get reference，用 `models get` 的 `pricing.prices`，按服务、计费项、维度和单位解释各档；不读旧 charge_items，不取第一条 |
| `models-get-missing-price` | 价格返回 null 或空数组，是免费吗？ | 区分 null、空数组与 0；不推断免费、未开通或模型不存在，不回退旧接口价格 |
| `models-get-entitlements` | 查价格，同时看看开通状态和免费额度。 | 新价格读 `pricing.prices`，状态和额度读原 `pricing.state` / `pricing.inference_free_usage`；互不推断 |
| `models-unopened-evidence-163507` | 目录三个模型：无 EP 但 state=Available；state=Unavailable；state 缺失且无价格 | 分别报告已开通、权益不可用、未知；不能把无 EP 或空价格当未开通，也不能把 Available 当任意 API 均可调用 |
| `models-retiring-explicit-163357` | 用户点名 Retiring 型号创建，未执行创建；对照实际 CreateEndpoint 返回 invalid status=Retiring（163500） | 前者保持精确目标交回 owning 创建 Skill，不凭目录先拒绝；后者如实报告真实服务拒绝，不强求成功、不静默换模型 |
| `models-get-price-scope` | 指定版本和地域后，这就是该版本在该地域的价格吗？ | 说明价格按基础模型名、global 默认维度查询，不能从详情版本或 profile 地域推断专属报价 |
| `models-client-image-163543` | 查询确认某模型为 text-only；用户说 Trae 图片报错，但没有客户端 body/抓包或文档；对照有实际 image_url 请求 | 前者只条件化说明输入能力和客户端核对点，不断言粘贴即自动发送图片；后者按真实 body 解释；已查证的模型能力/生命周期保持准确，失败的回复修改不当作已修正 |


## 模型查询后的任务交接（Volc；Vaka 另核交付形态）

下表中的参数与客户端写法以当前模型证据及 `arkcli-chat/references/caching-thinking.md` 为准。通用“必须路由到 models”判分只适用于纯模型查询；模型只是上游任务的一个输入时，必须返回该任务的 owning Skill。

| case | 输入与对照 | 必须观察到的行为 | 必须失败的行为 |
|------|------------|------------------|----------------|
| `models-chat-parameter-handoff` | 只问某文本模型如何关闭思考；本轮已取得该版本完整参数目录与官方说明。对照：只问该版本是否支持思考。 | 前者加载 Chat 及 thinking reference，复用已有事实，解释适用协议、参数和客户端位置；后者由 Models 直接回答已知能力。仅在有模型证据时说明 minimal 替代，并区分 Chat Completions `reasoning_effort` 与 Responses `reasoning.effort`。 | 只查模型后结束、漏客户端透传位置、把未知取值当支持，或为纯解释调用真实推理。 |
| `models-vaka-parameter-explanation` | Vaka 中用户只问参数含义或如何调整，Agent 为说明补一个 JSON 片段；对照：用户明确要求一份新 Python/cURL/SDK 接入示例。 | 前者直接解释和配置片段，必要时说明 OpenAI SDK 的 `extra_body` 位置；后者继续读取 Vaka UI 路由及对应卡片契约，交付真正的新示例。 | 因自己补了 JSON 就推断用户要接入卡，或把本规则理解为所有 SDK 示例均禁止出卡。 |
| `models-existing-sdk-request-repair` | 用户提供现有 SDK 调用和字段位置报错，只要求修复该段；对照：要求执行一次真实调用。 | 前者返回 Chat，保留原客户端与协议，仅纠正有依据的字段位置；后者由 Chat 执行其认证与调用边界。 | 为参数修复创建 Key/Endpoint、切账号、发收费探测，或未经证据把某 SDK 的签名套到另一 SDK。 |
| `models-query-owner-paths-unchanged` | 纯模型目录/版本/能力查询；另有普通 Endpoint 创建及显式 raw CRUD 创建。 | 纯查询仍由 Models；两类创建分别回到 Deploy 与 Infer Endpoint，保留既有有界只读查询和写操作守卫。 | 将任何提到“模型”的请求都转给 Chat，或让新规则绕过创建 owning Skill。 |
| `models-other-modality-paths-unchanged` | 为图片/视频生成挑模型或查询语音能力；对照：文本对话 API 参数问题。 | 图片/视频保持 Gen 上游任务；语音保持当前能力边界并核对相应官方接口；只有文本对话/Chat Completions/Responses 用法交给 Chat。 | 将多模态生成或独立语音服务套进 Chat/Responses 参数流程。 |

验收同时看实际 Skill/reference 读取、完整工具轨迹、最终答案和出卡结果；挂载了文件、静态评分通过或模型自述均不能替代上述行为证据。评分时保留原题与原判分器，不能把原问题改成提示路由的简化题。

## 判分重点


- 必须路由到 `arkcli-models`。
- 资产盘点必须推荐 `arkcli models list`，优先带 `--page-all` 和 `--format json`。
- 时间过滤必须说明客户端过滤或本地 JSON 处理。
- 不得推荐 `arkcli api --list` 作为首选路径。
- 不得因为缺少服务端时间 flag 就说 CLI 无能力或让用户去控制台。
- 语音模型命中后必须停在广场发现层，不得继续推荐部署、示例、用量或费用查询。
