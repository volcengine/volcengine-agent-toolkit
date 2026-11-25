#!/usr/bin/env python3
"""Export the development models to the standard-library runtime contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check that the committed contract matches the development models.")
    args = parser.parse_args()
    from cost_query.billing.contracts import build_static_contract_payload

    path = Path(__file__).parent / "cost_query" / "billing" / "contracts.json"
    expected = json.dumps(build_static_contract_payload(), ensure_ascii=False, separators=(",", ":")) + "\n"
    if args.check:
        matches = path.is_file() and path.read_text(encoding="utf-8") == expected
        print(json.dumps({"status": "passed" if matches else "failed", "contract_matches_models": matches}))
        return 0 if matches else 1
    path.write_text(expected, encoding="utf-8")
    print(json.dumps({"status": "passed", "contract_exported": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
