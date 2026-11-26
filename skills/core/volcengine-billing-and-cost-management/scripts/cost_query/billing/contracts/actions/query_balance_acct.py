from __future__ import annotations

from typing import Optional

from pydantic import StrictInt, StrictStr

from ..base import ActionContract, BillingContractModel, response_field


class QueryBalanceAcctRequest(BillingContractModel):
    pass


class QueryBalanceAcctResponse(BillingContractModel):
    account_id: Optional[StrictInt] = response_field(
        alias="AccountID",
        description="当前授权账户 ID；默认不对外展示",
        type_code=3,
        is_public=False,
        is_array=False,
    )
    arrears_balance: Optional[StrictStr] = response_field(
        alias="ArrearsBalance",
        description="欠费金额；大于零只表示存在欠费金额，不单独代表账户当前欠费",
        type_code=1,
        is_public=True,
        is_array=False,
    )
    available_balance: Optional[StrictStr] = response_field(
        alias="AvailableBalance",
        description="可用余额；小于零表示账户欠费，大于等于零表示账户当前不欠费",
        type_code=1,
        is_public=True,
        is_array=False,
    )
    cash_balance: Optional[StrictStr] = response_field(
        alias="CashBalance",
        description="现金余额",
        type_code=1,
        is_public=True,
        is_array=False,
    )
    credit_limit: Optional[StrictStr] = response_field(
        alias="CreditLimit",
        description="信控额度",
        type_code=1,
        is_public=True,
        is_array=False,
    )
    freeze_amount: Optional[StrictStr] = response_field(
        alias="FreezeAmount",
        description="冻结金额",
        type_code=1,
        is_public=True,
        is_array=False,
    )
    currency: Optional[StrictStr] = response_field(
        alias="Currency",
        description="响应返回的账号结算币种；按原值解释，不预设枚举",
        type_code=1,
        is_public=True,
        is_array=False,
    )


CONTRACT = ActionContract(
    action="QueryBalanceAcct",
    name_zh="查询用户账户余额信息",
    description="查询当前授权账户的资金余额快照。",
    timeout_ms=5000,
    response_data_path="Result",
    error_code_path="ResponseMetadata.Error.Code",
    error_message_path="ResponseMetadata.Error.Message",
    request_model=QueryBalanceAcctRequest,
    response_model=QueryBalanceAcctResponse,
)
