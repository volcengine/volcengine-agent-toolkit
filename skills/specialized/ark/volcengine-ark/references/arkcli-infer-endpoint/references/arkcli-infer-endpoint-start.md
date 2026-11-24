# arkcli infer endpoint start

Start an infer endpoint endpoint

## Usage

```bash
arkcli infer endpoint start <endpoint-id> [flags]
```

## Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `<endpoint-id>` | The ID of the endpoint to start | Yes |

## Flags

| Flag | Type | Description | Required |
|------|------|-------------|----------|
| `--dry-run` | bool | Emit a local `StartEndpoint` Client Preview without calling the API | No |
| `-h`, `--help` | | help for start | No |

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
