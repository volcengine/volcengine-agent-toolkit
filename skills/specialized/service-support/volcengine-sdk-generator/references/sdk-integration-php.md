# PHP SDK Integration Reference

## Requirements

PHP >= 5.5. Install dependencies with Composer.

## Credential Resolution

Use explicit `Configuration` AK/SK, `setCredentialProvider(...)`, or the
automatic default chain. When AK and SK are both empty, `ApiClient` creates and
caches a `DefaultCredentialProvider` on the configuration.

Default chain order:

1. `EnvironmentVariableCredentialProvider`
2. `OidcCredentialProvider::fromEnvironment()`
3. `CLIConfigCredentialProvider`
4. `EcsRoleCredentialProvider`

The default chain reuses the last successful provider by default.

### Environment Variables

`EnvironmentVariableCredentialProvider` reads:

- AK: `VOLCENGINE_ACCESS_KEY` > `VOLCSTACK_ACCESS_KEY_ID` > `VOLCSTACK_ACCESS_KEY`
- SK: `VOLCENGINE_SECRET_KEY` > `VOLCSTACK_SECRET_ACCESS_KEY` > `VOLCSTACK_SECRET_KEY`
- Token: `VOLCENGINE_SESSION_TOKEN` > `VOLCSTACK_SESSION_TOKEN`

Use `VOLCENGINE_*` for new code.

### AK/SK and STS Token

```php
<?php
require_once __DIR__ . '/vendor/autoload.php';

$config = \Volcengine\Common\Configuration::getDefaultConfiguration()
    ->setAk(getenv('VOLCENGINE_ACCESS_KEY'))
    ->setSk(getenv('VOLCENGINE_SECRET_KEY'))
    ->setSessionToken(getenv('VOLCENGINE_SESSION_TOKEN') ?: '')
    ->setRegion('cn-beijing');
```

### Environment Provider

```php
<?php
require_once __DIR__ . '/vendor/autoload.php';

$config = \Volcengine\Common\Configuration::getDefaultConfiguration()
    ->setRegion('cn-beijing')
    ->setCredentialProvider(
        new \Volcengine\Common\Auth\Providers\EnvironmentVariableCredentialProvider()
    );
```

### Default Credential Chain

```php
<?php
require_once __DIR__ . '/vendor/autoload.php';

$config = \Volcengine\Common\Configuration::getDefaultConfiguration()
    ->setRegion('cn-beijing');
```

With empty AK/SK, the next generated service API call uses
`DefaultCredentialProvider` automatically.

### STS AssumeRole

Current PHP SDK uses `StsProvider`. The old `setAssumeRoleTrn`,
`setAssumeRoleSessionName`, and `setAssumeRoleDurationSeconds` configuration
methods are not present in the current common `Configuration`.

```php
<?php
require_once __DIR__ . '/vendor/autoload.php';

$provider = new \Volcengine\Common\Auth\Providers\StsProvider(
    getenv('VOLCENGINE_ACCESS_KEY'),
    getenv('VOLCENGINE_SECRET_KEY'),
    'RoleName',
    'AccountId',
    'cn-beijing',
    3600,
    'https',
    'sts.volcengineapi.com',
    null
);

$config = \Volcengine\Common\Configuration::getDefaultConfiguration()
    ->setRegion('cn-beijing')
    ->setCredentialProvider($provider);
```

When `Configuration` has no explicit AK/SK, `ApiClient` calls the provider's
`getCredentials()` and reads `AccessKeyId`, `SecretAccessKey`, and
`SessionToken`. `StsProvider::getCredentials()` calls STS `AssumeRole` on each
invocation and does not maintain a local credential cache, unlike the OIDC and
SAML providers.

### OIDC

Supported OIDC environment variables:

- `VOLCENGINE_OIDC_ROLE_TRN`
- `VOLCENGINE_OIDC_TOKEN_FILE`
- `VOLCENGINE_OIDC_ROLE_SESSION_NAME`
- `VOLCENGINE_OIDC_ROLE_POLICY`
- `VOLCENGINE_OIDC_STS_ENDPOINT`

```php
<?php
require_once __DIR__ . '/vendor/autoload.php';

$provider = new \Volcengine\Common\Auth\Providers\OidcCredentialProvider(
    'trn:iam::<account-id>:role/oidc-role',
    '/var/run/secrets/oidc/token',
    'credentials-php-demo',
    null,
    'sts.volcengineapi.com'
);
$provider->setSchema('https')
    ->setMaxRetries(3)
    ->setRetryInterval(1);

$config = \Volcengine\Common\Configuration::getDefaultConfiguration()
    ->setRegion('cn-beijing')
    ->setCredentialProvider($provider);
```

Use `OidcCredentialProvider::fromEnvironment()` to read from environment
variables.

### SAML

```php
<?php
require_once __DIR__ . '/vendor/autoload.php';

$provider = new \Volcengine\Common\Auth\Providers\SamlCredentialProvider(
    'RoleName',
    '<account-id>',
    'MyIdp',
    'BASE64_ENCODED_SAML_RESPONSE',
    null,
    'sts.volcengineapi.com'
);
$provider->setSchema('https')
    ->setMaxRetries(3)
    ->setRetryInterval(1);

$config = \Volcengine\Common\Configuration::getDefaultConfiguration()
    ->setRegion('cn-beijing')
    ->setCredentialProvider($provider);
```

OIDC and SAML providers cache credentials and refresh before expiry. Their
expiry is estimated from local `durationSeconds`.

### CLI Profile Provider

`CLIConfigCredentialProvider` reads `~/.volcengine/config.json` by default.

- Config path priority: constructor `configPath` > `VOLCENGINE_CLI_CONFIG_FILE` > default path
- Profile priority: constructor `profileName` > `VOLCENGINE_PROFILE` / `VOLCSTACK_PROFILE` > config `current` > `default`

Supported modes include `ak`, `StsToken`, `ramrolearn`, `oidc`, `ecsrole`,
`sso`, and `console-login`.

For `sso` and `console-login`, PHP refreshes token cache files with an atomic
rename so short-lived PHP processes can share refreshed tokens.

### ECS Role Provider

`EcsRoleCredentialProvider` uses ECS IMDSv2 and supports role auto-detection:

- Role name priority: constructor argument > `VOLCENGINE_ECS_METADATA` > IMDS auto-detect
- Disable switch: `VOLCENGINE_ECS_METADATA_DISABLED=true`
- Default connect timeout: 1 second
- Default read timeout: 1 second
- Default retries: 3
- Default expiry buffer: 300 seconds

```php
<?php
require_once __DIR__ . '/vendor/autoload.php';

$provider = \Volcengine\Common\Auth\Providers\EcsRoleCredentialProvider::create(
    'your-ecs-role-name'
);
$provider->setMaxRetries(3)
    ->setRetryInterval(1)
    ->setConnectTimeout(1)
    ->setReadTimeout(1)
    ->setExpireBufferSeconds(300);

$config = \Volcengine\Common\Configuration::getDefaultConfiguration()
    ->setRegion('cn-beijing')
    ->setCredentialProvider($provider);
```

The previous documentation note claiming ECS role auto-detection is unsupported
is outdated for this source tree.

## Endpoint Configuration

```php
$config->setHost('custom-endpoint.volcengineapi.com');
$config->setRegion('cn-shanghai');
$config->setUseDualStack(true);
```

## SSL, Proxy, and HTTP Client

```php
$config->setSchema('http');
$config->setVerifySsl(false);

$apiInstance = new \Volcengine\Ecs\Api\ECSApi(
    new \GuzzleHttp\Client([
        'proxy' => 'http://proxy:8080',
        'timeout' => 30,
        'connect_timeout' => 5,
        'curl' => [CURLOPT_SSLVERSION => CURL_SSLVERSION_TLSv1_2],
    ]),
    $config
);
```

## Debugging

```php
$config->setDebug(true);
$config->setDebugFile('/path/to/sdk.log');
```
