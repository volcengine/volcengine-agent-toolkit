---
name: volcengine-knowledge-search
description: "使用 ve docs search/fetch 检索火山引擎官方文档并获取全文。Use when 用户咨询火山引擎产品的概念、用法、计费规则、部署步骤、最佳实践或服务条款，或提供 www.volcengine.com/docs/、docs.volcengine.com/docs/ 链接需要阅读正文时。"
license: MIT
metadata:
  openclaw:
    requires:
      bins:
        - ve
    install:
      - kind: node
        package: "@volcengine/cli"
        bins: [ve]
---

# volcengine-knowledge-search 火山引擎文档检索

通过 `ve docs search` 检索官方文档，通过 `ve docs fetch` 获取正文。请求、响应解析、正文清洗和分页由 CLI 处理；本 skill 负责场景判断、query 改写、二次检索和来源引用。

## 准备

首次使用时确认本机具备两个子命令：

```bash
ve docs search --help
ve docs fetch --help
```

若 `ve` 未安装或缺少子命令，加载 `volcengine-cli` skill，按其「Install or upgrade the ve CLI」章节安装最新版，再检查能力。文档命令访问公开服务，**无需登录、AK/SK、profile 或地域配置**；安装后直接使用，无需执行资源管理的身份初始化流程。

## 选择流程

1. **用户提供具体文章链接**：直接 `fetch`，读取与问题相关的正文。
2. **用户提出问题**：补全产品名和具体方向后 `search`，首次检索不带产品过滤。根据标题、摘要和产品编码判断相关性。
3. **结果过宽或不相关**：改写 query；只有结果中已确认目标产品的 `ServiceCodes` 时，才使用该编码二次检索。不要把无关命中的编码用作过滤条件。
4. **需要完整步骤、限制条件、精确计费规则或全文总结**：对相关结果的 URL 执行 `fetch`，按需续读；用户要求全文时，读到没有续读提示或 `has_more=false`。

## search：检索文档

```bash
ve docs search "对象存储 TOS 如何计费" --limit 3 --output text
```

搜索文本是**位置参数**，用引号包住完整问题。用 `--output text` 获取可直接阅读的 Markdown：每条包含标题、纯净 URL、`ServiceCodes` 和正文摘要。CLI 默认输出 JSON；需要程序化处理时显式用 `--output json`，结果在 `documents` 数组中，字段为 `title`、`url`、`service_codes`、`snippet`。

| 参数 | 用途 |
| --- | --- |
| `--limit N` | 返回文档数，正整数；一般先取 3 条 |
| `--service-code CODE` | 限定产品，编码取自已确认相关的结果；多个产品重复传此选项 |
| `--snippet-length N` | 每条摘要的最大 Unicode 字符数，正整数；用它控制上下文体积 |

### 改写 query

语义检索需要贴近文档表述。将口语、简称或营销名补成**产品全称 + 能力描述 + 具体问题**，例如把「Coding Plan 多少钱」改写为「火山方舟 Coding Plan AI 编程订阅套餐如何计费」。首搜跑偏时，换全称、近义描述或功能描述再搜。

```bash
ve docs search "火山方舟 Coding Plan AI 编程订阅套餐如何计费" --limit 3 --output text
```

先宽搜，确认相关结果的 `ServiceCodes` 为 `tos` 后，按产品精搜：

```bash
ve docs search "跨区域复制如何配置" --limit 5 --snippet-length 300 --output text
ve docs search "对象存储 TOS 跨区域复制如何配置" --limit 3 --service-code tos --output text
```

多个产品编码使用 `--service-code <code-a> --service-code <code-b>`，每个编码单独传递。

## fetch：获取正文

支持 `https://www.volcengine.com/docs/...` 和 `https://docs.volcengine.com/docs/...`。CLI 会去掉 URL 的 query 和 fragment，text 输出依次为标题、纯净 URL、当前页正文及续读提示。

```bash
ve docs fetch "https://www.volcengine.com/docs/6349/162514?lang=zh" --output text
```

| 参数 | 用途 |
| --- | --- |
| `--start-index N` | 从第 N 个 Unicode 字符开始，索引从 0 起 |
| `--max-length N` | 当前页最多返回的 Unicode 字符数，正整数；默认 5000 |

长文末尾会提示下一页的 `--start-index`。用**同一个 URL 和返回的索引**继续读，避免漏读或重复。以下示例先取 300 字，若续读提示为 `--start-index 300`，再读取下一页：

```bash
ve docs fetch "https://www.volcengine.com/docs/6349/162514" --max-length 300 --output text
ve docs fetch "https://www.volcengine.com/docs/6349/162514" --start-index 300 --max-length 300 --output text
```

程序化分页使用 `--output json`，读取 `content`、`start_index`、`next_start_index`、`remaining_characters`、`has_more` 和 `has_content`。`has_more=true` 时用 `next_start_index` 续读；结束时该字段为 `null`。

### 导航页与空正文

- `/docs/{产品编号}/{文档ID}` 是具体文章路径。
- `/docs/{产品编号}` 是产品文档导航页，没有单篇文章正文。识别到这种链接时，按产品名和用户关心的方向 `search`，从结果定位具体文章再 `fetch`，并向用户说明链接类型。
- `has_content=false` 表示没有取得正文，不能据此编造内容。检查链接是否为导航页、过期或错误地址，再用 `search` 定位替代文档。

## 结果与错误处理

- **按证据回答**：摘要足以支撑的概念问题可以直接回答；精确规则和完整步骤先取正文。部分页面不能表述为已读完整篇。
- **引用来源**：使用 CLI 返回的纯净 URL，格式为 `[文档标题](URL)`。优先展示最多 3 条最相关来源，每个结论都能对应到已读取的内容。
- **控制输出**：search 用 `--limit` 和 `--snippet-length`，fetch 用 `--max-length` 和 `--start-index`。CLI 不提供旧脚本的临时文件预览机制，续读依赖分页参数。
- **正常空结果**：退出码为 0 且 `documents` 为空时，改写 query 或放宽产品过滤；这不代表服务故障。
- **参数错误**：按对应子命令的 `--help` 修正参数；数量和长度必须为正数，起始索引非负。
- **请求失败**：非零退出时读取 stderr，区分网络问题和上游业务错误。超时或 `DownstreamError` 等暂时性故障可重试一两次；持续失败时说明失败原因，不把失败当成无结果。公开文档请求失败无需补充云账号凭据。
