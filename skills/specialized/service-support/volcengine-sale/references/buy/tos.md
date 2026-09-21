# TOS（对象存储）CommonBuy 参数

## 适用范围

本商品参数**仅用于开通 TOS 服务本身**（首次开通对象存储服务）。TOS 资源包（存储容量包、下行流量包、请求次数包等）不通过 CommonBuy 下单，遇到资源包意图按下方"资源包购买"分流。

## 意图分流

按用户表述关键词判定：

| 用户意图关键词 | 走向 |
|---|---|
| "开通 TOS"、"开通对象存储"、"开 TOS 服务"、未指定具体形态的"购买 TOS" | 走 CommonBuy（本文件的 ConfigList） |
| "TOS 资源包"、"存储包"、"存储容量包"、"下行流量包"、"请求次数包"、"买流量包" | **不走 CommonBuy**，按"资源包购买"分流 |

## ConfigList 参数（开通 TOS 服务）

```json
{
  "Product": "TOS",
  "ConfigurationCode": "TOS"
}
```

| 参数 | 值 | 说明 |
|---|---|---|
| `Product` | `TOS` | 固定值 |
| `ConfigurationCode` | `TOS` | 固定值 |
| `ChargeItemList` | 不传 | TOS 无需指定计费项 |

## 完整命令示例

```bash
ve billing CommonBuy --body '{"ConfigList":[{"Product":"TOS","ConfigurationCode":"TOS"}],"ClientToken":"<uuid>"}'
```

## 资源包购买

用户想购买 TOS 资源包时，直接引导前往资源包购买页，对客回复直接使用以下模板：

```
TOS 资源包请在控制台购买页选购：
https://console.volcengine.com/tos/resource

进入后在「资源包管理」中购买资源包即可。
```

## 控制台降级链接（开通 TOS 服务）

CommonBuy 命令实际返回错误、无法通过 CLI 完成"开通 TOS 服务"时，引导用户至控制台开通：

<https://console.volcengine.com/tos>

首次进入会弹出服务开通协议，同意后即完成开通。
