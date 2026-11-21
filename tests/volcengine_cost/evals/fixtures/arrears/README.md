# 欠费 Agent 评测 fixture

这些响应只用于离线 Agent 轨迹评测，执行时把目标场景目录传给
`cost.py query --fixture-dir`，不得调用真实接口。

- 账户状态：复用 `tests/volcengine_cost/fixtures/query_balance_acct/` 下的场景目录。
- `unpaid_composition/`：2026-09 产品维度已出账未还款构成，包含 CNY 与 USD。
- `discount_cause/`：当前账户欠费；2026-08 与 2026-09 用量相同、优惠金额下降、应付上升。
- `recharge_without_event/`：充值后仍问欠费，但只提供当前账户快照，没有充值到账或抵扣事件。

fixture 中的账号和 RequestId 均为固定占位符或合成值。
