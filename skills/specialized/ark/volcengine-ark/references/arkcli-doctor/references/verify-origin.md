# Ark 产物来源特征验证

## 1. 能力边界

命令：

```bash
arkcli doctor +verify-origin <media-url> [media-url...] --format json
```

用于验证 1-20 个公网图片或视频 URL 是否包含与 Ark 生成过程相关的技术特征。

它不能：

- 判断媒体内容是否真实、是否是假新闻；
- 判断版权、权属或法律责任；
- 构成官方认证、法律鉴定或权属认定；
- 判断内容安全、合规、画质或播放质量。

## 2. 输入与批量约束

- 一次输入 1-20 个 `http://` 或 `https://` URL；
- 图片和视频可在同一批中出现；
- 必须一次调用把整批 URL 交给 CLI；
- 禁止为每个 URL 分别启动 `arkcli`；
- 禁止使用 shell `for` 循环；
- 禁止直接调用 `CreateArkOfficialResultQuery` 或 `GetArkOfficialResult` Raw Action；
- 禁止 Agent 自己轮询。

超过 20 个 URL 时，把它们拆成多批，并且每一批都必须独立完成费用披露与确认。

## 3. 整批一次确认

首次调用不带 `--yes`：

```bash
arkcli doctor +verify-origin \
  "https://example.com/a.mp4" \
  "https://example.com/b.png" \
  --format json
```

该调用必须：

- 不获取产物验证 invoker 或 STS；
- 不调用 Create；
- 不调用 Get；
- 返回一份覆盖整批的价格、数量与限额披露。

Agent 必须完整展示披露，然后等待用户在看到披露后明确确认。用户确认后，对原命令只追加一次 `--yes`：

```bash
arkcli doctor +verify-origin \
  "https://example.com/a.mp4" \
  "https://example.com/b.png" \
  --yes \
  --format json
```

这一个 `--yes` 覆盖当前批次中的全部 URL。禁止逐 URL 确认，禁止弹出 20 次确认。

计费事实：

- 每账号提供 20 次免费额度，但 CLI 不知道当前剩余额度；
- 免费额度用尽后 `0.1 CNY/call`；
- 成功得到 `True`、`False` 或 `Null` 都计费；
- 鉴权或限流失败不计费；
- 单日上限 1000 次；
- Create 与 Get 均按目标态 20 QPS 设计。

## 4. 执行与恢复

CLI 对每个 URL：

```text
CreateArkOfficialResultQuery
  -> Result.QueryID
  -> 每 5 秒 GetArkOfficialResult
  -> running 继续
  -> succeeded / failed 结束
```

每个 URL 最多 Create 一次。Create 超时不能证明服务端没有创建，因此 CLI 不自动重试 Create。

Get 发生可重试限流或临时服务错误时，只能保留同一个 QueryID 重试 Get，绝不能回到 Create。

如果命令中断，使用输出中的 QueryID 恢复：

```bash
arkcli doctor +verify-origin \
  --query-id "<query-id-1>" \
  --query-id "<query-id-2>" \
  --format json
```

恢复已有 QueryID 不重新 Create，也不重复询问同批费用确认。

## 5. 鉴权

该命令是控制面 OpenTOP workflow：

- 支持 SSO 派生 STS AK/SK/SessionToken；
- 支持长期 AK/SK；
- 不使用 Ark API Key；
- 不要传全局 `--api-key` 或 `--base-url`。

## 6. 最终结果必须完整转交

单条结果是完整 `GetArkOfficialResult` JSON envelope。批量结果是按输入顺序排列的数组，每个成功项的 `response` 都是完整 envelope。

Agent 的最终回复必须只包含 CLI stdout 的完整 JSON：

- 不添加总结；
- 不翻译；
- 不解释 `IsOfficial`；
- 不只摘 `Result`；
- 不只摘 `Message`；
- 不添加 Markdown 代码围栏；
- 不添加“结果如下”等前缀；
- 不使用 `--transform`；
- 不切换为 YAML、table、CSV 或 JSONL。

特别禁止：

- 把 `True` 说成“已官方认证由 Ark 生成”；
- 把 `False` 说成“确定不是 Ark 生成”；
- 把 `Null` 说成 `False`；
- 改写服务端免责声明。

## 7. Client Preview

用户只想预览执行计划时：

```bash
arkcli doctor +verify-origin \
  "https://example.com/a.mp4" \
  "https://example.com/b.mp4" \
  --dry-run \
  --format json
```

Preview 零网络，只展示每个 URL 的 Create/Get 图、5 秒轮询、QPS 和整批确认范围。Preview 不是费用确认，不能因为 preview 成功自动添加 `--yes`。
