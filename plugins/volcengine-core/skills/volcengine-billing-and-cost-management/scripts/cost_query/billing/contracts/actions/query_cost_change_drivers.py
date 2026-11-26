"""计费项原价驱动因子契约；依据迁移源 call_openapi.py 整理。"""

from __future__ import annotations

from typing import List, Optional

from pydantic import StrictStr

from ..base import ActionContract, BillingContractModel, request_field, response_field
from ..cost_change_common import MONTH_START_PATTERN, CostChangeChargeItemFilters, CostChangeNumber


class QueryCostChangeDriversRequest(BillingContractModel):
    current_period: StrictStr = request_field(
        alias="current_period", description="本期账期，格式 YYYY-MM-01；保留底层 snake_case 字段名。",
        type_code=1, is_public=True, is_array=False, required=True, location_multi=(2,),
        reg_pattern=MONTH_START_PATTERN, date_format="YYYY-MM-DD",
    )
    base_period: StrictStr = request_field(
        alias="base_period", description="基期账期，格式 YYYY-MM-01。",
        type_code=1, is_public=True, is_array=False, required=True, location_multi=(2,),
        reg_pattern=MONTH_START_PATTERN, date_format="YYYY-MM-DD",
    )
    metric: StrictStr = request_field(
        alias="Metric", description="固定为 original_bill_amount（原价），不能当作应付变化贡献。",
        type_code=1, is_public=True, is_array=False, required=True, location_multi=(2,),
        reg_pattern=r"^original_bill_amount$", is_enum=True, enum_value="original_bill_amount",
    )
    filters: CostChangeChargeItemFilters = request_field(
        alias="filters", description="必须包含 charge_item_code，并保留已有范围筛选。",
        type_code=7, is_public=True, is_array=False, required=True, location_multi=(2,),
    )


class QueryCostChangeDriversResponseContribution(BillingContractModel):
    dimension: Optional[StrictStr] = response_field(
        alias="dimension", description="驱动因子编码，如 usage、unit_price 或其他影响因子。",
        type_code=1, is_public=True, is_array=False,
    )
    dimension_name: Optional[StrictStr] = response_field(
        alias="dimension_name", description="驱动因子名称。",
        type_code=1, is_public=True, is_array=False,
    )
    contribution: Optional[CostChangeNumber] = response_field(
        alias="contribution", description="该因子对原价变化的贡献金额，保留正负号。",
        type_code=6, is_public=True, is_array=False,
    )
    base_amount: Optional[CostChangeNumber] = response_field(
        alias="base_amount", description="该因子的基期返回值；按因子语义解释，不跨因子相加。",
        type_code=6, is_public=True, is_array=False,
    )
    current_amount: Optional[CostChangeNumber] = response_field(
        alias="current_amount", description="该因子的本期返回值；按因子语义解释，不跨因子相加。",
        type_code=6, is_public=True, is_array=False,
    )


class QueryCostChangeDriversResponse(BillingContractModel):
    total_diff: Optional[CostChangeNumber] = response_field(
        alias="total_diff", description="筛选范围内的原价总差额。",
        type_code=6, is_public=True, is_array=False,
    )
    base_amount: Optional[CostChangeNumber] = response_field(
        alias="base_amount", description="筛选范围内的基期原价金额。",
        type_code=6, is_public=True, is_array=False,
    )
    current_amount: Optional[CostChangeNumber] = response_field(
        alias="current_amount", description="筛选范围内的本期原价金额。",
        type_code=6, is_public=True, is_array=False,
    )
    contributions: Optional[List[QueryCostChangeDriversResponseContribution]] = response_field(
        alias="contributions", description="驱动因子贡献列表，不代表应付金额贡献。",
        type_code=7, is_public=True, is_array=True,
    )


CONTRACT = ActionContract(
    action="QueryCostChangeDrivers",
    name_zh="计费项原价驱动因子分析",
    description="分析指定计费项两账期原价变化的用量、单价及其他因子贡献；不能直接解释为应付涨幅贡献。",
    timeout_ms=120000,
    response_data_path="Result",
    error_code_path="ResponseMetadata.Error.Code",
    error_message_path="ResponseMetadata.Error.Message",
    request_model=QueryCostChangeDriversRequest,
    response_model=QueryCostChangeDriversResponse,
)
