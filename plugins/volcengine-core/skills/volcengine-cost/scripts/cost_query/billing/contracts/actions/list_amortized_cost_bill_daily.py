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

class ListAmortizedCostBillDailyRequest(BillingContractModel):
    billing_mode: Optional[BillingModeValues] = (
        billing_mode_field()
    )
    amortized_type: Optional[List[StrictStr]] = (
        request_field(
            alias='AmortizedType',
            description='分摊类型：1：履约计费分摊；2：合同计费分摊；3：按量计费分摊；4：新购分摊；5：更配分摊；6：续费分摊；7：退订分摊；8：预留实例调整分摊；9：试用分摊；10：转正分摊；默认不选为全部\n',
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
    amortized_day: Optional[StrictStr] = (
        request_field(
            alias='AmortizedDay',
            description='分摊日：格式为YYYY-MM-DD；仅支持单日查询；最早只能查询2023-04-01。该参数可提升查询性能，建议填写。',
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
    offset: Optional[StrictInt] = (
        page_offset_field()
    )
    limit: StrictInt = (
        page_limit_field()
    )
    bill_period: Optional[StrictStr] = (
        request_field(
            alias='BillPeriod',
            description='账务账期：格式为YYYY-MM；仅支持单月查询；所查账期至多距今 24 个月；最早只能查询2023-04',
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
    amortized_month: StrictStr = (
        request_field(
            alias='AmortizedMonth',
            description='分摊月：格式为YYYY-MM；仅支持单月查询；所查分摊月至多距今 24 个月；最早只能查询2023-04；资源实际使用日期对应的自然月；如4月27日购买包月实例，根据实际使用日期分摊到了2025年5月1日，则该条成本明细的归属分摊月为2025年5月；',
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
    instance_no: Optional[StrictStr] = (
        request_field(
            alias='InstanceNo',
            description='实例id，默认不选为全部；云产品计费实例id，承载购买的云资源或资产的计费实体；',
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

class ListAmortizedCostBillDailyResponseListItem(BillingContractModel):
    now_amortized_round_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedRoundAmount',
            description='本日已分摊-抹零金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    amortized_day: Optional[StrictStr] = (
        response_field(
            alias='AmortizedDay',
            description='分摊日',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_round_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedRoundAmount',
            description='每日分摊-抹零金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_discount_bill_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedDiscountBillAmount',
            description='每日分摊-折后价',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_paid_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedPaidAmount',
            description='每日分摊-现金支付',
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
    now_amortized_original_bill_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedOriginalBillAmount',
            description='本日已分摊-原价',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_original_bill_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedOriginalBillAmount',
            description='每日分摊-原始账单金额',
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
    now_amortized_paid_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedPaidAmount',
            description='本日已分摊-现金支付',
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
    now_amortized_preferential_bill_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedPreferentialBillAmount',
            description='本日已分摊-优惠金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    expense_time: Optional[StrictStr] = (
        response_field(
            alias='ExpenseTime',
            description='消费时间',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_preferential_bill_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedPreferentialBillAmount',
            description='每日分摊-优惠金额',
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
    now_amortized_discount_bill_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedDiscountBillAmount',
            description='本日已分摊-折后价',
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
    bill_period: Optional[StrictStr] = (
        response_field(
            alias='BillPeriod',
            description='账务账期',
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
            description='支付账号名',
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
            description='Seller账号名',
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
    amortized_month: Optional[StrictStr] = (
        response_field(
            alias='AmortizedMonth',
            description='资源实际使用日期对应的自然月；如4月27日购买包月实例，根据实际使用日期分摊到了2025年5月1日，则该条成本明细的归属分摊月为2025年5月；',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    instance_no: Optional[StrictStr] = (
        response_field(
            alias='InstanceNo',
            description='云产品计费实例id，承载购买的云资源或资产的计费实体；',
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
    instance_name: Optional[StrictStr] = (
        response_field(
            alias='InstanceName',
            description='实例名称',
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
    expand_field: Optional[StrictStr] = (
        response_field(
            alias='ExpandField',
            description='扩展字段',
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
            description='使用时长单位',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    bill_id: Optional[StrictStr] = (
        response_field(
            alias='BillID',
            description='预付费账单为订单号，否则为账单号',
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
    owner_user_name: Optional[StrictStr] = (
        response_field(
            alias='OwnerUserName',
            description='Owner账号名',
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
    config_name: Optional[StrictStr] = (
        response_field(
            alias='ConfigName',
            description='配置名称',
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
    bill_category: Optional[StrictStr] = (
        response_field(
            alias='BillCategory',
            description='账单类型',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    amortized_type: Optional[StrictStr] = (
        response_field(
            alias='AmortizedType',
            description='分摊类型',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    amortized_begin_time: Optional[StrictStr] = (
        response_field(
            alias='AmortizedBeginTime',
            description='分摊开始时间，格式：2023-04-02 00:00:00',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    amortized_end_time: Optional[StrictStr] = (
        response_field(
            alias='AmortizedEndTime',
            description='分摊结束时间，格式：2023-04-02 23:59:59',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_payable_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedPayableAmount',
            description='每日分摊-应付金额',
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
    tag: Optional[StrictStr] = (
        response_field(
            alias='Tag',
            description='标签：资源实例的标识；同一资源可绑定多个标签键值对，如资源创建者、资源使用部门、资源应用系统或环境等来标识资源费用信息；取值为结算周期的最后一小时内资源实例存在过的标签信息；按天/账期聚合时，标签展示为最新的标签；',
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
    currency: Optional[StrictStr] = (
        response_field(
            alias='Currency',
            description='币种',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_payable_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedPayableAmount',
            description='本日已分摊-应付金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_coupon_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedCouponAmount',
            description='本日已分摊-代金券抵扣',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_coupon_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedCouponAmount',
            description='每日分摊-代金券抵扣',
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
    round_amount: Optional[StrictStr] = (
        response_field(
            alias='RoundAmount',
            description='抹零金额',
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
    payable_amount: Optional[StrictStr] = (
        response_field(
            alias='PayableAmount',
            description='应付金额',
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
    project_display_name: Optional[StrictStr] = (
        response_field(
            alias='ProjectDisplayName',
            description='项目中文名',
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
    split_item_name: Optional[StrictStr] = (
        response_field(
            alias='SplitItemName',
            description='分拆项名称',
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
    saving_plan_original_amount: Optional[StrictStr] = (
        response_field(
            alias='SavingPlanOriginalAmount',
            description='节省计划抵扣原价',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_saving_plan_original_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedSavingPlanOriginalAmount',
            description='每日分摊-节省计划抵扣原价',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_saving_plan_original_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedSavingPlanOriginalAmount',
            description='本日已分摊-节省计划抵扣原价',
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
    pre_tax_real_value: Optional[StrictStr] = (
        response_field(
            alias='PreTaxRealValue',
            description='税前真实金额（定价币种）',
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
    pretax_amount: Optional[StrictStr] = (
        response_field(
            alias='PretaxAmount',
            description='税前应付金额（定价币种）',
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
    settle_pre_tax_real_value: Optional[StrictStr] = (
        response_field(
            alias='SettlePreTaxRealValue',
            description='税前真实金额（结算币种）',
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
    settle_pretax_amount: Optional[StrictStr] = (
        response_field(
            alias='SettlePretaxAmount',
            description='税前应付金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    settle_tax_amount: Optional[StrictStr] = (
        response_field(
            alias='SettleTaxAmount',
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
    settle_payable_amount: Optional[StrictStr] = (
        response_field(
            alias='SettlePayableAmount',
            description='税后应付金额（结算币种）',
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
    real_value: Optional[StrictStr] = (
        response_field(
            alias='RealValue',
            description='税后真实金额（定价币种）',
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
    daily_amortized_pre_tax_real_value: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedPreTaxRealValue',
            description='每日分摊-税前真实金额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_pre_tax_payable_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedPreTaxPayableAmount',
            description='每日分摊-税前应付金额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_pretax_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedPretaxAmount',
            description='每日分摊-税前应付金额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_tax_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedTaxAmount',
            description='每日分摊-税额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_settle_pre_tax_real_value: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedSettlePreTaxRealValue',
            description='每日分摊-税后真实金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_settle_pre_tax_payable_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedSettlePreTaxPayableAmount',
            description='每日分摊-税前应付金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_settle_pretax_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedSettlePretaxAmount',
            description='每日分摊-税前应付金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_settle_tax_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedSettleTaxAmount',
            description='每日分摊-税额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_settle_real_value: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedSettleRealValue',
            description='每日分摊-税后真实金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_settle_payable_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedSettlePayableAmount',
            description='每日分摊-税后应付金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_settle_posttax_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedSettlePosttaxAmount',
            description='每日分摊-税后应付金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_real_value: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedRealValue',
            description='每日分摊-税后真实金额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    daily_amortized_posttax_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedPosttaxAmount',
            description='每日分摊-税后应付金额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_pre_tax_real_value: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedPreTaxRealValue',
            description='本日已分摊-税前真实金额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_pre_tax_payable_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedPreTaxPayableAmount',
            description='本日已分摊-税前应付金额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_pretax_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedPretaxAmount',
            description='本日已分摊-税前应付金额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_tax_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedTaxAmount',
            description='本日已分摊-税额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_settle_pre_tax_real_value: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedSettlePreTaxRealValue',
            description='本日已分摊-税后真实金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_settle_pre_tax_payable_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedSettlePreTaxPayableAmount',
            description='本日已分摊-税前应付金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_settle_pretax_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedSettlePretaxAmount',
            description='本日已分摊-税前应付金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_settle_tax_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedSettleTaxAmount',
            description='本日已分摊-税额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_settle_real_value: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedSettleRealValue',
            description='本日已分摊-税后真实金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_settle_payable_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedSettlePayableAmount',
            description='本日已分摊-税后应付金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_settle_posttax_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedSettlePosttaxAmount',
            description='本日已分摊-税后应付金额（结算币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_real_value: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedRealValue',
            description='本日已分摊-税后真实金额（定价币种）',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_posttax_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedPosttaxAmount',
            description='本日已分摊-税后应付金额（定价币种）',
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
    effective_factor: Optional[StrictStr] = (
        response_field(
            alias='EffectiveFactor',
            description='有效因子',
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
    billing_function: Optional[StrictStr] = (
        response_field(
            alias='BillingFunction',
            description='代表单价价格类型；当BillingFunction为固定单价时，单价取Price字段；当BillingFunction为阶梯价时，单价取MeasureInterval和PriceInterval字段，表达各个用量区间的不同价格；',
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
            description='计费项Code',
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
    daily_amortized_point_deduct_amount: Optional[StrictStr] = (
        response_field(
            alias='DailyAmortizedPointDeductAmount',
            description='每日分摊-积分抵扣金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    now_amortized_point_deduct_amount: Optional[StrictStr] = (
        response_field(
            alias='NowAmortizedPointDeductAmount',
            description='本日已分摊-积分抵扣金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class ListAmortizedCostBillDailyResponse(BillingContractModel):
    warning: Optional[StrictStr] = (
        response_field(
            alias='Warning',
            description='当请求可被处理但部分筛选条件被忽略、过滤或降级时返回；为空表示无提示。',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    list: Optional[List[ListAmortizedCostBillDailyResponseListItem]] = (
        response_field(
            alias='List',
            description='成本明细按天列表',
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
    action='ListAmortizedCostBillDaily',
    name_zh='查询成本账单按天',
    description='提供基于资源实际使用周期的分摊账单并按分摊日聚合，如将包年包月订单费用分摊到实际生效周期的每一日；如需使用请及时[开通](https://console.volcengine.com/finance/bill/cost-bill)，未开通时不提供成本分摊数据；相比账单明细存在2天延迟；了解更多详情可查看[成本账单](https://www.volcengine.com/docs/6269/1112862?lang=zh)说明；',
    timeout_ms=5000,
    response_data_path='Result',
    error_code_path='ResponseMetadata.Error.Code',
    error_message_path='ResponseMetadata.Error.Message',
    request_model=ListAmortizedCostBillDailyRequest,
    response_model=ListAmortizedCostBillDailyResponse,
)
