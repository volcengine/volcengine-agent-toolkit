from __future__ import annotations

from typing import List, Optional

from pydantic import StrictInt, StrictStr

from ..base import (
    ActionContract,
    BillingContractModel,
    request_field,
    response_field,
)

class ListCostAnalysisOpenApiRequestFiltersItem(BillingContractModel):
    operator: StrictInt = (
        request_field(
            alias='Operator',
            description='运算符\n1：仅包含\n2：仅排除',
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
    filter_key: StrictInt = (
        request_field(
            alias='FilterKey',
            description='过滤条件：\n1:payerId, 2:ownerId, 3:产品, 4:计费模式, 5:计费单元, 6:地域, 7:可用区, 8:账单类型, 9:项目, 10:标签, 12:业务类型, 13:服务主体, 15:分拆项, 16: 配置名称, 17: 成本单元',
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
    filter_value: List[StrictStr] = (
        request_field(
            alias='FilterValue',
            description='过滤器值：（最多100个）\n\n- 若FilterKey = 1（payerId）或 2（ownerId），FilterValue格式：list<账号>，FilterValue示例：\\["2100054924", "2100054925"\\]\n- 若FilterKey = 3（产品），FilterValue格式：list<产品>，FilterValue示例：\\["TOS", "VKE" \\]\n- 若FilterKey = 4（计费模式），FilterValue格式：list<计费模式>，FilterValue示例：\\["1", "2"\\]\n- 若FilterKey=5（计费单元），FilterValue格式：list<map<商品><计费单元>>，FilterValue示例：\\["{"sms":\\["BE000383"\\]}", "{"ark\\_bd":\\["BE150994"\\]}"\\]\n- 若FilterKey=6（地域），FilterValue格式：list<地域>，FilterValue示例：\\[ "", "R000807"\\]\n- 若FilterKey=7（可用区），FilterValue格式：list<map<地域><可用区>>，FilterValue示例：\\["{"":\\[""\\]}", "{"R000017":\\["ZoneA"\\]}"\\]\n- 若FilterKey=8（账单类型），FilterValue格式：list<账单类型>，FilterValue示例：\\["consume-use", "consume-new", "refund-terminate"\\]\n- 若FilterKey=9（项目），FilterValue格式：list<项目>，FilterValue示例：\\[ "", "projectA"\\]\n- 若FilterKey=10（标签），FilterValue格式：map<标签key><list<标签value>>（放置于list的第一位），FilterValue示例：\\[{"voKey2": \\["v2", "v3"\\], "voKey1": \\["v1", "v11"\\]}\\]\n- 若FilterKey=12（业务类型），FilterValue格式：list<业务类型>，FilterValue示例：\\[ "0", "1"\\]\n- 若FilterKey=13（服务主体），FilterValue格式：list<服务主体>，FilterValue示例：\\[ "3423", "3002"\\]\n- 若FilterKey=15（分拆项），FilterValue格式：list<分拆项>，FilterValue示例：\\[ "aaa"\\]\n- 若FilterKey=16（配置名称），FilterValue格式：list<配置名称>，FilterValue示例：\\[ "adjust\\_code"\\]\n- 若FilterKey=17（成本单元），FilterValue格式：list<成本单元>，FilterValue示例：\\[ "aaa"\\]',
            type_code=1,
            is_public=True,
            is_array=True,
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

class ListCostAnalysisOpenApiRequest(BillingContractModel):
    cost_type: StrictInt = (
        request_field(
            alias='CostType',
            description='费用类型：0:原价、1:折后价、2:应付金额、4:本期已分摊原价、5:本期已分摊折后价、6:本期已分摊应付金额。现金支付口径 3、7 不再提供。',
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
    classify_dimension: StrictInt = (
        request_field(
            alias='ClassifyDimension',
            description='分类维度：\n1:payer, 2:owner, 3:产品, 4:计费模式, 5:计费单元, 6:地域, 7:可用区, 8:账单类型, 9:项目, 10:标签, 11:实例id、12:业务类型, 13:服务主体, 15:分拆项, 16: 配置名称, 17: 成本单元',
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
    classify_dimension_value: Optional[StrictStr] = (
        request_field(
            alias='ClassifyDimensionValue',
            description='若ClassifyDimension为10（标签），此处填tag标签\n若ClassifyDimension为11（实例ID），此处填实例ID，多个实例ID用逗号分隔\n若ClassifyDimension为15（分拆项），此处填分拆项',
            type_code=1,
            is_public=True,
            is_array=False,
            required=False,
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
    filters: Optional[List[ListCostAnalysisOpenApiRequestFiltersItem]] = (
        request_field(
            alias='Filters',
            description='过滤条件\n此参数不携带或携带值为空列表或携带值为null时，不作为筛选条件',
            type_code=7,
            is_public=True,
            is_array=True,
            required=False,
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
    limit: StrictInt = (
        request_field(
            alias='Limit',
            description='每次查询的记录数，默认为10',
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
    offset: StrictInt = (
        request_field(
            alias='Offset',
            description='偏移量，从0开始，默认值为0',
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

class ListCostAnalysisOpenApiResponseCostDataItemCostsItem(BillingContractModel):
    time_str: Optional[StrictStr] = (
        response_field(
            alias='TimeStr',
            description='时间',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )
    amount: Optional[StrictStr] = (
        response_field(
            alias='Amount',
            description='金额',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class ListCostAnalysisOpenApiResponseCostDataItem(BillingContractModel):
    costs: Optional[List[ListCostAnalysisOpenApiResponseCostDataItemCostsItem]] = (
        response_field(
            alias='Costs',
            description='费用数据',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    classify_dimension: Optional[StrictInt] = (
        response_field(
            alias='ClassifyDimension',
            description='分类维度： 1:payer, 2:owner, 3:产品, 4:计费模式, 5:计费单元, 6:地域, 7:可用区, 8:账单类型, 9:项目, 10:标签, 11:实例id, 12:业务类型, 13:服务主体, 15:分拆项ID, 16: 配置名称, 17: 成本单元',
            type_code=2,
            is_public=True,
            is_array=False,
        )
    )
    classify_item: Optional[StrictStr] = (
        response_field(
            alias='ClassifyItem',
            description='分类维度值',
            type_code=1,
            is_public=True,
            is_array=False,
        )
    )

class ListCostAnalysisOpenApiResponse(BillingContractModel):
    cost_data: Optional[List[ListCostAnalysisOpenApiResponseCostDataItem]] = (
        response_field(
            alias='CostData',
            description='费用数据',
            type_code=7,
            is_public=True,
            is_array=True,
        )
    )
    total: Optional[StrictInt] = (
        response_field(
            alias='Total',
            description='总条数',
            type_code=2,
            is_public=True,
            is_array=False,
        )
    )
    limit: Optional[StrictInt] = (
        response_field(
            alias='Limit',
            description='步长',
            type_code=2,
            is_public=True,
            is_array=False,
        )
    )
    offset: Optional[StrictInt] = (
        response_field(
            alias='Offset',
            description='偏移量',
            type_code=2,
            is_public=True,
            is_array=False,
        )
    )

CONTRACT = ActionContract(
    action='ListCostAnalysisOpenApi',
    name_zh='查询费用分析数据(当前仅支持账单口径为账单的费用分析)',
    description='查询费用分析数据(当前仅支持账单口径为账单的费用分析)',
    timeout_ms=10000,
    response_data_path='Result',
    error_code_path='',
    error_message_path='',
    request_model=ListCostAnalysisOpenApiRequest,
    response_model=ListCostAnalysisOpenApiResponse,
)
