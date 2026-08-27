"""Re-run stage 3 over an existing items.json, without regenerating anything.

Useful for auditing an accepted set with a different (or newer) verifier model, and for
seeing which criteria are carrying the rejections. Writes a judged copy alongside the
input rather than overwriting it.

Usage:
    python hard_task/verify.py
    python hard_task/verify.py --in hard_task/out/items.json --model gpt-5.6-terra
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from generate import (  # noqa: E402  — same-folder import by design
    VERIFY_PROPERTIES,
    VERIFY_SCHEMA,
    VERIFY_SYSTEM,
    call_json,
    verdict_problems,
    verify_payload,
)

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent.parent / ".env")


def rebuild_draft(record: dict) -> dict:
    """Reconstruct the stage-2 shape that verify_payload() expects from a saved record."""
    draft = {"turns": record["transcript"]}
    for event in record["events"]:
        draft[event["event"]] = {
            "evidence_turns": event["evidence_turns"],
            "evidence_summary": event["evidence_summary"],
        }
    return draft


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", type=Path, default=HERE / "out" / "items.json")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--model", default="gpt-5.6-terra")
    parser.add_argument("--effort", default="high")
    args = parser.parse_args()
    args.infile = args.infile.resolve()
    args.out = (args.out or args.infile.with_name(args.infile.stem + "_reverified.json")).resolve()
    return args


def main() -> None:
    args = parse_args()
    data = json.loads(args.infile.read_text(encoding="utf-8"))
    records = [r for r in data["results"] if "transcript" in r]
    if not records:
        raise SystemExit(f"no complete items in {args.infile}")

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)

    print(f"re-verifying {len(records)} item(s) with {args.model}", flush=True)

    judged: list[dict] = []
    criterion_fails: Counter = Counter()
    passes = 0

    for index, record in enumerate(records, start=1):
        draft = rebuild_draft(record)
        try:
            verdict, _, _ = call_json(
                client,
                VERIFY_SYSTEM,
                verify_payload(record["plan"], draft),
                VERIFY_SCHEMA,
                "hard_task_verdict",
                args.model,
                args.effort,
            )
        except Exception as exc:
            print(f"[{index}/{len(records)}] {record['item_id']:24} error: {exc}", flush=True)
            judged.append({**record, "reverdict": {"error": str(exc)}})
            continue

        problems = verdict_problems(verdict)
        if not problems:
            passes += 1
        for key_name, _ in VERIFY_PROPERTIES:
            result = verdict.get(key_name) or {}
            for event_name in ("event_1", "event_2"):
                if not result.get(event_name):
                    criterion_fails[key_name] += 1

        status = "PASS" if not problems else "FAIL"
        print(f"[{index}/{len(records)}] {record['item_id']:24} {status}", flush=True)
        if problems:
            print(f"    {verdict.get('reason')}", flush=True)
        judged.append({**record, "reverdict": verdict})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                **{k: v for k, v in data.items() if k != "results"},
                "reverified_with": args.model,
                "reverified_at": datetime.now(timezone.utc).isoformat(),
                "reverify_summary": {
                    "n": len(records),
                    "pass": passes,
                    "fail": len(records) - passes,
                    "event_level_fails_by_criterion": dict(criterion_fails),
                },
                "results": judged,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"\n{passes}/{len(records)} pass on re-verification")
    if criterion_fails:
        print("event-level failures by criterion:")
        for key_name, _ in VERIFY_PROPERTIES:
            count = criterion_fails.get(key_name, 0)
            print(f"  {key_name:42} {count}/{2 * len(records)}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
