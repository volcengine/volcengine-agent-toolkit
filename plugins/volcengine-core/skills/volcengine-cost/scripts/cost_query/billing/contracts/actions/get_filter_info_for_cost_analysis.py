from __future__ import annotations

from typing import List, Optional

from pydantic import StrictInt, StrictStr

from ..base import (
    ActionContract,
    BillingContractModel,
    request_field,
    response_field,
)

class GetFilterInfoForCostAnalysisRequest(BillingContractModel):
    time_granularity: StrictInt = (
        request_field(
            alias='TimeGranularity',
            description='查询时间粒度 0:账期, 1:天',
            type_code=2,
            is_public=True,
            is_array=False,
            required=True,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=False,
            enum_value='',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )
    begin_time_str: StrictStr = (
        request_field(
            alias='BeginTimeStr',
            description='查询开始时间，东八区时间\n- 当TimeGranularity为0时，格式为YYYY-MM-01\n- 当TimeGranularity为1时，格式为YYYY-MM-DD',
            type_code=1,
            is_public=True,
            is_array=False,
            required=True,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=False,
            enum_value='',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )
    end_time_str: StrictStr = (
        request_field(
            alias='EndTimeStr',
            description='查询结束时间，东八区时间 - 当TimeGranularity为0时，格式为YYYY-MM-01 - 当TimeGranularity为1时，格式为YYYY-MM-DD',
            type_code=1,
            is_public=True,
            is_array=False,
            required=True,
            location_multi=(2,),
            default_value='',
            split_type=0,
            is_enum=False,
            enum_value='',
            reg_pattern='',
            max_length=0,
            min_length=0,
            max_value='',
            min_value='',
        )
    )

class GetFilterInfoForCostAnalysisResponsePayerUserNameListItem(BillingContractModel):
    payer_id: Optional[StrictInt] = (
        response_field(
            alias='PayerID',
            description='PayerID',
            type_code=3,
            is_public=True,
            is_array=False,
        )
    )
    payer_user_name: Optional[StrictStr] = (
        response_field(
            alias='PayerUserName',
            description='payer账号名',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class GetFilterInfoForCostAnalysisResponseOwnerUserNameListItem(BillingContractModel):
    owner_user_name: Optional[StrictStr] = (
        response_field(
            alias='OwnerUserName',
            description='owner账号名',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    owner_id: Optional[StrictInt] = (
        response_field(
            alias='OwnerID',
            description='OwnerID',
            type_code=3,
            is_public=True,
            is_array=False,
        )
    )

class GetFilterInfoForCostAnalysisResponseProductListItem(BillingContractModel):
    product_code: Optional[StrictStr] = (
        response_field(
            alias='ProductCode',
            description='产品code',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    product_name: Optional[StrictStr] = (
        response_field(
            alias='ProductName',
            description='产品名称',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class GetFilterInfoForCostAnalysisResponseBillingModeListItem(BillingContractModel):
    billing_mode_code: Optional[StrictStr] = (
        response_field(
            alias='BillingModeCode',
            description='计费模式code',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    billing_mode_name: Optional[StrictStr] = (
        response_field(
            alias='BillingModeName',
            description='计费模式名称',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class GetFilterInfoForCostAnalysisResponseElementCodeListItem(BillingContractModel):
    product_element_code: Optional[StrictStr] = (
        response_field(
            alias='ProductElementCode',
            description='{product: element_code}的json格式字符串',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    product_element_name: Optional[StrictStr] = (
        response_field(
            alias='ProductElementName',
            description='商品名称和计费单元名称的拼接',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class GetFilterInfoForCostAnalysisResponseRegionListItem(BillingContractModel):
    region_code: Optional[StrictStr] = (
        response_field(
            alias='RegionCode',
            description='地域code',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    region_name: Optional[StrictStr] = (
        response_field(
            alias='RegionName',
            description='地域名称',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class GetFilterInfoForCostAnalysisResponseZoneListItem(BillingContractModel):
    region_zone_code: Optional[StrictStr] = (
        response_field(
            alias='RegionZoneCode',
            description='{region: zone}的json格式字符串',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    region_zone_name: Optional[StrictStr] = (
        response_field(
            alias='RegionZoneName',
            description='地域名称和可用区名称的拼接',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class GetFilterInfoForCostAnalysisResponseBillCategoryListItem(BillingContractModel):
    bill_category_code: Optional[StrictStr] = (
        response_field(
            alias='BillCategoryCode',
            description='账单类型code',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    bill_category_name: Optional[StrictStr] = (
        response_field(
            alias='BillCategoryName',
            description='账单类型名称',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class GetFilterInfoForCostAnalysisResponseProjectListItem(BillingContractModel):
    project: Optional[StrictStr] = (
        response_field(
            alias='Project',
            description='项目code',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    project_display_name: Optional[StrictStr] = (
        response_field(
            alias='ProjectDisplayName',
            description='项目展示名',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class GetFilterInfoForCostAnalysisResponseBusinessModeListItem(BillingContractModel):
    business_mode_code: Optional[StrictStr] = (
        response_field(
            alias='BusinessModeCode',
            description='业务类型Code',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    business_mode_name: Optional[StrictStr] = (
        response_field(
            alias='BusinessModeName',
            description='业务类型名称',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class GetFilterInfoForCostAnalysisResponseSubjectNoListItem(BillingContractModel):
    subject_name: Optional[StrictStr] = (
        response_field(
            alias='SubjectName',
            description='主体名称',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    subject_no: Optional[StrictStr] = (
        response_field(
            alias='SubjectNo',
            description='主体编号',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class GetFilterInfoForCostAnalysisResponseConfigurationCodeItem(BillingContractModel):
    config_code: Optional[StrictStr] = (
        response_field(
            alias='ConfigCode',
            description='配置名称Code',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    config_name: Optional[StrictStr] = (
        response_field(
            alias='ConfigName',
            description='配置名称',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class GetFilterInfoForCostAnalysisResponse(BillingContractModel):
    payer_user_name_list: Optional[List[GetFilterInfoForCostAnalysisResponsePayerUserNameListItem]] = (
        response_field(
            alias='PayerUserNameList',
            description='PayerID',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    owner_user_name_list: Optional[List[GetFilterInfoForCostAnalysisResponseOwnerUserNameListItem]] = (
        response_field(
            alias='OwnerUserNameList',
            description='ownerID',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    product_list: Optional[List[GetFilterInfoForCostAnalysisResponseProductListItem]] = (
        response_field(
            alias='ProductList',
            description='产品',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    billing_mode_list: Optional[List[GetFilterInfoForCostAnalysisResponseBillingModeListItem]] = (
        response_field(
            alias='BillingModeList',
            description='计费模式',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    element_code_list: Optional[List[GetFilterInfoForCostAnalysisResponseElementCodeListItem]] = (
        response_field(
            alias='ElementCodeList',
            description='计费单元',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    region_list: Optional[List[GetFilterInfoForCostAnalysisResponseRegionListItem]] = (
        response_field(
            alias='RegionList',
            description='地域',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    zone_list: Optional[List[GetFilterInfoForCostAnalysisResponseZoneListItem]] = (
        response_field(
            alias='ZoneList',
            description='可用区',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    bill_category_list: Optional[List[GetFilterInfoForCostAnalysisResponseBillCategoryListItem]] = (
        response_field(
            alias='BillCategoryList',
            description='账单类型',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    project_list: Optional[List[GetFilterInfoForCostAnalysisResponseProjectListItem]] = (
        response_field(
            alias='ProjectList',
            description='项目',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    tag_key_list: Optional[List[StrictStr]] = (
        response_field(
            alias='TagKeyList',
            description='标签key',
            type_code=1,
            is_public=True,
            is_array=True,
        )
    )
    business_mode_list: Optional[List[GetFilterInfoForCostAnalysisResponseBusinessModeListItem]] = (
        response_field(
            alias='BusinessModeList',
            description='业务类型',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    subject_no_list: Optional[List[GetFilterInfoForCostAnalysisResponseSubjectNoListItem]] = (
        response_field(
            alias='SubjectNoList',
            description='服务主体',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    configuration_code: Optional[List[GetFilterInfoForCostAnalysisResponseConfigurationCodeItem]] = (
        response_field(
            alias='ConfigurationCode',
            description='配置名称',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    cost_unit_list: Optional[List[StrictStr]] = (
        response_field(
            alias='CostUnitList',
            description='成本单元',
            type_code=1,
            is_public=True,
            is_array=True,
        )
    )

CONTRACT = ActionContract(
    action='GetFilterInfoForCostAnalysis',
    name_zh='获取费用分析筛选项',
    description='获取费用分析筛选项',
    timeout_ms=10000,
    response_data_path='Result',
    error_code_path='ResponseMetadata.Error.Code',
    error_message_path='ResponseMetadata.Error.Message',
    request_model=GetFilterInfoForCostAnalysisRequest,
    response_model=GetFilterInfoForCostAnalysisResponse,
)
