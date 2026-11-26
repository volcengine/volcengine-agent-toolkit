---
name: arkcli-datasets
description: 使用 ArkCLI 创建、校验、查询、更新、删除、版本化和下载 Dataset。用户提到 Dataset、数据集、ds-*、dsv-*、训练集/验证集复用、数据格式校验或把 Dataset 接入精调任务时使用。
---

# ArkCLI 数据集

先读取 [`../arkcli-shared/GUIDE.md`](../arkcli-shared/GUIDE.md)，遵循认证、输出、安全、Client Preview 和二次确认规则。

## 能力范围

- 创建 Dataset 及首个 `V1`，或为已有 Dataset 创建新版本。
- 从本地 `.jsonl` 文件或同一 TOS bucket 下的对象映射数据。
- 根据基础模型的精调配置解析准确 `DatasetSchema` 并执行服务端校验。
- 查询、更新、删除 Dataset，查询版本，下载版本中的 TOS 对象。
- 为 `train finetune create` 产出稳定的 `<dataset-id>:<version-id>` 引用。

只处理精调任务本身时改用 [`../arkcli-train-finetune/GUIDE.md`](../arkcli-train-finetune/GUIDE.md)。不要用 Raw API 模拟已有的 `dataset` 产品命令。

## 执行守卫

1. 先执行 `arkcli auth status`；认证失败时按 shared skill 恢复。
2. 执行前读取目标叶子命令的 `--help`，以当前安装版本为准。
3. `--dataset-format` 只接受 `LLMSft`、`LLMPretrain`、`LLMDPO`、`LLMRL`、`EmbeddingSft`、`ImageGenSft`、`VideoGenSft`；不要发送展示文案或其他后端 SchemaType。
4. `--local` 与 `--tos-uri` 互斥。本地输入只接受 `.jsonl`，最多 20 个文件；多个 TOS URI 必须属于同一 bucket。`--tos-uri` 必须能被当前身份列举且至少包含一个 `.jsonl`；不能复用 CLI 上传结果中的 `ds-ds/*` 暂存路径，应使用已注册版本的 `ark/dataset/<dataset-id>/<dataset-version-id>/` 路径或其他可读数据路径。
5. 创建和新增版本会先逐个校验输入；`ValidateDataset.StorageRawLocation.Storage` 不发送 `AccountID`，但随后两种工作流的 `CreateDatasetVersion.Storage` 都必须发送当前账号的数值型 `AccountID`。`CreateDatasetVersion` 不发送可选的 `Name`，CLI 也不提供该参数；正式版本号完全以服务端响应中的 `Version` 为准。任一步失败都保留已上传对象或已创建 Dataset，不臆造回滚。
6. `dataset version get <dataset-id> <Vn|dsv-*> --preview` 读取每个对象最多 100 KiB（102400 字节）内容，与控制台 Dataset 预览上限一致；版本 SID 仍可省略 Dataset ID。下载既支持 `dataset download ... --version ...`，也支持 `dataset version download <dataset-id> <Vn|dsv-*>`，且都不覆盖已有文件。
7. 删除前先展示版本数、存储路径数以及可获取时的对象数和总字节数，再单独确认。
8. 创建、版本创建、校验、下载、更新、删除支持叶子级 `--dry-run`。只读的 list/get 不使用 `--dry-run`；`version get --preview` 是真实只读查询，不是 Client Preview。
9. Client Preview 只展示离线计划；它不上传、不校验服务端数据，也不代替删除确认。


Volc 本地上传使用当前 profile 对应区域的 TOS endpoint，并启用 bucket rename。

## 工作流

- 创建、维护、校验、下载：读取 [`references/commands.md`](references/commands.md)。
- Dataset 接入精调：完成 Dataset 后读取 [`../arkcli-train-finetune/references/create.md`](../arkcli-train-finetune/references/create.md)。
- 维护者评测：读取 [`references/evals.md`](references/evals.md)。

只加载当前任务需要的 reference。
