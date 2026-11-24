# arkcli infer endpoint update

Update an infer endpoint (name / description / rate limit)

## Usage

```bash
arkcli infer endpoint update <endpoint-id> [flags]
```

至少需要提供 `--name`、`--description`、`--rpm`+`--tpm` 或任意 `--cg-*` 中的一项；否则命令会报「nothing to update」并不会发出请求。

## Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `<endpoint-id>` | The ID of the endpoint to update | Yes |

## Flags

| Flag | Type | Description | Required |
|------|------|-------------|----------|
| `--name` | string | New endpoint name | No |
| `--description` | string | New endpoint description (use empty string `""` to clear) | No |
| `--rpm` | int | Rate limit: requests per minute (must be paired with `--tpm`) | No |
| `--tpm` | int | Rate limit: tokens per minute (must be paired with `--rpm`) | No |
| `--cg-concurrent-requests` | int | ContentGeneration: max concurrent requests (image-generation endpoints) | No |
| `--cg-create-task-rpm` | int | ContentGeneration: CreateTask RPM (image-generation endpoints) | No |
| `--dry-run` | bool | Emit a local `UpdateEndpoint` Client Preview without calling the API | No |
| `-h`, `--help` | | help for update | No |

## Global Flags

| Flag | Type | Description |
|------|------|-------------|
| `--debug` | | Print request and response debug details to stderr |
| `--format` | string | Output format: json (default "json") |
| `--page-all` | | Automatically fetch all pages when supported |
| `--page-delay` | int | Delay in milliseconds between pages (default 200) |
| `--page-limit` | int | Maximum pages to fetch with --page-all (default 10) |
| `--profile` | string | Active config profile |
| `--transform` | string | Transform output with a GJSON-style path expression |

## Examples

仅改名：

```bash
arkcli infer endpoint update ep-20260101000000-xxxxx --name seed-2-0-pro-demo-123
```

清空描述：

```bash
arkcli infer endpoint update ep-20260101000000-xxxxx --description ""
```

调整限流（必须同时给 `--rpm` 和 `--tpm`）：

```bash
arkcli infer endpoint update ep-20260101000000-xxxxx --rpm 60 --tpm 100000
```

调整图像生成端点的内容生成参数（仅图像生成场景有效）：

```bash
arkcli infer endpoint update ep-20260101000000-xxxxx \
  --cg-concurrent-requests 10 \
  --cg-create-task-rpm 60
```

本地预演（不发请求）：

```bash
arkcli infer endpoint update ep-20260101000000-xxxxx --name foo --dry-run
```
