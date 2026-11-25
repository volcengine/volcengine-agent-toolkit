from __future__ import annotations

from typing import List, Optional

from pydantic import StrictFloat, StrictInt, StrictStr

from ..base import ActionContract, BillingContractModel, request_field, response_field


class ListCouponUsageRecordsRequest(BillingContractModel):
    limit: Optional[StrictInt] = request_field(
        alias="Limit",
        description="每页返回的数据量，默认 10，最大 1000。",
        type_code=2,
        is_public=True,
        is_array=False,
        required=False,
        location_multi=(2,),
        ge=1,
        le=1000,
    )
    offset: Optional[StrictInt] = request_field(
        alias="Offset",
        description="偏移量。",
        type_code=2,
        is_public=True,
        is_array=False,
        required=False,
        location_multi=(2,),
        ge=0,
    )
    coupon_id: StrictStr = request_field(
        alias="CouponID",
        description="代金券 ID。",
        type_code=1,
        is_public=True,
        is_array=False,
        required=True,
        location_multi=(2,),
        min_length=1,
    )


class ListCouponUsageRecordsResponseItem(BillingContractModel):
    coupon_id: Optional[StrictStr] = response_field(alias="CouponID", description="代金券 ID", type_code=1, is_public=True, is_array=False)
    product_code: Optional[StrictStr] = response_field(alias="ProductCode", description="商品编码", type_code=1, is_public=True, is_array=False)
    product_name: Optional[StrictStr] = response_field(alias="ProductName", description="商品名称", type_code=1, is_public=True, is_array=False)
    change_amount: Optional[StrictFloat] = response_field(alias="ChangeAmount", description="变动金额，单位元", type_code=5, is_public=True, is_array=False)
    created_time: Optional[StrictStr] = response_field(alias="CreatedTime", description="使用时间", type_code=1, is_public=True, is_array=False)
    pay_type: Optional[StrictStr] = response_field(alias="PayType", description="付费方式：pre 预付费；post 后付费", type_code=1, is_public=True, is_array=False)
    sub_business_id: Optional[StrictStr] = response_field(alias="SubBusinessID", description="订单号或账单明细号；pre 为订单号，post 为账单明细号", type_code=1, is_public=True, is_array=False)
    change_type: Optional[StrictInt] = response_field(alias="ChangeType", description="变更类型：2 抵扣；3 退回", type_code=2, is_public=True, is_array=False)
    account_id: Optional[StrictInt] = response_field(alias="AccountID", description="代金券所属账号 ID", type_code=3, is_public=True, is_array=False)
    user_account_id: Optional[StrictInt] = response_field(alias="UserAccountID", description="使用者账号 ID", type_code=3, is_public=True, is_array=False)
    billing_cycle: Optional[StrictStr] = response_field(alias="BillingCycle", description="账期", type_code=1, is_public=True, is_array=False)


class ListCouponUsageRecordsResponse(BillingContractModel):
    list_: Optional[List[ListCouponUsageRecordsResponseItem]] = response_field(
        alias="List", description="代金券核销记录列表", type_code=7, is_public=True, is_array=True
    )
    total: Optional[StrictInt] = response_field(alias="Total", description="总数", type_code=2, is_public=True, is_array=False)
    limit: Optional[StrictInt] = response_field(alias="Limit", description="每页返回的数据量", type_code=2, is_public=True, is_array=False)
    offset: Optional[StrictInt] = response_field(alias="Offset", description="偏移量", type_code=2, is_public=True, is_array=False)


CONTRACT = ActionContract(
    action="ListCouponUsageRecords",
    name_zh="查询代金券核销记录",
    description="按代金券 ID 查询实际抵扣和退回记录。",
    timeout_ms=5000,
    response_data_path="",
    error_code_path="Metadata.Error.Code",
    error_message_path="Metadata.Error.Message",
    request_model=ListCouponUsageRecordsRequest,
    response_model=ListCouponUsageRecordsResponse,
)
