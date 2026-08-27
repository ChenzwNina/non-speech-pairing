"""Re-run the mechanical checks over a saved pairs.json. No API calls.

Usage:
    python predicting_response_upgraded/verify.py
    python predicting_response_upgraded/verify.py --out predicting_response_upgraded/out/pairs.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from generate import validate

HERE = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "out" / "pairs.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = json.loads(args.out.read_text(encoding="utf-8"))
    records = [r for r in data["results"] if "shared_turn1" in r]
    missing = [r["pair_id"] for r in data["results"] if r.get("error")]

    print(f"{args.out}: {len(records)} record(s), {len(missing)} failed at generation")

    bad = 0
    for record in records:
        voc1, voc2 = record["contrast"].split("-")
        problems = validate(record, voc1, voc2, record["pair_id"])
        if problems:
            bad += 1
            print(f"  {record['pair_id']}")
            for problem in problems:
                print(f"    - {problem}")

    judged = [r for r in records if "judge" in r]
    if judged:
        keys = [k for k, v in judged[0]["judge"].items() if isinstance(v, bool)]
        print("\naudit properties, all should be true:")
        for key in keys:
            passed = sum(1 for r in judged if r["judge"].get(key))
            print(f"  {passed}/{len(judged)}  {key}")
        overall_pass = sum(1 for r in judged if r["judge"].get("overall") == "PASS")
        print(f"  {overall_pass}/{len(judged)}  overall == PASS")

    if missing:
        print("\nno pair for: " + ", ".join(missing))
    print(f"\n{len(records) - bad}/{len(records)} pass the mechanical checks")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
