"""把 Billing 原始契约投影为适合 Agent 决策和组参的语义视图。

静态 Action 契约仍是字段、类型和约束的事实源。本模块只补充接口选型、
字段含义、枚举、缺省行为和条件依赖，不改变原始 API 契约。
"""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Sequence

from .schema import ApiActionSpec, ApiElementSpec, ApiRequestParamSpec
from .preaggregation import list_bill_detail_preaggregation_guidance
from .field_grain import action_field_grain_guidance, field_grain_guidance


ACTION_GUIDANCE: Mapping[str, Mapping[str, Any]] = {
    "QueryCostChangeDimensions": {
        "title": "费用变化维度定位",
        "purpose": "定位两个账期应付金额变化主要集中在哪些对象，返回总差额和候选贡献。",
        "use_when": ["解释应付增减主要来自哪些产品、计费项、实例、地域或项目"],
        "avoid_when": [
            "只查单期金额、趋势或分类分布时按需使用 ListCostAnalysisOpenApi",
            "日级或当前月同期比较；本接口只接受月账期",
            "已知计费项且只问金额项或原价因子变化时直接选择对应归因接口",
        ],
        "data_grain": "两个账期 × 指定范围 × 一个定位维度",
        "result_kind": "cost_change_analysis",
        "important_limits": [
            "CurrentPeriod/BasePeriod 为 YYYY-MM-01；CandidateDimensions 仅传一个维度。",
            "Metric 固定为 3（应付）；不得与 CostType 的编码混用。",
            "非分页，候选列表及其覆盖率不证明全部费用对象都已覆盖。",
            "不向请求添加账号身份；Filters 保留已有 product/project/region_code/instance_no/charge_item_code 范围。",
            "按需读取 references/cost-change-analysis.md；无需先跑其他归因接口。",
        ],
    },
    "QueryCostChangeAmountComponents": {
        "title": "计费项金额构成变化",
        "purpose": "解释指定计费项两账期应付变化涉及的原价、优惠、退款等金额项变化。",
        "use_when": ["已知计费项，分析哪些金额项发生变化"],
        "avoid_when": [
            "单账期完整金额构成；应按可用账单字段查询汇总",
            "未知计费项；先按已有范围定位或补齐必要信息",
            "只问用量、单价驱动；选择 QueryCostChangeDrivers 并明确原价口径",
        ],
        "data_grain": "两个账期 × 指定计费项及筛选范围 × 金额项",
        "result_kind": "cost_change_analysis",
        "important_limits": [
            "CurrentPeriod/BasePeriod 为 YYYY-MM-01，Metric 固定为 3（应付）。",
            "Filters.charge_item_code 必填，保留其他范围筛选；无需固定先查产品。",
            "非分页，candidates 保留嵌套金额项；不得将原价、折后价等阶段金额直接相加。",
            "仅解释实际返回的金额项，不假设结果为完整构成。",
            "按需读取 references/cost-change-analysis.md。",
        ],
    },
    "QueryCostChangeDrivers": {
        "title": "计费项原价驱动因子分析",
        "purpose": "分析指定计费项原价变化的用量、单价及其他因子贡献。",
        "use_when": ["已知计费项，分析原价变化是否由用量、价格或其他因子驱动"],
        "avoid_when": [
            "将原价因子贡献直接当作应付或摊销成本变化贡献",
            "缺少计费项，或仅问变化对象、费用排行或趋势",
            "分析单账期构成或日级同期变化",
        ],
        "data_grain": "两个账期 × 指定计费项及筛选范围 × 驱动因子",
        "result_kind": "cost_change_analysis",
        "important_limits": [
            "current_period/base_period 为 YYYY-MM-01；保留 snake_case 请求字段。",
            "Metric 固定为 original_bill_amount，filters.charge_item_code 必填。",
            "非分页，contributions 保留因子及其贡献金额，不跨口径累计。",
            "无需先执行金额构成接口；依据用户问题和已有证据直接选用。",
            "按需读取 references/cost-change-analysis.md。",
        ],
    },
    "ListFinancialRelation": {
        "title": "财务托管与主子账号关系",
        "purpose": "查询当前身份可见的财务关系，核对关系类型、状态、主子账号视角和统一结算方。",
        "use_when": [
            "用户询问是否财务托管、谁替当前账号付账或主账号关联哪些成员",
            "余额和信用额度为零但仍能使用，需要核实是否由托管主账号结算",
        ],
        "avoid_when": [
            "只查询余额或当前是否欠费；使用 QueryBalanceAcct",
            "仅查询某账期费用或实际支付金额；使用对应账单 Action",
            "重建历史关系或证明资源当前可用；本 Action 不提供这些证据",
        ],
        "data_grain": "一条主子账号财务关系",
        "result_kind": "financial_relation",
        "important_limits": [
            "使用 Limit/Offset 分页，单页上限 100；确认完整关系范围使用 full。",
            "响应 Offset 可能为 -1；执行器按请求偏移分页，保留 Total、重复页和提前结束检查，不据此判断关系为空。",
            "AccountIDSearchList 是对方账号筛选；Relation/Status 请求使用字符串数组，响应使用整数编码。",
            "RelationDesc 区分财务托管与财务管理；前者主账号统一结算，后者各账号独立结算。",
            "Filiation/FiliationDesc 是主子相对视角；实际按同一凭证核验的 AccountId 匹配 MajorAccountID/SubAccountID，不从主或子文字推断当前角色。",
            "有关系记录时执行器调用同一凭证的只读 STS GetCallerIdentity，message 给出已核验账号及匹配角色；身份核验失败时明确角色无法确认并保留关系记录。",
            "无筛选的完整关系查询成功且结果为空时，直接说明当前账号没有财务关系，无需额外身份核验；有筛选或局部页时说明对应范围内没有记录。",
            "没有 BillPeriod、NeedRecordNum 或金额；UpdateTime 不等于关系生效时间。",
            "未知状态不推断是否生效，当前关系不能证明历史账期付费归属或资源可用性。",
            "按需读取 references/financial-relations.md；AuthInfo 不进入关系查询输出。",
        ],
    },
    "ListCouponUsageRecords": {
        "title": "代金券实际核销与退回记录",
        "purpose": "按代金券 ID 查询实际抵扣和退回记录，并按账期、商品或关联业务单核实核销事实。",
        "use_when": [
            "核实指定代金券是否实际发生抵扣或退回",
            "比较指定代金券本期与基期的实际抵扣金额",
            "用 SubBusinessID 关联账单：后付费匹配 BillDetailId，预付费匹配预付费账单的 BillID",
        ],
        "avoid_when": [
            "查询代金券当前余额、有效期或完整适用范围；这些信息使用 ListCoupons",
            "尚未取得 CouponID 时遍历核销记录；该 Action 要求 CouponID",
            "仅凭同账期核销记录认定用户所问的具体账单已被该券抵扣",
        ],
        "data_grain": "一张代金券 × 一次抵扣或退回事件",
        "result_kind": "coupon_usage_record",
        "important_limits": [
            "CouponID 必填；使用 Limit/Offset 分页，默认每页 10，接口上限 1000，准确汇总使用 full。",
            "ChangeType=2 表示抵扣，ChangeType=3 表示退回；两类非负金额分别汇总，负值不取绝对值并视为方向证据不足。",
            "PayType=post 时 SubBusinessID 匹配 ListBillDetail.BillDetailId；PayType=pre 时是订单号，匹配预付费账单的 BillID。",
            "记录提供 ProductCode 和 PayType，不提供券余额、有效期或计费项适用规则。",
        ],
    },
    "ListCoupons": {
        "title": "代金券库存、状态与适用范围",
        "purpose": "查询代金券状态、余额、有效期、付款方式、金额门槛以及产品/配置/计费项适用范围。",
        "use_when": [
            "查询代金券状态、余额、有效期或适用范围",
            "用户明确询问某张代金券为什么未抵扣",
            "核实代金券是否未生效、已失效、已使用、已作废或不适用",
            "账单 CouponAmount 下降或目标消费没有代金券抵扣时，定位候选券并核对库存与适用范围",
        ],
        "avoid_when": [
            "只查询普通账单或账户状态",
            "只问单张券状态时无目标范围地遍历全部代金券；用 CouponID 定位",
            "仅凭代金券库存解释某笔消费为何未抵扣",
            "查询实际抵扣或退回记录；使用 ListCouponUsageRecords",
        ],
        "data_grain": "一张代金券",
        "result_kind": "coupon_inventory_and_scope",
        "important_limits": [
            "使用 Limit/Offset 分页；契约未声明最大 Limit，默认每页 10，准确归因使用 full。",
            "Status：1 待生效、2 生效中、3 已失效、4 已使用、5 已作废。",
            "ProductLimitList.ConfigurationType=1/2/3 表示全部配置/全部预付费配置/全部后付费配置；4 才比较指定配置。",
            "ChargeItemType=0 表示全部计费项；1 才比较 ChargeItemCode。",
            "实际抵扣与退回记录使用 ListCouponUsageRecords；ListCoupons 本身只证明库存、状态与适用规则。",
        ],
    },
    "ListResourcePackages": {
        "title": "资源包库存与状态",
        "purpose": "查询资源包实例的状态、余量、生效/到期时间、商品、地域和配置标识；也可为抵扣原因提供库存证据。",
        "use_when": [
            "查询资源包状态、余量或有效期",
            "核实资源包是否未生效、已过期或已用尽",
            "需要用 InstanceNo 关联资源包抵扣明细",
            "账单明细出现可能由资源包覆盖的按量消费时，核对候选资源包库存",
        ],
        "avoid_when": [
            "仅查询普通账单或账户状态",
            "只问指定资源包状态时无目标范围地遍历全部资源包；先按产品缩小范围再用 InstanceNo 定位",
            "仅凭资源包库存解释某笔消费为何未抵扣",
            "仅凭 ConfigurationName/ConfigurationCode 判断全部配置或全部计费项适用范围",
        ],
        "data_grain": "资源包实例",
        "result_kind": "resource_package_inventory",
        "important_limits": [
            "使用 NextToken 分页，MaxResults 上限 20；full 必须从空 NextToken 开始，返回空、空字符串或 0 时结束。",
            "查询资源包使用 ResourceType=Package；RI/RSC 是相邻资源实例类型，不自动混入。",
            "Status/AvailableAmount 可证明状态或余量，但不能单独证明某笔账单本应被该资源包抵扣。",
            "package.json 未暴露全部配置、全部计费项或计费模式适用范围；ConfigurationName/Code 是资源包实例配置，不是通配声明。",
        ],
    },
    "ListPackageUsageDetails": {
        "title": "资源包抵扣明细",
        "purpose": "查询资源包抵扣事件，使用资源包实例、被抵扣产品、计费单元、实例、地域、消费时间和抵扣量建立实际关联。",
        "use_when": [
            "查询指定资源包在目标时间范围内的实际抵扣记录或用量",
            "证明目标资源包实际抵扣过对应产品、计费项、实例或地域",
            "比较本期与基期资源包抵扣用量是否下降",
            "把资源包状态证据与目标账单明细关联",
        ],
        "avoid_when": [
            "没有指定资源包或明确时间范围时无目标地遍历抵扣明细",
            "把历史抵扣记录直接解释为当前适用范围保证",
            "用 DeductionTime 替代账单 ExpenseBeginTime 判断消费是否在资源包生效周期",
        ],
        "data_grain": "资源包实例 × 一次抵扣事件",
        "result_kind": "resource_package_usage_detail",
        "important_limits": [
            "使用 NextToken 分页，MaxResults 上限 50；抵扣时间范围为 UTC 左闭右开区间。",
            "InstanceNo 关联资源包库存；DeductionProduct/ElementCode/InstanceNo/RegionCode 关联被抵扣消费。",
            "BeginTime/EndTime 是被抵扣消费时间，DeductionTime 是执行抵扣时间，两者不能互换。",
            "没有匹配抵扣明细或显式适用范围时，不输出资源包不覆盖或已覆盖结论。",
        ],
    },
    "QueryBalanceAcct": {
        "title": "当前账户资金快照",
        "purpose": "查询当前授权账户的可用余额、现金余额、冻结金额、信控额度、欠费金额和结算币种。",
        "use_when": [
            "确认当前账户是否欠费或查询当前账户资金情况",
            "用户询问当前欠费金额、可用余额、现金余额、冻结金额或信控额度",
            "欠费原因分析开始时获取账户级事实",
        ],
        "avoid_when": [
            "查询某个账期、产品或账单的已出账未还款金额；该口径使用 BILL Action 的 UnpaidAmount",
            "重建历史账户余额或历史欠费状态；本 Action 只提供当前账户资金对象",
            "查询账单、账单明细、分账或摊销成本",
        ],
        "data_grain": "当前授权账户",
        "result_kind": "account_balance_snapshot",
        "preferred_output": "structured_json_stdout",
        "important_limits": [
            "AvailableBalance < 0 表示账户欠费；AvailableBalance >= 0 表示账户当前不欠费。",
            "cost.py query 使用统一 status/message/result envelope；原始账户字段位于 result，message 提供欠费判定及余额公式核验说明，Agent 不重算判定。",
            "ArrearsBalance 大于零只表示当前存在欠费金额，不能单独判断账户当前欠费。",
            "工具按 Decimal 核验 AvailableBalance = CashBalance + CreditLimit - FreezeAmount - ArrearsBalance；公式不一致时说明无法确认状态，组成字段缺失时说明未核验。",
            "公开响应表未声明字段必返或空值语义；AvailableBalance 缺失、为空或无法解析时不能确认账户状态。",
            "Currency 按响应原值解释，公开契约未声明枚举；缺失时不能替金额补造币种。",
            "响应是当前账户资金快照，不能据此重建历史余额或余额转负时间。",
            "响应没有服务端快照时间字段；result、message 和 _meta 均不新增时间参数。",
        ],
    },
    "ListCostAnalysisOpenApi": {
        "title": "费用趋势与单维度汇总",
        "purpose": "查询 T+2 更新的费用分析数据；支持账单和成本账单的原价、折后价、应付金额口径，按月或按天返回趋势，并按一个分类维度汇总费用构成。",
        "use_when": [
            "查询一段时间内的月/日费用趋势",
            "按账号、产品、地域、项目、标签等单一维度查看构成或 TopN",
            "希望直接使用服务端汇总结果，且不需要逐条账单证据",
        ],
        "avoid_when": [
            "用户要求最新可获得的已出具账单明细、今天或刚出具的费用数据；费用分析在账单明细出具后 T+2 日更新，任何 Action 都不保证账户或资源的实时费用。",
            "需要逐条账单核对或账单明细记录",
            "需要多个维度自由组合聚合",
            "需要层级聚合、分组内 TopN，或选出一个分类项后继续沿另一维度分析",
            "需要跨来源关联或对账",
        ],
        "data_grain": "时间点 × 单个分类项",
        "result_kind": "aggregated_time_series",
        "important_limits": [
            "数据在账单明细出具后 T+2 日更新，不用于查询最新可获得的已出具账单明细或实时费用。",
            "CostType 仅支持 0/1/2（账单原价/折后价/应付金额）和 4/5/6（成本本期已分摊原价/折后价/应付金额）；不提供现金支付口径 3/7。",
            "标签筛选通过 Filters 传入，其中 FilterKey=10，FilterValue 的第一项为标签键到标签值列表的映射。",
        ],
    },
    "GetFilterInfoForCostAnalysis": {
        "title": "费用分析筛选值发现",
        "purpose": "获取费用分析筛选项，按同一时间范围返回可用的账号、产品、计费单元、地域、项目、标签键等候选值，不返回金额。",
        "use_when": [
            "构造费用分析请求前，需要发现当前时间范围内有哪些可选维度值",
            "用户给出名称但请求需要 code，需先解析合法筛选值",
            "用户只给出标签键或想按标签筛选前，需要确认该月份范围内有哪些 TagKeyList 可用",
        ],
        "avoid_when": ["需要查询金额或费用结果；本接口不返回金额。"],
        "data_grain": "筛选候选值目录",
        "result_kind": "filter_catalog",
        "preferred_output": "structured_json_stdout",
        "important_limits": [
            "只能作为参数发现证据，不能作为费用金额证据。",
            "TagKeyList 只返回可用标签键，不返回标签值。后续调用 ListCostAnalysisOpenApi 时，通过 Filters 传入标签筛选，其中 FilterKey=10，FilterValue 的第一项为标签键到标签值列表的映射。",
            "后续调用支持 TagKV 的账单明细、分账明细或分摊成本 Action 时，每个 TagKV 必须同时提供非空 Key 和 Value。",
        ],
    },
    "ListBillOverviewByCategory": {
        "title": "单月账号与账单大类总览",
        "purpose": "提供按账号汇总的当月总费用和账单大类金额。",
        "use_when": ["查询单月账号级总费用，或消费、退款、调账等账单大类构成"],
        "avoid_when": ["需要产品维度或分页明细", "需要实例、计费项或逐条账单证据"],
        "data_grain": "账期 × 账号 × 账单大类",
        "result_kind": "account_category_overview",
        "important_limits": ["只支持单月；上月完整数据应在次月第 2 个自然日 12 点后获取。"],
    },
    "ListBillOverviewByProd": {
        "title": "单月产品费用总览",
        "purpose": "提供按产品汇总的当月费用数据和金额构成。",
        "use_when": ["查询单月产品费用、产品 TopN 或产品级金额构成，且不需要明细粒度"],
        "avoid_when": ["需要实例、计费项、项目、地域或逐条账单证据"],
        "data_grain": "账期 × 产品",
        "result_kind": "product_overview",
        "important_limits": ["只支持单月；上月完整数据应在次月第 2 个自然日 12 点后获取。"],
    },
    "ListBill": {
        "title": "账单流水查询",
        "purpose": "提供按 BillPeriod 出账的产品、结算周期、支付状态、BillID 等账单流水信息和金额。",
        "use_when": [
            "查询账单或订单级金额、现金支付、已出账未还款金额、账单结算状态和结算类型",
            "需要 BillID 以便下钻到账单明细",
        ],
        "avoid_when": ["需要实例、计费项、用量、单价或优惠计算明细"],
        "data_grain": "账单流水",
        "result_kind": "bill_rows",
        "important_limits": [
            "只支持单月；上月完整数据应在次月第 2 个自然日 12 点后获取。",
            "BillPeriod 决定账单归属；ExpenseBeginTime/ExpenseEndTime 描述实例实际使用周期，可能晚于出账账期甚至位于未来，不改变账期归属。",
        ],
    },
    "ListBillDetail": {
        "title": "账单明细查询",
        "purpose": "提供包含配置、实例、时间、用量、价格、优惠折扣和计费规则等的计费明细信息，并支持按账号、产品、实例或计费项等服务端粒度查询；适合在完整行数据上做多维和层级分析。账单明细口径不存在产品+明细、账号+明细两种组合。",
        "use_when": [
            "解释费用、核查用量、单价、优惠、折扣或应付金额的明细证据",
            "按计费项、实例、产品、账号及月/日粒度查询；明细粒度仅支持计费项或实例，不支持产品或账号",
            "需要同时保留配置、实例、时间和金额等多个维度关系，并做层级聚合、分组内 TopN 或后续下钻分析",
            "需要 BillDetailId 与分账账单建立血缘或做对账",
        ],
        "avoid_when": ["只需要简单总览且服务端总览接口已能完整满足", "需要资源实际使用周期的分摊成本"],
        "data_grain": "账期、天或计费明细，由 GroupPeriod/GroupTerm 决定",
        "result_kind": "bill_detail_rows",
        "important_limits": [
            "只支持单月；上月完整数据应在次月第 2 个自然日 12 点后获取。",
            "服务端聚合可能丢失实例、项目或血缘键。",
            "GroupPeriod=2（明细）时不支持 GroupTerm=2（产品）或 GroupTerm=3（账号）。",
            "BillPeriod 决定账单归属；ExpenseBeginTime/ExpenseEndTime 描述实例实际使用周期，可能晚于出账账期甚至位于未来，不改变账期归属，也不能替代分摊成本。",
        ],
    },
    "ListSplitBillDetail": {
        "title": "资源粒度分账与费用归属查询",
        "purpose": "提供包含资源项目/标签信息的分账账单，把账单明细金额拆到资源管理和内部分账归属粒度。",
        "use_when": [
            "按部门、业务线、项目、标签、成本单元或分拆项查看费用归属",
            "通过 BillDetailId 与账单明细建立血缘或聚合后对账",
            "查看 EP、Domain、Bucket、EIP 等资源管理粒度产生的费用",
        ],
        "avoid_when": ["只需要普通账单支付状态", "需要资源实际使用周期成本"],
        "data_grain": "账期、天或分账明细，由 GroupPeriod 决定",
        "result_kind": "split_bill_rows",
        "important_limits": [
            "一条账单明细可以对应多个分拆项，金额按各分拆项用量情况拆分。",
            "通常比账单明细延迟约 2 天。",
            "分账生成后项目和标签最晚还可能延迟约 12 小时补充。",
        ],
    },
    "ListAmortizedCostBillMonthly": {
        "title": "月度分摊成本查询",
        "purpose": "提供基于资源实际使用周期并按分摊月聚合的成本账单，返回月度分摊成本、当期分摊和未分摊金额。",
        "use_when": [
            "按权责发生制把集中采购支出分摊为月度经营成本",
            "查询预付费或履约费用在实际使用月份的成本分布",
            "按资源实际使用周期查看月度成本、月度经营分析或业务线成本考核",
        ],
        "avoid_when": ["需要原始账务账期支付状态", "要与账单明细按同月直接对账"],
        "data_grain": "分摊月汇总",
        "result_kind": "monthly_amortized_cost_rows",
        "important_limits": [
            "需要开通成本账单；通常比账单明细延迟约 2 天。",
            "成本按实例实际使用周期归入 AmortizedMonth；BillPeriod 仅表示原始账务账期。",
        ],
    },
    "ListAmortizedCostBillDaily": {
        "title": "每日分摊成本查询",
        "purpose": "提供基于资源实际使用周期并按分摊日聚合的成本账单。",
        "use_when": ["查看每日分摊趋势、定位某日成本，或查询日粒度生命周期成本", "开展业务线日成本监控与考核"],
        "avoid_when": ["需要原始账务账期支付状态", "需要逐条成本证据"],
        "data_grain": "分摊日汇总",
        "result_kind": "daily_amortized_cost_rows",
        "important_limits": [
            "需要开通成本账单；通常比账单明细延迟约 2 天。",
            "成本按实例实际使用周期归入 AmortizedDay/AmortizedMonth；BillPeriod 仅表示原始账务账期。",
        ],
    },
    "ListAmortizedCostBillDetail": {
        "title": "分摊成本明细查询",
        "purpose": "提供基于资源实际使用周期的最细分摊账单，包含 CostID、分摊日、原始账期、资源、价格和金额。",
        "use_when": ["核查具体资源、价格、原始账期和分摊日的成本证据"],
        "avoid_when": [
            "需要原始账务账期支付状态",
            "尝试通过 BillDetailId 与账单明细逐条关联；本接口不提供该稳定键",
        ],
        "data_grain": "成本分摊明细",
        "result_kind": "amortized_cost_detail_rows",
        "important_limits": [
            "需要开通成本账单；通常比账单明细延迟约 2 天。",
            "成本明细按实例实际使用周期归入 AmortizedDay/AmortizedMonth；BillPeriod 仅表示原始账务账期。",
        ],
    },
}


VALUE_LABELS: Mapping[str, Mapping[str, str]] = {
    "BillingMode": {
        "1": "包年包月（预付费）",
        "2": "按量计费（后付费）",
        "3": "合同计费（线下计费）",
        "4": "履约计费",
        "5": "承诺消费",
    },
    "BusinessMode": {
        "0": "普通业务",
        "1": "财务托管",
        "2": "代销业务",
        "3": "代售业务",
        "4": "财务管理",
        "5": "代买业务",
    },
    "BusinessModeCode": {
        "0": "普通业务",
        "1": "财务托管",
        "2": "代销业务",
        "3": "代售业务",
        "4": "财务管理",
        "5": "代买业务",
    },
    "BillCategoryParent": {"consume": "消费", "refund": "退款", "transfer": "调账"},
    "BillCategory": {
        "consume-trial": "消费-试用",
        "consume-use": "消费-使用",
        "consume-new": "消费-新购",
        "consume-renew": "消费-续费",
        "consume-formalize": "消费-转正",
        "consume-modify": "消费-更配",
        "consume-TempUpgrade": "消费-临时升配",
        "consume-RIAdjust": "消费-预留实例调整",
        "refund-terminate": "退款-退订",
        "refund-modify": "退款-更配",
        "refund-TempUpgrade": "退款-临时升配",
        "refund-RIAdjust": "退款-预留实例调整",
        "transfer-manual": "调账-人工",
        "transfer-system": "调账-系统",
        "consumption-guarantee": "消费-保底",
        "refund-DeliveryFailed": "退款-交付失败",
        "transfer-guarantee": "调账-保底",
        "consume-Commitment": "消费-承诺消费",
        "consume-transfer": "消费-资源过户",
        "refund-transfer": "退款-资源过户",
    },
    "PayStatus": {"CompletedSettle": "已结清", "PartSettle": "未结清", "Unsettle": "未结算"},
    "IgnoreZero": {"0": "保留折后价为 0 的记录", "1": "忽略折后价为 0 的记录"},
    "NeedRecordNum": {"0": "不计算总记录数，Total 返回 -1", "1": "计算并返回总记录数"},
    "SettlementType": {
        "non-settle": "非结算：开通试用实例等无需支付结算的账单。",
        "settle": "结算：用户正常使用产品或服务产生、需要支付结算的费用账单。",
        "quota-settle": "Quota结算：代销或代售场景下，终端客户使用云服务，由伙伴和终端客户线下支付结算的账单。",
    },
    "TagKVFilterMode": {"0": "任一标签条件匹配", "1": "全部标签条件匹配"},
    "GroupPeriod": {"0": "账期汇总", "1": "按天汇总", "2": "明细"},
    "GroupTerm": {"0": "计费项", "1": "实例", "2": "产品", "3": "账号"},
    "AmortizedType": {
        "1": "履约计费分摊", "2": "合同计费分摊", "3": "按量计费分摊",
        "4": "新购分摊", "5": "更配分摊", "6": "续费分摊",
        "7": "退订分摊", "8": "预留实例调整分摊", "9": "试用分摊", "10": "转正分摊",
    },
    "CostType": {
        "0": "账单口径：原价",
        "1": "账单口径：折后价",
        "2": "账单口径：应付金额",
        "4": "成本账单口径：本期已分摊-原价",
        "5": "成本账单口径：本期已分摊-折后价",
        "6": "成本账单口径：本期已分摊-应付金额",
    },
    "TimeGranularity": {"0": "按账期（月）", "1": "按天"},
    "ClassifyDimension": {
        "1": "Payer 账号", "2": "Owner 账号", "3": "产品", "4": "计费模式",
        "5": "计费单元", "6": "地域", "7": "可用区", "8": "账单类型",
        "9": "项目", "10": "标签", "11": "实例 ID", "12": "业务类型",
        "13": "服务主体", "15": "分拆项", "16": "配置名称", "17": "成本单元",
    },
    "FilterKey": {
        "1": "Payer 账号", "2": "Owner 账号", "3": "产品", "4": "计费模式",
        "5": "计费单元", "6": "地域", "7": "可用区", "8": "账单类型",
        "9": "项目", "10": "标签", "12": "业务类型", "13": "服务主体",
        "15": "分拆项", "16": "配置名称", "17": "成本单元",
    },
    "Operator": {"1": "包含", "2": "排除"},
}


def _localized_response_values(labels: Mapping[str, str]) -> tuple[Mapping[str, str], ...]:
    return tuple(
        {
            "request_value": value,
            "response_value": meaning,
            "response_label": meaning,
        }
        for value, meaning in labels.items()
    )


BILLING_MODE_RESPONSE_VALUES: Mapping[str, str] = {
    "1": "包年包月",
    "2": "按量计费",
    "3": "合同计费",
    "4": "履约计费",
    "5": "承诺消费",
}


RESPONSE_VALUE_SEMANTICS: Mapping[str, Sequence[Mapping[str, str]]] = {
    "PayStatus": (
        {"request_value": "CompletedSettle", "response_value": "已结清", "response_label": "已结清"},
        {"request_value": "PartSettle", "response_value": "未结清", "response_label": "未结清"},
        {"request_value": "Unsettle", "response_value": "未结算", "response_label": "未结算"},
    ),
    "BillCategoryParent": _localized_response_values(VALUE_LABELS["BillCategoryParent"]),
    "BillCategory": _localized_response_values(VALUE_LABELS["BillCategory"]),
    "BusinessMode": (
        {"request_value": "0", "response_value": "普通业务", "response_label": "普通业务"},
        {"request_value": "1", "response_value": "财务托管", "response_label": "财务托管"},
        {"request_value": "2", "response_value": "代销业务", "response_label": "代销业务"},
        {"request_value": "3", "response_value": "代售业务", "response_label": "代售业务"},
        {"request_value": "4", "response_value": "财务管理", "response_label": "财务管理"},
        {"request_value": "5", "response_value": "代买业务", "response_label": "代买业务"},
    ),
    "SettlementType": (
        {
            "request_value": "non-settle",
            "response_value": "非结算",
            "response_label": "非结算",
            "meaning": "非结算：开通试用实例等无需支付结算的账单。",
        },
        {
            "request_value": "settle",
            "response_value": "结算",
            "response_label": "结算",
            "meaning": "结算：用户正常使用产品或服务产生、需要支付结算的费用账单。",
        },
        {
            "request_value": "quota-settle",
            "response_value": "Quota结算",
            "response_label": "Quota结算",
            "meaning": "Quota结算：代销或代售场景下，终端客户使用云服务，由伙伴和终端客户线下支付结算的账单。",
        },
    ),
    "AmortizedType": _localized_response_values(VALUE_LABELS["AmortizedType"]),
}


ACTION_RESPONSE_VALUE_SEMANTICS: Mapping[tuple[str, str], Sequence[Mapping[str, str]]] = {
    (action, "BillingMode"): _localized_response_values(BILLING_MODE_RESPONSE_VALUES)
    for action in (
        "ListBillDetail",
        "ListSplitBillDetail",
        "ListAmortizedCostBillMonthly",
        "ListAmortizedCostBillDaily",
        "ListAmortizedCostBillDetail",
    )
}


FIELD_PURPOSES: Mapping[str, str] = {
    "AccountID": "当前授权账户 ID；默认不展示。",
    "ArrearsBalance": "账户当前欠费金额；不单独代表账户当前欠费状态。",
    "AvailableBalance": "账户当前可用余额；小于零表示账户欠费。",
    "CashBalance": "账户当前现金余额。",
    "CreditLimit": "账户当前信控额度。",
    "FreezeAmount": "账户当前冻结金额。",
    "PayerID": "账单还款的对象，也是资源的支付结算账号；财务托管场景下为托管主账号，代销或代售场景下为代销/代售伙伴账号。",
    "OwnerID": "只查询指定 Owner 账号；财务托管场景下不传可能包含当前身份可见的多个 Owner。",
    "Product": "按产品 code 筛选；不传表示全部产品。",
    "BillingMode": "按计费模式筛选；不传表示全部计费模式。",
    "BillCategoryParent": "按消费、退款或调账大类筛选；不传表示全部大类。",
    "BillCategory": "按具体账单类型筛选，例如消费-使用、退款-退订或调账-人工；不传表示全部类型。",
    "BillPeriod": "指定原始账务账期。",
    "AmortizedMonth": "指定资源实际使用日期所属的分摊月，不等同于原始账务账期。",
    "AmortizedDay": "可选地限制单个分摊日，也可减少查询量。",
    "AmortizedType": "按成本分摊业务类型筛选；不传表示全部分摊类型。",
    "Project": "按项目筛选；是否生效取决于目标 Action 和服务端粒度。",
    "BusinessMode": "业务类型。",
    "BusinessModeCode": "业务类型 Code。",
    "BusinessModeName": "业务类型名称。",
    "OriginalOrderNo": "原订单号；退订等场景下表示对应的原始订单号。",
    "InstanceNo": "账单对应的实例 ID；请求中可按云产品计费实例 ID 筛选。",
    "InstanceName": "账单对应的实例名称。",
    "SplitDimension": "按商品指定分拆维度；接口要求传 JSON 编码字符串。",
    "SplitItemID": "按分拆项 ID 筛选。",
    "ExpenseDate": "按账单日期筛选，必须与 BillPeriod 在同一个月；仅支持单日查询；在天维度下该参数可提升查询性能，建议填写。",
    "Limit": "单次接口请求最多返回的记录数，不是用户最终 TopN。",
    "Offset": "接口分页偏移量；首请求从 0 开始，后续按实际 Limit 递增。",
    "NeedRecordNum": "控制接口是否计算 Total；需要证明分页完整时设为 1。",
    "IgnoreZero": "控制是否过滤折后价为 0 的记录。",
    "GroupPeriod": "选择服务端时间粒度；粒度变粗可能丢失更细日期或业务字段。",
    "GroupTerm": "选择账单明细的服务端统计项；会丢失非该统计项的明细维度。",
    "TagKV": "按标签键值对筛选，最多 20 个条件；每个条件必须同时提供非空 Key 和 Value。",
    "TagKVFilterMode": "多个 TagKV 条件之间的匹配方式。",
    "CostType": "选择费用分析返回的金额口径；仅支持 0/1/2 的账单原价/折后价/应付金额和 4/5/6 的成本本期已分摊原价/折后价/应付金额。",
    "TimeGranularity": "选择费用分析按月还是按天返回。",
    "BeginTimeStr": "费用分析查询起始时间，使用东八区。",
    "EndTimeStr": "费用分析查询结束时间，使用东八区。",
    "ClassifyDimension": "选择费用分析唯一的分类维度。",
    "ClassifyDimensionValue": "为标签、实例 ID 或分拆项分类补充目标值。",
    "Filters": "费用分析的附加筛选条件；不传、null 或空数组都表示不筛选。",
    "FilterKey": "选择一条费用分析筛选条件所作用的业务维度。",
    "FilterValue": "该筛选维度的值列表；不同 FilterKey 的编码格式不同。",
    "Operator": "指定筛选值是包含还是排除。",
    "Amount": "当前分类项在 TimeStr 对应时间点的金额；金额口径由请求 CostType 决定。",
    "TimeStr": "费用金额所属的账期或日期；格式由请求 TimeGranularity 决定。",
    "ClassifyItem": "ClassifyDimension 对应的实际分类值。",
    "SettlementType": "标记账单是否需要结算扣款，包含非结算、结算、Quota结算。",
    "PaidAmount": "现金支付金额，不等同于所有支付方式或账户总扣款。",
    "UnpaidAmount": "已出账未还款的账单金额，不代表账户当前实时欠费状态。",
    "CreditCarriedAmount": "信控额度退款抵扣；正负值具有不同业务含义，解释时保留符号。",
    "PayableAmount": "应付金额；解释或对账时需同时确认账期和结算类型。",
    "Currency": "原币种或账单币种；金额聚合时必须按币种隔离。",
    "CurrencySettlement": "结算币种；不能与其他币种金额直接相加。",
    "Warning": "接口返回的筛选降级或数据告警。",
}


FIELD_RULES: Mapping[str, Mapping[str, Any]] = {
    "BillPeriod": {"format": "YYYY-MM", "notes": ["单次接口请求只查询一个账期。"]},
    "AmortizedMonth": {"format": "YYYY-MM", "notes": ["最早支持 2023-04。"]},
    "AmortizedDay": {"format": "YYYY-MM-DD", "notes": ["最早支持 2023-04-01。"]},
    "ExpenseDate": {
        "format": "YYYY-MM-DD",
        "conditions": ["仅在 GroupPeriod=1（按天）或 2（明细）时传入。", "必须与 BillPeriod 属于同一个月。"],
    },
    "BeginTimeStr": {
        "format_by_condition": {"TimeGranularity=0": "YYYY-MM-01", "TimeGranularity=1": "YYYY-MM-DD"}
    },
    "EndTimeStr": {
        "format_by_condition": {"TimeGranularity=0": "YYYY-MM-01", "TimeGranularity=1": "YYYY-MM-DD"}
    },
    "ClassifyDimensionValue": {
        "conditionally_required_when": {
            "ClassifyDimension=10": "必须由用户提供标签 key，或由用户指定可用于确认标签 key 的方式。",
            "ClassifyDimension=11": "必须由用户提供实例 ID，或由用户指定可用于确认实例 ID 的方式；多个实例 ID 用逗号分隔。",
            "ClassifyDimension=15": "必须由用户提供分拆项名称，或由用户指定可用于确认分拆项的方式。",
        },
        "conditions": [
            "ClassifyDimension=10（标签）时必须填写标签 key。",
            "ClassifyDimension=11（实例 ID）时必须填写实例 ID；多个实例 ID 用逗号分隔。",
            "ClassifyDimension=15（分拆项）时必须填写分拆项名称。",
        ],
        "missing_value_policy": (
            "ClassifyDimension 为 10、11 或 15 时没有安全默认值；如果用户未提供 "
            "ClassifyDimensionValue，也未提供可确认该值的方式，必须先询问用户。"
        ),
    },
    "Limit": {"notes": ["分页 Limit 与用户结果 TopN 是两个不同概念。"]},
    "Offset": {"default_behavior": "从 0 开始。"},
    "NeedRecordNum": {"default_behavior": "不传时通常不计算总数，Total 可能为 -1。"},
    "IgnoreZero": {"default_behavior": "不传时保留折后价为 0 的记录。"},
    "GroupPeriod": {"default_behavior": "不传时按接口默认的月度/账期粒度返回。"},
    "Filters": {"default_behavior": "不传、null 或空数组时不作为筛选条件。"},
    "TagKV": {
        "conditions": [
            "每一项必须同时提供非空 Key 和 Value，不能直接构造只有 Key 的 TagKV",
            "用户只提供标签键时，先用 GetFilterInfoForCostAnalysis 确认该时间范围内可用的 TagKeyList。",
            "确认用户提供的标签键存在后，若缺少具体 Value 则询问用户或使用用户指定的确认方式。",
        ],
        "notes": ["最多传 20 个标签键值对。"],
    },
    "SplitDimension": {"format": "JSON encoded string"},
    "FilterValue": {
        "format_by_condition": {
            "FilterKey=1|2": "list<账号>",
            "FilterKey=3": "list<产品>",
            "FilterKey=4": "list<计费模式>",
            "FilterKey=5": "list<map<商品><计费单元>>；每个数组元素是 JSON 编码字符串",
            "FilterKey=6": "list<地域>",
            "FilterKey=7": "list<map<地域><可用区>>；每个数组元素是 JSON 编码字符串",
            "FilterKey=8": "list<账单类型>",
            "FilterKey=9": "list<项目>",
            "FilterKey=10": "map<标签key><list<标签value>>；放置于 list 的第一位",
            "FilterKey=12": "list<业务类型>",
            "FilterKey=13": "list<服务主体>",
            "FilterKey=15": "list<分拆项>",
            "FilterKey=16": "list<配置名称>",
            "FilterKey=17": "list<成本单元>",
        },
        "format_details": [
            {
                "filter_keys": [1, 2],
                "dimension": "payerId / ownerId",
                "format": "list<账号>",
                "example": ["2100054924", "2100054925"],
            },
            {
                "filter_keys": [3],
                "dimension": "产品",
                "format": "list<产品>",
                "example": ["TOS", "VKE"],
            },
            {
                "filter_keys": [4],
                "dimension": "计费模式",
                "format": "list<计费模式>",
                "example": ["1", "2"],
            },
            {
                "filter_keys": [5],
                "dimension": "计费单元",
                "format": "list<map<商品><计费单元>>",
                "example": ['{"sms":["BE000383"]}', '{"ark_bd":["BE150994"]}'],
            },
            {
                "filter_keys": [6],
                "dimension": "地域",
                "format": "list<地域>",
                "example": ["", "R000807"],
            },
            {
                "filter_keys": [7],
                "dimension": "可用区",
                "format": "list<map<地域><可用区>>",
                "example": ['{"":[""]}', '{"R000017":["ZoneA"]}'],
            },
            {
                "filter_keys": [8],
                "dimension": "账单类型",
                "format": "list<账单类型>",
                "example": ["consume-use", "consume-new", "refund-terminate"],
            },
            {
                "filter_keys": [9],
                "dimension": "项目",
                "format": "list<项目>",
                "example": ["", "projectA"],
            },
            {
                "filter_keys": [10],
                "dimension": "标签",
                "format": "map<标签key><list<标签value>>（放置于 list 的第一位）",
                "example": [{"voKey2": ["v2", "v3"], "voKey1": ["v1", "v11"]}],
            },
            {
                "filter_keys": [12],
                "dimension": "业务类型",
                "format": "list<业务类型>",
                "example": ["0", "1"],
            },
            {
                "filter_keys": [13],
                "dimension": "服务主体",
                "format": "list<服务主体>",
                "example": ["3423", "3002"],
            },
            {
                "filter_keys": [15],
                "dimension": "分拆项",
                "format": "list<分拆项>",
                "example": ["aaa"],
            },
            {
                "filter_keys": [16],
                "dimension": "配置名称",
                "format": "list<配置名称>",
                "example": ["adjust_code"],
            },
            {
                "filter_keys": [17],
                "dimension": "成本单元",
                "format": "list<成本单元>",
                "example": ["aaa"],
            },
        ],
        "notes": ["最多 100 个筛选值。"],
    },
}


ACTION_SECTION_FIELD_GUIDANCE: Mapping[tuple[str, str, str], Mapping[str, Any]] = {
    ("ListFinancialRelation", "response", "Offset"): {
        "summary": "响应页偏移；-1 表示接口未回显请求偏移。",
        "notes": ["执行器兼容 -1 并按请求 Offset 推进分页；其他明确矛盾的偏移仍报错。"],
    },
    ("ListFinancialRelation", "response", "Status"): {
        "summary": "财务关系状态编码；结合 StatusDesc 解释。",
        "notes": ["未知或缺失状态不推断为生效；不能复用代金券或资源包状态枚举。"],
    },
    ("ListFinancialRelation", "response", "Relation"): {
        "summary": "财务关系类型编码；结合 RelationDesc 解释。",
        "notes": ["不能复用账单 BusinessMode 编码；财务管理不代表主账号代付。"],
    },
    ("ListFinancialRelation", "response", "Filiation"): {
        "summary": "主子相对视角编码，不能直接用于判断当前登录角色。",
        "notes": ["实际看已核验账号 ID 与 MajorAccountID/SubAccountID 匹配；主或子文字不代表当前登录角色。"],
    },
    ("ListFinancialRelation", "response", "FiliationDesc"): {
        "summary": "主子相对视角说明，实际看已核验账号 ID 判角色。",
        "notes": ["即使返回主，当前账号也可能匹配 SubAccountID；采用 message 中的身份核验与角色结论。"],
    },
    ("ListCoupons", "response", "Status"): {
        "summary": "代金券状态。",
        "accepted_values": [
            {"value": 1, "meaning": "待生效"},
            {"value": 2, "meaning": "生效中"},
            {"value": 3, "meaning": "已失效"},
            {"value": 4, "meaning": "已使用"},
            {"value": 5, "meaning": "已作废"},
        ],
    },
}


ACTION_FIELD_GUIDANCE: Mapping[tuple[str, str], Mapping[str, Any]] = {
    ("ListBill", "BillPeriod"): {
        "summary": "账务账期；决定该账单记录归属和计入的出账账期。",
    },
    ("ListBill", "ExpenseBeginTime"): {
        "summary": "实例实际开始使用时间。",
        "notes": ["可能晚于 BillPeriod 甚至位于未来；不改变记录的账期归属，也不能据此把整笔金额归入该日期或月份。"],
    },
    ("ListBill", "ExpenseEndTime"): {
        "summary": "实例实际结束使用时间。",
        "notes": ["与 ExpenseBeginTime 共同描述实际使用周期；不能替代分摊成本账单。"],
    },
    ("ListBillDetail", "BillPeriod"): {
        "summary": "账务账期；决定该账单明细归属和计入的出账账期。",
    },
    ("ListBillDetail", "ExpenseBeginTime"): {
        "summary": "实例实际开始使用时间。",
        "notes": ["可能晚于 BillPeriod 甚至位于未来；该明细仍计入 BillPeriod，不能据此从账期合计中排除。"],
    },
    ("ListBillDetail", "ExpenseEndTime"): {
        "summary": "实例实际结束使用时间。",
        "notes": ["与 ExpenseBeginTime 共同描述实际使用周期；不能据此手工生成按日或按月分摊金额。"],
    },
    ("ListAmortizedCostBillMonthly", "AmortizedMonth"): {
        "summary": "分摊月；成本按实例实际使用周期归入对应自然月。",
    },
    ("ListAmortizedCostBillMonthly", "BillPeriod"): {
        "summary": "原始账务账期；用于追溯或筛选成本来源，不决定成本的分摊月份。",
    },
    ("ListAmortizedCostBillDaily", "AmortizedMonth"): {
        "summary": "分摊月；成本按实例实际使用周期归入对应自然月。",
    },
    ("ListAmortizedCostBillDaily", "AmortizedDay"): {
        "summary": "分摊日；成本按实例实际使用周期归入对应日期。",
    },
    ("ListAmortizedCostBillDaily", "BillPeriod"): {
        "summary": "原始账务账期；用于追溯或筛选成本来源，不决定成本的分摊日期。",
    },
    ("ListAmortizedCostBillDetail", "AmortizedMonth"): {
        "summary": "分摊月；成本明细按实例实际使用周期归入对应自然月。",
    },
    ("ListAmortizedCostBillDetail", "AmortizedDay"): {
        "summary": "分摊日；成本明细按实例实际使用周期归入对应日期。",
    },
    ("ListAmortizedCostBillDetail", "BillPeriod"): {
        "summary": "原始账务账期；用于追溯或筛选成本来源，不决定成本的分摊日期或月份。",
    },
    ("ListCoupons", "RemainingAmount"): {
        "summary": "代金券余额，单位元。",
        "notes": ["响应为 JSON number；计算时立即转为 Decimal，不经过额外 float 运算。"],
    },
    ("ListCoupons", "TotalAmount"): {
        "summary": "代金券面额，单位元。",
    },
    ("ListCoupons", "AmountLimit"): {
        "summary": "代金券使用金额门槛，单位元；与抵扣前的账单金额口径比较。",
    },
    ("ListCoupons", "PayTypeLimit"): {
        "summary": "适用付款方式：all 同时覆盖预付费和后付费，pre 仅预付费，post 仅后付费。",
    },
    ("ListCoupons", "ConfigurationType"): {
        "summary": "适用配置类型。",
        "accepted_values": [
            {"value": 1, "meaning": "全部配置可用"},
            {"value": 2, "meaning": "全部预付费配置可用"},
            {"value": 3, "meaning": "全部后付费配置可用"},
            {"value": 4, "meaning": "指定配置可用"},
        ],
        "notes": ["只有值为 4 时才比较 ConfigurationCode/ConfigurationName。"],
    },
    ("ListCoupons", "ChargeItemType"): {
        "summary": "适用计费项类型：0 全部计费项；1 指定计费项。",
        "notes": ["值为 0 时按通配命中，不因 ChargeItemCode 为空判定不适用。"],
    },
    ("ListResourcePackages", "InstanceNo"): {
        "summary": "资源包实例 ID；与 ListPackageUsageDetails.InstanceNo 关联。",
    },
    ("ListResourcePackages", "AvailableAmount"): {
        "summary": "资源包实例余量；按 Unit 使用 Decimal 解释。",
        "notes": ["等于 0 可作为用尽证据；接近 0 没有统一阈值，不能自行定义。"],
    },
    ("ListResourcePackages", "TotalAmount"): {
        "summary": "资源包实例总量；按 Unit 使用 Decimal 解释。",
    },
    ("ListResourcePackages", "Status"): {
        "summary": "资源包实例状态。",
        "accepted_values": [
            {"value": "NotEffective", "meaning": "未生效"},
            {"value": "Effective", "meaning": "生效中"},
            {"value": "FailedToCreate", "meaning": "创建失败"},
            {"value": "UsedUp", "meaning": "已用完"},
            {"value": "Expired", "meaning": "已到期"},
            {"value": "Refunded", "meaning": "已退款"},
        ],
    },
    ("ListResourcePackages", "ConfigurationCode"): {
        "summary": "资源包实例配置编码。",
        "notes": ["不是资源包适用配置范围，不据此推断全部配置或指定账单配置是否覆盖。"],
    },
    ("ListResourcePackages", "ConfigurationName"): {
        "summary": "资源包实例配置名称。",
        "notes": ["不是资源包适用范围或通配字段。"],
    },
    ("ListPackageUsageDetails", "InstanceNo"): {
        "summary": "发生抵扣的资源包实例 ID；与 ListResourcePackages.InstanceNo 关联。",
    },
    ("ListPackageUsageDetails", "DeductionProduct"): {
        "summary": "被抵扣按量消费的产品编码；与账单明细 Product 对齐。",
    },
    ("ListPackageUsageDetails", "DeductionElementCode"): {
        "summary": "被抵扣按量消费的计费单元编码；与账单明细 ElementCode 对齐。",
    },
    ("ListPackageUsageDetails", "DeductionInstanceNo"): {
        "summary": "被抵扣按量消费的实例 ID；与账单明细 InstanceNo 对齐。",
    },
    ("ListPackageUsageDetails", "DeductionRegionCode"): {
        "summary": "被抵扣按量消费的地域编码；与账单明细 Region 对齐前先核对编码口径。",
    },
    ("ListPackageUsageDetails", "DeductionUseAmount"): {
        "summary": "被抵扣按量实例用量；按 DeductionInstanceUnit 使用 Decimal 汇总。",
    },
    ("ListPackageUsageDetails", "DeductionAmount"): {
        "summary": "本次从资源包实例扣减的数量；按 Unit 使用 Decimal 解释。",
    },
    ("ListPackageUsageDetails", "BeginTime"): {
        "summary": "被抵扣消费开始时间；用于和账单消费时间核对。",
    },
    ("ListPackageUsageDetails", "EndTime"): {
        "summary": "被抵扣消费结束时间；用于和账单消费时间核对。",
    },
    ("ListPackageUsageDetails", "DeductionTime"): {
        "summary": "抵扣执行时间；不能替代消费时间判断资源包生效或到期。",
    },
    (
        "QueryBalanceAcct",
        "AvailableBalance",
    ): {
        "summary": "账户当前可用余额；小于零表示账户欠费，大于等于零表示账户当前不欠费。",
        "notes": [
            "金额计算使用 Decimal；不要经过 float。",
            "与 CashBalance、CreditLimit、FreezeAmount、ArrearsBalance 的关系为 CashBalance + CreditLimit - FreezeAmount - ArrearsBalance。",
        ],
    },
    (
        "QueryBalanceAcct",
        "ArrearsBalance",
    ): {
        "summary": "账户当前欠费金额；大于零只表示存在欠费金额，不单独代表账户当前欠费。",
        "notes": [
            "账户可能仍有足够可用余额但还款或抵扣尚未完成；账户状态以 AvailableBalance 是否小于零判断。",
            "金额计算使用 Decimal；不要经过 float。",
        ],
    },
    (
        "QueryBalanceAcct",
        "CashBalance",
    ): {
        "summary": "账户当前现金余额；不能单独用于判断账户欠费。",
        "notes": ["金额计算使用 Decimal；不要经过 float。"],
    },
    (
        "QueryBalanceAcct",
        "CreditLimit",
    ): {
        "summary": "账户当前信控额度；不能单独用于判断账户欠费。",
        "notes": ["金额计算使用 Decimal；不要经过 float。"],
    },
    (
        "QueryBalanceAcct",
        "FreezeAmount",
    ): {
        "summary": "账户当前冻结金额；参与可用余额关系，不单独用于判断账户欠费。",
        "notes": ["金额计算使用 Decimal；不要经过 float。"],
    },
    (
        "QueryBalanceAcct",
        "Currency",
    ): {
        "summary": "响应返回的账号结算币种；所有账户金额按该原始值解释。",
        "notes": [
            "公开契约未声明 Currency 枚举，不把一次观测到的 CNY 固化为唯一合法值。",
            "Currency 缺失时说明币种证据不足，不自行补造默认币种。",
        ],
    },
    (
        "GetFilterInfoForCostAnalysis",
        "PayerUserNameList",
    ): {
        "summary": "Payer 账号筛选候选列表；接口字段名包含 UserNameList，但列表项同时包含 PayerID 和展示名。",
        "notes": ["组装费用分析 FilterKey=1 的 FilterValue 时使用 PayerID，不使用 PayerUserName。"],
    },
    (
        "GetFilterInfoForCostAnalysis",
        "PayerID",
    ): {
        "summary": "Payer 账号 ID；用于 ListCostAnalysisOpenApi Filters 中 FilterKey=1 的 FilterValue。",
    },
    (
        "GetFilterInfoForCostAnalysis",
        "PayerUserName",
    ): {
        "summary": "Payer 账号展示名；仅用于帮助用户识别账号，不作为 FilterValue。",
    },
    (
        "GetFilterInfoForCostAnalysis",
        "OwnerUserNameList",
    ): {
        "summary": "Owner 账号筛选候选列表；接口字段名包含 UserNameList，但列表项同时包含 OwnerID 和展示名。",
        "notes": ["组装费用分析 FilterKey=2 的 FilterValue 时使用 OwnerID，不使用 OwnerUserName。"],
    },
    (
        "GetFilterInfoForCostAnalysis",
        "OwnerID",
    ): {
        "summary": "Owner 账号 ID；用于 ListCostAnalysisOpenApi Filters 中 FilterKey=2 的 FilterValue。",
    },
    (
        "GetFilterInfoForCostAnalysis",
        "OwnerUserName",
    ): {
        "summary": "Owner 账号展示名；仅用于帮助用户识别账号，不作为 FilterValue。",
    },
    (
        "GetFilterInfoForCostAnalysis",
        "TagKeyList",
    ): {
        "summary": "指定时间范围内费用分析可用的标签键列表；用于判断用户给出的标签键是否存在。",
        "notes": [
            "用于 ListCostAnalysisOpenApi 的 ClassifyDimension=10 或 Filters.FilterKey=10 前置发现。",
            "只返回标签键，不返回标签值；不能据此直接构造 TagKV，TagKV 仍必须同时有 Key 和 Value。",
            "结果随 BeginTimeStr、EndTimeStr 和 TimeGranularity 变化；不要跨月份默认复用。",
        ],
    },
    (
        "ListCostAnalysisOpenApi",
        "CostType",
    ): {
        "conditions": [
            "账单口径使用 0、1、2。",
            "成本账单口径使用 4、5、6。",
            "3、7 现金支付口径已屏蔽；核销相关金额只在 BILL 及其聚合维度暴露。",
        ],
    },
    (
        "ListCostAnalysisOpenApi",
        "Limit",
    ): {
        "summary": "控制费用分析返回的分类项数量；",
    },
    (
        "ListCostAnalysisOpenApi",
        "Offset",
    ): {
        "summary": "费用分析分类项的查询偏移量，从 0 开始。",
        "default_behavior": "从 0 开始。",
    },
    (
        "ListBillDetail",
        "GroupPeriod",
    ): {
        "conditions": [
            "GroupPeriod=2 表示明细粒度。",
            "ListBillDetail 在明细粒度下只支持 GroupTerm 不传、0（计费项）或 1（实例）。",
            "ListBillDetail 不存在 GroupTerm=2（产品）+ GroupPeriod=2（明细）和 GroupTerm=3（账号）+ GroupPeriod=2（明细）。",
        ],
    },
    (
        "ListBillDetail",
        "GroupTerm",
    ): {
        "conditions": [
            "GroupTerm=2（产品）和 GroupTerm=3（账号）只能用于非明细统计周期。",
            "GroupPeriod=2（明细）时，GroupTerm=2（产品）和 GroupTerm=3（账号）是无效组合，cost.py query 会在本地拒绝。",
        ],
        "unsupported_combinations": [
            {"GroupPeriod": 2, "GroupTerm": 2, "reason": "账单明细不存在产品+明细粒度。"},
            {"GroupPeriod": 2, "GroupTerm": 3, "reason": "账单明细不存在账号+明细粒度。"},
        ],
    },
}


ACTION_REQUEST_RULES: Mapping[str, Sequence[str]] = {
    "ListCostAnalysisOpenApi": (
        "CostType 仅支持 0/1/2（账单原价、折后价、应付金额）和 4/5/6（成本账单本期已分摊原价、折后价、应付金额）；3/7 现金支付口径已屏蔽。",
        "费用分析在账单明细出具后 T+2 日更新；用户要求最新可获得的已出具账单明细或实时费用时不要选择本 Action。",
        "BeginTimeStr 和 EndTimeStr 的格式必须与 TimeGranularity 一致。",
        "ClassifyDimension 一次只能选择一个分类维度。",
        "ClassifyDimension=10（标签）、11（实例 ID）或 15（分拆项）时，必须提供 ClassifyDimensionValue。",
        "上述三类 ClassifyDimensionValue 必须来自用户明确提供，或来自用户指定的确认方式；缺失时先询问用户，不能自动猜测。",
        "Filters 中每项都必须同时提供 Operator、FilterKey 和 FilterValue。",
    ),
    "GetFilterInfoForCostAnalysis": (
        "BeginTimeStr 和 EndTimeStr 的格式必须与 TimeGranularity 一致。",
        "可返回 Payer/Owner 账号、产品、计费模式、计费单元、地域、可用区、账单类型、项目、标签键、业务类型、服务主体、配置名称等筛选候选值。",
        "TagKeyList 只表示该时间范围内可用的标签键，不包含标签值；TagKV 筛选必须由用户明确提供 Key 和 Value。",
    ),
    "ListBillDetail": (
        "ExpenseDate 仅在 GroupPeriod=1 或 2 时传入，并与 BillPeriod 同月。",
        "Project 只在计费项明细粒度生效；选择其他服务端粒度时不要依赖该筛选。",
        "GroupPeriod=2（明细）时 GroupTerm 只能不传或使用 0（计费项）/1（实例）；不存在 GroupTerm=2（产品）+明细、GroupTerm=3（账号）+明细。",
        "TagKVFilterMode 只有与 TagKV 一起使用时才有业务意义。",
    ),
    "ListSplitBillDetail": (
        "ExpenseDate 仅在 GroupPeriod=1 或 2 时传入，并与 BillPeriod 同月。",
        "Project 只在明细粒度生效。",
        "TagKVFilterMode 只有与 TagKV 一起使用时才有业务意义。",
    ),
    "ListAmortizedCostBillMonthly": (
        "AmortizedMonth 是必填的分摊时间轴；BillPeriod 只是可选的原始账期筛选。",
        "TagKVFilterMode 只有与 TagKV 一起使用时才有业务意义。",
    ),
    "ListAmortizedCostBillDaily": (
        "AmortizedMonth 是必填的分摊时间轴；AmortizedDay 可进一步限制单日。",
        "TagKVFilterMode 只有与 TagKV 一起使用时才有业务意义。",
    ),
    "ListAmortizedCostBillDetail": (
        "AmortizedMonth 是必填的分摊时间轴；AmortizedDay 可进一步限制单日。",
        "TagKVFilterMode 只有与 TagKV 一起使用时才有业务意义。",
    ),
}


def _clean_text(value: str) -> str:
    value = value.strip().strip("“”")
    value = value.replace("**", "").replace("`", "")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value


def action_guidance(action: ApiActionSpec) -> Dict[str, Any]:
    guidance = ACTION_GUIDANCE.get(action.action)
    if guidance is None:
        return {
            "title": action.name_zh,
            "purpose": _clean_text(action.description),
            "use_when": [],
            "avoid_when": [],
            "data_grain": "以目标 Action 响应契约为准",
            "result_kind": "action_specific",
            "important_limits": [],
        }
    return dict(guidance)


def _response_value_semantics(action_name: str, leaf: str) -> Sequence[Mapping[str, str]] | None:
    return ACTION_RESPONSE_VALUE_SEMANTICS.get((action_name, leaf)) or RESPONSE_VALUE_SEMANTICS.get(leaf)


RESPONSE_FIELD_SUMMARY_OVERRIDES: Mapping[str, str] = {
    "BillingMode": "计费模式。",
}


def field_guidance(
    element: ApiElementSpec,
    path: str,
    section: str,
    action_name: str = "",
) -> Dict[str, Any]:
    leaf = path.rsplit(".", 1)[-1].replace("[]", "")
    raw = _clean_text(element.description)
    summary = (
        RESPONSE_FIELD_SUMMARY_OVERRIDES.get(leaf)
        if section == "response"
        else None
    )
    result: Dict[str, Any] = {"summary": summary or FIELD_PURPOSES.get(leaf, raw)}
    accepted = VALUE_LABELS.get(leaf)
    if accepted:
        response_semantics = _response_value_semantics(action_name, leaf) if section == "response" else None
        if response_semantics:
            result["accepted_values"] = [
                {
                    "value": item["response_value"],
                    "request_value": item["request_value"],
                    "response_value": item["response_value"],
                    "response_label": item["response_label"],
                    "meaning": item.get("meaning", item["response_label"]),
                    "localized_by": "service_or_cli",
                }
                for item in response_semantics
            ]
            result["value_for_csv_filter"] = "response_value"
            result.setdefault("notes", []).append(
                "响应 CSV 中使用 response_value；构造请求参数时使用 request_value。"
            )
        else:
            result["accepted_values"] = [
                {"value": value, "request_value": value, "meaning": meaning}
                for value, meaning in accepted.items()
            ]
    rules = FIELD_RULES.get(leaf)
    if rules:
        result.update(rules)
    action_override = ACTION_FIELD_GUIDANCE.get((action_name, leaf))
    section_override = ACTION_SECTION_FIELD_GUIDANCE.get((action_name, section, leaf))
    if action_override:
        result.update(action_override)
    if section_override:
        result.update(section_override)
    if section == "request" and isinstance(element, ApiRequestParamSpec):
        if element.date_format and "format" not in result and "format_by_condition" not in result:
            result["format"] = element.date_format
        date_range: Dict[str, Any] = {}
        if element.min_month:
            date_range["min_month"] = element.min_month
        if element.min_date:
            date_range["min_date"] = element.min_date
        if element.max_age_months:
            date_range["max_age_months"] = element.max_age_months
        if date_range:
            result["date_range"] = date_range
    if section == "response":
        grain_guidance = field_grain_guidance(action_name, leaf)
        if grain_guidance:
            result["grain_availability"] = grain_guidance
        if leaf in {"Amount", "PayableAmount", "PaidAmount", "UnpaidAmount"}:
            result.setdefault("notes", []).append("金额计算使用 Decimal；不要经过 float。")
        if leaf == "Warning":
            result.setdefault("notes", []).append("非空时必须向用户展示，不能静默忽略。")
        if leaf == "CreditCarriedAmount":
            result.setdefault("notes", []).extend(
                [
                    "大于 0 表示通过信控额度退款抵减的欠费金额。",
                    "小于 0 时，绝对值表示信控额度退款金额。",
                ]
            )
    return result


def response_interpretation(action: ApiActionSpec) -> Dict[str, Any]:
    names = {element.name for element in action.response_elements}
    base = action.response_data_path or "$"
    if "List" in names:
        records_path = f"{base}.List" if base != "$" else "List"
    elif "CostData" in names:
        records_path = f"{base}.CostData" if base != "$" else "CostData"
    else:
        records_path = base
    pagination = None
    if {"Total", "Limit", "Offset"}.issubset(names):
        pagination = {
            "total_field": "Total",
            "limit_field": "Limit",
            "offset_field": "Offset",
            "complete_when": "已覆盖 Total 条记录，且没有空页、重复页、提前结束或安全上限截断。",
        }
    elif "NextToken" in names:
        pagination = {
            "token_field": "NextToken",
            "complete_when": "full 从空 NextToken 开始，持续使用响应 token；响应 token 为空、0 或列表为空时结束，且没有重复 token 或安全上限截断。",
        }
    if action.action == "ListCostAnalysisOpenApi":
        currency_rule = "ListCostAnalysisOpenApi 不返回币种；cost.py query 按该接口固定 CNY 口径补充 Currency。"
    elif action.action == "ListFinancialRelation":
        currency_rule = "财务关系记录不提供金额或币种，不据此计算费用或判断账户是否欠费。"
    elif action.action in {"ListResourcePackages", "ListPackageUsageDetails"}:
        currency_rule = "资源包数量按各自 Unit 或 DeductionInstanceUnit 解释；不同单位不直接相加。"
    elif action.action == "ListCoupons":
        currency_rule = "RemainingAmount、TotalAmount 和 AmountLimit 的契约单位为元；与账单比较前确认账单 Currency 为 CNY。"
    elif action.action == "ListCouponUsageRecords":
        currency_rule = "ChangeAmount 的契约单位为元；按 ChangeType 分别汇总抵扣和退回。"
    else:
        currency_rule = "金额按响应声明的币种解释，不跨币种直接相加。"
    guidance = action_guidance(action)
    result = {
        "data_path": base,
        "records_path": records_path,
        "result_kind": guidance["result_kind"],
        "pagination": pagination,
        "warning_field": "Warning" if "Warning" in names else None,
        "interpretation_rules": [
            "字段缺失表示未知或不支持，不能当作 0。",
            currency_rule,
        ],
    }
    for key in ("preferred_output",):
        if key in guidance:
            result[key] = guidance[key]
    if action.action == "ListCostAnalysisOpenApi":
        result["flattening"] = {
            "strategy": "cost_data_costs",
            "output_rows": "one row per CostData[].Costs[] item",
            "source_path": f"{base}.CostData[].Costs[]" if base != "$" else "CostData[].Costs[]",
            "parent_fields_carried": ["ClassifyDimension", "ClassifyItem"],
            "child_fields": ["TimeStr", "Amount"],
            "time_field": "TimeStr",
            "amount_field": "Amount",
            "total_counts": "Total 统计分类项数量，不是 flatten 后的输出行数。",
        }
    if action.action == "ListFinancialRelation":
        result["interpretation_rules"].extend(action_guidance(action)["important_limits"])
    if action.action == "QueryBalanceAcct":
        result["interpretation_rules"].extend(
            [
                "cost.py query 使用统一 envelope；原始账户字段位于 result，message 说明欠费判定和余额公式核验结果。",
                "AvailableBalance < 0 表示账户欠费；AvailableBalance >= 0 表示账户当前不欠费。",
                "ArrearsBalance 大于零只表示存在欠费金额，不覆盖 AvailableBalance 给出的账户状态。",
                "工具以 Decimal 核验 AvailableBalance = CashBalance + CreditLimit - FreezeAmount - ArrearsBalance；公式不一致时 message 说明无法确认状态及差额，不要求 Agent 再次核验。",
                "公开响应表未声明字段必返；AvailableBalance 缺失、为空或无法解析时不能确认账户状态。",
                "Currency 按响应原值解释，未声明枚举；缺失时不补造币种。",
                "结果不能用于重建历史账户状态。",
                "响应不提供服务端快照时间字段；result、message 和 _meta 均不新增时间参数。",
            ]
        )
    if action.action in {"ListBill", "ListBillDetail"}:
        result["interpretation_rules"].extend(
            [
                "BillPeriod 决定账单记录归属和计入的出账账期。",
                "ExpenseBeginTime/ExpenseEndTime 表示实例实际使用周期，可能晚于 BillPeriod 甚至位于未来；这不改变记录的账期归属，不能据此从账期合计中排除。",
                "需要按实际使用日期或月份查看分摊成本时，使用 ListAmortizedCostBillDaily/Monthly/Detail；不要根据 ExpenseBeginTime/ExpenseEndTime 手工分配整笔账单金额。",
            ]
        )
    if action.action in {
        "ListAmortizedCostBillMonthly",
        "ListAmortizedCostBillDaily",
        "ListAmortizedCostBillDetail",
    }:
        result["interpretation_rules"].extend(
            [
                "分摊成本按实例实际使用周期归入对应 AmortizedMonth 或 AmortizedDay。",
                "BillPeriod 表示原始账务账期，只用于追溯或筛选成本来源，不决定成本的分摊日期或月份。",
            ]
        )
    if action.action == "ListResourcePackages":
        result["interpretation_rules"].extend(
            [
                "InstanceNo 是资源包实例与抵扣明细的关联键。",
                "TotalAmount/AvailableAmount 按 Unit 使用 Decimal；缺失不补零。",
                "ConfigurationName/ConfigurationCode 描述资源包实例配置，不代表适用范围或通配规则。",
                "状态或余量证据必须与账单明细及匹配抵扣记录共同使用，才能输出资源包原因。",
            ]
        )
    if action.action == "ListPackageUsageDetails":
        result["interpretation_rules"].extend(
            [
                "InstanceNo 关联资源包库存；DeductionProduct、DeductionElementCode、DeductionInstanceNo 和 DeductionRegionCode 描述被抵扣消费。",
                "BeginTime/EndTime 是消费时间，DeductionTime 是抵扣执行时间。",
                "DeductionAmount 按 Unit、DeductionUseAmount 按 DeductionInstanceUnit 使用 Decimal，不同单位分开。",
            ]
        )
    if action.action == "ListCoupons":
        result["interpretation_rules"].extend(
            [
                "ProductLimitList 是适用范围；ConfigurationType 和 ChargeItemType 的通配值必须按契约处理。",
                "BeginTime/ExpiredTime 与账单消费时间比较，不能用出账时间替代消费时间。",
                "实际抵扣与退回记录通过 ListCouponUsageRecords 查询；ListCoupons 只提供当前库存、状态和适用规则。",
                "AccountID 和 AssignedOwnerIDList 不进入 Agent 查询输出。",
            ]
        )
    if action.action == "ListCouponUsageRecords":
        result["interpretation_rules"].extend(
            [
                "ChangeType=2 是抵扣，ChangeType=3 是退回；分别汇总非负 ChangeAmount，负值不取绝对值并视为方向证据不足。",
                "PayType=post 时 SubBusinessID 匹配 ListBillDetail.BillDetailId；PayType=pre 时匹配预付费账单的 BillID。",
                "同账期存在核销记录不能单独证明它对应目标账单；必须按 PayType 使用相应标识关联。",
                "AccountID 和 UserAccountID 不进入 Agent 查询输出。",
            ]
        )
    return result


def request_overview(
    action: ApiActionSpec,
    selected_fields: Sequence[str] = (),
) -> Dict[str, Any]:
    selected = {field.rsplit(".", 1)[-1].replace("[]", "") for field in selected_fields}
    conditional_rules = list(ACTION_REQUEST_RULES.get(action.action, ()))
    optional_fields = [field.name for field in action.request_params if not field.is_required]
    if selected:
        optional_fields = [field for field in optional_fields if field in selected]
        conditional_rules = [
            rule for rule in conditional_rules
            if any(field in rule for field in selected)
        ]
    result = {
        "required_fields": [
            field.name for field in action.request_params if field.is_required
        ],
        "optional_fields": optional_fields,
        "conditional_rules": conditional_rules,
        "assembly_rule": (
            "只发送目标 Action request fields 中声明的参数；先满足 required_fields，"
            "再根据用户条件和 conditional_rules 选择 optional_fields。"
        ),
    }
    if action.action == "ListBillDetail" and (not selected or selected & {"GroupPeriod", "GroupTerm"}):
        result["preaggregation_guidance"] = list_bill_detail_preaggregation_guidance()
    if (
        action.action in {"ListBillDetail", "ListSplitBillDetail"}
        and (not selected or selected & {"GroupPeriod", "GroupTerm"})
    ):
        grain_guidance = action_field_grain_guidance(action.action)
        if grain_guidance:
            result["field_grain_guidance"] = grain_guidance
    return result


def action_selection_summary(action: ApiActionSpec) -> Dict[str, Any]:
    guidance = action_guidance(action)
    result = {
        "action": action.action,
        "title": guidance["title"],
        "purpose": guidance["purpose"],
        "data_grain": guidance["data_grain"],
        "result_kind": guidance["result_kind"],
        "use_when": guidance["use_when"],
        "avoid_when": guidance["avoid_when"],
        "important_limits": guidance["important_limits"],
    }
    for key in ("preferred_output",):
        if key in guidance:
            result[key] = guidance[key]
    return result
