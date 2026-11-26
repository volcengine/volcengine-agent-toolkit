"""经显式审核、允许跨 Action 复用的 Billing 契约定义。"""

from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from pydantic import StrictStr
from pydantic.fields import FieldInfo

from .base import BillingContractModel, request_field


class BillingMode(str, Enum):
    PREPAID = "1"
    POSTPAID = "2"
    CONTRACT = "3"
    FULFILLMENT = "4"
    COMMITMENT = "5"


BillingModeValues = List[BillingMode]
NeedRecordNumValue = Literal[0, 1]

BILLING_MODE_DESCRIPTION = (
    "计费模式：1：包年包月，代表预付费；2：按量计费，代表后付费；"
    "3：合同计费，代表线下计费；4：履约计费；5：承诺消费；默认不选为全部；"
)
TAG_KV_DESCRIPTION = "标签键值对筛选，最大支持传递20个；每一项必须同时提供非空 Key 和 Value"
PAGE_LIMIT_DESCRIPTION = (
    "数量：[1-300]，用于指定接口响应中返回记录的最大数量（上限），"
    "例如Limit=20表示每次请求最多返回20条"
)
PAGE_OFFSET_DESCRIPTION = (
    "用于在分页查询中指定“从结果集的第几条记录开始返回”（也就是先跳过多少条记录），"
    "通常与 **limit** 搭配使用实现翻页：例如每页 `limit=300` 时，第 1 页传 "
    "`offset=0` 获取第 1–300 条，第 2 页传 `offset=300` 获取第 301–600 条，"
    "第 3 页传 `offset=600` 获取第 601–900 条；因此每往后一页，`offset` 按"
    "固定步长累加：`offset = offset + limit`（等价于 `offset = (page-1) * limit`）。"
)
NEED_RECORD_NUM_DESCRIPTION = (
    "是否需要访问列表的总记录数：用于前端分页；1：表示需要； 0：表示不需要；"
    "默认为不需要，Total返回-1"
)


class TagKV(BillingContractModel):
    key: Optional[StrictStr] = request_field(
        alias="Key",
        description="标签键；与 Value 成对传入，不能只传 Key",
        type_code=1,
        is_public=True,
        is_array=False,
        required=False,
        location_multi=(2,),
    )
    value: Optional[StrictStr] = request_field(
        alias="Value",
        description="标签值；与 Key 成对传入，不能只传 Value",
        type_code=1,
        is_public=True,
        is_array=False,
        required=False,
        location_multi=(2,),
    )


def billing_mode_field() -> FieldInfo:
    return request_field(
        alias="BillingMode",
        description=BILLING_MODE_DESCRIPTION,
        type_code=1,
        is_public=True,
        is_array=True,
        required=False,
        location_multi=(2,),
        is_enum=True,
        enum_value="1,2,3,4,5",
    )


def tag_kv_field() -> FieldInfo:
    return request_field(
        alias="TagKV",
        description=TAG_KV_DESCRIPTION,
        type_code=7,
        is_public=True,
        is_array=True,
        required=False,
        location_multi=(2,),
        max_length=20,
    )


def page_limit_field() -> FieldInfo:
    return request_field(
        alias="Limit",
        description=PAGE_LIMIT_DESCRIPTION,
        type_code=2,
        is_public=True,
        is_array=False,
        required=True,
        location_multi=(2,),
        min_value="1",
        max_value="300",
        ge=1,
        le=300,
    )


def page_offset_field() -> FieldInfo:
    return request_field(
        alias="Offset",
        description=PAGE_OFFSET_DESCRIPTION,
        type_code=2,
        is_public=True,
        is_array=False,
        required=False,
        location_multi=(2,),
        min_value="0",
        ge=0,
    )


def need_record_num_field() -> FieldInfo:
    return request_field(
        alias="NeedRecordNum",
        description=NEED_RECORD_NUM_DESCRIPTION,
        type_code=2,
        is_public=True,
        is_array=False,
        required=False,
        location_multi=(2,),
        is_enum=True,
        enum_value="0,1",
    )
