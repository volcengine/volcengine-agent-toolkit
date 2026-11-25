"""费用变化维度定位契约；依据迁移源 call_openapi.py 整理。"""

from __future__ import annotations

from typing import List, Optional

from pydantic import StrictInt, StrictStr

from ..base import ActionContract, BillingContractModel, request_field
from ..cost_change_common import (
    DIMENSION_VALUES,
    MONTH_START_PATTERN,
    CostChangeDimension,
    CostChangeFilters,
)
from ..cost_change_common import CostChangeCandidateResponse as QueryCostChangeDimensionsResponse


class QueryCostChangeDimensionsRequest(BillingContractModel):
    current_period: StrictStr = request_field(
        alias="CurrentPeriod", description="本期账期，格式 YYYY-MM-01。",
        type_code=1, is_public=True, is_array=False, required=True, location_multi=(2,),
        reg_pattern=MONTH_START_PATTERN, date_format="YYYY-MM-DD",
    )
    base_period: StrictStr = request_field(
        alias="BasePeriod", description="基期账期，格式 YYYY-MM-01。",
        type_code=1, is_public=True, is_array=False, required=True, location_multi=(2,),
        reg_pattern=MONTH_START_PATTERN, date_format="YYYY-MM-DD",
    )
    candidate_dimensions: List[CostChangeDimension] = request_field(
        alias="CandidateDimensions", description="待定位维度，仅支持单元素数组。",
        type_code=1, is_public=True, is_array=True, required=True, location_multi=(2,),
        min_length=1, max_length=1, is_enum=True, enum_value=DIMENSION_VALUES,
    )
    metric: StrictInt = request_field(
        alias="Metric", description="分析金额口径，固定为 3（应付金额）。",
        type_code=2, is_public=True, is_array=False, required=True, location_multi=(2,),
        ge=3, le=3, is_enum=True, enum_value="3",
    )
    filters: Optional[CostChangeFilters] = request_field(
        alias="Filters", description="分析范围筛选；不携带账号身份或凭证。",
        type_code=7, is_public=True, is_array=False, required=False, location_multi=(2,),
    )


CONTRACT = ActionContract(
    action="QueryCostChangeDimensions",
    name_zh="费用变化维度定位",
    description="定位两账期应付金额变化主要集中在哪些产品、计费项、实例、地域或项目。",
    timeout_ms=120000,
    response_data_path="Result",
    error_code_path="ResponseMetadata.Error.Code",
    error_message_path="ResponseMetadata.Error.Message",
    request_model=QueryCostChangeDimensionsRequest,
    response_model=QueryCostChangeDimensionsResponse,
)
