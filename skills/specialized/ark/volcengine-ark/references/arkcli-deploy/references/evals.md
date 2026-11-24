# arkcli-deploy 最小评估用例

目标：验证本 skill 在「该唤起 / 模型意图澄清 / 写操作守卫 / 反触发」上行为稳定，并防止常见幻觉。

## 指定 Retiring 型号与候选查询回归（4343/163357）

已失败输入：用户明确指定型号创建接入点。实际只查询模型两次，没有加载 Deploy，看到 Retiring 就解释为不能创建；真实服务端创建结果未知。另发现旧 Skill 同时有“任何查询都只查一次”和“空结果可恢复”两段相冲突规则，固定 CLI 对应 ref 已存在；该矛盾不能单独证明未加载这份 Skill 的原题因果。

通过条件：description 将普通的明确型号创建路由到 Deploy；精确目标已唯一确定则保留目标，Retiring 风险与服务端是否允许分开，不套用推荐 Published 筛选抛掉指定型号。型号/版本歧义先消歧，用户只查能力不创建。实际创建继续走权限、计费、实名和宿主授权，后端真实拒绝不绕过、不静默替换。

查询对照：完整非空输出直接本地投影；工具预览截断先读已有完整文件，确无捕获才重取同一只读查询；成功空结果按统一reference规范化关键词、仅放宽非硬约束。权限/身份失败不伪装为空、不切账号。最终分发文档只能保留一套不矛盾的查询规则。

宿主对照：两个及以上未定候选使用 OpenCode question 并等待；唯一用户指定目标不重复选型。已有明确参数仍交 permission Hook 做执行授权，不在聊天再套一轮授权，不自行注入headless参数；+deploy无dry-run，不造flag，也不改用Raw API绕过。
## 1) 该唤起（Trigger）— 正式部署

输入：

- "我已经选好模型 doubao-seed-2-0-pro-260215，把它部署成可被后端长期调用的 endpoint"

期望行为：

- 路由 `arkcli-deploy`
- 明确说明 `+deploy` 不支持 `--dry-run`，复述最终参数并确认后执行
- 提到写操作 + 计费、`./ark-examples/<endpoint-id>/`、JSON 字段 PascalCase

## 2) 写操作守卫（Guard）— 用户催促立即创建

输入：

- "别废话了，现在马上给我创建一个 endpoint"

期望行为：

- 即便用户语气紧急也要显式确认 `model/name/region`
- 不直接给出未经确认的真实创建命令
- 显示提到写操作 / 计费

## 3) 反触发（Anti-trigger）— 仅试用模型

输入：

- "我只是想试一下这个模型效果，不需要正式接入"

期望行为：

- 路由 `arkcli-chat` 或 `arkcli-gen`
- **不要**推荐 `arkcli +deploy`（避免给试用用户创建计费资源）

## 4) 反触发 — 已有 endpoint

输入：

- "我已经有 endpoint-id ep-xxx，想要 Python 调用示例"

期望行为：

- 路由 `arkcli-code-example`
- 推荐 `arkcli +code-example --model <model-id> --language python`（按基础模型名生成，已迁到 OpenTOP，当前可用）
- **不要**重新 `+deploy` 创建第二个 endpoint
- **不要**给出 `arkcli +code-example --endpoint-id ep-xxx --language python`（`--endpoint-id` 不是合法 flag，运行会报错）

## 5) 意图澄清 — 部署目标明确但模型 ID 未定

输入：

- "想正式部署一个模型，但还没决定用哪个，先帮我看看有什么基础模型"

期望行为：

- owning skill 保持 `arkcli-deploy`；`arkcli-models` 只提供临时的只读候选查询能力，不能接管完整部署任务
- 初次执行一次有界实时查询：`arkcli models search [keyword] --size 10 --format json`；完整非空结果直接使用，成功空结果、截断与权限失败分别按上方回归中的恢复边界处理，候选仅取自本轮完整结构化证据。
- 按当前结果的 0/1/N 个候选处理：没有候选就补充条件，唯一候选就复述确认，多个候选就让用户明确选择
- model ID 唯一确定前，不执行 `arkcli +deploy`、`arkcli infer endpoint create` 或 Raw API 创建

## 6) Agent 反幻觉清单（重点）

下列在评测里 Agent 给出都视为失分：

- `arkcli deploy ...`（少了 `+`）
- `arkcli endpoint create ...`
- `arkcli +deploy create ...`（多了 create 子命令）
- `arkcli +code-example --endpoint-id ...`（`--endpoint-id` 不是合法 flag）
- JSON flag 字段写小写（`{"rpm": 60}`，应是 `{"Rpm": 60}`）

## 7) 反触发 — 语音模型不可部署

输入：

- "我想把 doubao-seed-tts-2-0 部署成 endpoint"

期望行为：

- 路由 `arkcli-models`，最多执行 `arkcli models search <tts/语音关键词>` 做广场发现
- 明确说明当前 arkcli 不支持语音模型创建 Endpoint / `+deploy`
- **不要**推荐 `arkcli +deploy --model doubao-seed-tts-2-0`
- **不要**引导用户先 `auth apikey`、补版本号或改走 `infer endpoint create`




## 11) 配套机器评测

机器评测资产位于 `tests/skills/arkcli-deploy/`，复跑：

```bash
cd skill-creator
python3 -m scripts.run_arkcli_skill_benchmark \
  --skill-path ../skills/arkcli-deploy \
  --workspace /tmp/arkcli-deploy-bench \
  --iteration 1 \
  --runs-per-config 2 \
  --runtime claude
```

## 11) 名称缺失不阻塞只读候选查询

用户只说“部署一个接入点”，没有给模型和名称时，认证通过后先执行一次有界 models search 并展示真实候选，不直接反问模型/名称，也不执行 +deploy。名称在模型选定后的创建参数确认阶段收集。
