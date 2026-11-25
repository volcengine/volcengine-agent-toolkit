from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import StrictStr

from ..base import ActionContract, BillingContractModel, request_field, response_field
from ....utils.billing import ISO8601_UTC_PATTERN


class ListResourcePackagesRequest(BillingContractModel):
    resource_type: Literal["Package", "RI", "RSC"] = request_field(
        alias="ResourceType",
        description="查询的资源实例类型：Package 资源包；RI 预留实例券；RSC 预留存储容量包。",
        type_code=1,
        is_public=True,
        is_array=False,
        required=True,
        location_multi=(2,),
        is_enum=True,
        enum_value="Package,RI,RSC",
    )
    max_results: StrictStr = request_field(
        alias="MaxResults",
        description="每次查询返回最大条数，上限 20。",
        type_code=1,
        is_public=True,
        is_array=False,
        required=True,
        location_multi=(2,),
    )
    next_token: Optional[StrictStr] = request_field(
        alias="NextToken",
        description="下一页开始 ID；首次为空，响应为空或 0 时表示后续无数据。",
        type_code=1,
        is_public=True,
        is_array=False,
        required=False,
        location_multi=(2,),
    )
    product: Optional[StrictStr] = request_field(
        alias="Product",
        description="资源实例对应商品编码。",
        type_code=1,
        is_public=True,
        is_array=False,
        required=False,
        location_multi=(2,),
    )
    effective_time_begin: Optional[StrictStr] = request_field(
        alias="EffectiveTimeBegin",
        description="资源实例生效开始时间，ISO8601 UTC：yyyy-MM-ddTHH:mm:ssZ。",
        type_code=1,
        is_public=True,
        is_array=False,
        required=False,
        location_multi=(2,),
        reg_pattern=ISO8601_UTC_PATTERN,
    )
    effective_time_end: Optional[StrictStr] = request_field(
        alias="EffectiveTimeEnd",
        description="资源实例生效结束时间，ISO8601 UTC：yyyy-MM-ddTHH:mm:ssZ。",
        type_code=1,
        is_public=True,
        is_array=False,
        required=False,
        location_multi=(2,),
        reg_pattern=ISO8601_UTC_PATTERN,
    )
    status: Optional[
        Literal["Effective", "NotEffective", "FailedToCreate", "UsedUp", "Expired", "Refunded"]
    ] = request_field(
        alias="Status",
        description="资源实例状态。",
        type_code=1,
        is_public=True,
        is_array=False,
        required=False,
        location_multi=(2,),
        is_enum=True,
        enum_value="Effective,NotEffective,FailedToCreate,UsedUp,Expired,Refunded",
    )

class ListResourcePackagesResponseItem(BillingContractModel):
    owner_id: Optional[StrictStr] = response_field(alias="OwnerID", description="资源实例归属账号", type_code=1, is_public=True, is_array=False)
    user_name: Optional[StrictStr] = response_field(alias="UserName", description="账户名称", type_code=1, is_public=True, is_array=False)
    package_type: Optional[StrictStr] = response_field(alias="PackageType", description="资源实例形态：Periodic、Diminishing 或 Hybrid", type_code=1, is_public=True, is_array=False)
    instance_no: Optional[StrictStr] = response_field(alias="InstanceNo", description="资源实例 ID", type_code=1, is_public=True, is_array=False)
    instance_name: Optional[StrictStr] = response_field(alias="InstanceName", description="资源实例名称", type_code=1, is_public=True, is_array=False)
    product: Optional[StrictStr] = response_field(alias="Product", description="商品英文编码", type_code=1, is_public=True, is_array=False)
    product_name: Optional[StrictStr] = response_field(alias="ProductName", description="商品中文名称", type_code=1, is_public=True, is_array=False)
    total_amount: Optional[StrictStr] = response_field(alias="TotalAmount", description="资源实例总量", type_code=1, is_public=True, is_array=False)
    available_amount: Optional[StrictStr] = response_field(alias="AvailableAmount", description="资源实例余量", type_code=1, is_public=True, is_array=False)
    unit: Optional[StrictStr] = response_field(alias="Unit", description="资源实例用量单位", type_code=1, is_public=True, is_array=False)
    effective_time: Optional[StrictStr] = response_field(alias="EffectiveTime", description="资源实例生效时间，ISO8601 UTC", type_code=1, is_public=True, is_array=False)
    expiry_time: Optional[StrictStr] = response_field(alias="ExpiryTime", description="资源实例失效时间，ISO8601 UTC", type_code=1, is_public=True, is_array=False)
    bill_time: Optional[StrictStr] = response_field(alias="BillTime", description="资源实例购买时间，ISO8601 UTC", type_code=1, is_public=True, is_array=False)
    status: Optional[StrictStr] = response_field(alias="Status", description="资源实例状态", type_code=1, is_public=True, is_array=False)
    configuration_code: Optional[StrictStr] = response_field(alias="ConfigurationCode", description="资源实例配置编码", type_code=1, is_public=True, is_array=False)
    configuration_name: Optional[StrictStr] = response_field(alias="ConfigurationName", description="资源实例配置名称", type_code=1, is_public=True, is_array=False)
    specification: Optional[StrictStr] = response_field(alias="Specification", description="资源实例规格", type_code=1, is_public=True, is_array=False)
    specification_unit: Optional[StrictStr] = response_field(alias="SpecificationUnit", description="资源实例规格单位", type_code=1, is_public=True, is_array=False)
    region_code: Optional[StrictStr] = response_field(alias="RegionCode", description="地域编码", type_code=1, is_public=True, is_array=False)
    zone_code: Optional[StrictStr] = response_field(alias="ZoneCode", description="可用区编码", type_code=1, is_public=True, is_array=False)
    spec_calculate_factor: Optional[StrictStr] = response_field(alias="SpecCalculateFactor", description="规格计算力因子", type_code=1, is_public=True, is_array=False)
    reset_period: Optional[StrictStr] = response_field(alias="ResetPeriod", description="周期型资源实例的重置周期", type_code=1, is_public=True, is_array=False)
    reset_by_natural_month: Optional[StrictStr] = response_field(alias="ResetByNaturalMonth", description="按月周期是否按自然月重置", type_code=1, is_public=True, is_array=False)
    subject_no: Optional[StrictStr] = response_field(alias="SubjectNo", description="服务主体", type_code=1, is_public=True, is_array=False)


class ListResourcePackagesResponse(BillingContractModel):
    list_: Optional[List[ListResourcePackagesResponseItem]] = response_field(
        alias="List", description="资源实例信息列表", type_code=7, is_public=True, is_array=True
    )
    next_token: Optional[StrictStr] = response_field(
        alias="NextToken", description="下一页起始 ID", type_code=1, is_public=True, is_array=False
    )


CONTRACT = ActionContract(
    action="ListResourcePackages",
    name_zh="查询资源包列表",
    description="查询资源包、预留实例券和预留存储容量包的信息。",
    timeout_ms=5000,
    response_data_path="Result",
    error_code_path="ResponseMetadata.Error.Code",
    error_message_path="ResponseMetadata.Error.Message",
    request_model=ListResourcePackagesRequest,
    response_model=ListResourcePackagesResponse,
)
