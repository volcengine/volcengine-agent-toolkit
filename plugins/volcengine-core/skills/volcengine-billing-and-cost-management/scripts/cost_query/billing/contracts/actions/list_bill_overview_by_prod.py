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
    billing_mode_field,
    need_record_num_field,
    page_limit_field,
    page_offset_field,
)

class ListBillOverviewByProdRequest(BillingContractModel):
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
    ignore_zero: Optional[StrictInt] = (
        request_field(
            alias='IgnoreZero',
            description='是否忽略折后价为0的数据：0：不忽略；1：忽略；默认为不忽略；',
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
    billing_mode: Optional[BillingModeValues] = (
        billing_mode_field()
    )
    bill_category_parent: Optional[List[StrictStr]] = (
        request_field(
            alias='BillCategoryParent',
            description='账单大类类型：consume：消费；refund：退款；transfer：调账；默认不选为全部；',
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

class ListBillOverviewByProdResponseListItem(BillingContractModel):
    bill_period: Optional[StrictStr] = (
        response_field(
            alias='BillPeriod',
            description='账期',
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
    owner_user_name: Optional[StrictStr] = (
        response_field(
            alias='OwnerUserName',
            description='Owner账户名',
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
    bill_category_parent: Optional[StrictStr] = (
        response_field(
            alias='BillCategoryParent',
            description='账单类型',
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
    round_bill_amount: Optional[StrictStr] = (
        response_field(
            alias='RoundBillAmount',
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
    settlement_type: Optional[StrictStr] = (
        response_field(
            alias='SettlementType',
            description='结算类型，settle：结算，non-settle：非结算，quota-settle：Quota结算',
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
    currency: Optional[StrictStr] = (
        response_field(
            alias='Currency',
            description='币种',
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
    settle_tax: Optional[StrictStr] = (
        response_field(
            alias='SettleTax',
            description='结算币种税额',
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
    posttax_amount: Optional[StrictStr] = (
        response_field(
            alias='PosttaxAmount',
            description='税后应付金额',
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
    tax: Optional[StrictStr] = (
        response_field(
            alias='Tax',
            description='税额',
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
    settle_real_value: Optional[StrictStr] = (
        response_field(
            alias='SettleRealValue',
            description='结算币种真实金额',
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
    pretax_real_value: Optional[StrictStr] = (
        response_field(
            alias='PretaxRealValue',
            description='税前真实金额',
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
    point_deduct_amount: Optional[StrictStr] = (
        response_field(
            alias='PointDeductAmount',
            description='积分抵扣金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class ListBillOverviewByProdResponse(BillingContractModel):
    list: Optional[List[ListBillOverviewByProdResponseListItem]] = (
        response_field(
            alias='List',
            description='账单总览-产品汇总列表',
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
    action='ListBillOverviewByProd',
    name_zh='分页查询账单总览-产品汇总信息',
    description='“提供按产品汇总的当月费用数据；请于每月第2个自然日12点后获取上月完整账单数据；”',
    timeout_ms=5000,
    response_data_path='Result',
    error_code_path='ResponseMetadata.Error.Code',
    error_message_path='ResponseMetadata.Error.Message',
    request_model=ListBillOverviewByProdRequest,
    response_model=ListBillOverviewByProdResponse,
)
