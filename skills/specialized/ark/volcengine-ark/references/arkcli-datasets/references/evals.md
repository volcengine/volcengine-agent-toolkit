# arkcli-datasets evals

## Trigger / 该唤起

- 创建、校验、查询、更新、删除或下载 Dataset。
- 用户提供 `ds-*`、`dsv-*` 或询问 `Vn` 版本。
- 把可复用 Dataset 作为精调训练集、验证集或 preset。

## Anti-trigger / 反唤起

- 仅管理已有 `mcj-*` 精调任务时转 `arkcli-train-finetune`。
- 仅上传普通 TOS 对象且不涉及 Dataset 时不加载本 skill。

## 回归用例

| case | prompt | 期望 |
|---|---|---|
| `dataset-create-local` | 用本地 train.jsonl 创建 LLMSft 数据集。 | 先执行 `dataset create ... --dry-run`，确认后真实创建；校验请求不发送 `AccountID`，首版 `CreateDatasetVersion.Storage.AccountID` 使用当前账号且 JSON 类型为 number；不臆造自动回滚。 |
| `dataset-format-invalid` | 用 `ImageGenerationSFT` 创建数据集。 | 本地拒绝，并提示全部合法值：`LLMSft`、`LLMPretrain`、`LLMDPO`、`LLMRL`、`EmbeddingSft`、`ImageGenSft`、`VideoGenSft`。 |
| `dataset-version-friendly-id` | 查询 ds-1 的 V3。 | 执行 `dataset version get ds-1 V3`；不得只传 V3。 |
| `dataset-version-sid` | 查询 dsv-1。 | 执行 `dataset version get dsv-1`，不要求多余 Dataset ID。 |
| `dataset-version-preview` | 预览 ds-1 的 V1 内容。 | 执行 `dataset version get ds-1 V1 --preview`；每个对象最多读取 100 KiB（102400 字节），并返回 `truncated`。 |
| `dataset-version-concurrent-create` | 并发为同一 Dataset 创建两个版本。 | 可以分别执行；`CreateDatasetVersion` 不发送可选 `Name`，也不从 `CreatedVersions` 计算名称；使用服务端为每次调用返回的 `Version`。 |
| `dataset-validate-model-schema` | 按 model/version 的 DPO 配置校验 TOS 数据。 | 使用 `dataset validate --tos-uri ... --model ... --model-version ... --type dpo`；不自行把 dpo 字面值当 SchemaType，不添加 `--sample-count`。 |
| `dataset-tos-staging-prefix` | 用上次本地上传返回的 `tos://.../ds-ds/<uuid>/` 创建 Dataset。 | 在调用 `ValidateDataset` 前拒绝，说明 `ds-ds/*` 是上传暂存路径，并引导使用 `ark/dataset/<dataset-id>/<dataset-version-id>/` 或其他可列举且包含 `.jsonl` 的路径。 |
| `dataset-download-conflict` | 下载 V2 到已有目录。 | 保留对象相对路径；发现目标文件冲突时停止且不覆盖。 |
| `dataset-version-download-alias` | 用版本命令下载 ds-1/V2。 | 使用 `dataset version download ds-1 V2`；其 Preview、输出与不覆盖契约和 `dataset download --version V2` 一致。 |
| `dataset-delete-impact` | 删除 ds-1。 | 删除前展示版本数、存储路径数以及可统计的对象数/字节数，再单独确认。 |
| `finetune-dataset-reference` | 用 ds-1/dsv-1 训练并添加一个 preset。 | 使用 `--train-dataset ds-1:dsv-1` 和 wire-shape JSON 的 `--preset-dataset`；不得同时使用训练 TOS/本地文件来源。 |
| `finetune-train-path-sampling` | 用一个 Dataset 放大 2 倍、另一个采样 500 条。 | 重复使用 `--train-path`；每项只传 `multiplier` 或 `sample_count` 之一，并拒绝与其他训练来源混用。 |
