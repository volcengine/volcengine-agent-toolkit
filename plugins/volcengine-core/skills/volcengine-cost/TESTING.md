# 自测

目录复制安装后的运行入口只需要 Python 3.10+ 标准库。在 Skill 目录执行：

```bash
python3 -S scripts/cost.py schema --list-actions
```

应列出 19 个只读 Action。真实费用查询另需已安装并授权的 ve；以下回归全部使用
合成或已脱敏的 fixtures，不调用线上 Billing/STS 接口。

测试与 evals 位于仓库的 `tests/volcengine_cost/`，不随 Skill 安装。以下命令在
仓库根目录执行：

```bash
python3 -S skills/core/volcengine-cost/scripts/cost.py query --action QueryBalanceAcct --body '{}' --fixture-dir tests/volcengine_cost/fixtures/query_balance_acct/current_arrears
python3 -S -m unittest discover -s tests/volcengine_cost -p test_runtime_install.py -v
```

第一条应返回 `status=success` 和合成账户的欠费状态，业务结果不含 AccountID；第二条
验证目录复制运行、错误脱敏、参数约束、来源绑定及下钻限制。

完整开发回归和契约导出需要 Pydantic 2.11+。这是开发依赖，运行已安装 Skill 无需
安装。使用已有开发环境，或先安装测试依赖：

```bash
python3 -m pip install -r tests/volcengine_cost/requirements.txt
python3 -m unittest discover -s tests/volcengine_cost -v
python3 tests/volcengine_cost/evals/run_evals.py
python3 skills/core/volcengine-cost/scripts/export_contracts.py --check
```

修改 `scripts/cost_query/billing/contracts/` 中的开发模型后，先重新生成静态契约再校验：

```bash
python3 skills/core/volcengine-cost/scripts/export_contracts.py
python3 skills/core/volcengine-cost/scripts/export_contracts.py --check
```

回归覆盖分页与字段粒度、Schema 与执行约束、Decimal JSON 金额、文件来源关联、
对账守恒、券适用性和核销缺口，以及资源包消费区间与账期归属。fixtures 中的账号、
资源 ID 均为合成值或明确脱敏值，不代表实时业务结果。
