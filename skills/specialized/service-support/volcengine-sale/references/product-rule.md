# 火山商品处理规则

`volcengine-sale` 根据本规则识别火山商品并按下表的处理方式进行处理。

| 商品 | 关键词（中英，大小写不敏感） | 目标 skill / 处理方式 |
| --- | --- | --- |
| 方舟 Ark | 方舟, ark, 火山方舟, 接入点, endpoint, deepseek 接入, doubao, 豆包接入 | 交给 `arkcli-onboard` 作为开通/接入主入口；后续参数由 ark-cli skill 组自行路由到 `arkcli-plans` / `arkcli-deploy` 等子 skill。源码：<https://github.com/volcengine/ark-cli>（不在 volcengine-skills marketplace） |
| veFaaS | vefaas, 函数计算, 函数服务, serverless 函数, function service, FaaS | 交给 `volcengine-vefaas`。源码：本仓库 `plugins/volcengine-containers-middleware/` |
| TLS | tls, 日志服务, 日志项目, log project, log topic, log service, volclog | 分两步：① **账号级开通**：引导用户访问控制台 <https://console.volcengine.com/tls>，首次访问会弹开通协议，同意后即完成开通。`volclog-core` / `ve` 均无账号开通能力，不要尝试代替用户开通。② **资源级操作**（项目、主题、检索等）：账号已开通后交给 `volclog-core`。源码：<https://github.com/volcengine-tls/ve-tls-cli>（不在 volcengine-skills marketplace）。运行时若下游返回 403 `The account does not open tls service`，退回 ① 引导控制台开通。 |
| TOS | tos, 对象存储, object storage, bucket, 桶, 存储桶 | 走 CommonBuy 直接下单（见下方 CommonBuy 入口说明）。用户意图为「TOS 资源包 / 存储包 / 存储容量包 / 下行流量包 / 请求次数包 / 买流量包」时不走 CommonBuy，按 [tos.md 资源包购买](./tos.md#资源包购买) 直接引导控制台购买页 <https://console.volcengine.com/tos/resource>。 |

## 匹配规则

- 按表格顺序自上而下匹配，首个命中的行决定商品。
- 中文按包含关系匹配，不做分词；英文大小写不敏感。
- 一句话同时命中多个商品：让用户拆成多条意图。
- 只出现商品名但不是售卖意图（例："方舟接入点断开了"）：走 `volcengine-troubleshooting`，不走本 skill。
- **商品不在本表内**：明确告知用户"volcengine-sale 当前不支持该商品的售卖"，不要尝试兜底调用其他 skill、也不要假装可以下单；如用户仍想寻找可用能力，可引导其调用 `volcengine-find-skills` 自行检索。

## CommonBuy 入口说明

走 CommonBuy 的商品，公共执行流程见 [commonbuy.md](./commonbuy.md)，商品专属参数见对应文件：

| 商品 | 参数文件 |
|---|---|
| TOS | [tos.md](./tos.md) |
