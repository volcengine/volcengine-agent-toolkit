# Changelog

## 3.0.8 - 2026-11-20

- 补齐工具和外部依赖声明，提供可直接安装的静态接口契约。
- 在分页和必要字段检查前统一请求参数别名，修正数组及嵌套对象 JSON Schema。
- 错误诊断统一脱敏，依赖检查不再读取凭证配置；查询继承已有 ve 地域设置。
- 移除未经兼容性验证的 ve 最低版本拦截；缺少 --force 时提示升级至支持该参数的版本。
- 保留查询和归因 JSON 金额精度；未知核销金额不补零，券适用性保留未知状态。
- 资源包按实际消费区间关联账期，已退款状态不解释为用尽。
- 对账校验输入产物配套关系，下钻守恒限制同步到摘要、CSV 和 metadata。
- 分离本地发布测试和独立运行测试，补充贡献修复回归用例。

## Unreleased

## 3.0.7 - 2026-11-12

- 新增[费用变化分析](references/cost-change-analysis.md)：按问题选择费用查询与三个归因接口，
  覆盖单账期分布/趋势、跨账期变化对象定位、金额项构成，以及用量、价格等驱动分析；
  `cost-query.md` 不再固定“解释费用变化”的逐级下钻步骤。
- 接入只读 `QueryCostChangeDimensions`、`QueryCostChangeAmountComponents`、
  `QueryCostChangeDrivers`：固定 `2022-01-01` 和 `--force` 调用，补充请求/响应契约、
  金额精度、覆盖范围和结果完整性校验，并增加契约、执行和精度用例。

## 3.0.6 - 2026-11-04

- 恢复财务关系“主/子相对视角，实际看 ID 判角色”的字段含义；有关系记录时，用同一凭证
  调用只读 STS GetCallerIdentity，按 AccountId 匹配 MajorAccountID/SubAccountID，在 message
  给出当前账号和角色。身份核验失败保留关系数据，当前角色不推断。
- 当前账号完整关系查询成功且结果为空时，明确说明没有财务关系；不额外查询身份。
  用户指定筛选或局部页时按对应范围说明空结果。

## 3.0.5 - 2026-11-04

- 修复 `ListFinancialRelation` 实测返回 `Offset=-1` 时误报分页不完整的问题；兼容仅作用于
  该接口，继续检查 Total、重复页和提前结束，分页矛盾错误补充请求值与响应值。

## 3.0.4 - 2026-11-04

- 新增财务托管与付费归属指引，区分财务托管、财务管理、主子账号视角和历史账单证据。
- 统一 schema/query 接入只读 `ListFinancialRelation`，沿用完整分页、partial 和字段契约输出；
  关系查询单页上限 100，不引入独立 SDK 或关系修改命令。

## 3.0.3 - 2026-10-20

- 删除对账和下钻的 `--allow-nonstandard-dimension` 参数及非标准维度确认拦截。
  Project/Tag 双侧分组、过滤和下钻直接计算，在 Agent 可见的 `message` 中说明语义限制，
  结论范围保留为 observational；不切换 mode，默认模式的来源、范围和完整性检查保持不变。

## 3.0.2 - 2026-10-19

- 对账 `ARTIFACT_INVALID` 明确说明当前没有有效双侧输入、尚未执行范围/维度/金额检查，并提供
  产物核对、重新导出和重跑 preflight 的恢复步骤；禁止据此推断 scope mismatch 或继续 run。
- Action 选择与响应解释补充账期、实例实际使用周期和成本分摊时间轴：未来使用时间不改变
  `BillPeriod` 出账归属，按实际使用日/月查看金额时使用分摊成本账单而非手工分配账单金额。
- 强化成功 artifact 复用、错误定向重试和下钻前读取父结果的约束，避免重复 full 查询、
  结论形成后的 discovery 以及本地路径错误触发远端重查。
- 将 scripts 中完全相同的参数错误处理、行字段读取、ISO 时间解析、Decimal 处理、字段路径归一化、
  Billing 分页常量和校验错误构造按类别收敛到 `cost_query/utils/`；删除未使用的重复输入加载函数。
- 接入公开只读 `ListCouponUsageRecords`，按 `CouponID` 使用 Limit/Offset 完整采集实际抵扣与
  退回记录，并屏蔽券所属账号和使用者账号字段。
- 代金券核查组合 `ListCoupons` 当前库存与适用规则、`ListCouponUsageRecords` 券级核销记录
  和 `ListBillDetail` 账单事实；后付费记录按 `SubBusinessID=BillDetailId` 关联，预付费记录按
  `SubBusinessID=BillID` 关联预付费账单。
- 账单抵扣变化、范围匹配候选券和券级核销汇总分层输出；移除固定
  `redemption_record_available=false`，不再把候选券 ID 绑定为账单抵扣下降的实际来源。

## 3.0.1 - 2026-10-14

- `_meta` 改为按结果类型最小投影，不再直接输出执行器内部对象；单对象 Action 不携带分页、
  Total、行数、分片、重试或固定 false/空字段。
- `QueryBalanceAcct` 的 stdout `_meta` 只保留协议版本、Action、账户判断、判断原因和最小
  余额核验；只有信控确实覆盖时才输出 `credit_covered=true`。显式导出仅增加 sidecar 引用。
- 设计文档和专项验收新增 `_meta` 字段消费依据与单对象最小化约束。

## 3.0.0 - 2026-10-14

- 所有任务执行命令统一输出 `status/message/result/_meta`；Agent 只使用前三个公开字段，
  `_meta.output_protocol_version=1.0` 保留分页、完整性、时效、失败范围和追溯证据。
- 移除公开 `delivery`、`data.rows`、`artifacts`、`completed/page_completed/provisional` 及
  `QueryBalanceAcct` 顶层原始字段/`tool_hint` 特例；小结果直接进入 `result`，文件结果使用
  `result.file`，账户对象与确定性结论分别进入 `result` 和 `message`。
- `partial` 继续使用退出码 6 并在 stdout 交付可用结果；所有可处理错误使用同一 stdout
  envelope，stderr 只保留诊断日志。JSON 严格拒绝 NaN/Infinity。
- 归因和对账消费者改为读取新 envelope、`_meta` 及 sidecar，不解析自然语言 message；
  查询、对账、资源包和代金券入口共享协议版本、错误出口和文件交付规则。
- 下线旧受控分析 runtime、模板、validator、legacy cost-rule 导出及专用测试/eval 路径；
  保留仍被直接数据处理使用的 Decimal、字段解析、币种分组、公开字段和原子写入 helper。
- 账户分析指引改为读取统一 `message/result`，移除 Agent 自行判断和公式核验步骤；
  `QueryBalanceAcct` 不增加原接口未返回的时间参数。
- 修复代金券与资源包跨期归因取首条基期记录的问题：按完整维度汇总两期全部账单明细，
  每组比较一次抵扣与应付总额，输出比较轴、分组维度和两期行数，结果不依赖输入行顺序。
- 缺失维度不再作为跨期匹配通配值；任一相关记录金额缺失或非法时阻止该组确定比较。
  资源包抵扣比较严格匹配消费对象、用量单位和消费时间，拒绝跨账期或多分组的歧义分配。

## 2.0.25 - 2026-10-13

- 修订查询、对账和欠费指引：补齐费用变化分析、两期抵扣数据准备与完整对账示例，
  独立路由普通未抵扣问题，并区分当前状态、关联变化和因果证据。
- 移除统一 CLI 的 `validate` 子命令及发布 smoke 调用，保留底层旧协议兼容模块和测试。
- 修正代金券归因命令注册名为 `coupon`，恢复文档中的调用入口。

- 接入 `coupon.json` 中公开只读 `ListCoupons`，支持状态、余额、有效期、付款方式、金额门槛、
  产品/配置/计费项范围和 Limit/Offset 全量采集。
- 新增 `cost.py coupon` 本地归因入口，支持代金券用尽、过期、未生效、显式候选不适用和
  账单侧抵扣下降；配置与计费项通配按 `ConfigurationType`/`ChargeItemType` 解释。
- `ListCoupons` 不提供独立核销流水；抵扣下降只从可比账单 `CouponAmount` 得出，输出显式
  保留该证据限制，不把库存查询描述为核销记录。
- 查询输出屏蔽代金券所属账号和指定 Owner ID 列表。

## 2.0.24 - 2026-10-13

- 接入 `package.json` 中公开只读 `ListResourcePackages` 和 `ListPackageUsageDetails`，支持
  NextToken 完整采集、页大小上限、重复 token/重复页和安全上限检查。
- 新增 `cost.py resource-package` 本地归因入口，基于资源包库存、抵扣明细和账单明细确认
  已用尽、已过期、未生效和抵扣下降；缺少匹配抵扣证据时返回证据不足。
- 资源包实例配置不再被误作适用范围；当前契约未声明“全部配置”“全部计费项”或计费模式
  通配字段，因此不据库存字段生成不覆盖结论。
- 资源包查询结果屏蔽账号名称、账号 ID 和服务主体等归因不需要的身份字段。

## 2.0.23 - 2026-10-13

- 新增公开只读 `QueryBalanceAcct` Action，支持通过统一 schema/query 查询当前账户资金快照；
  明确 `AvailableBalance < 0` 才表示账户欠费，`ArrearsBalance` 只表示当前欠费金额。
- 新增欠费分析指引，区分当前账户状态、已出账未还款金额构成和欠费原因三条路径；原因
  分析只使用已接入的账户与 BILL 证据，不迁移固定延迟、产品级欠费或未接入能力结论。
- 固化官方契约评审与脱敏真实响应 fixture；未声明的字段必返性、Currency 枚举和服务端
  快照时间保持开放语义，缺少权威字段时不生成欠费结论。
- 根入口开放账户欠费、余额为负、产品未还款构成和欠费原因路由；继续保持全流程只读，
  不执行充值、支付、购买、续费、退订、预算或资源操作。

## 2.0.22 - 2026-10-12

- 主入口统一任务路由、公共约束与结果核验；查询选型、执行、解释和分析原则合并为
  `references/cost-query.md`，标准对账保留在 `references/cost-reconciliation.md`。
- 通用分析按原则直接编写处理代码，保留金额精度、可比性、关联核验和来源限制；
  文件或复现需求不再强制接入受控分析模板、回调和 validate。
- 旧分析 runtime、模板和 validate 保持兼容，帮助与 describe 明确其旧协议范围；
  公共 helper 继续供现有执行器和数据处理代码按需使用。
- 查询、对账、字段契约、分页与结果协议保持，更新机器输出中的 reference 指针。

## 2.0.21 - 2026-09-18

- 明确金额展示和字段映射规则：查询值默认保留服务端原始十进制精度，且原价、折后价、
  应付金额、抹零金额必须分别使用对应响应字段，不再将两位小数的应付金额替代原价。
- 查询交付简化为 `inline` / `artifact` 两种模式：未指定 `--out` 且 compact
  `data.rows` 不超过 64 KiB 时直接内联且不写文件；超过 64 KiB、显式指定 `--out` 或
  结果为 `partial` 时写入 CSV、metadata 和 fields。取消 20 行限制和
  `inline_and_artifact` 双份交付。
- 收紧受控分析触发条件：普通查看、过滤、计数、求和、单层分组、排序和 TopN 默认直接
  处理 inline rows 或用短 Python 读取 artifact；行数、`full` 和普通聚合本身不再触发
  模板复制与校验。

## 2.0.20 - 2026-09-18

- `cost.py query` 默认启用自动交付：不传 `--out` 时将 CSV、metadata 和字段目录写入唯一
  的系统临时目录，并在 stdout 返回可直接读取的绝对路径。
- 自动交付结果同时不超过 20 行和 32 KiB 时在 stdout 返回完整 rows；超过任一阈值时
  stdout 不返回数据行，Agent 按 `artifacts.csv` 读取完整结果。
- 删除 `--output-format`、`--inline-field` 和 JSON 文件输出；stdout 固定为精简 JSON 执行
  清单；除筛选目录外，成功查询固定生成 CSV、metadata 和字段目录。筛选目录继续完整返回
  `data.catalog`。详细 coverage 只保留在 metadata。

## 2.0.19 - 2026-09-18

- 正式费用分析改用 `cost_query.analysis.run_controlled_analysis` 单入口：运行时统一完成字段
  解析、Decimal 金额、币种分组、公开字段投影、evidence 继承和产物写出，任务脚本在
  `analyze(ctx)` 中实现筛选、聚合、排序、TopN 与时间分析。
- 受控分析模板收敛为稳定上下文与 `AnalysisOutput`，校验器改为验证运行时入口及实际 CSV
  与 metadata 的行列一致性；缺少来源 metadata 时按 `input_file_only` 证据范围通过校验。
- `AnalysisContext` 新增字段解析、类型读取和原始字符串键接口，覆盖筛选、日期、普通数值
  与单 CSV 内自关联，同时明确双来源比较仍使用 `reconcile`。
- 分析运行时会先规范化并序列化完整 metadata，再暂存 CSV 与 metadata 后成对提交；提交
  失败时回滚新产物或恢复覆盖前产物，避免留下阻断安全重试的单边 CSV。
- 受控分析允许空 `metrics`，支持不涉及金额的计数、筛选、投影和正式导出。

## 2.0.18 - 2026-09-17

- 重新打包并覆盖安装当前费用查询 Skill，刷新本地安装包和 zip 分发归档。

## 2.0.17 - 2026-09-17

- Action 目录不再暴露 `query_shape`；一次性返回的 Action 由执行器自动识别。即使调用方
  传入 `--pagination`、`--page-size` 或 `--page-offset`，也只发起一次请求并返回完整结果，
  同时通过 warning 明确这些分页参数未生效。
- 受控费用分析模板新增显式 `--skill-root`，复制到任务目录后仍能加载 Skill 内公开规则；
  正式分析指引和离线门禁同步覆盖复制后的真实执行路径。
- 补回完整 response schema 的字段名发现入口，并明确 `response_field_decisions` 只对已登记
  粒度规则的字段返回；缺少该对象不等于服务端保证字段在任意粒度保留。
- 修正响应字段粒度规划：先按 `available_request_values` 验证候选请求并保留已合法的粒度，
  仅在候选值不合法时才将 `required_request` 用作修复补丁，避免把实例粒度机械覆写为
  计费项粒度。
- 明确双来源比较先检查已登记 Action Pair；未登记 Pair 不进入标准对账，由 Agent 根据
  可用 Action、字段契约和用户目标自主规划核验或 observational 分析。
- 正式费用分析要求先读取 `cost.py validate describe`，并以
  `templates/controlled_cost_analysis.py` 为单来源脚本基线，避免重复实现公开字段过滤、
  Decimal、币种分区、证据继承和 metadata。
- 统一当前期 provisional 对账语义：完整 full 结果继续正常对账；对已达首次
  Total 边界、仅因当前期 Total 漂移停止且无失败分片的受限 provisional 快照，
  preflight 返回 `warn` 并允许观察性计算；其他不完整结果仍 `block`。
- 将 T+2、分账与成本账单延迟等具体时效规则收敛到 `result-interpretation.md`；
  `SKILL.md` 只保留加载入口，`action-selection.md` 只保留会影响 Action 选择的结论。
- 删除没有独立执行路线的 `safety-and-scope.md`：只读与凭证约束保留在
  `SKILL.md`，金额、缺失值和字段推断规则归入结果解释，时间轴、分拆和关联键
  约束归入 Action 选择。
- 为 `ListBillDetail` 增加高风险响应字段的粒度保护：`Count/Price/PriceUnit` 仅允许
  计费项维度，`BillID/BillDetailId` 仅允许计费项明细，`InstanceNo` 不允许产品或账号
  维度；`--require-field` 会在远端查询前拦截不保留目标字段的组合。
- `cost.py schema` 的精确响应字段查询新增 `response_field_decisions`，直接返回首次查询
  所需的粒度参数；request schema 使用 `--include-guidance` 时公开预聚合建议和字段粒度
  矩阵，使 Agent 能在发起查询前完成字段保真决策。

## 2.0.16 - 2026-09-17

- 对客发布包改为携带单份静态 Billing 契约并使用标准库轻量校验，不再携带或依赖
  Pydantic；源码仓库继续保留 Pydantic models 作为开发态契约维护源。
- 发布门禁通过 `ve mcp` 对 10 个只读 Billing Action 做 metadata 更新发现和一致性检查，
  并在 `python -S` 环境验证安装包运行时不依赖第三方 site-packages。
- 从 Action 契约和 describe 输出中移除未参与运行逻辑的 `operation_type`、`auth_type`。

## 2.0.15 - 2026-08-27

- 重新打包并覆盖安装当前费用查询 Skill，刷新本地安装包和 zip 分发归档。

## 2.0.14 - 2026-08-27

- 重新发布当前费用查询 Skill 与公开工具契约，刷新本地安装包和分发归档。

## 2.0.13 - 2026-08-27

- 费用规则机器契约改由真实 Python 签名和类型生成，以轻量索引支持按公开函数或类型查询
  并自动展开传递依赖，补齐 `FieldRef` 属性、枚举、具名返回值、错误条件和最小组合示例。
- `load_cost_csv`、`load_cost_metadata` 和 `ensure_money_grouping` 返回可按属性访问且兼容
  tuple 解包的具名结果；输出 helper 的 `overwrite` 统一为默认关闭的仅关键字参数。
- 明确费用规则只控制 Decimal、币种、缺失、负数、字段暴露和 evidence 等底线；筛选、
  关联、分组、排序、TopN 和时间分析继续由 Agent 使用 Python 自由实现。

## 2.0.12 - 2026-08-27

- 当前月 full 查询达到首次 Total 边界后若 Total 变化或采集行数超过首次 Total，保持立即
  停止翻页，但改为成功的 `provisional` 结果；允许基于本次采集数据分析，同时明确不是
  最终账期全量。
- coverage 新增当前月漂移、停止原因和首次 Total 边界证据；受控分析继承
  `provisional_current_period` 范围，不再误标为分页失败。
- 当前月在达到首次 Total 前漂移、已关闭账期漂移及其他分页异常仍保持 `partial`。

## 2.0.11 - 2026-08-26

- 文件输出在任何 Billing 调用前预检主文件、metadata 和字段目录，输出冲突返回
  `remote_call_attempted=false` 与安全恢复动作，避免补 `--overwrite` 或换路径时重复查询。
- 查询执行参考和机器契约要求使用任务专属输出路径；`--overwrite` 只用于
  已确认由本轮任务拥有且允许替换的产物，不作为默认重试参数。

## 2.0.10 - 2026-08-26

- 重新发布当前 Skill 文档、评测门禁和查询执行契约，刷新本地安装包与分发归档。

## 2.0.9 - 2026-08-26

- Action 选择先从最终分析所需的最细粒度和字段反推数据源；层级聚合、分组内 TopN 和
  跨维度下钻优先使用保留维度关系的行数据 Action，避免误用多次单维度费用分析查询。
- 对账关系改为根据左右查询产物中的 Action 自动识别；机器契约提供分阶段参数清单，
  profile 中的关系文字明确为只读说明，不再暴露为 `relationship` 配置字段。
- `GetFilterInfoForCostAnalysis` 改为非分页一次性查询，默认在 stdout 返回结构化筛选目录，
  不生成 CSV；显式导出仍支持 CSV 或 JSON 文件。
- 新增层级账单分析和对账关系参数评测，并将筛选目录评测切换到非分页结构化输出。

## 2.0.8 - 2026-08-26

- 精简 Agent 面向的字段契约说明：主 Skill 和 Action 参考只描述 request/response 契约的
  使用时机、公开命令和业务语义，不再依赖 JSON Schema 容器路径、内部错误码或补丁键名。
- 调整字段粒度评测文案，验证 Agent 是否做出正确业务决策，而不是是否读取特定契约节点。
- 将主 Skill 中的对账章节收敛为入口判断和解释边界；Action Pair、执行阶段、Join、容差
  和下钻参数按需从对账 reference 与机器契约加载。
- 调整对账评测文案，验证标准工具选择、可比性检查和证据输出，不要求 Agent 复述内部
  Join 算法。
- 精简主 Skill 的受控 Python 说明：保留分析分级、财务约束、机器契约入口和校验要求，
  不再常驻 Python 包路径、函数名称、公共库职责或 metadata 内部结构。
- 调整费用分析 reference、评测和 release 断言，以机器契约作为模块路径、导入方式、
  函数名称与签名的唯一动态来源。
- 主 Skill 统一以“查询结果、字段目录和执行证据”描述查询产物，不再要求 Agent 预先
  理解 manifest、stdout 数据路径或 fields/metadata 挂载结构。
- 将精确查询产物结构集中到 query output 机器契约和查询执行 reference；结果解释、费用
  分析、对账 reference 与自然语言评测改用完整性、时效、告警、失败分片和证据范围语义。
- 主 Skill 的查询主路径只保留 `page` 与 `full` 对结论强度的影响；JSON inline、
  `Limit=1` 和具体结果载体留在查询执行 reference 与执行器校验中。
- 调整最小披露评测文案，验证按需读取契约、最小查询范围、字段最小披露和局部结论边界，
  不要求 Agent 复述 inline 的运输层实现。
- 合并主 Skill 中重复的回答规则：只披露会改变结论可信度的范围、完整性、时效异常、
  失败分片和非空告警；简单查询不再机械列出正常证据项。
- 详细回答结构继续由结果解释 reference 承担，并将完整分析中的告警和时效项明确为
  条件披露。
- 将主 Skill 顶部的契约复用说明压缩为同轮复用与重新查询两项行为边界；Action、字段、
  安装版本等刷新条件不再逐项枚举，详细边界继续由查询执行 reference 承担。
- 回补主 Skill 必须常驻的领域决策：Action 高层口径、当前月与 T+2/分账/成本时效、
  `PaidAmount` 和 `UnpaidAmount` 的正向业务含义。
- 明确单份结果的正式计算使用受控分析，两份账务来源的一致性、差异和下钻使用标准
  `cost.py reconcile`；同步移除费用分析 reference 中把对账归入受控脚本的冲突表述。

## 2.0.7 - 2026-08-26

- 澄清 JSON inline 使用边界：分页类 Action 主动使用 inline 时只允许有效
  `Limit=1`；需要多行结果时必须输出 CSV 或 JSON 文件，不使用 stdout inline。
- 从面向 Agent 的查询执行文档中移除 inline 运行时保护阈值等实现细节，避免误解为
  可选查询行数。

## 2.0.6 - 2026-08-26

- `cost.py schema --list-actions` 默认输出完整 Action 决策信息，包含
  `use_when`、`avoid_when` 和 `important_limits`；删除独立 `--verbose` 模式。

## 2.0.5 - 2026-08-26

- 发布当前费用分析文档与工具契约改动，刷新本地安装包。

## 2.0.4 - 2026-08-26

- 精修费用分析分层文案：简单一次性 CSV 分析只遵守自然语言费用底线，不强制
  `cost_rules` 或 `cost.py validate`；正式分析才使用 `cost_rules` helper 和
  `cost.py validate` 收口。

## 2.0.3 - 2026-08-26

- 进一步澄清费用分析分层：简单一次性 CSV 分析不强制使用 `cost_rules`，自然语言规则
  是第一层底线；正式分析、导出、复现、多步计算、跨期比较和对账才要求先读取
  `cost.py schema --section cost_rules`。

## 2.0.2 - 2026-08-26

- 修正 CSV 分析分层语义：简单一次性回答不强制导入 `cost_rules`，只要求 Decimal、
  币种隔离、缺失不当 0、保留负数，并说明只基于当前输入文件。
- 将 `cost.py schema --section cost_rules` 明确为正式分析、导出、复现、多步计算、
  跨期比较和对账前的 helper 发现入口，避免 Agent 猜测 `cost_rules.py` 函数。

## 2.0.1 - 2026-08-26

- 新增 `cost.py schema --section cost_rules`，作为费用分析 Python 代码可复用 helper
  的机器可读发现入口，避免 Agent 猜测 `cost_rules.py` 函数名。
- CSV 分析规则收敛为两档：简单一次性回答可用短 Python 管道，但必须使用 Decimal、
  按币种分组并说明只基于当前输入文件；正式分析、导出、复现、多步计算、跨期比较或
  对账必须使用受控脚本、保存结果和 metadata，并运行 `cost.py validate`。
- release smoke 和安装校验统一使用 `cost.py schema/query/reconcile/validate` 入口。

## 2.0.0 - 2026-08-26

- 明确费用处理原则：财务事实固定化、计算过程开放化、输出结论可验证；普通单表
  筛选、聚合、TopN、比例、透视、分桶和跨期差额不再优先扩展为私有 DSL。
- 新增公共 `cost_rules.py` 和 `validate_cost_analysis.py`，将 Decimal、币种隔离、
  空值、字段屏蔽、coverage/freshness/evidence 等费用规则提供给 Agent 生成的
  受控 Python/DuckDB/Polars 脚本调用和校验。
- 删除公开 `transform_cost.py` 和内部 `cost_query.transform` DSL 实现；单表费用分析
  改为受控脚本，字段目录继续由 `cost.py query` 查询产物提供。
- `cost.py reconcile` 不再复用 TransformPlan 执行器，改为模块内受控过滤、Decimal
  聚合和币种 Join Key 生成。
- `cost.py schema --field` 默认改为字段级最小响应：不再自动携带
  request `overview`、`preaggregation_guidance` 或 response `interpretation`；
  `GroupPeriod`/`GroupTerm` 等关键请求字段改由 `field_decisions` 提供可直接选值的
  短决策卡片。需要完整 Action 级背景时显式传 `--include overview`。
- 新增统一入口 `cost.py schema/query/reconcile/check`；`schema` 输出标准 JSON Schema，
  并把 Agent 决策和费用业务约束作为 overlay 返回。
- 修复 `reconcile_cost.py --help`，根命令现在按标准 CLI 习惯展示可用子命令。
- 将 Query Plan 规则拆成“内部必须形成计划”和“不要机械展示计划”：Agent 先自行规划、
  执行最小足够查询，再根据结果决定是否继续 full、受控分析、对账或请用户确认；用户要求
  过程、计划、口径或复现方式时，再自然说明实际执行链路。
- 将结果回答要求分层：普通查询只交代结论、Action/筛选、查询范围和必要 warning；
  正式分析、导出、对账和可复现产物继续保留完整 coverage、freshness、币种和产物路径说明。
- 简化 frontmatter description：只保留 Skill 触发所需的费用查询/分析意图，移除
  page/full、JSON inline 等执行实现细节。

## 1.9.2 - 2026-08-21

- 公开 CLI 的 JSON stdout/stderr 默认改为单行输出；`--compact` 保留为隐藏兼容参数，
  不再出现在 Skill 示例或机器契约中。
- 将字段能力矩阵从 `Action × Field` 补齐为 `Action × GroupPeriod × GroupTerm × Field`；
  response describe 和 fields artifact 统一输出 `grain_availability`。
- `ListSplitBillDetail` 的 `BillID`、`BillDetailId`、`SplitBillDetailId`、`SplitItemID`
  以及 `ListBillDetail.BillDetailId` 登记为明细标识，明确要求 `GroupPeriod=2`。
- `query_billing.py` 新增可重复的 `--require-field`。当用户要求的字段不会被当前粒度
  保留时，在调用 `ve billing` 前返回 `RESPONSE_FIELD_NOT_PRESERVED` 和请求补丁，避免
  先查一次 full 汇总再重查明细。
- 汇总粒度产物中的粒度敏感字段标记为 `not_preserved` 并生成 warning；字段为空或缺失
  只表示服务端汇总未保留，不能解释为业务上没有分拆项或明细记录。
- 强化 `transform_cost.py --filter` 的使用契约和错误恢复提示：`FIELD OP VALUE` 必须
  是三个独立 CLI 参数，不要写成 `--filter 'FIELD OP VALUE'`。
- 删除独立的“轻量直读”步骤和 20 行硬阈值，将“小结果直接读 CSV”的原则收敛到
  Transform 前置判断，减少 Agent 的额外决策路径。
- 增加同轮契约复用规则：已加载的 `tool + section + Action + field` 契约片段直接
  复用，避免 Agent 在同一轮机械重复调用 describe。
- 将字段目录重建入口并入 `transform_cost.py describe --section fields --input <csv>`，
  移除独立 `describe-fields` 子命令，统一 describe 模式。

## 1.9.1 - 2026-08-21

- 收紧对账差异解释边界：对账不平只报告差异、完整性和时效证据，不根据
  `BillingMode`、计费项、Project/Tag 或单侧缺失记录推断业务根因。
- 明确账单和账单明细是金额对账依据；分账账单用于费用归属参考，不作为账单金额
  对账依据。账单明细与分账明细不平时，只能提示可能受数据时效、分账生成延迟或
  归属更新延迟影响，确需确认原因或修正归属建议提工单。
- `reconcile_cost.py` 的机器契约和 metadata 新增 mismatch interpretation 规则，
  防止 Agent 把分账差异解释为某计费模式“不参与分账”。

## 1.9.0 - 2026-08-21

- 新增 `reconcile_cost.py preflight/run/drill-down/describe`，把高频跨文件对账从受控
  Python fallback 提升为可发现、可审计的标准能力。
- 首版登记产品总览<>账单、账单<>账单明细、账单明细<>分账明细三组关系；复用
  TransformPlan 做双侧公共 Filter 和聚合，按 Currency 隔离后执行唯一 Key FULL OUTER JOIN。
- 支持应付金额、原价、节省计划抵扣原价、优惠金额和折后价五个 Decimal 指标，
  tolerance 固定为 0，输出 matched/mismatched/left_only/right_only/inconclusive。
- Project/Tag 双侧比较要求显式确认并降级为 observational；推荐先按实例等共同出账
  维度对账，再在分账侧作为 attribution breakdown 展开。
- 新增守恒式 drill-down：继承父级来源、筛选、指标和口径，按更细维度重新聚合，
  强制校验子项左右金额分别回卷到父级。

## 1.8.13 - 2026-08-20

- JSON inline 默认改为最小披露：不传字段时只返回 `has_data/row_count`；重复
  `--inline-field` 返回指定公共字段，显式 `--inline-field '*'` 才返回完整公共行。
- inline 投影只裁剪 stdout，不改变 API body、coverage、row_count、JSON/CSV 文件或
  metadata；输出携带 projection mode、请求/解析字段和作用域标记。
- 三个公开 CLI 支持单行 JSON 输出。
- field-scoped request describe 不再返回 capability 和完整 optional fields，只保留目标
  字段、必填字段、相关条件规则及必要的预聚合 guidance。
- Skill 正常路径改为 compact + 显式 section，不再鼓励加载 query/transform 全量契约。

## 1.8.12 - 2026-08-20

- 将 `BillPeriod`、`AmortizedMonth`、`AmortizedDay` 等时间范围约束写入
  Pydantic 字段 metadata，由 `describe_billing_api.py` 输出机器可读的
  `date_format`、`max_age_months`、`min_month` 和 `min_date`。
- `validate_request_body()` 改为从结构化契约统一校验时间范围，拒绝超过最近
  24 个月的账期/分摊月，并继续保留成本账单最早 `2023-04` / `2023-04-01`
  下界。
- 收窄“最新”数据说明：`ListBillDetail` 只表示查询最新可获得的已出具账单明细，
  任何 Action 都不保证账户或资源的实时费用。
- 将 `ListBill` 适用场景中的“欠费/结清状态”改为“已出账未还款金额/账单结算状态”，
  避免和禁止处理的账户实时欠费能力混淆。
- 修正 TagKV 提示病句、上游契约描述中的 `1忽略` 缺冒号和“恒本单元”错字。
- 将“按天比”统一为“日环比/指定日期对比”，并明确 JSON inline、JSON 文件和 CSV
  fields artifact 的回答差异。

## 1.8.11 - 2026-08-20

- 将独立的 `list-bill-detail-preaggregation.md` 合并到 `action-selection.md` 的
  “ListBillDetail 服务端预聚合与字段保真”章节，减少文件和跳转。
- `request.overview.preaggregation_guidance` 保持不变，只把 `details_reference` 指向
  合并后的文档及章节；高频路径仍不增加工具调用。
- 修正 Skill 主文中的字段示例：`ListBillDetail` 用量响应字段是 `Count`，不是
  `Measure`。

## 1.8.10 - 2026-08-20

- `transform_cost.py` 新增 `compare-periods` 子命令，标准化同比、环比、日环比和指定日期对比等
  双时间桶费用对比，不再要求 Agent 为该高频场景现场编写 Python。
- `compare-periods` 支持显式 previous/current，或在输入 CSV 恰好只有两个时间值时
  自动选择较早值为 previous、较晚值为 current；支持 `TimeStr`、`BillPeriod`、
  `ExpenseDate`、`AmortizedMonth`、`AmortizedDay` 等实际存在的时间桶字段。
- 输出固定包含 current/previous、delta、delta_rate、abs_delta、
  delta_contribution_rate 和 presence，并继承输入 metadata 的 coverage/freshness
  证据；金额字段存在币种列时自动按币种隔离。

## 1.8.9 - 2026-08-20

- 撤回独立 `planning` section，把 `ListBillDetail` 的 4 条高频预聚合建议和 10 个
  核心响应概念并入现有 `request.overview.preaggregation_guidance`；一次 request
  describe 即可完成高频组参，不增加工具调用和公开模式。
- 去掉对外 profile 名，改为直接返回 `when + request_patch + tradeoff`；提示仍是字段
  保真建议，不承诺服务端每行一定返回非空字段。
- 新增 `references/list-bill-detail-preaggregation.md` 承接完整合法组合、快照语义、
  服务端/本地聚合取舍和长尾字段处理。
- `RESPONSE_FIELDS_IN_REQUEST_BODY` 的恢复建议改为指向同一次 request contract。
- 核心概念映射以当前精确响应契约为准：`ListBillDetail` 用量字段是 `Count`，不是
  `Measure`；后者在该 Action response contract 中不存在。

## 1.8.8 - 2026-08-20

- 为 `ListBillDetail` 新增唯一的显式 `--section planning` 紧凑决策卡，固定 4 个高频
  模板、1 条日粒度修饰规则和 10 个核心概念；默认 `all` 不携带 planning，其他
  Action 不提供该 section，避免模式和输出膨胀。
- planning 只提供字段保真与聚合取舍提示，不是请求参数，也不承诺服务端每行字段；
  长尾继续使用原有 request/response 契约。
- `ListBillDetail` body 出现 `Usage`、`UnitPrice` 等响应字段或常见误写时，返回
  `RESPONSE_FIELDS_IN_REQUEST_BODY` 和 `Measure` / `Price` 等修正建议；不自动改写、
  不自动重试。
- 新增第 16 条可执行 eval，锁定 planning 的体积、模板数、概念数和恢复行为。

## 1.8.7 - 2026-08-20

- 补充 `PayerID` 统一业务语义：表示账单还款对象和资源支付结算账号；财务托管下
  为托管主账号，代销/代售下为伙伴账号。
- 补充 `BusinessMode` / `BusinessModeCode` 枚举：0 普通业务、1 财务托管、
  2 代销业务、3 代售业务、4 财务管理、5 代买业务。
- 补充 `OriginalOrderNo`、`SettlementType`、`InstanceNo`、`InstanceName`
  的字段解释，并同步 describe 输出与 Transform 字段目录。
- 保留 `ListBillDetail` 响应字段 `ExpenseDate` 的单日查询与天维度性能提示。

## 1.8.6 - 2026-08-20

- 将 15 条自然语言 eval 绑定为可执行离线 verifier，真实执行三个公开 CLI 并校验
  契约、退出码、coverage、字段语义和产物；明确该门禁不替代 Agent 宿主回答评分。
- 修正 eval 15 的错误字段预期：要求拒绝或纠正 `ProductName`、`OriginalAmount`、
  `DiscountAmount`，再使用真实字段加载响应契约。
- 发布流程改为单测 + 可执行 eval + 临时包清单/hash + 解压 smoke 全通过后原子替换
  正式 `.skill`，失败时保留旧 dist。
- 新增 `TODO.md` 记录暂缓的冷启动/preflight 工作，本版本不实现该能力。

## 1.8.5 - 2026-08-20

- 所有查询分片均失败且没有合法响应时，在写产物前直接向 stderr 返回结构化错误，
  不再生成可被误用的空 CSV/JSON、fields 或 metadata。
- 同因失败沿用具体错误码，异因失败使用 `ALL_QUERIES_FAILED`；成功空结果和部分成功
  的原有语义保持不变。
- 错误中保留经过脱敏、限长的 ve billing 原生 stdout/stderr、进程退出码、远端
  code/message 和 request ID，补充 refresh/session token 与 `ve login` 认证错误识别。

## 1.8.4 - 2026-08-19

- `VeBillingClient` 兼容 ve CLI 在 stdout JSON 前输出的非结构化诊断文本：
  先尝试纯 JSON 解析，失败后从第一个 `{` 开始解析后续 JSON object。
- 非零退出码语义保持不变：能解析到 JSON 时继续按远端错误处理，无法解析时再用
  stderr/stdout 生成调用错误；退出码为 0 但没有 JSON object 时仍返回
  `RESPONSE_INVALID`。
- ve CLI 参数改为当前标准写法 `--region` / `--profile`。
- 补充回归测试覆盖前置诊断文本和无 JSON 成功 stdout 两个场景。

## 1.8.3 - 2026-08-19

- 补充 Transform 前的轻量直读判定：小结果集、简单存在性/字段查看/少量列举问题
  直接读取原始 CSV、metadata 和已有 fields artifact 回答。
- 收窄 Transform 触发条件：大结果集筛选、批量投影、金额聚合、分组排序 TopN、
  多币种处理、字段口径歧义或需要可复现加工产物时才优先使用。
- 明确 manifest 已提供 `artifacts.fields` 时复用该文件，不为查看字段或 Transform
  重复运行 `describe --section fields`。

## 1.8.2 - 2026-08-19

- 修正核销字段 BILL 维度范围：`ListBill`、`ListBillOverviewByProd`、
  `ListBillOverviewByCategory` 均保留 PaidAmount、UnpaidAmount、
  CreditCarriedAmount。
- 继续屏蔽费用分析、账单明细、分账账单和成本账单中的核销字段及其
  Amortized 字段族。
- 同步恢复两个 Overview Action 的动态响应契约、CSV/JSON、fields artifact 和
  Transform 可见性，并补充回归测试。
- 修复 `describe_billing_api.py describe` 重复 `--field` 只处理最后一个值的问题；
  现在返回全部命中字段，并在错误中一次列出所有真正缺失的字段。

## 1.8.1 - 2026-08-19

- TagKV 请求筛选改为本地强校验：每一项必须同时提供非空 `Key` 和 `Value`，
  否则在调用 `ve billing` 前返回 `INVALID_ARGUMENT`。
- TagKV 动态契约说明补充 Key/Value 成对要求；只知道标签键时不能构造只有 Key
  的 TagKV。
- `GetFilterInfoForCostAnalysis` 文档补充其可发现账号、产品、项目、标签键等筛选
  候选值；`TagKeyList` 只表示标签键，不返回标签值。

## 1.8.0 - 2026-08-19

- TransformPlan 新增 COUNT 与 AVG，CLI/JSON Plan 共用同一执行语义。
- `count:*` 统计过滤后行数；`count:<field>` 统计非空值数量。
- AVG 仅接受数值字段，忽略空值，使用 Decimal + ROUND_HALF_EVEN，最多保留
  6 位小数；金额 AVG 自动按币种隔离。
- COUNT(*) 对空输入返回 0；SUM/AVG 全空保持空并 warning。
- P90/P95 本期不实现；后续以通用 percentile(field, p, method) 扩展，并先固定
  百分位算法、插值、空值、精度与小样本口径。

## 1.7.0 - 2026-08-19

- 将 TransformPlan 定位为高频费用处理的标准路径，而非 Agent 唯一计算能力。
- 当前计划无法表达 AVG/COUNT、派生列、比例、同比/环比、窗口、透视、分桶、
  Join 或跨文件对账时，允许受控 Python 回退。
- 回退必须说明 DSL 缺口，复用 CSV/metadata/fields，并继承 Decimal、币种隔离、
  coverage、freshness、字段屏蔽、evidence 和可复现产物要求。
- 明确不再设计一门通用文本 DSL；保留结构化 TransformPlan 为稳定计划协议，
  未来可按需要替换为 DuckDB、Polars 或 Ibis 执行引擎。

## 1.6.3 - 2026-08-19

- 调整 artifact 复用策略：只默认复用同一任务内刚生成的 completed/page_completed
  产物，避免同一轮重复 full 查询。
- 明确跨任务或历史产物不能默认代表当前数据；用户要求最新/当前数据时应重新查询，
  或先确认用户接受旧产物。

## 1.6.2 - 2026-08-19

- 收窄 JSON inline 的 Agent 使用策略：仅用于不计划继续 full 查询的轻量确认、
  排障样本和 `Limit=1` 小结果。
- 明确已计划 full 查询时不要先跑 inline probe；字段结构应通过
  `describe --section response --field <Field> --expand` 或 fields artifact 获取。

## 1.6.1 - 2026-08-19

- `describe_billing_api.py describe --section response --field <nested> --expand`
  会返回命中字段及其后代字段，便于 Agent 一次拿到嵌套响应字段。
- `ListCostAnalysisOpenApi` 响应解释新增 `flattening`，明确
  `CostData[].Costs[]` 会展开为输出行，`Amount` 是金额字段，`TimeStr` 是时间字段。

## 1.6.0 - 2026-08-19

- 费用分析明确为账单明细出具后 T+2 日更新；用户要求最新数据时禁止选用。
- `ListCostAnalysisOpenApi.CostType` 屏蔽现金支付口径 3/7，只支持
  0/1/2/4/5/6。
- 核销字段收敛到 `ListBill`：其他 Action 的动态响应契约、CSV/JSON 输出和
  fields artifact 均屏蔽 PaidAmount、UnpaidAmount、CreditCarriedAmount 及其
  Daily/Now/Before/Unamortized 等字段族。
- 线上响应仍返回旧字段时保持前向兼容：查询正常完成、字段静默剔除，不产生
  warning，也不把它们降级为 unknown 字段。

## 1.5.1 - 2026-08-19

- `ListCostAnalysisOpenApi` 不再使用 11 条的特殊 Limit；默认页大小与其他分页
  Action 统一为 300。
- 本地请求校验放宽为 `ListCostAnalysisOpenApi.Limit` 取值 1 到 300。

## 1.5.0 - 2026-08-19

- CSV 查询自动生成 `<out>.fields.json`，并通过 stdout/metadata 的
  `artifacts.fields` 暴露给 Agent。
- 新增 Action 字段语义目录：结合响应契约和维护表输出 label、aliases、role、
  type、aggregations、currency_field、description 和 notes。
- 字段目录只投影当前 CSV 实际表头，避免 Agent 选择文件中不存在的字段。
- 新增 `transform_cost.py describe --section fields --input <csv>`，支持外部 CSV 或缺失产物
  时重建字段目录。
- aliases 只作为 Agent 候选知识，不自动解析整句 Query；歧义金额口径仍由 Agent
  结合上下文或询问用户。
- 未知线上字段在 fields artifact 中标记 unknown，不 warning、不失败、不猜含义。

## 1.4.0 - 2026-08-19

- `query_billing.py` 新增 `--output-format csv|json`，默认仍为 CSV。
- 支持 JSON inline 输出：不传 `--out` 时把小结果写入 stdout 的 `data.rows`。
- JSON inline 仅用于试探性查询、小结果决策和查条数；分页类 Action 必须使用
  `page` 且有效 `Limit=1`。
- JSON inline 行数硬限制为 100，超过时拒绝并提示改用 JSON 文件或默认 CSV。
- 用户明确要求 JSON 文件时支持 `--output-format json --out result.json`，并继续
  生成 metadata。

## 1.3.0 - 2026-08-19

- `scripts/` 按 `common`、`billing`、`transform` 三个能力域重组，顶层三个 Agent
  入口保持不变。
- Transform 内部拆分为 fields、models、engine、artifacts 和 contract，消除计划
  校验、计算与文件 I/O 混杂。
- 新增 `query_billing.py describe [--section ...]` 执行器契约，覆盖输入、page/full、
  多账期、重试、输出、错误和示例。
- 查询执行契约只描述执行层，Action body 继续以 `describe_billing_api.py` 为唯一
  事实源。
- SKILL.md 收敛为 Agent 主流程、资源路由、回答要求和安全原则；references 保留
  选型、示例、业务语义与限制。
- 两个 Tool contract 与 SKILL 共享 release 版本，并新增结构、链接、契约和打包
  一致性验证。

## 1.2.0 - 2026-08-19

- 新增 `transform_cost.py describe [--section ...]` 机器可读 Tool 契约。
- 契约覆盖输入参数、字段解析、select/SUM、filter、group/order/limit、
  TransformPlan、输出、证据、错误和 Agent 调用示例。
- 支持按 section 加载，避免 Agent 为简单任务读取整份契约。
- filter 提供单一、稳定的操作符集合：
  `eq/ne/in/not-in/gt/gte/lt/lte/between/contains`。
- 明确 reference 同样面向 Agent，用于复杂示例、口径解释和能力限制；精确调用
  以版本化机器契约为准。

## 1.1.0 - 2026-08-19

- 新增独立 `transform_cost.py` CSV DSL。
- 支持 CLI DSL 和 JSON TransformPlan，共用同一执行器。
- 支持 raw API 字段名与 canonical snake_case 别名。
- 支持 select、filter、Decimal SUM、group by、order by 和 limit/TopN。
- 金额聚合自动按币种隔离；空值不视为 0。
- metadata 改为可选证据输入，不再作为单文件计算前置条件。
- 数据输入仅支持 CSV，不支持任意 JSON/JSONL 数据。

## 1.0.0 - 2026-08-18

首个 release：

- 支持 10 个公开只读 Billing Action 的能力发现、选型、请求/响应契约加载。
- 支持请求 Pydantic 校验和跨字段业务校验。
- 支持 page/full 两种显式查询范围。
- Agent 可通过 body 或 CLI 指定 Limit/Offset；值冲突时明确拒绝。full 模式
  从 Offset=0 开始并使用 NeedRecordNum=1，page 模式保留单页查询意图。
- full 模式支持 Offset/Limit、Total、空页、重复页、提前结束、Total 变化和
  安全上限检查。
- 支持多账期独立查询，单个失败不阻断其他账期。
- 仅对限流和超时做有限指数退避重试。
- 输出 CSV、metadata、coverage、freshness、warning 和 failed queries。
- 响应前向兼容：未知新增字段原样保留，已知字段类型继续严格校验。
- `ListCostAnalysisOpenApi.CostType` 支持 0–3 账单口径和 4–7 成本账单口径。
