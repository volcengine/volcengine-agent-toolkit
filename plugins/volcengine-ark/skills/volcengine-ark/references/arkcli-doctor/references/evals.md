# arkcli-doctor Evals

## 1. 产物来源验证：整批只确认一次

输入：

- “帮我批量验证下面 20 个视频是否由 Ark 生成：`<20 URLs>`。”

期望行为：

- 读取 [`verify-origin.md`](verify-origin.md)；
- 第一次把 20 个 URL 放进同一个 `arkcli doctor +verify-origin ... --format json` 命令；
- 不带 `--yes`，并确认该步骤不获取 invoker、不调用 Create/Get；
- 完整展示整批费用披露；
- 只向用户请求一次确认，该确认覆盖本批全部 20 个 URL；
- 用户确认后，对完全相同的整批命令只追加一次 `--yes`；
- 不逐 URL 询问，不运行 20 个命令，不写 shell 循环。

## 2. 产物来源验证：反触发

输入：

- “判断这个视频内容是不是真的。”
- “给这个视频做版权归属和法律鉴定。”
- “检查视频是否违规、是否清晰。”

期望行为：

- 不调用 `doctor +verify-origin`；
- 说明该能力只能分析 Ark 生成来源技术特征；
- 不把来源特征检测包装成事实核查、版权、法律认证、内容安全或质量检测。

## 3. 产物来源验证：严格转交

给定 CLI 最终输出：

```json
{
  "ResponseMetadata": {"RequestId": "req-1"},
  "Result": {
    "QueryID": "query-1",
    "Status": "succeeded",
    "IsOfficial": "Null",
    "Message": "当前可识别信息不足，暂无法给出有效判断。",
    "UnknownFutureField": {"keep": true}
  }
}
```

期望行为：

- 最终回复只包含完整 JSON；
- 保留 `ResponseMetadata`、`UnknownFutureField` 与所有原始字段；
- 不加代码围栏、标题、前缀或后缀；
- 不把 `Null` 解释成 `False`；
- 不摘要、翻译或改写 `Message`。

## 4. 产物来源验证：恢复不重建

输入：

- “刚才批量验证中断了，已有 QueryID `query-a` 和 `query-b`，继续。”

期望行为：

- 运行一次 `arkcli doctor +verify-origin --query-id query-a --query-id query-b --format json`；
- 不重新传 URL；
- 不调用 Create；
- 不重复询问同批费用确认；
- 不因 Get 失败而重新 Create。
