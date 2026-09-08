# Go SDK Integration Reference

## Requirements

Go 1.14+ (1.18+ for Ark service) for the common SDK. Some service packages may require newer Go
versions. Use Go modules.

## Credential Resolution

Prefer the default credential chain or explicit provider objects. Do not hardcode
AK/SK in production examples.

Default chain order when a session is created without explicit credentials:

1. `EnvProvider`
2. `OIDCCredentialsProvider` from `VOLCENGINE_OIDC_*`
3. CLI profile provider from `~/.volcengine/config.json`
4. `EcsRoleProvider` from ECS IMDSv2

The chain reuses the last successful provider by default and falls back to the
full chain if that provider later fails.

### Environment Variables

`EnvProvider` reads these variables in order:

- AK: `VOLCENGINE_ACCESS_KEY` > `VOLCSTACK_ACCESS_KEY_ID` > `VOLCSTACK_ACCESS_KEY`
- SK: `VOLCENGINE_SECRET_KEY` > `VOLCSTACK_SECRET_ACCESS_KEY` > `VOLCSTACK_SECRET_KEY`
- Token: `VOLCENGINE_SESSION_TOKEN` > `VOLCSTACK_SESSION_TOKEN`

Use `VOLCENGINE_*` for new code.

### AK/SK and STS Token

```go
package main

import (
	"os"

	"github.com/volcengine/volcengine-go-sdk/volcengine"
	"github.com/volcengine/volcengine-go-sdk/volcengine/credentials"
	"github.com/volcengine/volcengine-go-sdk/volcengine/session"
)

func main() {
	config := volcengine.NewConfig().
		WithRegion("cn-beijing").
		WithCredentials(credentials.NewStaticCredentials(
			os.Getenv("VOLCENGINE_ACCESS_KEY"),
			os.Getenv("VOLCENGINE_SECRET_KEY"),
			os.Getenv("VOLCENGINE_SESSION_TOKEN"),
		))

	_, err := session.NewSession(config)
	if err != nil {
		panic(err)
	}
}
```

For environment-only resolution:

```go
config := volcengine.NewConfig().
	WithRegion("cn-beijing").
	WithCredentials(credentials.NewEnvCredentials())
```

### Default Credential Chain

```go
package main

import (
	"github.com/volcengine/volcengine-go-sdk/service/ecs"
	"github.com/volcengine/volcengine-go-sdk/volcengine/session"
)

func main() {
	sess, err := session.NewSession()
	if err != nil {
		panic(err)
	}
	_ = ecs.New(sess)
}
```

To customize the ECS role name used by the default chain:

```go
package main

import (
	"github.com/volcengine/volcengine-go-sdk/volcengine"
	"github.com/volcengine/volcengine-go-sdk/volcengine/credentials"
	"github.com/volcengine/volcengine-go-sdk/volcengine/defaults"
	"github.com/volcengine/volcengine-go-sdk/volcengine/session"
)

func main() {
	creds := defaults.NewDefaultCredentialProvider(func(o *credentials.DefaultCredentialProviderOptions) {
		o.RoleName = "your-ecs-role-name"
	})
	_, err := session.NewSession(volcengine.NewConfig().
		WithRegion("cn-beijing").
		WithCredentials(creds))
	if err != nil {
		panic(err)
	}
}
```

### STS AssumeRole

Current Go SDK uses `credentials.NewStsCredentialsWithOptions` or
`credentials.NewStsCredentials`. The older `NewAssumeRoleCredentials` helper is
not present in this SDK.

```go
package main

import (
	"os"
	"time"

	"github.com/volcengine/volcengine-go-sdk/volcengine"
	"github.com/volcengine/volcengine-go-sdk/volcengine/credentials"
	"github.com/volcengine/volcengine-go-sdk/volcengine/session"
)

func main() {
	config := volcengine.NewConfig().
		WithRegion("cn-beijing").
		WithCredentials(credentials.NewStsCredentialsWithOptions(
			os.Getenv("VOLCENGINE_ACCESS_KEY"),
			os.Getenv("VOLCENGINE_SECRET_KEY"),
			"RoleName",
			"AccountId",
			func(o *credentials.StsAssumeRoleOptions) {
				o.Host = "sts.volcengineapi.com"
				o.Region = "cn-beijing"
				o.Schema = "https"
				o.DurationSeconds = 3600
				o.Timeout = 30 * time.Second
				o.MaxRetries = 3
				o.RetryInterval = time.Second
			},
		))

	_, err := session.NewSession(config)
	if err != nil {
		panic(err)
	}
}
```

`DurationSeconds` must be at least 900. The provider refreshes before expiry.
If the source credentials are temporary, set `o.SessionToken`.

### OIDC

The default chain can read OIDC settings from environment variables:

- `VOLCENGINE_OIDC_ROLE_TRN`
- `VOLCENGINE_OIDC_TOKEN_FILE`
- `VOLCENGINE_OIDC_ROLE_SESSION_NAME`
- `VOLCENGINE_OIDC_ROLE_POLICY`
- `VOLCENGINE_OIDC_STS_ENDPOINT`

```go
provider := credentials.NewOIDCCredentialsProviderWithOptions(
	"/path/to/oidc-token",
	"trn:iam::<account-id>:role/oidc-role",
	func(o *credentials.OIDCProviderOptions) {
		o.DurationSeconds = 3600
		o.Endpoint = "sts.volcengineapi.com"
		o.MaxRetries = volcengine.Int(3)
		o.RetryInterval = time.Second
	},
)
config := volcengine.NewConfig().
	WithRegion("cn-beijing").
	WithCredentials(credentials.NewCredentials(provider))
```

### SAML

```go
provider := credentials.NewSAMLCredentialsProviderWithOptions(
	"trn:iam::<account-id>:role/saml-role",
	"trn:iam::<account-id>:saml-provider/MyIdp",
	"BASE64_ENCODED_SAML_RESPONSE",
	func(o *credentials.SAMLProviderOptions) {
		o.DurationSeconds = 3600
		o.MaxRetries = volcengine.Int(3)
		o.RetryInterval = time.Second
	},
)
config := volcengine.NewConfig().
	WithRegion("cn-beijing").
	WithCredentials(credentials.NewCredentials(provider))
```

### CLI Profile Provider

The CLI provider reads `~/.volcengine/config.json` unless overridden.

- Config path priority: constructor argument > `VOLCENGINE_CLI_CONFIG_FILE` > default path
- Profile priority: constructor argument > `VOLCENGINE_PROFILE` > `VOLCSTACK_PROFILE` > config `current` > `default`

Supported modes include `AK`, `StsToken`, `RamRoleArn`, `OIDC`, `EcsRole`,
`SSO`, and `console-login`.

### ECS Role Provider

`EcsRoleProvider` uses ECS IMDSv2:

1. PUT `/latest/api/token`
2. Resolve role name: constructor argument > `VOLCENGINE_ECS_METADATA` > IMDS auto-detect
3. GET `/volcstack/latest/iam/security_credentials/{roleName}`

Set `VOLCENGINE_ECS_METADATA_DISABLED=true` to disable IMDS credentials.

```go
config := volcengine.NewConfig().
	WithRegion("cn-beijing").
	WithCredentials(credentials.NewEcsRoleCredentials("your-ecs-role-name"))
```

## Endpoint Configuration

```go
config := volcengine.NewConfig().
	WithRegion("cn-shanghai").
	WithEndpoint("custom-endpoint.volcengineapi.com").
	WithUseDualStack(true)
```

## HTTP Transport, Proxy, SSL

```go
httpClient := &http.Client{
	Timeout: 60 * time.Second,
	Transport: &http.Transport{
		Proxy:           http.ProxyFromEnvironment,
		MaxIdleConns:    200,
		IdleConnTimeout: 120 * time.Second,
		TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS12},
	},
}

config := volcengine.NewConfig().
	WithHTTPClient(httpClient).
	WithHTTPProxy("http://proxy:8080").
	WithHTTPSProxy("https://proxy:8080")
```

`WithDisableSSL(true)` switches to HTTP. Do not disable TLS unless the target
endpoint requires it.

## Timeouts

```go
ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
resp, err := svc.DescribeInstancesWithContext(ctx, input)
```

## Retry

```go
config := volcengine.NewConfig().WithMaxRetries(5)
input.SetRetryableErrorCodes([]string{"Throttling", "ResourceIsBusy"})
```

## Debugging

```go
config := volcengine.NewConfig().
	WithDebug(true).
	WithLogWriter(os.Stderr)
```
