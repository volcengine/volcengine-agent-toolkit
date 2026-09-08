# Python SDK Integration Reference

## Requirements

Python >= 2.7 for the common SDK. Some runtimes, such as Ark, require Python 3.6+.

## Credential Resolution

Use explicit `configuration.ak/sk`, `configuration.credential_provider`, or the
automatic default chain. When `ak`, `sk`, and `credential_provider` are all
unset, `SignRequestInterceptor` creates a shared `DefaultCredentialProvider`.

Default chain order:

1. `EnvironmentVariableCredentialProvider`
2. `StsOidcCredentialProvider`
3. `CLIConfigCredentialProvider`
4. `EcsRoleCredentialProvider` unless `VOLCENGINE_ECS_METADATA_DISABLED=true`

The chain reuses the last successful provider by default.

### Environment Variables

Python reads these basic credential variables:

- `VOLCENGINE_ACCESS_KEY`
- `VOLCENGINE_SECRET_KEY`
- `VOLCENGINE_SESSION_TOKEN`

It does not use legacy `VOLCSTACK_*` fallbacks for basic credentials.

### AK/SK and STS Token

```python
import os
import volcenginesdkcore

configuration = volcenginesdkcore.Configuration()
configuration.ak = os.environ.get("VOLCENGINE_ACCESS_KEY")
configuration.sk = os.environ.get("VOLCENGINE_SECRET_KEY")
configuration.session_token = os.environ.get("VOLCENGINE_SESSION_TOKEN")
configuration.region = "cn-beijing"
volcenginesdkcore.Configuration.set_default(configuration)
```

### Environment Provider

```python
import volcenginesdkcore
from volcenginesdkcore.auth.providers.env_provider import EnvironmentVariableCredentialProvider

configuration = volcenginesdkcore.Configuration()
configuration.region = "cn-beijing"
configuration.credential_provider = EnvironmentVariableCredentialProvider()
volcenginesdkcore.Configuration.set_default(configuration)
```

### Default Credential Chain

```python
import volcenginesdkcore
from volcenginesdkcore.auth.providers.default_provider import DefaultCredentialProvider

configuration = volcenginesdkcore.Configuration()
configuration.region = "cn-beijing"
configuration.credential_provider = DefaultCredentialProvider()
volcenginesdkcore.Configuration.set_default(configuration)
```

You can omit `credential_provider`; the SDK creates the default chain
automatically when no explicit AK/SK are configured.

### STS AssumeRole

Current Python SDK uses `StsCredentialProvider`. The old
`configuration.assume_role_*` fields are not implemented in
`Configuration`.

```python
import os
import volcenginesdkcore
from volcenginesdkcore.auth.providers.sts_provider import StsCredentialProvider

configuration = volcenginesdkcore.Configuration()
configuration.region = "cn-beijing"
configuration.credential_provider = StsCredentialProvider(
    ak=os.environ.get("VOLCENGINE_ACCESS_KEY"),
    sk=os.environ.get("VOLCENGINE_SECRET_KEY"),
    role_name="RoleName",
    account_id="AccountId",
    duration_seconds=3600,
    scheme="https",
    host="sts.volcengineapi.com",
    region="cn-beijing",
    timeout=30,
    expired_buffer_seconds=60,
    max_retries=3,
    retry_interval=1,
)
volcenginesdkcore.Configuration.set_default(configuration)
```

`max_retries` is total attempts and is coerced to at least 1.
`expired_buffer_seconds` must be <= 600.

### OIDC

`StsOidcCredentialProvider` supports two modes:

- Backward-compatible explicit mode with `role_name + account_id + oidc_token`
- Env-aware mode with `role_trn + oidc_token_file`

Supported OIDC environment variables:

- `VOLCENGINE_OIDC_ROLE_TRN`
- `VOLCENGINE_OIDC_TOKEN_FILE`
- `VOLCENGINE_OIDC_ROLE_SESSION_NAME`
- `VOLCENGINE_OIDC_ROLE_POLICY`
- `VOLCENGINE_OIDC_STS_ENDPOINT`

```python
import volcenginesdkcore
from volcenginesdkcore.auth.providers.sts_oidc_provider import StsOidcCredentialProvider

configuration = volcenginesdkcore.Configuration()
configuration.region = "cn-beijing"
configuration.credential_provider = StsOidcCredentialProvider(
    role_trn="trn:iam::<account-id>:role/oidc-role",
    oidc_token_file="/var/run/secrets/oidc/token",
    duration_seconds=3600,
    host="sts.volcengineapi.com",
    region="cn-beijing",
    max_retries=3,
    retry_interval=1,
)
volcenginesdkcore.Configuration.set_default(configuration)
```

Use `StsOidcCredentialProvider()` with no arguments to read from environment
variables.

### SAML

```python
import volcenginesdkcore
from volcenginesdkcore.auth.providers.sts_saml_provider import StsSamlCredentialProvider

configuration = volcenginesdkcore.Configuration()
configuration.region = "cn-beijing"
configuration.credential_provider = StsSamlCredentialProvider(
    role_trn="trn:iam::<account-id>:role/saml-role",
    saml_provider_trn="trn:iam::<account-id>:saml-provider/MyIdp",
    saml_resp="BASE64_ENCODED_SAML_RESPONSE",
    duration_seconds=3600,
    host="sts.volcengineapi.com",
    region="cn-beijing",
    max_retries=3,
    retry_interval=1,
)
volcenginesdkcore.Configuration.set_default(configuration)
```

`role_trn` has priority over `role_name + account_id`. `saml_provider_trn` has
priority over `account_id + provider_name`.

### CLI Profile Provider

`CLIConfigCredentialProvider` reads `~/.volcengine/config.json` by default.

- Config path priority: constructor `config_path` > `VOLCENGINE_CLI_CONFIG_FILE` > default path
- Profile priority: constructor `profile_name` > `VOLCENGINE_PROFILE` > config `current` > `default`

Supported modes include `AK`, `StsToken`, `RamRoleArn`, `OIDC`, `EcsRole`,
`SSO`, and `console-login`.

For `SSO` and `console-login`, the SDK refreshes tokens in memory and does not
write cache files.

### ECS Role Provider

`EcsRoleCredentialProvider` uses ECS IMDSv2:

- Role name priority: constructor argument > `VOLCENGINE_ECS_METADATA` > IMDS auto-detect
- Disable switch: `VOLCENGINE_ECS_METADATA_DISABLED=true`
- Default connect timeout: 1 second
- Default read timeout: 1 second
- Default retries: 3
- Default expiry buffer: 300 seconds

```python
import volcenginesdkcore
from volcenginesdkcore.auth.providers.ecs_role_provider import EcsRoleCredentialProvider

configuration = volcenginesdkcore.Configuration()
configuration.region = "cn-beijing"
configuration.credential_provider = EcsRoleCredentialProvider(
    role_name="your-ecs-role-name",
    connect_timeout=1,
    read_timeout=1,
    max_retries=3,
    retry_interval=1,
    expired_buffer_seconds=300,
)
volcenginesdkcore.Configuration.set_default(configuration)
```

## Endpoint Configuration

```python
configuration.host = "custom-endpoint.volcengineapi.com"
configuration.region = "cn-shanghai"
configuration.use_dual_stack = True
```

## Connection Pool

```python
configuration.num_pools = 8
configuration.connection_pool_maxsize = 20
```

Use `num_pools`; `connection_pools_count` is not a field on the current
`Configuration`.

## SSL and Proxy

```python
configuration.scheme = "http"
configuration.verify_ssl = False
configuration.ssl_ca_cert = "/path/to/ca-bundle.crt"
configuration.proxy = "http://proxy:8080"
configuration.http_proxy = "http://proxy:8080"
configuration.https_proxy = "https://proxy:8080"
```

## Timeouts

```python
configuration.connect_timeout = 10.0
configuration.read_timeout = 60.0
```

Per-request timeout may be supplied through generated SDK runtime options when
the target service method supports `_runtime_option`.

## Retry

```python
configuration.auto_retry = True
configuration.num_max_retries = 5
configuration.min_retry_delay_ms = 300
configuration.max_retry_delay_ms = 300000
configuration.retry_error_codes = ["Throttling", "ResourceIsBusy"]
```

The retryer uses retries-after-initial-attempt semantics. Provider-level STS
helpers may use total-attempt semantics and adapt internally.

## Debugging

```python
configuration.debug = True
configuration.logger_file = "/path/to/sdk.log"
```
