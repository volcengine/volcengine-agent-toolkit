# Node.js SDK Integration Reference

## Requirements

Node.js >= 18. Install `@volcengine/sdk-core` and the target service package.

```bash
pnpm add @volcengine/sdk-core
pnpm add @volcengine/ecs  # service-specific package
```

## Credential Resolution

Use explicit client credentials, `credentialProvider`, `assumeRoleParams`, or the
automatic default chain. If a client has no inline AK/SK and no
`credentialProvider`, the credentials middleware creates a
`DefaultCredentialProvider`.

Resolution order inside the middleware:

1. Inline `accessKeyId` + `secretAccessKey`
2. Legacy `assumeRoleParams`, converted to `StsAssumeRoleProvider`
3. Explicit `credentialProvider`
4. `DefaultCredentialProvider`

Default chain order:

1. `EnvironmentVariableCredentialProvider`
2. `OidcCredentialProvider`
3. `CLIConfigCredentialProvider`
4. `EcsRoleCredentialProvider` unless `VOLCENGINE_ECS_METADATA_DISABLED=true`

### Environment Variables

`EnvironmentVariableCredentialProvider` reads:

- AK: `VOLCENGINE_ACCESS_KEY` > `VOLCSTACK_ACCESS_KEY_ID` > `VOLCSTACK_ACCESS_KEY`
- SK: `VOLCENGINE_SECRET_KEY` > `VOLCSTACK_SECRET_ACCESS_KEY` > `VOLCSTACK_SECRET_KEY`
- Token: `VOLCENGINE_SESSION_TOKEN` > `VOLCSTACK_SESSION_TOKEN`

Use `VOLCENGINE_*` for new code.

### AK/SK and STS Token

```typescript
import { EcsClient } from "@volcengine/ecs";

const client = new EcsClient({
  region: "cn-beijing",
  accessKeyId: process.env.VOLCENGINE_ACCESS_KEY,
  secretAccessKey: process.env.VOLCENGINE_SECRET_KEY,
  sessionToken: process.env.VOLCENGINE_SESSION_TOKEN,
});
```

Environment-only usage:

```typescript
import { EcsClient } from "@volcengine/ecs";

const client = new EcsClient({ region: "cn-beijing" });
```

### Default Credential Chain

```typescript
import { DefaultCredentialProvider } from "@volcengine/sdk-core";
import { EcsClient } from "@volcengine/ecs";

const client = new EcsClient({
  region: "cn-beijing",
  credentialProvider: new DefaultCredentialProvider({
    roleName: "your-ecs-role-name",
    reuseLastProviderEnabled: true,
  }),
});
```

### STS AssumeRole

Use `StsAssumeRoleProvider`. It caches credentials by source AK/SK and role TRN,
merges concurrent refreshes, and refreshes before expiry.

```typescript
import { StsAssumeRoleProvider } from "@volcengine/sdk-core";
import { EcsClient } from "@volcengine/ecs";

const credentialProvider = new StsAssumeRoleProvider({
  accessKeyId: process.env.VOLCENGINE_ACCESS_KEY!,
  secretAccessKey: process.env.VOLCENGINE_SECRET_KEY!,
  roleTrn: "trn:iam::<account-id>:role/role123",
  roleSessionName: "sdk-node-demo",
  region: "cn-beijing",
  host: "sts.volcengineapi.com",
  protocol: "https",
  durationSeconds: 3600,
  policy: undefined,
});

const client = new EcsClient({
  region: "cn-beijing",
  credentialProvider,
});
```

Legacy `assumeRoleParams` is still accepted by the middleware and translated to
`StsAssumeRoleProvider`.

### OIDC

Supported OIDC environment variables:

- `VOLCENGINE_OIDC_ROLE_TRN`
- `VOLCENGINE_OIDC_TOKEN_FILE`
- `VOLCENGINE_OIDC_ROLE_SESSION_NAME`
- `VOLCENGINE_OIDC_ROLE_POLICY`
- `VOLCENGINE_OIDC_STS_ENDPOINT`

```typescript
import { OidcCredentialProvider } from "@volcengine/sdk-core";
import { EcsClient } from "@volcengine/ecs";

const credentialProvider = new OidcCredentialProvider({
  roleTrn: "trn:iam::<account-id>:role/oidc-role",
  oidcTokenFile: "/path/to/oidc/token",
  roleSessionName: "sdk-node-oidc",
  host: "sts.volcengineapi.com",
});

const client = new EcsClient({
  region: "cn-beijing",
  credentialProvider,
});
```

Use `new OidcCredentialProvider()` to read from environment variables.

### SAML

Supported SAML environment variables:

- `VOLCENGINE_SAML_ROLE_TRN`
- `VOLCENGINE_SAML_ACCOUNT_ID`
- `VOLCENGINE_SAML_PROVIDER_TRN`
- `VOLCENGINE_SAML_ASSERTION`
- `VOLCENGINE_SAML_ENDPOINT`
- `VOLCENGINE_SAML_POLICY`

```typescript
import { SamlCredentialProvider } from "@volcengine/sdk-core";
import { EcsClient } from "@volcengine/ecs";

const credentialProvider = new SamlCredentialProvider({
  roleTrn: "trn:iam::<account-id>:role/saml-role",
  accountId: "<account-id>",
  samlProviderTrn: "trn:iam::<account-id>:saml-provider/my-provider",
  samlAssertion: "BASE64_ENCODED_SAML_ASSERTION",
  host: "sts.volcengineapi.com",
});

const client = new EcsClient({
  region: "cn-beijing",
  credentialProvider,
});
```

Use `new SamlCredentialProvider()` to read from environment variables.

### CLI Profile Provider

`CLIConfigCredentialProvider` reads `~/.volcengine/config.json` by default.

- Config path priority: `VOLCENGINE_CLI_CONFIG_FILE` > default path
- Supported modes include AK/static credentials, STS token, role, OIDC, ECS role, SSO, and console-login according to the current CLI provider implementation.

### ECS Role Provider

`EcsRoleCredentialProvider` uses ECS IMDSv2:

- Role name priority: constructor argument > `VOLCENGINE_ECS_METADATA`
- Disable switch: `VOLCENGINE_ECS_METADATA_DISABLED=true`
- Default connect timeout: 1 second
- Default read timeout: 1 second
- Default retries: 3
- Default expiry buffer: 300 seconds

The current source contains an `autoDetectRoleName` helper, but
`resolveRoleName` still throws when neither constructor `roleName` nor
`VOLCENGINE_ECS_METADATA` is set. Pass the role name explicitly for now.

```typescript
import { EcsRoleCredentialProvider } from "@volcengine/sdk-core";
import { EcsClient } from "@volcengine/ecs";

const credentialProvider = new EcsRoleCredentialProvider({
  roleName: "your-ecs-role-name",
  connectTimeout: 1,
  readTimeout: 1,
  maxRetries: 3,
  retryInterval: 1,
  expiredBufferSeconds: 300,
});

const client = new EcsClient({
  region: "cn-beijing",
  credentialProvider,
});
```

## Endpoint Configuration

```typescript
const client = new EcsClient({
  region: "cn-shanghai",
  host: "custom-endpoint.volcengineapi.com",
  useDualStack: true,
});
```

## Network Configuration

```typescript
const client = new EcsClient({
  region: "cn-beijing",
  protocol: "https",
  httpOptions: {
    timeout: 5000,
    ignoreSSL: false,
    proxy: { protocol: "http", host: "127.0.0.1", port: 8888 },
    pool: {
      keepAlive: true,
      keepAliveMsecs: 1000,
      maxSockets: 50,
      maxFreeSockets: 10,
    },
  },
});
```

Proxy can also be configured with `VOLC_PROXY_PROTOCOL`, `VOLC_PROXY_HOST`, and
`VOLC_PROXY_PORT`. Constructor options take priority.

## Timeouts

```typescript
const client = new EcsClient({
  region: "cn-beijing",
  httpOptions: { timeout: 5000 },
});

await client.send(command, { timeout: 30000 });
```

## Retry

```typescript
import { StrategyName } from "@volcengine/sdk-core";

const client = new EcsClient({
  region: "cn-beijing",
  maxRetries: 5,
  strategyName: StrategyName.ExponentialWithRandomJitterBackoffStrategy,
});
```

Set `autoRetry: false` to disable retry.

## Error Handling

```typescript
import { HttpRequestError } from "@volcengine/sdk-core";

try {
  await client.send(command);
} catch (error) {
  if (error instanceof HttpRequestError) {
    const requestId = error.data?.ResponseMetadata?.RequestId;
    const apiError = error.data?.ResponseMetadata?.Error;
    console.error(error.status, requestId, apiError?.Code, apiError?.Message);
  }
}
```

## Resource Cleanup

```typescript
client.destroy();
```

## Debugging

```typescript
client.middlewareStack.add(
  (next) => async (args) => {
    console.log("Request:", args.request.method, args.request.host);
    const result = await next(args);
    console.log("Response:", result.response?.status);
    return result;
  },
  { step: "finalizeRequest", name: "LogMiddleware", priority: 10 },
);
```
