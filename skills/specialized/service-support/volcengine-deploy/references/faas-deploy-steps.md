# veFaaS Skill Execution

`volcengine-deploy` does not duplicate veFaaS deployment details. When the user chooses veFaaS, switch to/call the `volcengine-vefaas` skill. If that path fails, return to the main deployment flow so the user can fix the issue, retry veFaaS, or choose ECS/VKE.

## What to pass

Provide the `volcengine-vefaas` skill with:

- repo path or Git URL
- app name
- target region
- detected framework and port, if known
- whether env vars or `.env.example` exist
- warnings from prepare, such as migrations, long-running workers, WebSocket usage, or external dependencies

## Expected `volcengine-vefaas` workflow

The `volcengine-vefaas` skill owns:

```bash
vefaas --version
vefaas login --check
vefaas inspect
vefaas deploy --newApp <app-name> --gatewayName $(vefaas run listgateways --first) --yes
vefaas domains
```

For apps with environment variables, tell `volcengine-vefaas` to link/create the app, configure env vars, then deploy.

## Failure return path

If `volcengine-vefaas` fails:

1. summarize the failure in user terms, such as auth failure, no gateway, framework detection failure, build failure, or deploy timeout;
2. show the relevant debug/log command from `vefaas` if available;
3. return to the main deployment choice and offer:
   - retry veFaaS after fixing the issue,
   - switch to ECS,
   - switch to VKE.

## Recommendation constraints

veFaaS remains a visible option even when it is not first in the recommendation order. Explain the reason plainly:

- supported framework and stateless shape: strong veFaaS candidate
- migrations: needs a separate migration step before/around deploy
- long-running workers or WebSocket: ECS/VKE is usually safer
- unknown start command or unsupported framework: `vefaas inspect` must confirm before deployment

Do not fall back to the legacy `ve vefaas` ZIP/API flow unless the user explicitly asks for low-level API work.
