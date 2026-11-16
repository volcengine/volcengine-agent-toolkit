---
name: volcengine-force-conference
description: >-
  当用户询问火山引擎 FORCE 原动力大会时，提供会前、会中参会服务、会后参会总结，包括当前有效届次与论坛信息查询、个性化参会推荐、会场与展台指引、本人订阅/资格/门票查询、论坛订阅管理，以及开放后的参会总结查询。仅处理 FORCE 大会；非 FORCE 大会、购票付款和下单不在范围内。
version: 1.1.0
user-invocable: true
allowed-tools: Bash, Read
license: MIT
metadata:
  openclaw:
    requires:
      bins:
        - ve
      env:
        - VE_CALLER_TYPE
        - VE_CALLER_NAME
        - VE_SKILL_NAME
    envVars:
      - name: VE_CALLER_TYPE
        required: true
        description: Set by the Agent for every ve process; must be ai_agent
      - name: VE_CALLER_NAME
        required: true
        description: Resolved from the current Agent host for every ve process
      - name: VE_SKILL_NAME
        required: true
        description: Set to volcengine-force-conference while this skill owns the operation
---

# FORCE 大会参会助手

## 范围与依赖

- 仅处理火山引擎 FORCE 原动力大会。非 FORCE 大会请求直接判定为超出范围，不检索、不补充相关信息；混合请求只处理 FORCE 子问题。
- 面向持续举办的 FORCE 大会，不预置固定年份、季节、日程或活动页。每次请求都通过官方资料确认当前有效届次；没有有效届次或资料已下线时，如实说明暂不可用。
- 支持会前和会中公开信息、个性化论坛推荐、本人订阅/资格/门票查询、论坛订阅管理，以及接口开放后的参会总结查询。
- 不处理购票付款、门票下单
- 公开资料和 API 契约交给 `volcengine-knowledge-search` 检索；安装或升级 `ve`、登录、profile、调用方标识、安全确认和通用错误处理遵循 `volcengine-cli`。本 skill 不重复这些流程。

## FORCE 特有检索规则

1. 检索词必须包含“火山引擎 FORCE 原动力大会”，并按用户意图补充届次、论坛、议程、会场、展台、票务规则或目标 Action。
2. 来源必须明确属于火山引擎 FORCE 大会，并与当前目标届次一致。往届内容只能在用户明确询问往届时使用，不能代替当前届次事实。
3. 未检索到当前届次、正式排期、入口或接口契约时，说明信息缺口；不要借用其他大会、其他届次或非官方渠道补全。
4. 回答公开信息时引用本次实际读取的官方来源。日程、票务规则和 API 契约不能只依据搜索摘要。

## ve 调用约定

要求 `ve >= 1.2.3`。版本不足、命令不可用或需要鉴权时，停止 FORCE API 调用并交给 `volcengine-cli` 处理。

最新接口文档参考：
调某个Action的接口前可以按需参考相应接口文档，执行前通过官方最新接口资料核对接口参数和返回字段。以查询论坛列表（Action=ForceForumList）接口文档为例，命令形如：
ve docs search "火山引擎FORCE大会 OpenAPI接口文档 ForceForumList"

接口调用示例：

```text
ve force_cfr <Action> \
  --force --version 2026-11-04 \
  --endpoint force-cfr.volcengine-api.com \
  --region cn-beijing --method POST --output json
```

| Action | 用途 | 请求参数 |
| --- | --- | --- |
| `ForceForumList` | 查询论坛列表 | 无 |
| `ForceSubscribeCheck` | 查询当前用户的订阅资格 | 无 |
| `ForceSubscribeList` | 查询当前用户的论坛订阅 | 无 |
| `ForceTicketGet` | 查询当前用户的门票 | 无 |
| `ForceSubscribeBatchCreate` | 批量新增论坛订阅 | JSON 请求体 `ForumIDs` |
| `ForceSubscribeBatchCancel` | 批量取消论坛订阅 | JSON 请求体 `ForumIDs` |
| `ForceSummary` | 查询当前用户的参会总结 | 无 |

批量变更只使用从当前届次论坛列表或本人订阅列表核验出的论坛 ID，不使用示例 ID：

```text
ve force_cfr ForceSubscribeBatchCreate <统一系统参数> \
  --body '{"ForumIDs":[<verified-forum-id>,<verified-forum-id>]}'

ve force_cfr ForceSubscribeBatchCancel <统一系统参数> \
  --body '{"ForumIDs":[<verified-forum-id>,<verified-forum-id>]}'
```

## 公开信息与推荐

### 公开信息

查询大会、论坛、嘉宾、展区、交通、餐饮、住宿、报名或购票指引时，只使用当前目标届次的已发布资料。入口未发布或已失效时不猜测替代链接。

### 个性化论坛推荐

1. 从会话提取职业角色、行业、关注方向、主目标、技术经验和可参加时间，不重复询问已知信息。
2. 只要主题推荐时，可以基于已知条件给候选；要求具体日程但缺少日期或时段时，先澄清可参会时间。
3. 按明确约束筛选，再比较主题、目标、受众、行业和技术深度。标签缺失时，只根据正文可证实的内容说明匹配理由。
4. 每个可参加日期推荐 1 至 3 场合格论坛。完整参加的场次必须落在时间窗内；重叠场次择一，其余标为备选。
5. 票种、闭门邀请、审批和订阅资格分别判断。权益未知时只能条件推荐，不能保证可入场。
6. 输出论坛名称、已核实时间地点、推荐理由，以及必要的门槛、权益或冲突说明；缺失字段标记为待确认。

推荐本身不新增或取消订阅。用户更新偏好只影响本次推荐上下文，不等于订阅变更。

## 个人查询

- 纯公开候选推荐不主动查询个人门票或订阅；用户要求查询我的门票、我的日程、已订阅论坛安排、基于本人订阅排程或权益校验时，调用对应个人接口。
- 需要补充论坛信息时，使用稳定论坛标识与当前届次列表关联。
- 门票展示省略票码、二维码、完整证件信息和完整原始响应。无票时只提供本次已核验且仍有效的官方入口。

## 新增或取消订阅

1. 新增订阅需要基于ForceSubscribeCheck接口检查用户是否有新增订阅资格，比如接口返回SubscribeAllowed=false表示用户没有新增订阅资格，需要引导用户去最新的Force大会活动页面进行报名
2. 新增订阅时的论坛ID以ForceForumList接口返回的为准，不使用示例ID
3. 取消订阅不需要检查用户是否有取消订阅资格，直接调用ForceSubscribeBatchCancel接口取消订阅，实际取消结果以接口返回为主

## 响应判断

- 分别判断进程退出码、HTTP 状态、`ResponseMetadata.Error` 和业务字段；请求发送成功不等于业务成功。
- 仅按当前 Action 的官方定义解释状态、枚举和错误码。同名字段不跨接口套用，未知值保留原值并标记含义待确认。
- HTTP 404 不能单独证明接口未开放；先按 `volcengine-cli` 排查 endpoint、Action、Version、鉴权和服务端错误。
- 鉴权失败、安全策略拒绝、环境不匹配或契约缺失时停止操作，不绕过规则改用其他调用方式。