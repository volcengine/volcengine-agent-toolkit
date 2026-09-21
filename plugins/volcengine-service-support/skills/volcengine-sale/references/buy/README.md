# buy 动作：开通购买流程

用户想开通 / 购买 / 下单某个火山商品时执行本流程。

## 执行步骤

1. **商品识别**：读 [product-rule.md](./product-rule.md)，按关键词匹配确定商品及其处理方式。用户只表达了购买意图、未说明具体商品时（例："我想买个 AI 商品"），先按 [common/product-list-schema.md](../common/product-list-schema.md) 的 `ProductList` 结构返回商品清单供其挑选，选定后再继续。
2. **分支执行**：

   | 处理方式 | 执行 |
   | --- | --- |
   | 走 CommonBuy | 按下方「CommonBuy 通用下单流程」执行，商品专属参数见对应的 `<product>.md` |
   | 交给 `<skill>` | 把用户意图与已确认的上下文移交该 skill；目标 skill 未加载时按 [SKILL.md](../../SKILL.md) 的「依赖 skill 自动加载」处理 |
   | 引导控制台 | 向用户说明需在控制台完成，并给出购买页链接 |

3. **商品未命中**：按 [product-rule.md](./product-rule.md) 的匹配规则处理，不要兜底调用其他 skill、不要假装可以下单。

## CommonBuy 通用下单流程

当 [product-rule.md](./product-rule.md) 路由表指定某商品"走 CommonBuy"时，按本节的公共流程执行。商品专属参数见对应的 `<product>.md` 文件。

登录/凭证由 `ve` 自身负责：命令返回鉴权错误时，交给 volcengine-cli skill 走 `ve login` 流程。sale skill 不做任何登录态前置检查。

### 执行流程

1. **生成 ClientToken**：`uuidgen` 生成 UUID 作为幂等键。同一次购买意图的所有重试共享同一个 ClientToken。
2. **加载商品参数**：读取对应的 `<product>.md`，获取 `ConfigList` 内容。
3. **组装命令**：将商品参数填入命令模板。
4. **展示并确认**：向用户展示完整命令，说明将要执行的购买操作。**未经用户确认不得执行。**
5. **用户确认后立即执行**：调用命令，将完整响应返回用户。
6. **查询实例交付状态**：从 CommonBuy 响应中提取 `InstanceIDList`，作为 `InstanceIDs` 参数调用 `ListAvailableInstances`，判断实例 `Status`。未查询到结果时每 3s 重试一次，最多 5 次。
   - `Status=Running` → 提示用户"开通成功"，返回实例信息。
   - 5 次重试后仍查不到数据或状态不符合预期 → 引导用户前往控制台查看实例（控制台链接见商品专属文件）。
7. **执行失败时**：按需加载 [errors.md](./errors.md) 的错误处理表分流；未命中特定分类时展示原始错误并询问是否重试，重试复用同一个 ClientToken。

### 命令模板

```bash
ve billing CommonBuy --body '{"ConfigList":[{<商品参数>}],"ClientToken":"<uuid>"}'
```

- 服务：`billing`
- Action：`CommonBuy`
- 版本：`2022-01-01`
- 方法：`POST`

### 通用字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ClientToken` | string | 否 | UUID，同一次购买意图内保持不变，支持重试幂等；最长 36 字符 |
| `ConfigList` | array[object] | 是 | 配置列表，每个元素对应一个商品的固定参数，见商品专属文件 |

### 实例交付状态查询

CommonBuy 成功返回后，用 `ListAvailableInstances` 查询实例交付状态：

```bash
ve billing ListAvailableInstances --body '{"InstanceIDs":["<instance-id-1>","<instance-id-2>"],"MaxResults":10}'
```

- 入参 `InstanceIDs` 直接取 CommonBuy 响应中的 `InstanceIDList`；`MaxResults` 固定填 `10`。
- 轮询策略：未查询到结果时每 3s 重试一次，最多 5 次。
- 结果判定：
  - `Status=Running` → 视为开通成功，输出实例信息。
  - 5 次内查到但状态不是 `Running`，或最终仍未查到数据 → 引导用户前往控制台查看实例（控制台链接见商品专属文件）。

### 扩展新商品

新增 CommonBuy 商品时：

1. 在本目录下新建 `<product>.md`，写明该商品的 `ConfigList` 参数和控制台链接。
2. 在 [product-rule.md](./product-rule.md) 路由表追加一行，处理方式写"走 CommonBuy"。
3. 公共流程无需修改。

## 本目录文件

| 文件 | 用途 |
| --- | --- |
| [product-rule.md](./product-rule.md) | 商品识别与处理方式路由表 |
| [errors.md](./errors.md) | CommonBuy 执行失败的错误处理表（命令实际报错后才加载） |
| [tos.md](./tos.md) | TOS 商品的 CommonBuy 参数 |
