"""归因接口共用字段；依据迁移源 call_openapi.py 的请求和响应校验整理。

这些定义是增量维护的契约，不是由 billing.json 生成的模型。
"""

from __future__ import annotations

from enum import Enum
from decimal import Decimal
from typing import Annotated, List, Optional, Union

from pydantic import Field, StrictFloat, StrictInt, StrictStr

from .base import BillingContractModel, request_field, response_field


DIMENSION_VALUES = "product,charge_item_code,instance_no,region_code,project"
MONTH_START_PATTERN = r"^[1-9][0-9]{3}-(0[1-9]|1[0-2])-01$"
CostChangeNumber = Union[
    StrictInt,
    Annotated[Decimal, Field(strict=True, allow_inf_nan=False)],
    Annotated[StrictFloat, Field(allow_inf_nan=False)],
]


class CostChangeDimension(str, Enum):
    PRODUCT = "product"
    CHARGE_ITEM_CODE = "charge_item_code"
    INSTANCE_NO = "instance_no"
    REGION_CODE = "region_code"
    PROJECT = "project"


class CostChangeFilters(BillingContractModel):
    product: StrictStr = request_field(
        alias="product", description="产品筛选，保留已有分析范围。",
        type_code=1, is_public=True, is_array=False, required=False, location_multi=(2,),
    )
    charge_item_code: StrictStr = request_field(
        alias="charge_item_code", description="计费项编码筛选。",
        type_code=1, is_public=True, is_array=False, required=False, location_multi=(2,),
    )
    instance_no: StrictStr = request_field(
        alias="instance_no", description="实例标识筛选。",
        type_code=1, is_public=True, is_array=False, required=False, location_multi=(2,),
    )
    region_code: StrictStr = request_field(
        alias="region_code", description="地域编码筛选。",
        type_code=1, is_public=True, is_array=False, required=False, location_multi=(2,),
    )
    project: StrictStr = request_field(
        alias="project", description="项目筛选。",
        type_code=1, is_public=True, is_array=False, required=False, location_multi=(2,),
    )


class CostChangeChargeItemFilters(CostChangeFilters):
    charge_item_code: StrictStr = request_field(
        alias="charge_item_code", description="待分析的计费项编码，必填且不能仅含空白。",
        type_code=1, is_public=True, is_array=False, required=True, location_multi=(2,),
        min_length=1, reg_pattern=r"\S",
    )


class CostChangeCandidateValue(BillingContractModel):
    value_key: Optional[StrictStr] = response_field(
        alias="valueKey", description="变化对象或金额项编码。",
        type_code=1, is_public=True, is_array=False,
    )
    value_name: Optional[StrictStr] = response_field(
        alias="valueName", description="变化对象或金额项名称。",
        type_code=1, is_public=True, is_array=False,
    )
    delta_amount: Optional[CostChangeNumber] = response_field(
        alias="deltaAmount", description="本期相对基期的变化金额，保留正负号。",
        type_code=6, is_public=True, is_array=False,
    )
    base_amount: Optional[CostChangeNumber] = response_field(
        alias="baseAmount", description="该对象或金额项的基期金额。",
        type_code=6, is_public=True, is_array=False,
    )
    current_amount: Optional[CostChangeNumber] = response_field(
        alias="currentAmount", description="该对象或金额项的本期金额。",
        type_code=6, is_public=True, is_array=False,
    )
    contribution_ratio: Optional[CostChangeNumber] = response_field(
        alias="contributionRatio", description="接口返回的变化贡献比例；按实际口径解释，不假定为构成占比。",
        type_code=6, is_public=True, is_array=False,
    )


class CostChangeCandidate(BillingContractModel):
    dimension: Optional[StrictStr] = response_field(
        alias="dimension", description="候选维度；金额构成分析返回 amount_component。",
        type_code=1, is_public=True, is_array=False,
    )
    coverage_ratio: Optional[CostChangeNumber] = response_field(
        alias="coverageRatio", description="候选值对变化的覆盖率，不代表原始数据采集完整性。",
        type_code=6, is_public=True, is_array=False,
    )
    values: Optional[List[CostChangeCandidateValue]] = response_field(
        alias="values", description="变化对象或金额项列表；不将缺失值当作零。",
        type_code=7, is_public=True, is_array=True,
    )


class CostChangeCandidateResponse(BillingContractModel):
    total_diff: Optional[CostChangeNumber] = response_field(
        alias="totalDiff", description="筛选范围内的应付金额总差额。",
        type_code=6, is_public=True, is_array=False,
    )
    base_amount: Optional[CostChangeNumber] = response_field(
        alias="baseAmount", description="筛选范围内的基期应付金额。",
        type_code=6, is_public=True, is_array=False,
    )
    current_amount: Optional[CostChangeNumber] = response_field(
        alias="currentAmount", description="筛选范围内的本期应付金额。",
        type_code=6, is_public=True, is_array=False,
    )
    candidates: Optional[List[CostChangeCandidate]] = response_field(
        alias="candidates", description="变化候选列表；空列表不证明没有费用。",
        type_code=7, is_public=True, is_array=True,
    )
