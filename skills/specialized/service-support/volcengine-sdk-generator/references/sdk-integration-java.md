# Java SDK Integration Reference

## Requirements

Java 1.8.0_131+. For Java 9+, add `javax.annotation-api` if your build complains about
missing annotation classes.

## Credential Resolution

Use either explicit `Credentials`, a `CredentialProvider`, or the automatic
default chain. When neither `ApiClient.setCredentials(...)` nor
`ApiClient.setCredentialProvider(...)` is configured, the signing interceptor
creates a default chain automatically.

Default chain order:

1. `EnvironmentVariableCredentialProvider`
2. `OidcCredentialProvider.fromEnvironment()`
3. `CLIConfigCredentialProvider`
4. `EcsRoleCredentialProvider` unless `VOLCENGINE_ECS_METADATA_DISABLED=true`

The default chain reuses the last successful provider by default.

### Environment Variables

Java reads only `VOLCENGINE_*` credential variables:

- `VOLCENGINE_ACCESS_KEY`
- `VOLCENGINE_SECRET_KEY`
- `VOLCENGINE_SESSION_TOKEN`

It does not use the legacy `VOLCSTACK_*` fallbacks for basic credentials.

### AK/SK and STS Token

```java
import com.volcengine.ApiClient;
import com.volcengine.sign.Credentials;

public class SampleCode {
    public static void main(String[] args) {
        ApiClient apiClient = new ApiClient()
                .setCredentials(Credentials.getCredentials(
                        System.getenv("VOLCENGINE_ACCESS_KEY"),
                        System.getenv("VOLCENGINE_SECRET_KEY"),
                        System.getenv("VOLCENGINE_SESSION_TOKEN")))
                .setRegion("cn-beijing");
    }
}
```

### Environment Provider

```java
import com.volcengine.ApiClient;
import com.volcengine.auth.CredentialProvider;
import com.volcengine.auth.EnvironmentVariableCredentialProvider;

public class SampleCode {
    public static void main(String[] args) {
        ApiClient apiClient = new ApiClient()
                .setCredentialProvider(new CredentialProvider(
                        new EnvironmentVariableCredentialProvider()))
                .setRegion("cn-beijing");
    }
}
```

### Default Credential Chain

```java
import com.volcengine.ApiClient;

public class SampleCode {
    public static void main(String[] args) {
        ApiClient apiClient = new ApiClient().setRegion("cn-beijing");
    }
}
```

To customize the ECS role name used by the default chain:

```java
import com.volcengine.ApiClient;
import com.volcengine.auth.CredentialProvider;
import com.volcengine.auth.DefaultCredentialProvider;

public class SampleCode {
    public static void main(String[] args) {
        DefaultCredentialProvider provider = DefaultCredentialProvider.builder()
                .roleName("your-ecs-role-name")
                .reuseLastProviderEnabled(true)
                .build();
        ApiClient apiClient = new ApiClient()
                .setCredentialProvider(new CredentialProvider(provider))
                .setRegion("cn-beijing");
    }
}
```

### STS AssumeRole

Current Java SDK uses `StsAssumeRoleProvider`. The older
`Credentials.getAssumeRoleCredentials(...)` helper is not present in this SDK.

```java
import com.volcengine.ApiClient;
import com.volcengine.auth.CredentialProvider;
import com.volcengine.auth.StsAssumeRoleProvider;

public class SampleCode {
    public static void main(String[] args) {
        StsAssumeRoleProvider provider = new StsAssumeRoleProvider(
                System.getenv("VOLCENGINE_ACCESS_KEY"),
                System.getenv("VOLCENGINE_SECRET_KEY"),
                "RoleName",
                "AccountId");
        provider.setHost("sts.volcengineapi.com");
        provider.setRegion("cn-beijing");
        provider.setSchema("https");
        provider.setDurationSeconds(3600);
        provider.setTimeout(30);
        provider.setExpireBufferSeconds(60);

        ApiClient apiClient = new ApiClient()
                .setCredentialProvider(new CredentialProvider(provider))
                .setRegion("cn-beijing");
    }
}
```

If the source AK/SK are temporary, use the constructor that also accepts
`sessionToken`.

### OIDC

Required environment variables for env mode:

- `VOLCENGINE_OIDC_ROLE_TRN`
- `VOLCENGINE_OIDC_TOKEN_FILE`

Optional:

- `VOLCENGINE_OIDC_ROLE_SESSION_NAME`
- `VOLCENGINE_OIDC_ROLE_POLICY`
- `VOLCENGINE_OIDC_STS_ENDPOINT`

```java
import com.volcengine.ApiClient;
import com.volcengine.auth.CredentialProvider;
import com.volcengine.auth.OidcCredentialProvider;

public class SampleCode {
    public static void main(String[] args) {
        OidcCredentialProvider provider = new OidcCredentialProvider(
                "trn:iam::<account-id>:role/oidc-role",
                null,
                "/var/run/secrets/oidc/token",
                null,
                "sts.volcengineapi.com");
        provider.setDurationSeconds(3600);
        provider.setExpireBufferSeconds(300);
        provider.setSchema("https");
        provider.setMaxRetries(3);
        provider.setRetryIntervalMs(1000);

        ApiClient apiClient = new ApiClient()
                .setCredentialProvider(new CredentialProvider(provider))
                .setRegion("cn-beijing");
    }
}
```

### SAML

```java
import com.volcengine.ApiClient;
import com.volcengine.auth.CredentialProvider;
import com.volcengine.auth.SamlCredentialProvider;

public class SampleCode {
    public static void main(String[] args) {
        SamlCredentialProvider provider = new SamlCredentialProvider(
                "trn:iam::<account-id>:role/saml-role",
                "trn:iam::<account-id>:saml-provider/MyIdp",
                "BASE64_ENCODED_SAML_RESPONSE",
                null,
                "sts.volcengineapi.com");
        provider.setDurationSeconds(3600);
        provider.setExpireBufferSeconds(300);
        provider.setSchema("https");
        provider.setMaxRetries(3);
        provider.setRetryIntervalMs(1000);

        ApiClient apiClient = new ApiClient()
                .setCredentialProvider(new CredentialProvider(provider))
                .setRegion("cn-beijing");
    }
}
```

### CLI Profile Provider

`CLIConfigCredentialProvider` reads `$HOME/.volcengine/config.json` by default.

- Config path priority: constructor `configPath` > `VOLCENGINE_CLI_CONFIG_FILE` > default path
- Profile priority: constructor `profileName` > `VOLCENGINE_PROFILE` > config `current` > `default`

Supported modes include `AK`, `StsToken`, `RamRoleArn`, `OIDC`, `EcsRole`,
`SSO`, and `console-login`. Mode matching is case-insensitive.

### ECS Role Provider

`EcsRoleCredentialProvider` uses ECS IMDSv2 and supports role auto-detection:

- Role name priority: constructor argument > `VOLCENGINE_ECS_METADATA` > IMDS auto-detect
- Disable switch: `VOLCENGINE_ECS_METADATA_DISABLED=true`
- Default connect timeout: 1000 ms
- Default read timeout: 1000 ms
- Default retries: 3
- Default expiry buffer: 300 seconds

```java
import com.volcengine.ApiClient;
import com.volcengine.auth.CredentialProvider;
import com.volcengine.auth.EcsRoleCredentialProvider;

public class SampleCode {
    public static void main(String[] args) {
        EcsRoleCredentialProvider provider =
                EcsRoleCredentialProvider.create("your-ecs-role-name");
        provider.setMaxRetries(3);
        provider.setRetryIntervalMs(1000);
        provider.setExpireBufferSeconds(300);

        ApiClient apiClient = new ApiClient()
                .setCredentialProvider(new CredentialProvider(provider))
                .setRegion("cn-beijing");
    }
}
```

## Endpoint Configuration

```java
apiClient.setEndpoint("custom-endpoint.volcengineapi.com");
apiClient.setRegion("cn-shanghai");
apiClient.setUseDualStack(true);
```

## HTTP Connection Pool

```java
apiClient.setMaxIdleConns(10);
apiClient.setKeepAliveDurationMs(300000);
```

## SSL, Proxy, Timeouts

```java
apiClient.setVerifyingSsl(false);
apiClient.setDisableSSL(true);
apiClient.setHttpProxy("http://proxy:8080");
apiClient.setHttpsProxy("https://proxy:8080");
apiClient.setConnectionTimeout(5000);
apiClient.setReadTimeout(30000);
apiClient.setWriteTimeout(30000);
```

## Retry

```java
apiClient.setRetrySettings(new RetrySettings()
        .setMaxAttempts(5)
        .setMinDelay(300)
        .setMaxDelay(300000));
```

## Debugging

```java
apiClient.setDebugging(true);
```
