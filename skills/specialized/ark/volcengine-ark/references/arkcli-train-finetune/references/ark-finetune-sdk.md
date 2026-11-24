---
name: ark-finetune-sdk
description: 用于创建、配置、测试、调试、提交、监控或排查模型精调 SDK 项目，尤其是包含 rollout 和 grader 插件的强化学习任务。当请求涉及 `ark` SDK 命令入口、`ark_sdk` Python 包、`job.py`、`job.yaml`、`arkworkspace.toml`、`custom_rl_pipeline`、`ModelCustomizationJob`、rollout/grader 函数、插件测试、RL debug 任务、轨迹分析或精调产物时使用。
---

# Ark Finetune SDK

这是通过精调 SDK 执行模型定制任务的操作指南。优先相信当前 SDK 行为和最新生成的模板，而不是记忆中的旧示例。

## 信息优先级

1. 当前已安装 SDK 和命令输出。
2. 使用 `ark init workspace` 新生成的 SDK 模板。
3. 需要用户可见引用时，使用官方公开产品文档。
4. 本 skill 附带的 reference。

不要把访问标签、环境专属说明、准入清单、变化较快的模型支持列表或敏感来源链接写进用户可见输出或生成文件。


## 起步检查

处理任何实质性任务前：

1. **准备 venv 并安装 SDK**（用户自管 venv，arkcli 不代管）
   ```bash
   python3.11 -m venv /tmp/ark-rl     # 必须 ≥ 3.10
   source /tmp/ark-rl/bin/activate
   ```
   火山方舟 SDK 使用以下安装源：
   ```bash
   python -m pip install https://ark-public-example-cn-beijing.tos-cn-beijing.volces.com/ark-sdk/ark_sdk-latest.tar.gz
   ```
   后续 `ark` / `python` 命令必须在同一 shell 里执行,或显式用 `/tmp/ark-rl/bin/ark`。

2. **完成 SDK 鉴权**
   火山方舟鉴权走 ArkCLI 桥，不要单独执行 `ark login`：
   ```bash
   arkcli auth login                            # 已登录时跳过
   arkcli train finetune sdk login              # 把 ArkCLI STS 写入 ~/.ark/authorization.json
   ```
   说明：
   - `sdk login` 会**临时覆盖** `~/.ark/authorization.json`；如果用户机器上已有 `ark login` 的长期 SSO 状态，该状态会被 STS 替换。
   - STS 默认约 30 分钟过期。鉴权报错时重跑 `arkcli train finetune sdk login --refresh`；该命令使用 ArkCLI 缓存的 refresh token，不会再次打开浏览器。
   - 多账号防误操作：既有文件的 `account_id` 与 ArkCLI 当前 active profile 不同时会拒绝覆盖；仅在确认目标账号后使用 `--force`。

3. 确认 SDK 版本和命令面。
   ```bash
   python -m pip show ark-sdk
   ark upgrade --help
   ark --help
   ark init workspace --help
   ark create mcj --help
   ark test pipeline_plugin --help
   ```
   需要升级且用户明确同意后再执行 `ark upgrade`；该命令会实际更新 SDK，不把它当只读版本检查。
4. 如果要创建或改造项目，先在临时目录用当前 SDK 初始化模板，并阅读生成文件后再改用户项目。
   ```bash
   ark init workspace <workspace-dir> --template <template-name>
   ```
5. 判断任务类型：SFT/DPO/CPT 类监督精调、带自定义 rollout/grader 的 RL、Agent RL，或产物管理。
6. 涉及写入或可能产生费用的操作时，如果用户没有明确要求提交，先总结最终配置并等待明确意图。`ark create mcj` 无 dry-run，提交即真实创建任务并上传插件 zip。

## Reference 路由

只加载需要的文件：

- 任务与数据配置：[job-configuration.md](job-configuration.md)
- RL rollout/grader 实现：[rl-plugins.md](rl-plugins.md)
- 测试、调试、监控与排障：[testing-debug-monitoring.md](testing-debug-monitoring.md)

## 核心流程

执行 SDK 精调任务时：

1. 完成当前环境要求的 SDK 鉴权。
   - 火山方舟按“起步检查”步骤 2 准备 ArkCLI STS，**不要**单独执行 `ark login`；否则会覆盖 ArkCLI 写入的 STS，导致鉴权状态分裂。


2. 初始化或检查 SDK workspace。
3. 配置 `job.py` 或 `job.yaml`：模型引用、训练方式、数据、超参、可选验证集、可选产物配置。
4. 对 RL 任务，先实现或改造 rollout，再实现 grader，最后接入 `custom_rl_pipeline`。
5. 在正式测试前补齐可观测性：轨迹、函数日志、指标，以及可用的 tracing。
6. 用一条预期通过样本和一条预期失败样本做本地测试。
7. 用小批量数据测试，并发接近计划 batch size。
8. 模板支持时，执行在线插件或类 FaaS 测试。
9. RL 正式训练前提交 debug 任务，除非用户明确接受跳过风险。
10. 提交正式任务后,**用 arkcli native 监控**(下一节"长任务监控")—— 不要在 python 里循环 `mcj.get`。

## 稳定规则

- 不硬编码超参表。针对所选模型和版本实时查询。
  ```bash
  ark get foundation-model --model <model-name> --version <model-version> --fields hyperparameters
  ```
- 除非当前 SDK 文档或模板明确允许，否则 `foundation_model` 和 `custom_model_id` 互斥。
- 本地数据路径尽量保持为项目内相对路径；生成模板通常按相对路径工作。
- RL 任务中，SDK 支持且有排障价值时设置 `enable_trajectory=True`。
- 不在代码、日志或最终答复中暴露 API key、AK/SK、token、endpoint JWT 或 Authorization header。优先使用环境变量或本地鉴权。
- 不凭记忆编造 SDK 类名或装饰器。名称不一致时，检查生成模板 import 和已安装的 `ark_sdk`。
- 不依赖本 skill 获取变化较快的支持矩阵。使用当前 SDK 输出、生成模板和官方公开产品文档确认。

## 常用命令

```bash
ark upgrade  # 会实际更新 SDK，先取得用户确认
ark login
arkcli auth login
arkcli train finetune sdk login
ark init workspace <workspace-dir> --template rl_demo
ark init workspace <workspace-dir> --template rl_search_mcp_demo
ark get foundation-model --model <model-name> --version <model-version> --fields hyperparameters
python job.py
ark create mcj -f job.yaml
ark create mcj --file job.yaml --debug
ark get mcj <mcj-id>
ark list mcj
ark pull mcj <mcj-id> --include-plugin
```

命令参数不确定时，优先执行 `ark <command> --help`。

## 长任务监控:回到 arkcli native

火山方舟的 SDK 鉴权使用短期 STS，默认约 30 分钟过期。提交完任务后不要在 Python 里实现无边界的 `while True: mcj.get(...)` 轮询，否则长任务会遇到鉴权过期。改用 ArkCLI native，由产品命令管理鉴权，并统一使用产品侧的状态、日志和指标查询：

```bash
arkcli train finetune watch <mcj-id>           # 阻塞到终态
arkcli train finetune get <mcj-id>             # 一次性查详情
arkcli train finetune metrics <mcj-id>         # 指标
arkcli train finetune logs <mcj-id>            # 日志
arkcli train finetune trajectory list <mcj-id> # RL 轨迹
arkcli train finetune artifacts list <mcj-id>  # 产物
```
