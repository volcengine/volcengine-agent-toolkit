"""Billing contract constants shared by validation and execution."""

from __future__ import annotations


ISO8601_UTC_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"

TOKEN_PAGE_SIZE_LIMITS = {
    "ListResourcePackages": 20,
    "ListPackageUsageDetails": 50,
}
