"""Shared normalization for field paths."""

from __future__ import annotations


def normalize_field_path(value: str) -> str:
    return value.replace("[]", "").casefold()
