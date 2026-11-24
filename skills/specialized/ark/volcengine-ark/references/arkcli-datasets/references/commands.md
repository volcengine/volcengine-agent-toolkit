# Dataset 命令工作流

## 创建

先用 Client Preview 检查计划，再执行真实命令：

```bash
arkcli dataset create --name <name> --dataset-format LLMSft --local <train.jsonl> --dry-run
arkcli dataset create --name <name> --dataset-format LLMSft --local <train.jsonl>
```

映射已有 TOS 对象：

```bash
arkcli dataset create --name <name> --dataset-format LLMSft --tos-uri tos://<bucket>/<path>
```

`--tos-uri` 指向的 prefix 必须能被当前身份列举，并且至少包含一个 `.jsonl` 对象。不要把本地上传输出中的 `ds-ds/<uuid>/...` 暂存路径再次作为 `--tos-uri`；Dataset 校验引擎不能把它当作映射数据源。优先使用已注册版本的 `ark/dataset/<dataset-id>/<dataset-version-id>/` 路径或其他确认可读的业务数据路径。CLI 会在提交校验任务前执行 TOS 列举预检，并区分无法列举与未发现 `.jsonl`。

创建成功后保存结构化输出中的 `dataset_id`、`dataset_version_id`、`version`、`storage` 和 `validation_jobs`。本地上传对象键位于 `ds-ds/<uuid>/<filename>`。`ValidateDataset.StorageRawLocation.Storage` 不发送 `AccountID`；首版和新增版本的 `CreateDatasetVersion.Storage` 都发送当前账号的数值型 `AccountID`。

为已有 Dataset 创建下一版本：

```bash
arkcli dataset version create <dataset-id> --local <new.jsonl> --dry-run
arkcli dataset version create <dataset-id> --local <new.jsonl>
```

真实执行仍会读取 Dataset 以获得校验所需的 SchemaType，但不会从 `CreatedVersions` 计算名称，也不会发送可选的 `CreateDatasetVersion.Name`。CLI 不提供手工指定该字段的参数，Client Preview 中同样不出现 `Name`。正式版本号完全以服务端响应中的 `Version` 为准；并发版本分配由服务端处理。

## 查询与维护

```bash
arkcli dataset list --page-number 1 --page-size 100
arkcli dataset get <dataset-id>
arkcli dataset update <dataset-id> --name <new-name> --description <text> --dry-run
arkcli dataset update <dataset-id> --name <new-name>
arkcli dataset delete <dataset-id> --dry-run
arkcli dataset delete <dataset-id>
arkcli dataset version list <dataset-id>
arkcli dataset version get <dataset-version-sid>
arkcli dataset version get <dataset-id> V2
arkcli dataset version get <dataset-id> V2 --preview
```

友好版本号 `Vn` 必须同时提供 Dataset ID；版本 SID `dsv-*` 可直接查询。`--preview` 对版本内每个对象最多读取 100 KiB（102400 字节，与控制台一致），并在结构化输出中标记是否截断。删除命令会先查询并展示版本、存储路径和可统计的对象影响范围，再请求确认；不要跳过这一步自行调用 Raw API。

## 独立校验

```bash
arkcli dataset validate --local <data.jsonl> --model <model> --model-version <version> --type sft --dry-run
arkcli dataset validate --local <data.jsonl> --model <model> --model-version <version> --type sft
```

真实执行会先查询 `models finetune-config` 对应的精确 schema，再上传或解析 TOS 路径，并逐个调用服务端校验、轮询到 `Succeed` 或 `Failed`。不要自行从 `--type` 猜测 schema，也不要添加本命令不存在的 `--sample-count`。

## 下载

```bash
arkcli dataset download <dataset-id> --version <dsv-id-or-vn> --dry-run
arkcli dataset download <dataset-id> --version <dsv-id-or-vn>
arkcli dataset download <dataset-id> --version V2 --output-dir ./dataset-copy
arkcli dataset version download <dataset-id> <dsv-id-or-vn> --dry-run
arkcli dataset version download <dataset-id> V2 --output-dir ./dataset-copy
```

未提供 `--output-dir` 时目录为 `./<dataset-id>-<version>/`。对象相对路径保持不变；任何目标文件已存在时不覆盖。

## 接入精调

```bash
arkcli train finetune create \
  --name <job-name> \
  --model <model> --model-version <version> --type sft \
  --train-dataset <dataset-id>:<dataset-version-id>
```

验证集使用 `--validation-dataset <dataset-id>:<dataset-version-id>`。需要重复引用 Dataset 或设置倍率/采样数时使用可重复的 `--train-path`；每个 JSON 最多设置 `multiplier` 或 `sample_count` 之一，均不设置时默认 `Multiplier=1`：

```bash
--train-path '{"dataset_id":"ds-...","dataset_version_id":"dsv-...","multiplier":1}'
--train-path '{"dataset_id":"ds-...","dataset_version_id":"dsv-...","sample_count":500}'
```

预置数据集也使用可重复 JSON，并且 `inject_multiplier` 与 `inject_sample_count` 必须且只能设置一个：

```bash
--preset-dataset '{"dataset_version_id":"dsv-...","inject_sample_count":100}'
```

`--train-path` 与其他训练 Dataset/TOS/本地文件来源互斥。创建任务前 CLI 会检查模型要求的 schema，并拒绝模型配置未声明支持的 preset。
