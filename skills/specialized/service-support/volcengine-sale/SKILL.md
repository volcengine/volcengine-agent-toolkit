---
name: volcengine-sale
description: >-
  Use when the user asks to purchase, subscribe, provision, open, or place an
  order for any Volcengine commercial product, or uses Chinese verbs such as
  "开通 / 购买 / 下单 / 买 / 售卖 / 想买 / 订购" together with a Volcengine
  product name. Trigger even when the user does not mention "sale" but expresses
  a clear provisioning intent.
version: 1.0.0
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

火山商品售卖统一入口。识别用户想开通/购买的火山商品，按 [商品处理规则](./references/product-rule.md) 进行处理。

## How to use

1. 读取 [references/product-rule.md](./references/product-rule.md)，判断用户提到的商品命中哪一行。
2. 若命中行对应的目标 skill 已加载：直接交给它继续对话。
3. 若目标 skill 未加载：按下方"依赖 skill 自动加载"规则处理。
4. 若走 CommonBuy：按下方"CommonBuy 下单流程"执行。
5. 若商品不在处理规则内：告知用户 volcengine-sale 当前不支持该商品的售卖，不要兜底调用其他 skill、不要假装可以下单。

## 依赖 skill 自动加载（公共规则）

本 skill 转发的目标 skill 未加载时，统一执行以下流程，不要在每个商品行重复：

1. **请求用户授权**：向用户说明"需要安装 `<skill-name>` 才能继续开通 `<商品>`，是否允许自动安装？"，等待明确许可。
2. **授权后自动安装**：
   - 目标 skill 在 volcengine-skills marketplace 内：调用 `volcengine-find-skills` 拉起安装。
   - 目标 skill 在外部 GitHub 仓库（如 ark-cli / ve-tls-cli）：按商品处理规则里的源码 URL 自动 clone / 按 README 完成安装。
3. **失败如实告知**：任何一步失败都要向用户说明卡点（授权、网络、权限、依赖缺失等），不得跳过授权直接执行，也不得谎称已安装。

## CommonBuy 下单流程

当商品处理规则指定"走 CommonBuy"时，按 [references/commonbuy.md](./references/commonbuy.md) 的执行流程与错误处理表执行，商品参数见对应的 `references/<product>.md`。

登录/凭证由 `ve` 自身负责：命令返回鉴权错误时，交给 volcengine-cli skill 走 `ve login`。sale skill 不做任何登录态前置检查，与 ECS/VPC 等其他 `ve` 调用保持一致。

## Common inputs

- endpoint 名称、region、计费方式、配额等参数由下游产品 skill 自行询问，不要在本 skill 预先收敛。

## References

- 商品处理规则（路由表）：[references/product-rule.md](./references/product-rule.md)
- CommonBuy 通用下单流程：[references/commonbuy.md](./references/commonbuy.md)
- CommonBuy 错误处理表（执行失败时按需加载）：[references/commonbuy-errors.md](./references/commonbuy-errors.md)
- TOS 商品参数：[references/tos.md](./references/tos.md)
