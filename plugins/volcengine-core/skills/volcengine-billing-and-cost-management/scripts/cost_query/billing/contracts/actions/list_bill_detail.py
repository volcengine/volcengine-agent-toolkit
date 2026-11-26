from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import StrictFloat, StrictInt, StrictStr

from ..base import (
    ActionContract,
    BillingContractModel,
    request_field,
    response_field,
)
from ..common import (
    BillingModeValues,
    NeedRecordNumValue,
    TagKV,
    billing_mode_field,
    need_record_num_field,
    page_limit_field,
    page_offset_field,
    tag_kv_field,
)

class ListBillDetailRequest(BillingContractModel):
    payer_id: Optional[List[StrictInt]] = (
        request_field(
            alias='PayerID',
            description='Payer账号ID\n',
            type_code=3,
            is_public=True,
            is_array=True,
            required=False,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=False,
            enum_value='',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )
    owner_id: Optional[List[StrictInt]] = (
        request_field(
            alias='OwnerID',
            description='Owner账号ID\n',
            type_code=3,
            is_public=True,
            is_array=True,
            required=False,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=False,
            enum_value='',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )
    project: Optional[List[StrictStr]] = (
        request_field(
            alias='Project',
            description='项目筛选，目前只支持计费项明细维度生效，其他维度默认不生效。',
            type_code=1,
            is_public=True,
            is_array=True,
            required=False,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=False,
            enum_value='',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )
    tag_kv: Optional[List[TagKV]] = (
        tag_kv_field()
    )
    tag_kv_filter_mode: Optional[StrictInt] = (
        request_field(
            alias='TagKVFilterMode',
            description='标签键值对筛选匹配模式。当传入多个 TagKV 条件时，用于控制条件之间的匹配逻辑。\n  - 0：任一匹配，满足任意一个标签键值对条件即可返回结果。\n  - 1：全部匹配，必须同时满足所有标签键值对条件才返回结果。',
            type_code=2,
            is_public=True,
            is_array=False,
            required=False,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=False,
            enum_value='',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )
    product: Optional[List[StrictStr]] = (
        request_field(
            alias='Product',
            description='产品名称，默认不选为全部\n',
            type_code=1,
            is_public=True,
            is_array=True,
            required=False,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=False,
            enum_value='',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )
    billing_mode: Optional[BillingModeValues] = (
        billing_mode_field()
    )
    bill_category: Optional[List[StrictStr]] = (
        request_field(
            alias='BillCategory',
            description='账单类型：consume-use：消费-使用；consume-new：消费-新购；consume-renew：消费-续费；consume-formalize：消费-转正；consume-modify：消费-更配；consume-trial：消费-试用；refund-terminate：退款-退订；refund-modify：退款-更配；transfer-manual：调账-人工；transfer-system：调账-系统；默认不选为全部\n',
            type_code=1,
            is_public=True,
            is_array=True,
            required=False,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=False,
            enum_value='',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )
    offset: Optional[StrictInt] = (
        page_offset_field()
    )
    limit: StrictInt = (
        page_limit_field()
    )
    bill_period: StrictStr = (
        request_field(
            alias='BillPeriod',
            description='账期：格式为YYYY-MM；仅支持单月查询；所查账期至多距今 24 个月',
            type_code=1,
            is_public=True,
            is_array=False,
            required=True,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=False,
            enum_value='',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )
    expense_date: Optional[StrictStr] = (
        request_field(
            alias='ExpenseDate',
            description='账单日期，在GroupPeriod=1或2时支持账单日期传参，必须与账期在同一月份。该参数可提升查询性能，建议填写。',
            type_code=1,
            is_public=True,
            is_array=False,
            required=False,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=False,
            enum_value='',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )
    group_term: Optional[Literal[0, 1, 2, 3]] = (
        request_field(
            alias='GroupTerm',
            description='统计项：0：计费项；1：实例；2：产品；3：账号。账单明细口径下不存在产品+明细、账号+明细粒度，因此 GroupPeriod=2 时不支持 GroupTerm=2 或 3。',
            type_code=2,
            is_public=True,
            is_array=False,
            required=False,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=True,
            enum_value='0,1,2,3',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )
    group_period: Optional[Literal[0, 1, 2]] = (
        request_field(
            alias='GroupPeriod',
            description='统计周期；0：账期；1：按天；2：明细；不传时默认按月汇总费用，若需按天分别汇总每日费用可传1；账单明细口径下不存在产品+明细、账号+明细粒度，因此 GroupPeriod=2 时不支持 GroupTerm=2 或 3。',
            type_code=2,
            is_public=True,
            is_array=False,
            required=False,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=True,
            enum_value='0,1,2',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )
    instance_no: Optional[StrictStr] = (
        request_field(
            alias='InstanceNo',
            description='实例id：云产品计费实例id，承载购买的云资源或资产的计费实体；',
            type_code=1,
            is_public=True,
            is_array=False,
            required=False,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=False,
            enum_value='',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )
    ignore_zero: Optional[StrictInt] = (
        request_field(
            alias='IgnoreZero',
            description='是否忽略折后价为0的数据：0：不忽略；1：忽略；默认为不忽略',
            type_code=2,
            is_public=True,
            is_array=False,
            required=False,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=False,
            enum_value='',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )
    need_record_num: Optional[NeedRecordNumValue] = (
        need_record_num_field()
    )

class ListBillDetailResponseListItem(BillingContractModel):
    project_display_name: Optional[StrictStr] = (
        response_field(
            alias='ProjectDisplayName',
            description='项目中文名',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    formula: Optional[StrictStr] = (
        response_field(
            alias='Formula',
            description='应付金额计费公式',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    posttax_amount: Optional[StrictStr] = (
        response_field(
            alias='PosttaxAmount',
            description='税后应付金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    country_region: Optional[StrictStr] = (
        response_field(
            alias='CountryRegion',
            description='国家地区',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    tax: Optional[StrictStr] = (
        response_field(
            alias='Tax',
            description='税额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    settle_tax: Optional[StrictStr] = (
        response_field(
            alias='SettleTax',
            description='结算币种税额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    tax_rate: Optional[StrictStr] = (
        response_field(
            alias='TaxRate',
            description='税率',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    pretax_real_value: Optional[StrictStr] = (
        response_field(
            alias='PretaxRealValue',
            description='税前真实金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    settle_real_value: Optional[StrictStr] = (
        response_field(
            alias='SettleRealValue',
            description='结算币种真实金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    settle_pretax_real_value: Optional[StrictStr] = (
        response_field(
            alias='SettlePretaxRealValue',
            description='结算币种税前真实金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    real_value: Optional[StrictStr] = (
        response_field(
            alias='RealValue',
            description='真实金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    pretax_amount: Optional[StrictStr] = (
        response_field(
            alias='PretaxAmount',
            description='税前应付金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    settle_posttax_amount: Optional[StrictStr] = (
        response_field(
            alias='SettlePosttaxAmount',
            description='结算币种税后应付金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    settle_pretax_amount: Optional[StrictStr] = (
        response_field(
            alias='SettlePretaxAmount',
            description='结算币种税前应付金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    saving_plan_original_amount: Optional[StrictStr] = (
        response_field(
            alias='SavingPlanOriginalAmount',
            description='节省计划抵扣原价',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    saving_plan_deduction_sp_id: Optional[StrictStr] = (
        response_field(
            alias='SavingPlanDeductionSpID',
            description='节省计划实例ID',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    saving_plan_deduction_discount_amount: Optional[StrictStr] = (
        response_field(
            alias='SavingPlanDeductionDiscountAmount',
            description='节省计划抵扣金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    discount_info: Optional[StrictStr] = (
        response_field(
            alias='DiscountInfo',
            description='优惠信息',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    pre_tax_payable_amount: Optional[StrictStr] = (
        response_field(
            alias='PreTaxPayableAmount',
            description='税前应付金额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    settle_payable_amount: Optional[StrictStr] = (
        response_field(
            alias='SettlePayableAmount',
            description='税后应付金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    settle_pre_tax_payable_amount: Optional[StrictStr] = (
        response_field(
            alias='SettlePreTaxPayableAmount',
            description='税前应付金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    currency_settlement: Optional[StrictStr] = (
        response_field(
            alias='CurrencySettlement',
            description='结算币种',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    exchange_rate: Optional[StrictStr] = (
        response_field(
            alias='ExchangeRate',
            description='汇率',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    main_contract_number: Optional[StrictStr] = (
        response_field(
            alias='MainContractNumber',
            description='合同号',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    original_order_no: Optional[StrictStr] = (
        response_field(
            alias='OriginalOrderNo',
            description='原订单号',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    resource_id: Optional[StrictStr] = (
        response_field(
            alias='ResourceID',
            description='资源ID',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    charge_item_code: Optional[StrictStr] = (
        response_field(
            alias='ChargeItemCode',
            description='计费项code',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    saving_plan_deduction_discount_total_amount: Optional[StrictStr] = (
        response_field(
            alias='SavingPlanDeductionDiscountTotalAmount',
            description='节省计划抵扣总额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    price_factor: Optional[StrictStr] = (
        response_field(
            alias='PriceFactor',
            description='算价因子',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    pickup_voucher_count_unit: Optional[StrictStr] = (
        response_field(
            alias='PickupVoucherCountUnit',
            description='提货券抵扣量单位',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    pickup_voucher_id: Optional[StrictStr] = (
        response_field(
            alias='PickupVoucherID',
            description='提货券ID',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    pickup_voucher_deduct_count: Optional[StrictStr] = (
        response_field(
            alias='PickupVoucherDeductCount',
            description='提货券抵扣量',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    tag_remark: Optional[StrictStr] = (
        response_field(
            alias='TagRemark',
            description='标签备注',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    project_remark: Optional[StrictStr] = (
        response_field(
            alias='ProjectRemark',
            description='项目备注',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    point_deduct_amount: Optional[StrictStr] = (
        response_field(
            alias='PointDeductAmount',
            description='积分抵扣金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    discount_biz_unit_price: Optional[StrictStr] = (
        response_field(
            alias='DiscountBizUnitPrice',
            description='优惠价格/折扣',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    discount_biz_unit_price_interval: Optional[StrictStr] = (
        response_field(
            alias='DiscountBizUnitPriceInterval',
            description='优惠价格区间',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    discount_biz_measure_interval: Optional[StrictStr] = (
        response_field(
            alias='DiscountBizMeasureInterval',
            description='优惠用量区间',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    effective_factor: Optional[StrictStr] = (
        response_field(
            alias='EffectiveFactor',
            description='有效因子',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    price_interval: Optional[StrictStr] = (
        response_field(
            alias='PriceInterval',
            description='单价价格区间',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    measure_interval: Optional[StrictStr] = (
        response_field(
            alias='MeasureInterval',
            description='单价用量区间',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    billing_method_code: Optional[StrictStr] = (
        response_field(
            alias='BillingMethodCode',
            description='计费方式',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    discount_biz_billing_function: Optional[StrictStr] = (
        response_field(
            alias='DiscountBizBillingFunction',
            description='代表优惠类型；当DiscountBizBillingFunction为固定单价和单一折扣时，优惠内容取DiscountBizUnitPrice字段；当DiscountBizBillingFunction为阶梯价时，单价取DiscountBizMeasureInterval和DiscountBizUnitPriceInterval字段，表达各个用量区间的不同优惠内容',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    price: Optional[StrictStr] = (
        response_field(
            alias='Price',
            description='单价',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    market_price: Optional[StrictStr] = (
        response_field(
            alias='MarketPrice',
            description='市场价',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    billing_function: Optional[StrictStr] = (
        response_field(
            alias='BillingFunction',
            description='代表单价价格类型；当BillingFunction为固定单价时，单价取Price字段；当BillingFunction为阶梯价时，单价取MeasureInterval和PriceInterval字段，表达各个用量区间的不同价格',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    credit_carried_amount: Optional[StrictStr] = (
        response_field(
            alias='CreditCarriedAmount',
            description='信控额度退款抵扣',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    preferential_bill_amount: Optional[StrictStr] = (
        response_field(
            alias='PreferentialBillAmount',
            description='优惠金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    instance_name: Optional[StrictStr] = (
        response_field(
            alias='InstanceName',
            description='实例名称',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    config_name: Optional[StrictStr] = (
        response_field(
            alias='ConfigName',
            description='配置名称',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    element: Optional[StrictStr] = (
        response_field(
            alias='Element',
            description='计费单元',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    region: Optional[StrictStr] = (
        response_field(
            alias='Region',
            description='地域',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    zone: Optional[StrictStr] = (
        response_field(
            alias='Zone',
            description='可用区',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    factor: Optional[StrictStr] = (
        response_field(
            alias='Factor',
            description='影响因子',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    expand_field: Optional[StrictStr] = (
        response_field(
            alias='ExpandField',
            description='扩展字段',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    price_unit: Optional[StrictStr] = (
        response_field(
            alias='PriceUnit',
            description='单价单位',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    busi_period: Optional[StrictStr] = (
        response_field(
            alias='BusiPeriod',
            description='业务账期',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    count: Optional[StrictStr] = (
        response_field(
            alias='Count',
            description='用量',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    unit: Optional[StrictStr] = (
        response_field(
            alias='Unit',
            description='用量单位',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    bill_detail_id: Optional[StrictStr] = (
        response_field(
            alias='BillDetailId',
            description='账单明细ID',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    deduction_count: Optional[StrictStr] = (
        response_field(
            alias='DeductionCount',
            description='资源包抵扣量',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    original_bill_amount: Optional[StrictStr] = (
        response_field(
            alias='OriginalBillAmount',
            description='原价',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    round_amount: Optional[StrictFloat] = (
        response_field(
            alias='RoundAmount',
            description='抹零金额',
            type_code=5,
            is_public=True,
            is_array=False,
        )
    )
    discount_bill_amount: Optional[StrictStr] = (
        response_field(
            alias='DiscountBillAmount',
            description='折后价',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    coupon_amount: Optional[StrictStr] = (
        response_field(
            alias='CouponAmount',
            description='代金券抵扣',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    payable_amount: Optional[StrictStr] = (
        response_field(
            alias='PayableAmount',
            description='应付金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    paid_amount: Optional[StrictStr] = (
        response_field(
            alias='PaidAmount',
            description='现金支付',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    unpaid_amount: Optional[StrictStr] = (
        response_field(
            alias='UnpaidAmount',
            description='欠费金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    currency: Optional[StrictStr] = (
        response_field(
            alias='Currency',
            description='币种',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    settlement_type: Optional[StrictStr] = (
        response_field(
            alias='SettlementType',
            description='非结算',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    project: Optional[StrictStr] = (
        response_field(
            alias='Project',
            description='项目：资源实例所属的项目信息，通常可定义为企业内部的部门、业务线等以便厘清成本归属与进行分账管理；取值为结算周期所在小时末实例所属的项目；按天/账期聚合时，项目展示为最新的项目；',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    tag: Optional[StrictStr] = (
        response_field(
            alias='Tag',
            description='标签：资源实例的标识；同一资源可绑定多个标签键值对，如资源创建者、资源使用部门、资源应用系统或环境等来标识资源费用信息；取值为结算周期的最后一小时内资源实例存在过的标签信息；按天/账期聚合时，标签展示为最新的标签；',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    selling_mode: Optional[StrictStr] = (
        response_field(
            alias='SellingMode',
            description='售卖模式，0：普通实例，1：竞价实例',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    solution_zh: Optional[StrictStr] = (
        response_field(
            alias='SolutionZh',
            description='解决方案中文名称',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    subject_name: Optional[StrictStr] = (
        response_field(
            alias='SubjectName',
            description='主体名',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    owner_user_name: Optional[StrictStr] = (
        response_field(
            alias='OwnerUserName',
            description='Owner账户名',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    bill_category: Optional[StrictStr] = (
        response_field(
            alias='BillCategory',
            description='账单类型',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    reservation_instance: Optional[StrictStr] = (
        response_field(
            alias='ReservationInstance',
            description='售卖模式，0：普通实例，1：弹性预约实例',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    element_code: Optional[StrictStr] = (
        response_field(
            alias='ElementCode',
            description='计费单元Code',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    region_code: Optional[StrictStr] = (
        response_field(
            alias='RegionCode',
            description='地域Code',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    zone_code: Optional[StrictStr] = (
        response_field(
            alias='ZoneCode',
            description='可用区Code',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    factor_code: Optional[StrictStr] = (
        response_field(
            alias='FactorCode',
            description='影响因子Code',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    configuration_code: Optional[StrictStr] = (
        response_field(
            alias='ConfigurationCode',
            description='配置Code',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    deduction_use_duration: Optional[StrictStr] = (
        response_field(
            alias='DeductionUseDuration',
            description='抵扣量',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    bill_period: Optional[StrictStr] = (
        response_field(
            alias='BillPeriod',
            description='账期',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    expense_date: Optional[StrictStr] = (
        response_field(
            alias='ExpenseDate',
            description='日期；仅支持单日查询；在天维度下该参数可提升查询性能，建议填写',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    payer_id: Optional[StrictStr] = (
        response_field(
            alias='PayerID',
            description='支付账号ID',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    payer_user_name: Optional[StrictStr] = (
        response_field(
            alias='PayerUserName',
            description='支付账户名',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    payer_customer_name: Optional[StrictStr] = (
        response_field(
            alias='PayerCustomerName',
            description='支付账号客户名称',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    seller_id: Optional[StrictStr] = (
        response_field(
            alias='SellerID',
            description='Seller账号ID',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    seller_user_name: Optional[StrictStr] = (
        response_field(
            alias='SellerUserName',
            description='Seller账户名',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    seller_customer_name: Optional[StrictStr] = (
        response_field(
            alias='SellerCustomerName',
            description='Seller账号客户名称',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    owner_id: Optional[StrictStr] = (
        response_field(
            alias='OwnerID',
            description='Owner账号ID',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    owner_customer_name: Optional[StrictStr] = (
        response_field(
            alias='OwnerCustomerName',
            description='Owner账号客户名称',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    business_mode: Optional[StrictStr] = (
        response_field(
            alias='BusinessMode',
            description='业务类型',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    product: Optional[StrictStr] = (
        response_field(
            alias='Product',
            description='产品英文名称',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    product_zh: Optional[StrictStr] = (
        response_field(
            alias='ProductZh',
            description='使用的产品/服务的商品中文名称；',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    billing_mode: Optional[StrictStr] = (
        response_field(
            alias='BillingMode',
            description='计费模式：1：包年包月，代表预付费；2：按量计费，代表后付费；3：合同计费，代表线下计费；4：履约计费；5：承诺消费；',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    expense_begin_time: Optional[StrictStr] = (
        response_field(
            alias='ExpenseBeginTime',
            description='消费开始时间',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    expense_end_time: Optional[StrictStr] = (
        response_field(
            alias='ExpenseEndTime',
            description='消费结束时间',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    use_duration: Optional[StrictStr] = (
        response_field(
            alias='UseDuration',
            description='使用时长',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    use_duration_unit: Optional[StrictStr] = (
        response_field(
            alias='UseDurationUnit',
            description='时长单位',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    trade_time: Optional[StrictStr] = (
        response_field(
            alias='TradeTime',
            description='交易时间，格式：2006-01-02 15:04:05',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    bill_id: Optional[StrictStr] = (
        response_field(
            alias='BillID',
            description='订单号/账单号',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    instance_no: Optional[StrictStr] = (
        response_field(
            alias='InstanceNo',
            description='实例ID',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class ListBillDetailResponse(BillingContractModel):
    warning: Optional[StrictStr] = (
        response_field(
            alias='Warning',
            description='当请求可被处理但部分筛选条件被忽略、过滤或降级时返回；为空表示无提示。',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    list: Optional[List[ListBillDetailResponseListItem]] = (
        response_field(
            alias='List',
            description='账单明细列表',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    total: Optional[StrictInt] = (
        response_field(
            alias='Total',
            description='总数，默认返回-1（NeedRecordNum=0时）',
            type_code=2,
            is_public=True,
            is_array=False,
        )
    )
    limit: Optional[StrictInt] = (
        response_field(
            alias='Limit',
            description='步长',
            type_code=2,
            is_public=True,
            is_array=False,
        )
    )
    offset: Optional[StrictInt] = (
        response_field(
            alias='Offset',
            description='偏移量',
            type_code=2,
            is_public=True,
            is_array=False,
        )
    )

CONTRACT = ActionContract(
    action='ListBillDetail',
    name_zh='分页查询账单明细',
    description='提供包含用量、价格、优惠折扣、计费规则等的计费明细信息；账单明细口径不存在产品+明细、账号+明细粒度；请于每月第2个自然日12点后获取上月完整账单数据；',
    timeout_ms=5000,
    response_data_path='Result',
    error_code_path='ResponseMetadata.Error.Code',
    error_message_path='ResponseMetadata.Error.Message',
    request_model=ListBillDetailRequest,
    response_model=ListBillDetailResponse,
)
