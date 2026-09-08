---
name: volcengine-sdk-generator
description: >
  Generate accurate Volcengine SDK examples by locating an API through API Explorer search,
  fetching its swagger, and calling api/common/explorer/make-code with user-provided
  Params. Use when the user asks how to write Volcengine SDK code, generate SDK samples, or call a
  Volcengine API in Python, Go, Java, PHP, cURL, Node.js. Supports Chinese and
  English API names such as "角色扮演", "AssumeRole", or "STS AssumeRole". Also use for explicit SDK
  configuration questions about retry, timeout, AK/SK, STS, AssumeRole, temporary credentials,
  proxy, connection pooling, SSL, debug mode, request signing, response parsing, and error handling.
  If the user only needs API parameters, enum values, required fields, error codes, response
  schemas, pagination, or API comparisons, hand off to volcengine-api. If they need CLI-based
  operations, hand off to volcengine-cli.
license: MIT
---

# Volcengine SDK Generator

Generate ordinary Volcengine API call examples by default. Keep the default output focused on the
API call itself: authentication setup, request object/params, invocation, and printing the response.
Do not add retry, proxy, connection pool, debug logging, or other advanced SDK configuration unless
the user explicitly asks for those topics.

For advanced SDK configuration questions, use the language-specific files under `references/`.
These reference files are self-contained; answer from them directly.

| Topic | Reference |
| --- | --- |
| Go SDK configuration | `references/sdk-integration-go.md` |
| Python SDK configuration | `references/sdk-integration-python.md` |
| Java SDK configuration | `references/sdk-integration-java.md` |
| Node.js SDK configuration | `references/sdk-integration-nodejs.md` |
| PHP SDK configuration | `references/sdk-integration-php.md` |

## Core Rules

- API discovery uses `scripts/rg_rank.py`, which calls API Explorer search with both `Channel=service` and `Channel=api`. After a concrete API is selected, call `scripts/make_code.py` in direct mode with `--service-code`, `--api-version`, and `--action`.
- API discovery is online-only. The search endpoint does not require cookies, login state, UID, DID, UUID, or browser-specific headers. The script sends only `Query`, `Channel`, `Limit`, and `Offset` as query parameters.
- `rg_rank.py` preserves `Channel=api` order except for version selection: when the same `service_code + action` has multiple versions and the user did not specify one, it moves the result with `IsRecommended=1` ahead of the other versions in that group. It also includes `Channel=service` results as separate service metadata.
- If online search fails, report the returned search errors. Do not guess an API or fall back to a bundled catalog.
- Use the user's original request as `--query`; do not rewrite it into a guessed API name or SDK method.
- Extract a shorter `--query` only when the user clearly self-corrects with words such as `等等`, `不对`, `重新来`, `我改主意`, `其实想要`, `其实是想要`, `应该是`, or `改成`; the extracted query must be a continuous substring from the user request, not a guessed API name.
- When multiple resources or services appear without a clear self-correction, run `rg_rank.py` once with the original request. If the returned candidates remain ambiguous, list them concisely and ask the user to choose.
- Pure-generic queries such as `api`, `sdk`, or `demo` are sent online but are likely to be ambiguous. Refine the query with a concrete resource or action word.
- ServiceCode is case-sensitive. Preserve the exact `service_code` value from the selected API record when calling `make_code.py`; for example, `Kafka` is not `kafka`.
- When the same `service_code + action` appears in multiple API versions and the user did not specify a version, select the result with `is_recommended=true` even if its `remote_rank` is lower. If the user specified a version, use that exact version.
- Fetch `api-swagger` only after a concrete API is selected.
- The `api-swagger` fetch may include both `Version` and `APIVersion` because that endpoint expects them; the `make-code` payload must not include `Version`.
- Call `make-code` with `ApiAction`, `ServiceCode`, `APIVersion`, `Region`, and `Params`.
- Do not send `Version` to `make-code`.
- `Params` must come from the user. Do not auto-fill from swagger demos.
- Swagger is used for API metadata, required parameter hints, and lightweight validation. Do not serialize query arrays, form arrays, or `.N` parameters for `make-code`; pass the user’s JSON object as `Params`.
- If the user omits required top-level parameters, mock only those top-level required parameters and clearly mark them as mock values. Do not mock optional parameters. If a required top-level parameter is an object or array, recursively fill only required child fields/items.
- Mock values must be derived from the fetched swagger first: prefer `example`, then `examples`, then `default`, then `enum`, then type/constraint-aware fallback. If a swagger example is masked, such as `****` or `XX`, skip it and use a valid fallback value.
- Mock comments must be in Chinese by default and placed near the mocked assignment line when the target language supports line comments; do not add a duplicate mock banner at the top of the returned code.
- Returned SDK code must print the API response value. The script post-processes fixed `make-code` templates for Python, Go, Java, and PHP to assign the response and print it.
- Return the code generated by `scripts/make_code.py` as the primary SDK example. Do not rewrite SDK request construction, authentication setup, or response handling into a custom application unless the user explicitly asks for that. If optional formatting or convenience logic is added, keep the generated active response print, such as `print(resp)`, `fmt.Println(resp)`, `System.out.println(resp)`, `print_r($response)`, or `console.log(response)`.
- If language is not specified, return all languages from `DemoSdk`.
- SDK install/dependency info is a separate, on-demand capability. Only when the user explicitly asks how to install the SDK or which package/version to use (keywords such as 依赖, 安装, install, 版本, 包, maven, `go get`, pip, composer, npm), run `scripts/sdk_info.py` with `--service-code` and `--api-version` (reuse the selected API's values; add `--language` to filter to one of go/python/java/php/nodejs). It returns the live install command (`RunCommand`) plus package and version per language. Do NOT run it during normal code generation.
- If the API match is ambiguous, show concise candidates and ask the user to choose one. Do not add follow-up execution boilerplate such as saying that you will fetch swagger, mock required params, and call `make-code` after the user chooses.

## Workflow

1. Parse the user request:
   - API hint: action, Chinese name, service code, or natural-language description.
   - Language: Python, Go, Java, PHP, cURL, Node.js, or unspecified.
   - Params: JSON object supplied by the user.
   - Region: user value or default `cn-beijing`.

2. Locate or validate the API once for every request. If the user already provides `service_code`, `api_version`, and `action`, use those exact values in direct mode; `make_code.py` verifies them through the online `api-swagger` response. For natural-language requests, call `scripts/rg_rank.py` with `--query` first. Use the full original request unless a clear self-correction keyword points to a later target; in that case use the final target substring.

3. After selecting `service_code`, `api_version`, and `action`, call `scripts/make_code.py` in direct API mode with `--service-code`, `--api-version`, and `--action`. If top-level required params are missing, the script fills only those required top-level params with swagger-derived mock values and annotates the returned code in Chinese. Ask for clarification only when API selection is genuinely ambiguous in the online results; in that clarification, only list candidates and ask the user to choose.

4. Once params are available, call `make-code` through the script and return the official code. Do not transform the generated sample into a hand-written utility; any custom formatting must be secondary and must preserve the active response print.

## Commands

Search online candidates:

```bash
python3 scripts/rg_rank.py \
  --query '角色扮演' \
  --limit 10 \
  --format text
```

Direct API mode:

In TRN examples, `<account-id>` is the Volcengine account ID segment, such as a masked `2134xxxyyy`.

```bash
python3 scripts/make_code.py \
  --service-code sts \
  --api-version 2018-01-01 \
  --action AssumeRole \
  --language python \
  --params-json '{"DurationSeconds":3600,"RoleSessionName":"demo","RoleTrn":"trn:iam::<account-id>:role/demo"}'
```

Use `--refresh-swagger` when API Explorer metadata has just changed or generated code looks stale:

```bash
python3 scripts/make_code.py \
  --service-code sts \
  --api-version 2018-01-01 \
  --action AssumeRole \
  --refresh-swagger \
  --params-json '{}'
```

Fetch SDK install/dependency info on demand (only when the user asks about install, package, or version):

```bash
python3 scripts/sdk_info.py \
  --service-code sts \
  --api-version 2018-01-01 \
  --language go
```
