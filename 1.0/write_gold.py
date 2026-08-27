"""Stage 3.5 — write the gold answers against the conversation as it will actually sound.

Previously the gold came out of stage 2, at the same time as the words, before anything had
been placed. That made it a prediction: the writer knew the happy version would carry laughter
somewhere, and guessed how it would land. It never saw where the sounds ended up, how many
there were, or whether one fell mid-sentence.

Now the gold is written last, from the rendered transcript — every laugh and sigh sitting
exactly where it will be spliced. A separate model call, with no memory of having written the
words, reads that and says what a third person should say next, in what tone, and which
sounds would be wrong in a reply.

The three conditions are written in separate calls. Shown all three together, a model writes
them comparatively — "unlike the happy version, here..." — which produces gold defined by
contrast rather than by what each version actually sounds like on its own.

Usage:
    python benchmark/write_gold.py --limit 2 --dry-run
    python benchmark/write_gold.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
load_dotenv(REPO / ".env")

TRANSCRIPTS = HERE / "out" / "transcripts.json"
OUT_MD = HERE / "out" / "transcripts.md"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
CONDITIONS = ("neutral", "happy", "sad")
TONES = ("amused", "teasing", "sympathetic", "consoling", "neutral", "curious")
WORKERS = 6

SYSTEM = (
    "You are given a short conversation between two friends, written out exactly as it will "
    "be heard — including the non-speech sounds, in brackets, at the point where each one "
    "occurs.\n\n"
    "A third person has been listening and is about to speak. Describe what that person "
    "should say, at three separate levels.\n\n"

    "1. CONTENT — what the reply should be about: the move it makes, what it asks, offers, "
    "points out or acknowledges. Guidance, not a script, and no delivery here. "
    "Wrong: \"warmly joke about the mishap\". Right: \"ask whether anyone else in the "
    "class noticed\".\n\n"

    "2. TONE — how those words should be delivered. The voice, not the content: warm, dry, "
    "hushed, brisk, teasing, careful. Two people can say the same sentence in opposite "
    "tones, and this is the difference between them. Give a short free-text phrase, and "
    "separately the closest single label:\n"
    "  amused      - enjoying it along with them\n"
    "  teasing     - playful at their expense, affectionate\n"
    "  sympathetic - feeling for them, without taking over\n"
    "  consoling   - actively comforting, softening the blow\n"
    "  neutral     - level, neither warm nor cool\n"
    "  curious     - interested, drawing the story out\n\n"

    "3. MUST NOT APPEAR — non-speech sounds that would be wrong in this reply, as plain "
    "words like laughter, sigh, groan. Wrong means it would misread the room: laughing at "
    "someone who is deflated, sighing at someone enjoying their own story. Empty if nothing "
    "would be.\n\n"

    "Judge only this version. Do not imagine how it would read without the sounds, or with "
    "different ones. If the sounds are laughter, this is a story being enjoyed; if they are "
    "sighs, the same events are landing badly; if there are none, it is simply being "
    "recounted. Let that decide all three."
)


def schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "expectation": {"type": "string"},
            "tone": {"type": "string"},
            "tone_label": {"type": "string", "enum": list(TONES)},
            "must_not_appear": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["expectation", "tone", "tone_label", "must_not_appear"],
        "additionalProperties": False,
    }


def ask(client: OpenAI, item: dict, condition: str, model: str, effort: str) -> dict:
    lines = item["rendered"][condition]
    sounds = len(item["happy_insertions"]) if condition != "neutral" else 0
    prompt = "\n".join([
        f"Situation: {item['situation']}",
        "",
        "The conversation, exactly as it will be heard:",
        "",
        *lines,
        "",
        (f"It carries {sounds} non-speech sound(s), at the points marked."
         if sounds else "It carries no non-speech sounds at all."),
    ])
    last: Exception | None = None
    for attempt in range(4):
        try:
            kwargs = dict(
                model=model, instructions=SYSTEM, input=prompt,
                text={"format": {"type": "json_schema", "name": "gold",
                                 "schema": schema(), "strict": True}},
                max_output_tokens=4000)
            if not re.match(r"^gpt-(4|3\.5)", model):
                kwargs["reasoning"] = {"effort": effort}
            response = client.responses.create(**kwargs)
            if response.status != "completed":
                raise RuntimeError(f"status={response.status}")
            return json.loads(response.output_text)
        except Exception as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"{item['item_id']}/{condition}: {last}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--only", action="append")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--effort", default=EFFORT)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = json.loads(TRANSCRIPTS.read_text(encoding="utf-8"))
    items = [i for i in data["items"] if "error" not in i]
    if args.only:
        items = [i for i in items if i["item_id"] in args.only]
    if args.limit:
        items = items[: args.limit]

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip())
    jobs = [(item, condition) for item in items for condition in CONDITIONS]
    print(f"{len(items)} item(s) × 3 conditions = {len(jobs)} calls · "
          f"{args.model}, {args.effort} effort", flush=True)

    gold: dict[tuple[str, str], dict] = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(ask, client, i, c, args.model, args.effort): (i["item_id"], c)
                   for i, c in jobs}
        for future in as_completed(futures):
            key = futures[future]
            gold[key] = future.result()
            print(f"  {key[0]} {key[1]:8} {gold[key]['tone_label']:12} "
                  f"{gold[key]['expectation'][:66]}", flush=True)

    if args.dry_run:
        print("\n(dry run — nothing written)")
        return

    backup = TRANSCRIPTS.with_suffix(".pre-gold.json")
    if not backup.exists():
        shutil.copy(TRANSCRIPTS, backup)
        print(f"\nkept the previous gold at {backup.name}")
    for item in data["items"]:
        for condition in CONDITIONS:
            if (item["item_id"], condition) in gold:
                item[condition] = gold[(item["item_id"], condition)]
    data["gold"] = {"written_by": args.model, "effort": args.effort,
                    "from": "the rendered transcript, after placement",
                    "one_call_per_condition": True,
                    "written_at": datetime.now(timezone.utc).isoformat()}
    TRANSCRIPTS.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    good = [i for i in data["items"] if "error" not in i]
    md = ["# Benchmark transcripts", "",
          f"{len(good)} items · gold written from the rendered transcript by "
          f"`{args.model}`, one call per condition.", ""]
    for item in good:
        md += [f"## {item['item_id']} — {len(item['turns'])} turns, "
               f"{len(item['happy_insertions'])} vocalizations", "",
               f"*{item['situation']}*", ""]
        for condition in CONDITIONS:
            g = item[condition]
            md += [f"**{condition}** — {g['expectation']} ({g['tone_label']}; "
                   f"must not: {', '.join(g['must_not_appear']) or 'nothing'})", ""]
            md += [f"> {line}" for line in item["rendered"][condition]] + [""]
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote gold for {len(gold)//3} item(s)")


if __name__ == "__main__":
    main()
