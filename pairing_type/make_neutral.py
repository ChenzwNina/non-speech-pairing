"""Build tag-free A+B transcripts from pairing_type pairs.

Drops audio tags and vocalization formula tokens (haha, ..., hoo, mm-hm).
Turn 3 is omitted because it depends on the vocalization.

Usage:
    python pairing_type/make_neutral.py
    python pairing_type/make_neutral.py --in pairing_type/out/pairs.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_IN = HERE / "out" / "pairs.json"
DEFAULT_OUT = HERE / "out" / "pairs_neutral.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def render_markdown(records: list[dict]) -> str:
    lines = [
        "# Neutral pairing-type transcripts",
        "",
        f"{len(records)} item(s) · Turn 1 and Turn 2 only, with vocalization formulas removed.",
        "",
    ]
    current = None
    for record in records:
        if record["contrast"] != current:
            current = record["contrast"]
            lines += [f"## {record['comparison_id']}. {current}", ""]
        lines += [f"### {record['item_id']} · {record['domain']}", ""]
        for turn in record["transcript"]:
            lines.append(f"- {turn['speaker']}: {turn['text']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    payload = json.loads(args.infile.read_text(encoding="utf-8"))
    records = []
    for item in payload.get("results") or []:
        if "shared_context" not in item:
            continue
        shared = item["shared_context"]
        records.append(
            {
                "item_id": item["item_id"],
                "comparison_id": item.get("comparison_id"),
                "contrast": item.get("contrast"),
                "domain": item.get("domain"),
                "transcript": [
                    {
                        "speaker": "A",
                        "text": shared["turn_1"]["text"],
                    },
                    {
                        "speaker": "B",
                        "text": shared["turn_2_lexical_content"],
                    },
                ],
            }
        )

    out = {
        "source": str(args.infile),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Turn 3 omitted; it depends on the vocalization.",
        "results": records,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = args.out.with_suffix(".md")
    md_path.write_text(render_markdown(records), encoding="utf-8")
    print(f"wrote {args.out} and {md_path} ({len(records)} item(s))")


if __name__ == "__main__":
    main()
