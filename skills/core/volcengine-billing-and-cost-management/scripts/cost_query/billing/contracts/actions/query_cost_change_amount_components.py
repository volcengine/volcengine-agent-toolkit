"""计费项金额构成变化契约；依据迁移源 call_openapi.py 整理。"""

from __future__ import annotations

from pydantic import StrictInt, StrictStr

from ..base import ActionContract, BillingContractModel, request_field
from ..cost_change_common import (
    MONTH_START_PATTERN,
    CostChangeChargeItemFilters,
)
from ..cost_change_common import CostChangeCandidateResponse as QueryCostChangeAmountComponentsResponse


class QueryCostChangeAmountComponentsRequest(BillingContractModel):
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
    metric: StrictInt = request_field(
        alias="Metric", description="分析金额口径，固定为 3（应付金额）。",
        type_code=2, is_public=True, is_array=False, required=True, location_multi=(2,),
        ge=3, le=3, is_enum=True, enum_value="3",
    )
    filters: CostChangeChargeItemFilters = request_field(
        alias="Filters", description="必须包含 charge_item_code，并保留已有范围筛选。",
        type_code=7, is_public=True, is_array=False, required=True, location_multi=(2,),
    )


CONTRACT = ActionContract(
    action="QueryCostChangeAmountComponents",
    name_zh="计费项金额构成变化分析",
    description="分析指定计费项两账期应付金额变化涉及的原价、优惠、退款等实际返回金额项；不是单账期完整构成。",
    timeout_ms=120000,
    response_data_path="Result",
    error_code_path="ResponseMetadata.Error.Code",
    error_message_path="ResponseMetadata.Error.Message",
    request_model=QueryCostChangeAmountComponentsRequest,
    response_model=QueryCostChangeAmountComponentsResponse,
)
