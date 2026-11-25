"""财务关系契约；类型核对 SDK 4.0.20，分页约束核对 CLI 和 2026-11-04 实测。"""

from __future__ import annotations

from typing import List, Optional

from pydantic import StrictInt, StrictStr

from ..base import ActionContract, BillingContractModel, request_field, response_field


class ListFinancialRelationRequest(BillingContractModel):
    account_id_search_list: Optional[List[StrictStr]] = request_field(
        alias="AccountIDSearchList", description="对方账号 ID 筛选；使用字符串数组，保留账号标识。",
        type_code=1, is_public=True, is_array=True, required=False, location_multi=(2,),
    )
    limit: Optional[StrictInt] = request_field(
        alias="Limit", description="单页记录数，范围 1–100。",
        type_code=2, is_public=True, is_array=False, required=False, location_multi=(2,),
        min_value="1", max_value="100", ge=1, le=100,
    )
    offset: Optional[StrictInt] = request_field(
        alias="Offset", description="分页偏移，默认 0。",
        type_code=2, is_public=True, is_array=False, required=False, location_multi=(2,),
        min_value="0", ge=0,
    )
    relation: Optional[List[StrictStr]] = request_field(
        alias="Relation", description="财务关系类型筛选；使用接口关系编码的字符串数组，不复用账单 BusinessMode 编码。",
        type_code=1, is_public=True, is_array=True, required=False, location_multi=(2,),
    )
    status: Optional[List[StrictStr]] = request_field(
        alias="Status", description="对方账号与当前账号的关系状态筛选；使用接口状态编码的字符串数组。",
        type_code=1, is_public=True, is_array=True, required=False, location_multi=(2,),
    )


class ListFinancialRelationItem(BillingContractModel):
    account_alias: Optional[StrictStr] = response_field(
        alias="AccountAlias", description="账号别名；不能单独用于识别当前账号角色。",
        type_code=1, is_public=True, is_array=False,
    )
    filiation: Optional[StrictInt] = response_field(
        alias="Filiation", description="主子相对视角编码；不能据此判断当前登录角色，实际按已核验账号 ID 匹配主子账号。",
        type_code=2, is_public=True, is_array=False,
    )
    filiation_desc: Optional[StrictStr] = response_field(
        alias="FiliationDesc", description="主子相对视角说明；返回主不代表当前登录账号是主账号，实际看已核验账号 ID 判角色。",
        type_code=1, is_public=True, is_array=False,
    )
    major_account_id: Optional[StrictInt] = response_field(
        alias="MajorAccountID", description="关系中的主账号 ID；仅在确认有效财务托管关系时解释为统一结算账号。",
        type_code=3, is_public=True, is_array=False,
    )
    major_account_name: Optional[StrictStr] = response_field(
        alias="MajorAccountName", description="关系中的主账号名称。",
        type_code=1, is_public=True, is_array=False,
    )
    sub_account_id: Optional[StrictInt] = response_field(
        alias="SubAccountID", description="关系中的子账号 ID；不能据此默认当前授权账号就是子账号。",
        type_code=3, is_public=True, is_array=False,
    )
    sub_account_name: Optional[StrictStr] = response_field(
        alias="SubAccountName", description="关系中的子账号名称。",
        type_code=1, is_public=True, is_array=False,
    )
    relation: Optional[StrictInt] = response_field(
        alias="Relation", description="财务关系类型编码；结合 RelationDesc 解释，不复用账单业务类型编码。",
        type_code=2, is_public=True, is_array=False,
    )
    relation_desc: Optional[StrictStr] = response_field(
        alias="RelationDesc", description="财务关系类型说明；财务托管由主账号统一结算，财务管理各账号独立结算。",
        type_code=1, is_public=True, is_array=False,
    )
    relation_id: Optional[StrictStr] = response_field(
        alias="RelationID", description="财务关系记录 ID。",
        type_code=1, is_public=True, is_array=False,
    )
    status: Optional[StrictInt] = response_field(
        alias="Status", description="财务关系状态编码；结合 StatusDesc 解释，未知编码不推断是否生效。",
        type_code=2, is_public=True, is_array=False,
    )
    status_desc: Optional[StrictStr] = response_field(
        alias="StatusDesc", description="财务关系状态说明；未明确生效的关系不能用于确认当前由主账号代付。",
        type_code=1, is_public=True, is_array=False,
    )
    update_time: Optional[StrictStr] = response_field(
        alias="UpdateTime", description="关系记录更新时间；不等于关系生效时间或历史代付区间。",
        type_code=1, is_public=True, is_array=False,
    )


class ListFinancialRelationResponse(BillingContractModel):
    list: Optional[List[ListFinancialRelationItem]] = response_field(
        alias="List", description="当前身份可见、符合筛选条件的财务关系列表。",
        type_code=7, is_public=True, is_array=True,
    )
    total: Optional[StrictInt] = response_field(
        alias="Total", description="筛选范围内的关系记录总数。",
        type_code=3, is_public=True, is_array=False,
    )
    limit: Optional[StrictInt] = response_field(
        alias="Limit", description="本次响应的单页记录数上限。",
        type_code=2, is_public=True, is_array=False,
    )
    offset: Optional[StrictInt] = response_field(
        alias="Offset", description="响应分页偏移；实测可能返回 -1 表示未回显，此时按请求 Offset 推进分页并检查完整性。",
        type_code=2, is_public=True, is_array=False,
    )


CONTRACT = ActionContract(
    action="ListFinancialRelation",
    name_zh="查询财务关系",
    description="查询当前身份可见的主子账号财务关系、关系类型和状态；不提供费用或余额。",
    timeout_ms=5000,
    response_data_path="Result",
    error_code_path="ResponseMetadata.Error.Code",
    error_message_path="ResponseMetadata.Error.Message",
    request_model=ListFinancialRelationRequest,
    response_model=ListFinancialRelationResponse,
)
