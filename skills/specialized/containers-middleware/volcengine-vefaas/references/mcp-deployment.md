# MCP Deployment

Use this reference when the user wants to deploy an MCP project to Volcengine.

## Deployment path

For MCP projects, prefer:

1. **veFaaS**: default path for MCP HTTP exposure and session-keeping support.
2. **ECS**: fallback when veFaaS does not fit the runtime, dependency installation, or system-control needs.
3. **VKE**: do not recommend by default. Use only when the user explicitly asks for Kubernetes and already has a session-affinity plan.

## Protocol detection

Treat MCP as **STDIO by default** unless the code, docs, or startup command clearly shows an SSE or Streamable-HTTP service.

- **STDIO**: no explicit HTTP listener, `transport="stdio"`, `mcp.run(..., transport="stdio")`, or a command that communicates through stdin/stdout.
- **SSE / Streamable-HTTP**: the code or startup command clearly starts an HTTP service and exposes a path such as `/mcp`, `/sse`, `/api/mcp`, or `/api/sse`.

## `run.sh` checks

- `run.sh` must be in the selected MCP module root.
- The first line must be `#!/bin/bash`.
- Make it executable before deployment:

```bash
chmod +x run.sh
```

## STDIO MCP

STDIO MCP must be wrapped with `mcp-proxy` before deployment to veFaaS. In veFaaS, `mcp-proxy` is a built-in tool that converts STDIO MCP to Streamable-HTTP MCP.

- If a STDIO MCP is not started through `mcp-proxy`, report: `MCP needs to be started through mcp-proxy`.
- `mcp-proxy` must include:

```bash
--host 0.0.0.0 --port 8000
```

- For a STDIO binary, wrap it with `exec`:

```bash
mcp-proxy --host 0.0.0.0 --port 8000 -- exec ./server
```

`8000` is the `mcp-proxy` wrapper port. It is not a global veFaaS port rule.

## SSE / Streamable-HTTP MCP

If the MCP already serves SSE or Streamable-HTTP, do not add `mcp-proxy`.

Check that:

- The service listens on `0.0.0.0`.
- The listening port matches the veFaaS deployment configuration.
- The endpoint path is clear from code or startup arguments.

Do not force port `8000` unless the startup command or veFaaS config explicitly uses `8000`. If host, port, or endpoint path cannot be confirmed, ask for confirmation instead of failing the deployment.

## Python MCP

If `run.sh` starts MCP with `python3`:

- `requirements.txt` must exist in the MCP module root.
- The first line of `requirements.txt` must be `.` so the module itself is installed.

## Node.js MCP

- Add `-y` when using `npx` to avoid interactive prompts.
- For Node.js STDIO MCP, first try wrapping it with `mcp-proxy`; if that cannot work, suggest changing the MCP to SSE or Streamable-HTTP.

## Unsupported or manual-confirmation paths

- Do not use `uv` and `uvx`; veFaaS not support this MCP run Mode.
- Kotlin, Java, Swift, C#, Ruby, and PHP MCP projects are not default deployment paths.

## Output

After deployment, print the MCP service URL.

- With `mcp-proxy`, treat the protocol as Streamable-HTTP and use:

```text
{AccessUrl}/mcp
```

- Without `mcp-proxy`, print the actual endpoint path from code or startup arguments.

Client example:

```json
{
  "mcpServers": {
    "<function-name>": {
      "url": "<AccessUrl>/mcp"
    }
  }
}
```
