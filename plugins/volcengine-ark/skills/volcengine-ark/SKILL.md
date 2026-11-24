---
name: volcengine-ark
description: >-
  Use for Volcengine Ark (火山方舟) work through `ve arkcli`: choosing and comparing Doubao / Seed /
  Seedream / Seedance models, model pricing, activating a model, creating or selecting an Ark API
  Key, inference endpoints, test calls and debugging, image / video generation, multimodal
  understanding, code examples, token usage and Ark bills, Agent Plan / Coding Plan, fine-tuning,
  datasets, managed agents, and arkcli diagnostics. 当用户提到火山方舟、方舟、豆包大模型、Doubao、
  Seed、Seedream、Seedance、arkcli，或要做模型选型、查模型价格、开通模型、创建 API Key、创建推理接入点
  (Endpoint)、调用或调试模型、生图生视频、查用量和费用、模型精调时调用；也包括“我想用方舟做个问答助手，
  帮我选模型”“怎么接入这个模型”这类接入诉求。方舟的概念、用法、计费规则等文档类问题不在此列，走
  volcengine-knowledge-search。
license: Apache-2.0
metadata:
  openclaw:
    emoji: "🧠"
    homepage: "https://github.com/volcengine/ark-cli"
    requires:
      bins:
        - ve
    install:
      - kind: node
        package: "@volcengine/cli"
        bins: [ve]
---

# Volcengine Ark (arkcli)

> Bundles the official Ark CLI skills from [`volcengine/ark-cli`](https://github.com/volcengine/ark-cli/tree/main/skills) (Apache-2.0) as guides under `references/`; the pinned commit and the changes made while vendoring are in [references/UPSTREAM.md](references/UPSTREAM.md). The guides keep the upstream native `arkcli ...` form. Run every command as `ve arkcli ...` (requires `ve >= 1.1.11`), keeping all later arguments.

This file only routes and states what differs under `ve`. Product rules live in the guides.

## How to work

1. Read [references/arkcli-shared/GUIDE.md](references/arkcli-shared/GUIDE.md) once per conversation. It holds the auth gate, the control-plane / data-plane split, the command selection order, and the confirmation protocol that every other guide relies on.
2. Pick the guide for the user's goal from the table below. Read it, and the references it names for the command you are about to run, before running anything.
3. Run the command through `ve` as described in [Running under `ve`](#running-under-ve).
4. After a login, a lookup, or an install, go back to the user's original goal. Those steps are not the result.

The guides are plain files in this skill. Read them by path; nothing else has to be installed or loaded, and no new conversation is needed.

## Pick the guide

| User goal | Guide | Entry commands |
| --- | --- | --- |
| Choose or compare models, model details, limits | [arkcli-models](references/arkcli-models/GUIDE.md) | `models search`, `models get`, `models list` |
| Model or plan prices | [arkcli-pricing](references/arkcli-pricing/GUIDE.md) | `pricing ...` |
| "I want to use model X in my app" end to end | [arkcli-onboard](references/arkcli-onboard/GUIDE.md) | orchestrates the rows below |
| Activate (开通) a foundation model service | [arkcli-models](references/arkcli-models/GUIDE.md) | `models activate` |
| Log in, check identity, create or pick an API Key | [arkcli-auth](references/arkcli-auth/GUIDE.md) | `auth status`, `auth login`, `auth apikey` |
| List, reuse or inspect inference endpoints | [arkcli-infer-endpoint](references/arkcli-infer-endpoint/GUIDE.md) | `infer endpoint list` |
| Create an inference endpoint | [arkcli-deploy](references/arkcli-deploy/GUIDE.md) | `+deploy` |
| Test call, debugging, Chat / Responses parameters | [arkcli-chat](references/arkcli-chat/GUIDE.md) | `+chat` |
| Call with a given key, endpoint, model name or base URL | [execution-context](references/arkcli-shared/references/execution-context.md) | flags of `+chat` / `+gen` |
| Code example for an application | [arkcli-code-example](references/arkcli-code-example/GUIDE.md) | `+code-example` |
| Token usage, free quota, plan quota | [arkcli-usage](references/arkcli-usage/GUIDE.md) | `usage stats`, `usage balance` |
| What a call or a month cost (Ark bills) | [arkcli-billing](references/arkcli-billing/GUIDE.md) | `billing list` |
| Image, video or speech generation | [arkcli-gen](references/arkcli-gen/GUIDE.md) | `+gen` |
| Transcribe, extract, caption, locate in media or documents | [arkcli-understand](references/arkcli-understand/GUIDE.md) | `+understand` |
| Agent Plan / Coding Plan, seats, plan keys | [arkcli-plans](references/arkcli-plans/GUIDE.md) | `plans ...` |
| Point a local agent at a plan or an endpoint | [arkcli-helper](references/arkcli-helper/GUIDE.md) | `helper` |
| Fine-tuning, custom models, datasets | [arkcli-train-finetune](references/arkcli-train-finetune/GUIDE.md), [arkcli-custommodel](references/arkcli-custommodel/GUIDE.md), [arkcli-datasets](references/arkcli-datasets/GUIDE.md) | `train finetune`, `models custommodel`, `dataset` |
| Managed agents | [arkcli-agent](references/arkcli-agent/GUIDE.md) | `agent ...` |
| Profiles, default resources, configuration | [arkcli-profile](references/arkcli-profile/GUIDE.md), [arkcli-resources](references/arkcli-resources/GUIDE.md), [arkcli-config](references/arkcli-config/GUIDE.md) | `profile`, `resources`, `config` |
| A call fails, a key or endpoint misbehaves, CLI health | [arkcli-doctor](references/arkcli-doctor/GUIDE.md), [troubleshooting](references/arkcli-shared/references/troubleshooting.md) | `doctor` |
| Rollout watching, before / after comparison, capacity review | [arkcli-vmp](references/arkcli-vmp/GUIDE.md), [arkcli-vmp-workflows](references/arkcli-vmp-workflows/GUIDE.md) | `doctor monitor ...` |
| A registered action no product command covers | [arkcli-api-explorer](references/arkcli-api-explorer/GUIDE.md) | `api` |

Which models exist, what a model can do, and what a model costs are answered from live `ve arkcli models ...` and `ve arkcli pricing ...` results, as are activation state, keys, endpoints and usage. Do not answer them from documentation search alone.

Ark knowledge questions are a different job: what a feature is, how to use it, how a billing rule works, limits, best practices, or reading a documentation link. Answer those with the `volcengine-knowledge-search` skill (`ve docs search`, `ve docs fetch`), not with `arkcli docs`. Where a guide points to a documentation step, use that skill for it.

## Running under `ve`

These points replace what the guides say for standalone `arkcli`.

- **Command prefix.** Put the three caller variables before `ve` on every command, including help and version:

  ```text
  VE_CALLER_TYPE=ai_agent VE_CALLER_NAME="<agent-id>" VE_SKILL_NAME=volcengine-ark \
    ve arkcli models search seed
  ```

  Write your own Agent product name as `<agent-id>`. `ve` passes the caller on to arkcli, so do not add `ARKCLI_CALLER_TYPE`, `ARKCLI_CALLER_NAME`, `ARKCLI_SKILL_NAME` or `ARKCLI_NO_UPDATE_NOTIFIER`, although the shared guide asks for them.
- **Version.** Run `ve version` first and require `ve >= 1.1.11`. If `ve` is missing or older, install or upgrade it with the `volcengine-cli` skill.
- **Installing and upgrading arkcli.** `ve` installs arkcli on first use. Do not run `npm i @volcengine/ark-cli`, `arkcli update` or `+connect`. Upgrade with `ve proxycli upgrade arkcli` when the user asks or a guide requires a newer arkcli.
- **Flags.** Child flags go after the child command: `ve arkcli ... --profile <name>` selects an Ark profile. `ve --profile <name> arkcli ...` is invalid.
- **Authentication.** Ark keeps its own login and profiles. `ve arkcli auth status` is the check; a working `ve sts GetCallerIdentity` does not prove Ark is logged in. When Ark needs a login, follow [arkcli-auth](references/arkcli-auth/GUIDE.md); Agent sessions use its two-step `auth login --no-browser`.
- **Warnings from `ve`.** `ve` may print a warning about refreshing its own Console Login session before it starts arkcli. Judge the command by arkcli's own output and exit status.
- **Confirmation.** arkcli's rules apply: a `requires_confirmation` result means ask the user, then repeat the same command with `--yes`. The `ve` safety policy, `--DryRun`, `--output` and `--query` belong to native `ve <service> <Action>` calls and do not apply here.
- **Secrets.** Never print an API Key, AK/SK or token, and never read files under `~/.arkcli` or `~/.volcengine`.

## Boundaries

- Purchase orders, price quotes for other products and unsubscribing are the `volcengine-sale` workflow. Activating a pay-as-you-go model service is `models activate` here.
- Cost changes across the whole account or across products belong to `volcengine-billing-and-cost-management`. Ark token usage and Ark bill lines are answered here.
- Use native `ve ark <Action>` only when a guide sends you to the raw API and no product command covers the task.
