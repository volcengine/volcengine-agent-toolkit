"""公开只读 Billing Action 的结构化契约注册表。"""

from __future__ import annotations

from .base import BillingContractRegistry
from .metadata import API_VERSION, SERVICE_CODE, SOURCE_FILE, SOURCE_SHA256
from .actions.list_cost_analysis_open_api import CONTRACT as LIST_COST_ANALYSIS_OPEN_API_CONTRACT
from .actions.get_filter_info_for_cost_analysis import CONTRACT as GET_FILTER_INFO_FOR_COST_ANALYSIS_CONTRACT
from .actions.list_bill_overview_by_category import CONTRACT as LIST_BILL_OVERVIEW_BY_CATEGORY_CONTRACT
from .actions.list_bill_overview_by_prod import CONTRACT as LIST_BILL_OVERVIEW_BY_PROD_CONTRACT
from .actions.list_bill import CONTRACT as LIST_BILL_CONTRACT
from .actions.list_amortized_cost_bill_detail import CONTRACT as LIST_AMORTIZED_COST_BILL_DETAIL_CONTRACT
from .actions.list_amortized_cost_bill_daily import CONTRACT as LIST_AMORTIZED_COST_BILL_DAILY_CONTRACT
from .actions.list_amortized_cost_bill_monthly import CONTRACT as LIST_AMORTIZED_COST_BILL_MONTHLY_CONTRACT
from .actions.list_split_bill_detail import CONTRACT as LIST_SPLIT_BILL_DETAIL_CONTRACT
from .actions.list_bill_detail import CONTRACT as LIST_BILL_DETAIL_CONTRACT
from .actions.query_balance_acct import CONTRACT as QUERY_BALANCE_ACCT_CONTRACT
from .actions.list_financial_relation import CONTRACT as LIST_FINANCIAL_RELATION_CONTRACT
from .actions.list_resource_packages import CONTRACT as LIST_RESOURCE_PACKAGES_CONTRACT
from .actions.list_package_usage_details import CONTRACT as LIST_PACKAGE_USAGE_DETAILS_CONTRACT
from .actions.list_coupons import CONTRACT as LIST_COUPONS_CONTRACT
from .actions.list_coupon_usage_records import CONTRACT as LIST_COUPON_USAGE_RECORDS_CONTRACT
from .actions.query_cost_change_dimensions import CONTRACT as QUERY_COST_CHANGE_DIMENSIONS_CONTRACT
from .actions.query_cost_change_amount_components import CONTRACT as QUERY_COST_CHANGE_AMOUNT_COMPONENTS_CONTRACT
from .actions.query_cost_change_drivers import CONTRACT as QUERY_COST_CHANGE_DRIVERS_CONTRACT

_CONTRACTS = (
    LIST_COST_ANALYSIS_OPEN_API_CONTRACT,
    GET_FILTER_INFO_FOR_COST_ANALYSIS_CONTRACT,
    LIST_BILL_OVERVIEW_BY_CATEGORY_CONTRACT,
    LIST_BILL_OVERVIEW_BY_PROD_CONTRACT,
    LIST_BILL_CONTRACT,
    LIST_AMORTIZED_COST_BILL_DETAIL_CONTRACT,
    LIST_AMORTIZED_COST_BILL_DAILY_CONTRACT,
    LIST_AMORTIZED_COST_BILL_MONTHLY_CONTRACT,
    LIST_SPLIT_BILL_DETAIL_CONTRACT,
    LIST_BILL_DETAIL_CONTRACT,
    QUERY_BALANCE_ACCT_CONTRACT,
    LIST_FINANCIAL_RELATION_CONTRACT,
    LIST_RESOURCE_PACKAGES_CONTRACT,
    LIST_PACKAGE_USAGE_DETAILS_CONTRACT,
    LIST_COUPONS_CONTRACT,
    LIST_COUPON_USAGE_RECORDS_CONTRACT,
    QUERY_COST_CHANGE_DIMENSIONS_CONTRACT,
    QUERY_COST_CHANGE_AMOUNT_COMPONENTS_CONTRACT,
    QUERY_COST_CHANGE_DRIVERS_CONTRACT,
)
# 上游 wire schema 源：保留服务仍可能返回的旧字段，不直接暴露给 Agent。
UPSTREAM_ACTION_CONTRACTS = {contract.action: contract for contract in _CONTRACTS}
UPSTREAM_BILLING_API_CONTRACT = BillingContractRegistry(
    service_code=SERVICE_CODE,
    api_version=API_VERSION,
    source_file=SOURCE_FILE,
    source_sha256=SOURCE_SHA256,
    actions=UPSTREAM_ACTION_CONTRACTS,
)
