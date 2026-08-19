"""Build four-choice attitude items from pairing_type pairs.json.

One question per realization (24 pairs × 2). The correct option is B's
Turn 2 intended attitude. Distractors always include the paired contrast
attitude, plus two others from the inventory.

Usage:
    python pairing_type/make_mcq.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_IN = HERE / "out" / "pairs.json"
DEFAULT_OUT = HERE / "out" / "mcq.json"

ATTITUDES = [
    {
        "id": "enjoyment laughter",
        "label": "Enjoyment / amusement",
        "description": "B is enjoying the situation, amused, or playfully engaged.",
    },
    {
        "id": "impatient groan",
        "label": "Impatience",
        "description": "B is impatient, annoyed, or wants the activity to end.",
    },
    {
        "id": "exhausted sigh",
        "label": "Exhaustion",
        "description": "B is physically or mentally exhausted.",
    },
    {
        "id": "relief sigh",
        "label": "Relief",
        "description": "B feels relief after something difficult or tedious has ended.",
    },
    {
        "id": "engagement mm-hm",
        "label": "Engagement / attention",
        "description": "B is engaged, attentive, and encouraging continuation.",
    },
]

ATTITUDE_BY_ID = {item["id"]: item for item in ATTITUDES}
QUESTION = "What attitude is Speaker B expressing in Turn 2?"
KEYS = ["A", "B", "C", "D"]


def rng_for(*parts: str) -> random.Random:
    digest = hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def choose_distractors(correct: str, paired: str, rng: random.Random) -> list[str]:
    leftover = [item["id"] for item in ATTITUDES if item["id"] not in {correct, paired}]
    extra = rng.sample(leftover, k=2)
    return [paired, *extra]


def make_question(item: dict, version_key: str, suffix: str) -> dict:
    version = item[version_key]
    other_key = "realization_b" if version_key == "realization_a" else "realization_a"
    correct = version["intended_meaning"]
    paired = item[other_key]["intended_meaning"]
    rng = rng_for(item["item_id"], suffix, correct)
    distractors = choose_distractors(correct, paired, rng)
    option_ids = [correct, *distractors]
    rng.shuffle(option_ids)
    options = []
    correct_key = None
    for key, attitude_id in zip(KEYS, option_ids):
        attitude = ATTITUDE_BY_ID[attitude_id]
        options.append(
            {
                "key": key,
                "id": attitude_id,
                "label": attitude["label"],
                "description": attitude["description"],
            }
        )
        if attitude_id == correct:
            correct_key = key
    turns = version["transcript"]
    return {
        "question_id": f"{item['item_id']}-{suffix}",
        "item_id": item["item_id"],
        "comparison_id": item.get("comparison_id"),
        "contrast": item.get("contrast"),
        "domain": item.get("domain"),
        "version": suffix,
        "vocalization": version.get("vocalization"),
        "audio": f"pairing_type/out/audio_sewn/{item['item_id']}-{suffix}.mp3",
        "turn_1": turns[0]["text"],
        "turn_2_lexical": item["shared_context"]["turn_2_lexical_content"],
        "turn_2": turns[1]["text"],
        "question": QUESTION,
        "options": options,
        "correct_key": correct_key,
        "correct_id": correct,
        "paired_id": paired,
    }


def render_markdown(questions: list[dict]) -> str:
    lines = [
        "# Turn 2 attitude multiple choice",
        "",
        f"{len(questions)} question(s) · 4 options · 1 correct",
        "",
        QUESTION,
        "",
    ]
    current = None
    for row in questions:
        if row["item_id"] != current:
            current = row["item_id"]
            lines += [
                f"## {row['item_id']} · {row['domain']}",
                "",
                f"{row['contrast']}",
                "",
                f"- A: {row['turn_1']}",
                f"- B lexical: {row['turn_2_lexical']}",
                "",
            ]
        lines += [
            f"### {row['question_id']} ({row['vocalization']})",
            "",
            f"Audio: `{row['audio']}`",
            "",
        ]
        for option in row["options"]:
            mark = " **(correct)**" if option["key"] == row["correct_key"] else ""
            lines.append(f"- {option['key']}. {option['label']}{mark}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = json.loads(args.infile.read_text(encoding="utf-8"))
    questions = []
    for item in payload.get("results") or []:
        if "realization_a" not in item:
            continue
        questions.append(make_question(item, "realization_a", "a"))
        questions.append(make_question(item, "realization_b", "b"))

    out = {
        "source": str(args.infile),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "question": QUESTION,
        "attitudes": ATTITUDES,
        "n": len(questions),
        "results": questions,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = args.out.with_suffix(".md")
    md_path.write_text(render_markdown(questions), encoding="utf-8")
    print(f"wrote {args.out} and {md_path} ({len(questions)} question(s))")


if __name__ == "__main__":
    main()
