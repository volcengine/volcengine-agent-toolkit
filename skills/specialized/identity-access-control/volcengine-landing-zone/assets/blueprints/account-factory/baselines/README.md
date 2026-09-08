# Account Factory Baseline Packages

本目录保存 `Account Factory` 的内置 baseline package。每个 package 都是一个固定目录、
可直接复制到 workspace 里执行的 Terraform baseline 单元。agent 负责读取 baseline
执行计划、解析输入、排执行顺序，并串行 apply 这些 package。

## 设计原则

- baseline 文件描述的是“执行计划”，而不是 Terraform `module {}` 装配
- 内置 baseline package 放在 `assets/blueprints/account-factory/baselines/`
- workspace 中的自定义 baseline 与内置 baseline 使用同一种 package 模型
- source 解析只按目录查找：先看 workspace 下的 `account-factory/baselines/`，找不到再回退到内置目录
- agent 负责选择 package、解析变量、排执行顺序、逐个 apply，并在
  `account-factory/runs/<run_id>/` 下记录状态
- 每个 package 自己声明 provider、变量和输出，不依赖额外的顶层 root 注入

## 当前内置 Package

- `network-cross-account-connectivity`

## 执行模型

对于一次账号工厂 run，agent 会：

1. 先在 `account-factory/runs/<run_id>/account-create/terraform/` 中执行账号创建，并把账号输出写回同一个 run 的上下文
2. 读取 `*.baseline.json` 执行计划
3. 解析出最终启用的 baseline package 列表
4. 根据 `depends_on`、`order` 和声明顺序生成串行执行计划
5. 将每个 package 复制到
   `./volcengine-landing-zone-workspace/account-factory/runs/<run_id>/baselines/<baseline-name>/terraform/`
6. 为每个 package 写入 `terraform.tfvars.json`
7. 依次执行 `terraform init / plan / apply`
8. 将每个 package 的输入、输出、状态和报错写入同级 `status.json`

## Package 契约

每个 baseline package 至少应包含：

- `README.md`
- `versions.tf`
- `providers.tf`
- `variables.tf`
- `main.tf`
- `outputs.tf`

对于以成员账号为目标的 package：

- package 通过运行时环境变量提供 Terraform 底座凭证
- 所有 Terraform 资源直接使用 package 内定义好的 provider
- `local-exec` 从当前 `ve` 登录态出发，显式执行 `AssumeRole` 切到目标成员账号，再写隔离临时 CLI home 并显式 `--profile` 调用 `ve`

对于以管理账号为目标的 package：

- package 直接使用当前运行时环境变量对应的 Terraform 身份
- `ve` CLI 动作直接使用当前登录态
- 如果需要跨账号访问，必须在 package 内显式处理，而不是依赖外层模板接线

## 扩展 Baseline

- 客户新增 baseline 时，应在 workspace 下创建
  `./volcengine-landing-zone-workspace/account-factory/baselines/<baseline-name>/`
- 自定义 baseline 与内置 baseline 使用同一种 package 结构，进入 run 目录后不再区分来源
- 每个新增 package 至少应包含本页列出的六个 Terraform 文件，并在自己的 `README.md` 中写清用途、最低输入、主要输出、前置条件和失败排查提示
