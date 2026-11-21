from __future__ import annotations

from typing import List, Optional

from pydantic import StrictFloat, StrictInt, StrictStr

from ..base import ActionContract, BillingContractModel, request_field, response_field


ISO8601_OFFSET_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$"


class ListCouponsRequest(BillingContractModel):
    valid_begin_time: Optional[StrictStr] = request_field(
        alias="ValidBeginTime",
        description="代金券生效时间范围开始时间，ISO8601。",
        type_code=1,
        is_public=True,
        is_array=False,
        required=False,
        location_multi=(2,),
        reg_pattern=ISO8601_OFFSET_PATTERN,
    )
    valid_end_time: Optional[StrictStr] = request_field(
        alias="ValidEndTime",
        description="代金券生效时间范围结束时间，ISO8601。",
        type_code=1,
        is_public=True,
        is_array=False,
        required=False,
        location_multi=(2,),
        reg_pattern=ISO8601_OFFSET_PATTERN,
    )
    product_code: Optional[StrictStr] = request_field(
        alias="ProductCode", description="商品编码。", type_code=1, is_public=True, is_array=False, required=False, location_multi=(2,)
    )
    status: Optional[StrictStr] = request_field(
        alias="Status", description="代金券状态，多个值用英文逗号分隔。", type_code=1, is_public=True, is_array=False, required=False, location_multi=(2,)
    )
    limit: Optional[StrictInt] = request_field(
        alias="Limit", description="每页返回的数据量。", type_code=2, is_public=True, is_array=False, required=False, location_multi=(2,), ge=1
    )
    offset: Optional[StrictInt] = request_field(
        alias="Offset", description="偏移量。", type_code=2, is_public=True, is_array=False, required=False, location_multi=(2,), ge=0
    )
    coupon_id: Optional[StrictStr] = request_field(
        alias="CouponID", description="代金券 ID。", type_code=1, is_public=True, is_array=False, required=False, location_multi=(2,)
    )


class ListCouponsProductLimitItem(BillingContractModel):
    product_code: Optional[StrictStr] = response_field(alias="ProductCode", description="商品编码", type_code=1, is_public=True, is_array=False)
    product_name: Optional[StrictStr] = response_field(alias="ProductName", description="商品名称", type_code=1, is_public=True, is_array=False)
    configuration_type: Optional[StrictInt] = response_field(alias="ConfigurationType", description="适用配置类型：1 全部配置；2 全部预付费配置；3 全部后付费配置；4 指定配置", type_code=2, is_public=True, is_array=False)
    configuration_code: Optional[StrictStr] = response_field(alias="ConfigurationCode", description="指定配置编码；ConfigurationType=4 时有值", type_code=1, is_public=True, is_array=False)
    configuration_name: Optional[StrictStr] = response_field(alias="ConfigurationName", description="指定配置名称；ConfigurationType=4 时有值", type_code=1, is_public=True, is_array=False)
    time_limit_lower: Optional[StrictInt] = response_field(alias="TimeLimitLower", description="预付费购买时长限制下限", type_code=2, is_public=True, is_array=False)
    billing_method: Optional[StrictStr] = response_field(alias="BillingMethod", description="计费方式", type_code=1, is_public=True, is_array=False)
    charge_item_type: Optional[StrictInt] = response_field(alias="ChargeItemType", description="计费项类型：0 全部计费项；1 指定计费项", type_code=2, is_public=True, is_array=False)
    charge_item_code: Optional[StrictStr] = response_field(alias="ChargeItemCode", description="指定计费项编号；ChargeItemType=1 时有值", type_code=1, is_public=True, is_array=False)
    time_limit_upper: Optional[StrictInt] = response_field(alias="TimeLimitUpper", description="预付费购买时长限制上限", type_code=2, is_public=True, is_array=False)


class ListCouponsResponseItem(BillingContractModel):
    pay_type_limit: Optional[StrictStr] = response_field(alias="PayTypeLimit", description="适用付款方式：all、pre 或 post", type_code=1, is_public=True, is_array=False)
    order_type_limit: Optional[StrictStr] = response_field(alias="OrderTypeLimit", description="适用订单类型", type_code=1, is_public=True, is_array=False)
    remark: Optional[StrictStr] = response_field(alias="Remark", description="备注", type_code=1, is_public=True, is_array=False)
    remaining_amount: Optional[StrictFloat] = response_field(alias="RemainingAmount", description="代金券余额，单位元", type_code=5, is_public=True, is_array=False)
    expired_time: Optional[StrictStr] = response_field(alias="ExpiredTime", description="有效期结束时间", type_code=1, is_public=True, is_array=False)
    amount_limit: Optional[StrictFloat] = response_field(alias="AmountLimit", description="金额限制，单位元", type_code=5, is_public=True, is_array=False)
    usage_limit: Optional[StrictInt] = response_field(alias="UsageLimit", description="使用次数：1 单次；2 多次", type_code=2, is_public=True, is_array=False)
    acquire_time: Optional[StrictStr] = response_field(alias="AcquireTime", description="发放时间", type_code=1, is_public=True, is_array=False)
    coupon_name: Optional[StrictStr] = response_field(alias="CouponName", description="代金券名称", type_code=1, is_public=True, is_array=False)
    coupon_id: Optional[StrictStr] = response_field(alias="CouponID", description="代金券 ID", type_code=1, is_public=True, is_array=False)
    status: Optional[StrictInt] = response_field(alias="Status", description="状态：1 待生效；2 生效中；3 已失效；4 已使用；5 已作废", type_code=2, is_public=True, is_array=False)
    begin_time: Optional[StrictStr] = response_field(alias="BeginTime", description="有效期开始时间", type_code=1, is_public=True, is_array=False)
    product_limit_list: Optional[List[ListCouponsProductLimitItem]] = response_field(alias="ProductLimitList", description="适用商品配置范围", type_code=7, is_public=True, is_array=True)
    total_amount: Optional[StrictFloat] = response_field(alias="TotalAmount", description="代金券面额，单位元", type_code=5, is_public=True, is_array=False)
    account_id: Optional[StrictInt] = response_field(alias="AccountID", description="代金券所属账号 ID", type_code=3, is_public=True, is_array=False)
    assigned_owner_id_list: Optional[List[StrictInt]] = response_field(alias="AssignedOwnerIDList", description="指定适用账号；空表示不限制", type_code=3, is_public=True, is_array=True)
    void_reason: Optional[StrictStr] = response_field(alias="VoidReason", description="作废原因", type_code=1, is_public=True, is_array=False)


class ListCouponsResponse(BillingContractModel):
    list_: Optional[List[ListCouponsResponseItem]] = response_field(alias="List", description="代金券列表", type_code=7, is_public=True, is_array=True)
    total: Optional[StrictInt] = response_field(alias="Total", description="总数", type_code=2, is_public=True, is_array=False)
    limit: Optional[StrictInt] = response_field(alias="Limit", description="步长", type_code=2, is_public=True, is_array=False)
    offset: Optional[StrictInt] = response_field(alias="Offset", description="偏移量", type_code=2, is_public=True, is_array=False)


CONTRACT = ActionContract(
    action="ListCoupons",
    name_zh="查询代金券信息",
    description="查询代金券状态、余额、有效期、门槛和适用商品配置范围。",
    timeout_ms=5000,
    response_data_path="",
    error_code_path="Metadata.Error.Code",
    error_message_path="Metadata.Error.Message",
    request_model=ListCouponsRequest,
    response_model=ListCouponsResponse,
)
