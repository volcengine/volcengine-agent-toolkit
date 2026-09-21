---
name: volcengine-sale
description: >-
  Use when the user wants to transact on any Volcengine commercial product —
  purchase/provision it, ask what it costs, or unsubscribe from it. Covers three
  actions: buy (purchase, subscribe, provision, open, place an order; Chinese
  "开通 / 购买 / 下单 / 买 / 售卖 / 订购"), price (how much does it cost, quote,
  billing rules, estimated spend; Chinese "多少钱 / 价格 / 报价 / 费用 / 怎么收费 /
  如何计费 / 预估费用"), and unsubscribe (cancel a subscription, refund a
  prepaid instance; Chinese "退订 / 退款 / 取消订阅"). Trigger even when the user
  does not mention "sale" but expresses a clear purchase, pricing, or
  cancellation intent toward a Volcengine product. Only handles these three
  transaction actions; anything outside them is out of scope.
version: 1.1.0
user-invocable: true
allowed-tools: Bash, Read, Write
license: MIT
metadata:
  openclaw:
    requires:
      bins:
        - git
        - ve
---

# volcengine-sale

火山商品交易统一入口，编排 **buy（开通购买）/ price（询价）/ unsubscribe（退订）** 三个动作。客户完整交易链路是询价 → 购买 → 退订，也可以单独使用其中任一能力。

## How to use

1. 按下方「意图路由」表判定用户的交易动作。
2. 读该动作的流程文件，按其中的步骤执行。

## 意图路由

| 动作 | 关键词（中英，大小写不敏感） | 流程文件 |
|---|---|---|
| price 询价 | 多少钱、价格、报价、费用、收费、怎么收费、如何计费、计费方式、计费规则、收费标准、价格表、单价、总价、预估费用、成本、预算、price、pricing、quote、cost | [references/price/README.md](./references/price/README.md) |
| unsubscribe 退订 | 退订、退款、取消订阅、不想要了、退掉、不续了、unsubscribe、cancel subscription、refund | [references/unsubscribe/README.md](./references/unsubscribe/README.md) |
| buy 开通购买 | 开通、购买、下单、买、售卖、想买、订购、buy、purchase、subscribe、provision | [references/buy/README.md](./references/buy/README.md) |

**只处理命中上表的诉求。** 未命中任何一行即不属于本 skill 范畴，说明本 skill 只承接询价、购买、退订三类交易执行场景，返还上层 agent，**不调用任何交易接口、不做兜底解答**。

常见的未命中场景：已出账账单与欠费明细（计量计费争议）、优惠与代金券申请、议价与报价单盖章、免费额度咨询。这类诉求即使提到了商品名或金额，也不进入本 skill 流程。

- **同时命中 price + buy**（例："ECS 多少钱，帮我买一台"）→ 先执行 price，用户确认价格后再询问是否进入 buy。
- **其他组合同时命中** → 让用户拆成多条意图，不要并行执行。

## 对客表述

商品一律只说中文名称，不出现商品编码的字段名与取值。用客户说的商品名在商品清单中匹配，匹配不到就直接问客户是哪个商品——**仅限流程确实需要商品编码作为入参时**。退订流程的商品编码取自实例查询的返回值，不得为此追问客户。

需要配置与计费项时，直接说明需要配置编码与计费项编码，不用业务说法代替。客户提供不了则按流程降级。

命令本身、报错原文、客户主动使用的编码，原样展示不改写。

## 登录与凭证

由 `ve` 自身负责。命令返回鉴权错误时交给 volcengine-cli skill 走 `ve login`，本 skill 不做登录态前置检查，与 ECS / VPC 等其他 `ve` 调用保持一致。

## 依赖 skill 自动加载

本 skill 转交的目标 skill 未加载时，统一执行以下流程：

1. **请求用户授权**：向用户说明"需要安装 `<skill-name>` 才能继续处理 `<商品>`，是否允许自动安装？"，等待明确许可。
2. **授权后自动安装**：
   - 目标 skill 在 volcengine-skills marketplace 内：调用 `volcengine-find-skills` 拉起安装。
   - 目标 skill 在外部 GitHub 仓库（如 ark-cli / ve-tls-cli）：按流程文件里给出的源码 URL 自动 clone / 按 README 完成安装。
3. **失败如实告知**：任何一步失败都要向用户说明卡点（授权、网络、权限、依赖缺失等），不得跳过授权直接执行，也不得谎称已安装。
