# 自测

运行入口只需要 Python 3.10+ 标准库。在 Skill 根目录执行：

```bash
python3 -S scripts/cost.py schema --list-actions
```

应列出 19 个只读 Action。真实查询另需已安装并授权的 ve；以下回归全部使用合成或
已脱敏 fixtures，不调用线上 Billing/STS 接口。

测试有两种源码布局，本文件同时适用：

| 布局 | 测试目录 | eval 入口 |
|---|---|---|
| 本地完整 Skill 源码 | Skill 内的 tests/ | Skill 内的 evals/run_evals.py |
| volcengine-skills 贡献仓库 | 仓库 tests/volcengine_cost/ | 仓库 tests/volcengine_cost/evals/run_evals.py |

贡献仓库的测试不随 Skill 安装。仅复制运行文件的目录没有 fixtures，应回到上述源码
目录自测。完整开发回归及契约导出需要 Pydantic 2.11+；这是开发依赖，运行已安装
Skill 无需安装。贡献仓库提供 tests/volcengine_cost/requirements.txt 供准备开发环境。

准备好开发依赖后，在 Skill 根目录执行以下完整代码块。它自动选择测试布局：

```bash
set -e
if [ -d tests/fixtures ]; then
  cost_test_dir=tests
  cost_eval_file=evals/run_evals.py
else
  cost_test_dir=../../../tests/volcengine_cost
  cost_eval_file="$cost_test_dir/evals/run_evals.py"
fi
if [ ! -d "$cost_test_dir/fixtures" ]; then
  printf '%s\n' '当前目录没有测试数据，请在完整源码的 Skill 根目录执行。' >&2
  exit 1
fi
python3 -S scripts/cost.py query --action QueryBalanceAcct --body '{}' --fixture-dir "$cost_test_dir/fixtures/query_balance_acct/current_arrears"
python3 -S -m unittest discover -s "$cost_test_dir" -p test_runtime_install.py -v
python3 -m unittest discover -s "$cost_test_dir" -v
python3 "$cost_eval_file"
python3 scripts/export_contracts.py --check
```

合成资金查询应返回 success 和欠费状态，业务结果不含 AccountID。独立运行回归
验证目录复制、错误脱敏、参数约束、来源绑定及下钻限制；完整回归和 eval 进一步核对
严格单页、文件衔接、空核销对象范围、连续下钻和同币种净差额贡献。

修改 scripts/cost_query/billing/contracts/ 中的开发模型后，先重新生成静态契约：

```bash
python3 scripts/export_contracts.py
python3 scripts/export_contracts.py --check
```

本地 fund_agent 发布包及安装器的测试位于 Skill 外的 ve-skills/tests/，由本地发布门禁
单独运行。它们及本地 CHANGELOG 不属于贡献 Skill 的分发文件。
