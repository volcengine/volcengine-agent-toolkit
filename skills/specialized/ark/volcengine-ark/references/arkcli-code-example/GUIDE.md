---
name: arkcli-code-example
version: 1.2.0
description: "arkcli +code-example：为指定基础模型生成多语言（Python / Go / Java / Node / curl）调用示例代码并写入本地文件。数据源是火山方舟 OpenTOP OpenGetSampleCode。当用户需要拿某个基础模型的 SDK / curl 调用示例、保存为本地接入模板时使用。反触发：TTS/ASR/语音模型没有 arkcli 示例代码路径，不能靠补版本解决，只能转 models search 说明当前不支持。"
metadata:
  requires:
    bins: ["arkcli"]
  cliHelp: "arkcli +code-example --help"
---

# arkcli +code-example

> **前置条件：** 先阅读 [`../arkcli-shared/GUIDE.md`](../arkcli-shared/GUIDE.md) 了解认证、全局参数和安全规则。

为指定基础模型生成多语言 SDK 调用示例代码，同时写入本地文件。数据源是火山方舟 OpenTOP `OpenGetSampleCode`。

## 什么时候用

- 用户说"生成示例代码 / SDK 示例 / curl 命令 / 怎么调用这个模型"，且已经知道模型名
- 想把某个基础模型的多语言调用模板保存到本地
- 教程或技术文档需要引用该基础模型的具体 SDK import、安装包、方法或请求格式：先取得对应版本示例并核对官方文档，不能从模型生成的草稿直接采信接口写法。

## 教程中的代码事实核对

以真实返回条目的 `install`、`language`、`io_type` 和 `code` 作为示例依据；明确目标模型/版本、语言及接口路径。更换 SDK 包或版本、图片/视频方法、响应字段、错误码时必须另核对该版本源码或官方文档正文；一个模型的文本示例不能证明所有媒体接口。服务端提供模板也不等于已在本轮执行成功，分别标明“官方示例/静态核对/实际运行”。检索片段或 AI 初稿不足时缩小教程到已查证内容，未验证片段标注或移除，不写成完整已验证接入指南。

示例命令可能将当前 Key 填入文件；遵守共享身份/授权协议，提交教程前将 Key、Token 和签名 URL 等真实凭证替换为占位符并检查附件。不得直接回显未脱敏的生成条目，不为拿示例切换账号或绕过 Access 门禁。

**反路由**（不要用本命令）：

- 只是想试模型效果 → [`../arkcli-chat/GUIDE.md`](../arkcli-chat/GUIDE.md)（文本/多模态对话）或 [`../arkcli-gen/GUIDE.md`](../arkcli-gen/GUIDE.md)（出图/视频）
- 还不知道模型名 → 先 [`../arkcli-models/GUIDE.md`](../arkcli-models/GUIDE.md) `models search/get`
- 需要先创建接入点 → [`../arkcli-deploy/GUIDE.md`](../arkcli-deploy/GUIDE.md)
- 语音模型（TTS / ASR / 配音 / 朗读 / 播客 / 音色 / 实时语音交互，或 `doubao-seed-tts-*` / `doubao-seed-asr-*` / `seedasr-*`）→ 不使用 `+code-example`。`models search` 能搜到不代表 OpenGetSampleCode 有示例；不要把后端 `ModelVersion required` 理解成"补一个版本就能生成"，应说明当前 arkcli 不支持语音模型示例代码。

## 快速开始

```bash
# 拿某基础模型的全部语言示例（写入 ./ark-examples/<model>/）
arkcli +code-example --model doubao-seedream-5-0

# 指定版本 + 只看 Python + 结构化输出
arkcli +code-example --model doubao-seedream-5-0 --version 260128 --language python --format json
```

- `--model` 必填，可传基础模型名或合并 ID（`doubao-seedream-5-0-260128`）
- `--version` 可选；不传时 CLI 自动推导（合并 ID 拆版本 → 找 `ArkModels` 匹配 → GetFoundationModel 取 `PrimaryVersion` 兜底），全都拿不到才报错要求显式传 `--version`
- 内部机制：接口约束 `ModelVersion` 必填，缺失时 CLI 走上述回退链自动补齐；custom model 走 PrimaryVersion 兜底时 scenario 自动切 `finetune_inference`，foundation model 无论显式版本或 PrimaryVersion 兜底一律保持 `quick_access`
- `--language` 可选：`python` / `go` / `java` / `node` / `curl`（`shell` 是 `curl` 别名），默认全部
- `--output-dir` 可选，默认 `./ark-examples/<model>`
- `--format json` 输出结构化条目（含 `language` / `io_type` / `install` / `code`）
- 语音模型没有 arkcli 示例代码路径；命中 TTS / ASR / 语音交互时停在 `arkcli models search <keyword>` 的发现说明，不要继续调用本命令

> **0.1.17 变更**：旧版 `--endpoint-id` 已移除——新数据源按基础模型取码，不再支持按已有接入点 ID 取码。如需指向某 endpoint，生成后把代码里的 `model="..."` 手动改成你的 `ep-xxx`。

## 命令一览

| 命令 | 说明 |
|------|------|
| `arkcli +code-example --model <name> [--version <ver>] [--language <lang>] [--output-dir <dir>] [--format json]` | 生成多语言示例代码并写入本地 |

## 输出形态

- **本地文件**：按"IO 任务类型"分子目录（对齐后端 `IOType` 维度），同类型下按语言分文件；带安装步骤的语言把安装命令写进文件头注释。
- **结构化 JSON**：`--format json` 时给出按 `(语言 × IO 类型)` 展开的条目。
- **人类可读**：默认按后端顺序打印各代码块。

详细参数、目录结构示例、常见链路与 FAQ 见 [`references/arkcli-code-example.md`](references/arkcli-code-example.md)。

## 参考

- [references/arkcli-code-example.md](references/arkcli-code-example.md) — 完整命令手册
- [arkcli-models](../arkcli-models/GUIDE.md) / [arkcli-deploy](../arkcli-deploy/GUIDE.md) / [arkcli-infer-endpoint](../arkcli-infer-endpoint/GUIDE.md) / [arkcli-shared](../arkcli-shared/GUIDE.md)
