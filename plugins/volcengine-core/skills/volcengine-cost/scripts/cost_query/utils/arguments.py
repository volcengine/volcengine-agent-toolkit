"""Shared command-line parsing behavior."""

from __future__ import annotations

import argparse

from ..common.errors import BillingQueryError, ErrorCode, ExitCode


class BillingArgumentParser(argparse.ArgumentParser):
    """Raise the standard machine-readable error instead of exiting."""

    def error(self, message: str) -> None:
        raise BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            f"参数无效：{message}",
            ExitCode.INVALID_ARGUMENT,
        )
