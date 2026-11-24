# 下载精调任务数据

用户想找回某个精调任务实际使用的训练集 / 验证集时，使用：

```bash
arkcli train finetune download <job-id> [--set all|train|validation] [--output-dir <dir>]
```

该命令从 `GetModelCustomizationJob` 的 `Data.TrainingSet` / `Data.ValidationSet` 解析数据来源，
再从 TOS 下载到本地。默认输出目录是 `./<job-id>-data`，默认下载训练集和验证集。

## 支持的来源

| Job Data 字段 | 行为 |
|---|---|
| `TosBucket` + `TosPaths` | 按原 TOS 对象路径下载，保留相对路径 |
| `Datasets[]`（`DatasetId` + `DatasetVersionId`） | 先查 Dataset 版本存储位置，再下载其 `Storage.Bucket` / `Storage.Prefixes` |
| `PresetDatasets[]` | 平台托管预设数据，不可下载；结果里列为 `skipped` |
| `LocalFiles[]` | 仅记录创建时的本机路径，服务端不保留文件内容；结果里列为 `skipped` |

如果训练集/验证集同时存在多种来源，命令会分别下载到 `train/` 或 `validation/` 子目录；
同一集合有多个来源时再追加 `01/`、`02/` 等序号目录，避免同名文件冲突。

## 示例

```bash
# 下载训练集和验证集
arkcli train finetune download mcj-20260722153822-jqvd

# 只下载训练集到指定目录
arkcli train finetune download mcj-20260722153822-jqvd --set train --output-dir ./mcj-data

# 只下载验证集
arkcli train finetune download mcj-20260722153822-jqvd --set validation
```

结果包含每个文件的 `object_key`、本地 `path`、`size_bytes`，以及每个集合的 `bucket` / `prefixes`。

## 边界

- 这是控制面任务加 TOS 读取，不是 `--api-key` 数据面调用；不要传 `--api-key` / `--base-url`。
- 输出目录已有同名文件时命令会失败，避免静默覆盖本地文件；换一个 `--output-dir` 再试。
- 如果 job 只有 `PresetDatasets` 或 `LocalFiles`，没有可下载的 TOS 对象，命令会返回明确的无可下载数据错误。
- 不要根据任务名、模型名或历史目录猜测数据位置；以 job 返回的 `TosBucket` / `TosPaths` 或 Dataset 版本为准。
