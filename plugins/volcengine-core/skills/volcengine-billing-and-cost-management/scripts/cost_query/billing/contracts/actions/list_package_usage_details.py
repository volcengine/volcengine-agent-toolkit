from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import StrictStr

from ..base import ActionContract, BillingContractModel, request_field, response_field
from ....utils.billing import ISO8601_UTC_PATTERN


class ListPackageUsageDetailsRequest(BillingContractModel):
    resource_type: Literal["Package", "RI", "RSC"] = request_field(
        alias="ResourceType",
        description="查询抵扣的资源实例类型：Package、RI 或 RSC。",
        type_code=1,
        is_public=True,
        is_array=False,
        required=True,
        location_multi=(2,),
        is_enum=True,
        enum_value="Package,RI,RSC",
    )
    deduct_begin_time: StrictStr = request_field(
        alias="DeductBeginTime",
        description="抵扣开始时间，左闭右开，ISO8601 UTC：yyyy-MM-ddTHH:mm:ssZ。",
        type_code=1,
        is_public=True,
        is_array=False,
        required=True,
        location_multi=(2,),
        reg_pattern=ISO8601_UTC_PATTERN,
    )
    deduct_end_time: StrictStr = request_field(
        alias="DeductEndTime",
        description="抵扣结束时间，左闭右开，ISO8601 UTC：yyyy-MM-ddTHH:mm:ssZ。",
        type_code=1,
        is_public=True,
        is_array=False,
        required=True,
        location_multi=(2,),
        reg_pattern=ISO8601_UTC_PATTERN,
    )
    max_results: StrictStr = request_field(
        alias="MaxResults",
        description="每次查询返回最大条数，上限 50。",
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
    instance_no: Optional[StrictStr] = request_field(
        alias="InstanceNo",
        description="抵扣的资源实例 ID。",
        type_code=1,
        is_public=True,
        is_array=False,
        required=False,
        location_multi=(2,),
    )

class ListPackageUsageDetailsResponseItem(BillingContractModel):
    user_name: Optional[StrictStr] = response_field(alias="UserName", description="资源实例所属账号名称", type_code=1, is_public=True, is_array=False)
    product: Optional[StrictStr] = response_field(alias="Product", description="资源实例商品英文编码", type_code=1, is_public=True, is_array=False)
    product_name: Optional[StrictStr] = response_field(alias="ProductName", description="资源实例商品中文名称", type_code=1, is_public=True, is_array=False)
    configuration_name: Optional[StrictStr] = response_field(alias="ConfigurationName", description="资源实例配置名称", type_code=1, is_public=True, is_array=False)
    configuration_code: Optional[StrictStr] = response_field(alias="ConfigurationCode", description="资源实例配置编码", type_code=1, is_public=True, is_array=False)
    instance_no: Optional[StrictStr] = response_field(alias="InstanceNo", description="资源实例 ID", type_code=1, is_public=True, is_array=False)
    instance_name: Optional[StrictStr] = response_field(alias="InstanceName", description="资源实例名称", type_code=1, is_public=True, is_array=False)
    specification: Optional[StrictStr] = response_field(alias="Specification", description="资源实例规格", type_code=1, is_public=True, is_array=False)
    specification_unit: Optional[StrictStr] = response_field(alias="SpecificationUnit", description="资源实例规格单位", type_code=1, is_public=True, is_array=False)
    spec_calculate_factor: Optional[StrictStr] = response_field(alias="SpecCalculateFactor", description="规格计算力因子", type_code=1, is_public=True, is_array=False)
    owner_id: Optional[StrictStr] = response_field(alias="OwnerID", description="资源实例所属账号 ID", type_code=1, is_public=True, is_array=False)
    deduction_specification: Optional[StrictStr] = response_field(alias="DeductionSpecification", description="被抵扣按量实例规格", type_code=1, is_public=True, is_array=False)
    begin_time: Optional[StrictStr] = response_field(alias="BeginTime", description="抵扣消费开始时间，ISO8601 UTC", type_code=1, is_public=True, is_array=False)
    deduction_specification_unit: Optional[StrictStr] = response_field(alias="DeductionSpecificationUnit", description="被抵扣按量实例规格单位", type_code=1, is_public=True, is_array=False)
    deduction_ratio: Optional[StrictStr] = response_field(alias="DeductionRatio", description="抵扣系数", type_code=1, is_public=True, is_array=False)
    deduction_product: Optional[StrictStr] = response_field(alias="DeductionProduct", description="被抵扣按量实例商品编码", type_code=1, is_public=True, is_array=False)
    deduction_account_id: Optional[StrictStr] = response_field(alias="DeductionAccountID", description="被抵扣按量实例账号 ID", type_code=1, is_public=True, is_array=False)
    deduction_user_name: Optional[StrictStr] = response_field(alias="DeductionUserName", description="被抵扣按量实例账号名称", type_code=1, is_public=True, is_array=False)
    deduction_calculate_factor: Optional[StrictStr] = response_field(alias="DeductionCalculateFactor", description="被抵扣按量实例计算力因子", type_code=1, is_public=True, is_array=False)
    deduct_billing_factor: Optional[StrictStr] = response_field(alias="DeductBillingFactor", description="被抵扣按量实例价格影响因子", type_code=1, is_public=True, is_array=False)
    deduction_element_code: Optional[StrictStr] = response_field(alias="DeductionElementCode", description="被抵扣按量实例计费单元", type_code=1, is_public=True, is_array=False)
    deduction_region_code: Optional[StrictStr] = response_field(alias="DeductionRegionCode", description="被抵扣按量实例地域编码", type_code=1, is_public=True, is_array=False)
    subject_no: Optional[StrictStr] = response_field(alias="SubjectNo", description="服务主体名称", type_code=1, is_public=True, is_array=False)
    deduction_instance_unit: Optional[StrictStr] = response_field(alias="DeductionInstanceUnit", description="被抵扣按量实例用量单位", type_code=1, is_public=True, is_array=False)
    deduction_use_amount: Optional[StrictStr] = response_field(alias="DeductionUseAmount", description="被抵扣按量实例用量", type_code=1, is_public=True, is_array=False)
    deduction_instance_no: Optional[StrictStr] = response_field(alias="DeductionInstanceNo", description="被抵扣按量实例 ID", type_code=1, is_public=True, is_array=False)
    deduction_time: Optional[StrictStr] = response_field(alias="DeductionTime", description="抵扣时间，ISO8601 UTC", type_code=1, is_public=True, is_array=False)
    end_time: Optional[StrictStr] = response_field(alias="EndTime", description="抵扣消费结束时间，ISO8601 UTC", type_code=1, is_public=True, is_array=False)
    unit: Optional[StrictStr] = response_field(alias="Unit", description="资源实例单位", type_code=1, is_public=True, is_array=False)
    after_amount: Optional[StrictStr] = response_field(alias="AfterAmount", description="资源实例抵扣后余量", type_code=1, is_public=True, is_array=False)
    deduction_amount: Optional[StrictStr] = response_field(alias="DeductionAmount", description="资源实例抵扣量", type_code=1, is_public=True, is_array=False)
    before_amount: Optional[StrictStr] = response_field(alias="BeforeAmount", description="资源实例抵扣前余量", type_code=1, is_public=True, is_array=False)
    package_type: Optional[StrictStr] = response_field(alias="PackageType", description="资源实例形态", type_code=1, is_public=True, is_array=False)
    zone_code: Optional[StrictStr] = response_field(alias="ZoneCode", description="可用区编码", type_code=1, is_public=True, is_array=False)
    region_code: Optional[StrictStr] = response_field(alias="RegionCode", description="地域编码", type_code=1, is_public=True, is_array=False)


class ListPackageUsageDetailsResponse(BillingContractModel):
    list_: Optional[List[ListPackageUsageDetailsResponseItem]] = response_field(
        alias="List", description="抵扣明细列表", type_code=7, is_public=True, is_array=True
    )
    next_token: Optional[StrictStr] = response_field(
        alias="NextToken", description="下一页起始 ID", type_code=1, is_public=True, is_array=False
    )


CONTRACT = ActionContract(
    action="ListPackageUsageDetails",
    name_zh="查询资源包抵扣明细列表",
    description="查询资源包、预留实例券和预留存储容量包的抵扣明细。",
    timeout_ms=5000,
    response_data_path="Result",
    error_code_path="ResponseMetadata.Error.Code",
    error_message_path="ResponseMetadata.Error.Message",
    request_model=ListPackageUsageDetailsRequest,
    response_model=ListPackageUsageDetailsResponse,
)
