from __future__ import annotations

from typing import List, Optional

from pydantic import StrictInt, StrictStr

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

class ListSplitBillDetailRequest(BillingContractModel):
    billing_mode: Optional[BillingModeValues] = (
        billing_mode_field()
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
            description='Owner账号ID；财务托管场景下，不指定owner时主账号可获取自身及其下绑定所有owner子账号费用；选择owner后，可精准获取指定owner的账单费用；',
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
    split_dimension: Optional[StrictStr] = (
        request_field(
            alias='SplitDimension',
            description='分拆维度，格式为JSON字符串，例如：\n{\n    "Product1": "Dim_A",\n    "Product2": "Dim_B"\n}\n当商品不支持多维度拆分，或分拆维度不存在时查询会报错。\n',
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
    project: Optional[List[StrictStr]] = (
        request_field(
            alias='Project',
            description='项目筛选，目前只支持明细维度生效，其他维度默认不生效。',
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
    tag_kv: Optional[List[TagKV]] = (
        tag_kv_field()
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
            description='账务账期：格式为YYYY-MM；仅支持单月查询；所查账期至多距今 24 个月',
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
    group_period: Optional[StrictInt] = (
        request_field(
            alias='GroupPeriod',
            description='统计周期；0：账期；1：按天；2：明细；不传时默认按月汇总费用，若需按天分别汇总每日费用可传1；',
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
    instance_no: Optional[StrictStr] = (
        request_field(
            alias='InstanceNo',
            description='云产品计费实例id，承载购买的云资源或资产的计费实体；',
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
    split_item_id: Optional[StrictStr] = (
        request_field(
            alias='SplitItemID',
            description='分拆项ID',
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

class ListSplitBillDetailResponseListItem(BillingContractModel):
    split_item_amount: Optional[StrictStr] = (
        response_field(
            alias='SplitItemAmount',
            description='分拆项用量',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    owner_user_name: Optional[StrictStr] = (
        response_field(
            alias='OwnerUserName',
            description='Owner账号名',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    payer_user_name: Optional[StrictStr] = (
        response_field(
            alias='PayerUserName',
            description='支付账号名',
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
    price_unit: Optional[StrictStr] = (
        response_field(
            alias='PriceUnit',
            description='单价单位',
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
            description='使用的产品/服务的商品中文名称；产品中文名称',
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
    billing_mode: Optional[StrictStr] = (
        response_field(
            alias='BillingMode',
            description='计费模式：1：包年包月，代表预付费；2：按量计费，代表后付费；3：合同计费，代表线下计费；4：履约计费；5：承诺消费；',
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
            description='交易时间，格式：2006-01-02 15:04:05，仅在GroupPeriod为2时有意义',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    bill_id: Optional[StrictStr] = (
        response_field(
            alias='BillID',
            description='预付费账单为订单号，否则为账单号，仅在GroupPeriod为2时有意义',
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
    settlement_type: Optional[StrictStr] = (
        response_field(
            alias='SettlementType',
            description='结算类型，settle：结算，non-settle：非结算，quota-settle：Quota结算，仅在GroupPeriod为2时有意义',
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
            description='配置名称，仅在GroupPeriod为2时有意义',
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
    split_item_id: Optional[StrictStr] = (
        response_field(
            alias='SplitItemID',
            description='分拆项ID',
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
    expense_time: Optional[StrictStr] = (
        response_field(
            alias='ExpenseTime',
            description='消费时间，GroupPeriod为0时无意义，GroupPeriod为1时表示消费日期，GroupPeriod为2时表示消费开始时间~消费结束时间',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    seller_user_name: Optional[StrictStr] = (
        response_field(
            alias='SellerUserName',
            description='Seller账号名',
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
    split_item_ratio: Optional[StrictStr] = (
        response_field(
            alias='SplitItemRatio',
            description='分拆用量占比，仅在GroupPeriod为2时有意义',
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
    solution_zh: Optional[StrictStr] = (
        response_field(
            alias='SolutionZh',
            description='解决方案中文名称',
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
    preferential_bill_amount: Optional[StrictStr] = (
        response_field(
            alias='PreferentialBillAmount',
            description='优惠金额',
            type_code=1,
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
    coupon_deduction_amount: Optional[StrictStr] = (
        response_field(
            alias='CouponDeductionAmount',
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
    subject_name: Optional[StrictStr] = (
        response_field(
            alias='SubjectName',
            description='主体名',
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
    split_bill_detail_id: Optional[StrictStr] = (
        response_field(
            alias='SplitBillDetailId',
            description='分账账单明细ID',
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
    split_item_name: Optional[StrictStr] = (
        response_field(
            alias='SplitItemName',
            description='分拆项名称',
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
    credit_carried_amount: Optional[StrictStr] = (
        response_field(
            alias='CreditCarriedAmount',
            description='信控额度退款抵扣',
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
            description='代表优惠类型；当DiscountBizBillingFunction为固定单价和单一折扣时，优惠内容取DiscountBizUnitPrice字段；当DiscountBizBillingFunction为阶梯价时，单价取DiscountBizMeasureInterval和DiscountBizUnitPriceInterval字段，表达各个用量区间的不同优惠内容；',
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
            description='代表单价价格类型；当BillingFunction为固定单价时，单价取Price字段；当BillingFunction为阶梯价时，单价取MeasureInterval和PriceInterval字段，表达各个用量区间的不同价格；',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    project_display_name: Optional[StrictStr] = (
        response_field(
            alias='ProjectDisplayName',
            description='项目中文名',
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
    payer_customer_name: Optional[StrictStr] = (
        response_field(
            alias='PayerCustomerName',
            description='支付账号客户名称',
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
    seller_id: Optional[StrictStr] = (
        response_field(
            alias='SellerID',
            description='Seller账号ID',
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
    busi_period: Optional[StrictStr] = (
        response_field(
            alias='BusiPeriod',
            description='业务账期',
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
    round_amount: Optional[StrictStr] = (
        response_field(
            alias='RoundAmount',
            description='抹零金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    tax: Optional[StrictStr] = (
        response_field(
            alias='Tax',
            description='税额（定价币种）',
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
    posttax_amount: Optional[StrictStr] = (
        response_field(
            alias='PosttaxAmount',
            description='税后应付金额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    pretax_amount: Optional[StrictStr] = (
        response_field(
            alias='PretaxAmount',
            description='税前应付金额（定价币种）',
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
    country_region: Optional[StrictStr] = (
        response_field(
            alias='CountryRegion',
            description='国家地区',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    real_value: Optional[StrictStr] = (
        response_field(
            alias='RealValue',
            description='真实金额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    pretax_real_value: Optional[StrictStr] = (
        response_field(
            alias='PretaxRealValue',
            description='税前真实金额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    settle_posttax_amount: Optional[StrictStr] = (
        response_field(
            alias='SettlePosttaxAmount',
            description='税后应付金额（结算币种）',
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
    settle_pretax_amount: Optional[StrictStr] = (
        response_field(
            alias='SettlePretaxAmount',
            description='税前应付金额（结算币种）',
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
    settle_tax: Optional[StrictStr] = (
        response_field(
            alias='SettleTax',
            description='税额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    settle_real_value: Optional[StrictStr] = (
        response_field(
            alias='SettleRealValue',
            description='税后真实金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    settle_pretax_real_value: Optional[StrictStr] = (
        response_field(
            alias='SettlePretaxRealValue',
            description='税前真实金额（结算币种）',
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
    original_order_no: Optional[StrictStr] = (
        response_field(
            alias='OriginalOrderNo',
            description='原订单号',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    bill_detail_id: Optional[StrictStr] = (
        response_field(
            alias='BillDetailId',
            description='账单明细号',
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
    cost_unit: Optional[StrictStr] = (
        response_field(
            alias='CostUnit',
            description='成本单元',
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
    count: Optional[StrictStr] = (
        response_field(
            alias='Count',
            description='账单明细用量',
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
    expense_date: Optional[StrictStr] = (
        response_field(
            alias='ExpenseDate',
            description='日期',
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

class ListSplitBillDetailResponse(BillingContractModel):
    warning: Optional[StrictStr] = (
        response_field(
            alias='Warning',
            description='当请求可被处理但部分筛选条件被忽略、过滤或降级时返回；为空表示无提示。',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    list: Optional[List[ListSplitBillDetailResponseListItem]] = (
        response_field(
            alias='List',
            description='分账账单列表',
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
    action='ListSplitBillDetail',
    name_zh='分页查询分账账单',
    description='提供包含资源项目/标签信息的分账账单，以供企业用于识别基于内部部门、业务线、组织等的费用分账归属和管理；相比账单明细存在2天延迟，分账账单生成后，项目/标签参数最晚延迟12小时更新补充；了解更多详情可查看[分账账单](https://www.volcengine.com/docs/6269/177196?lang=zh)说明；',
    timeout_ms=5000,
    response_data_path='Result',
    error_code_path='ResponseMetadata.Error.Code',
    error_message_path='ResponseMetadata.Error.Message',
    request_model=ListSplitBillDetailRequest,
    response_model=ListSplitBillDetailResponse,
)
