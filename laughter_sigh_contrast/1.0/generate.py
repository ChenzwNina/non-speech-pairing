"""Write one conversation per seed, plus the two vocalization insertion plans.

The words must be byte-identical across the three conditions, because the audio pipeline
synthesizes the content once and splices vocalizations into it. Asking a writer for three
transcripts and checking afterwards that the words match is a losing game — it drifts, and
every drift is a rebuild. So the model is never asked for three transcripts. It writes the
conversation **once**, and then says where the laughter goes and where the sighs go:

    turns:      the spoken words, the same in all three conditions
    happy:      insertions — (turn, start|end, "[chuckle] haha")
    sad:        insertions — (turn, start|end, "[sigh] ugh")

Identical wording is then true by construction rather than by inspection, and the audio for a
condition is the neutral turn audio with clips spliced at the recorded positions.

Insertions sit at a turn boundary, never inside a turn. Mid-turn would mean cutting a
synthesized sentence in half, and the seam is audible; start and end cover the natural cases
(a laugh that opens a reply, a sigh that closes one).

Also recorded per condition, for the evals downstream: what the third speaker should say next
and in what tone (free text plus a label from a fixed set, so eval 3 has something less
slippery than prose to compare), and the vocalizations that must NOT appear in a response.

Usage:
    python benchmark/generate.py --limit 2
    python benchmark/generate.py
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
import os

HERE = Path(__file__).resolve().parent
FAMILY = HERE.parent          # laughter_sigh_contrast/, holding both versions
REPO = FAMILY.parent         # the repository root, where .env and archive/ live
load_dotenv(REPO / ".env")

SEEDS = HERE / "out" / "seeds.json"
OUT_JSON = HERE / "out" / "transcripts.json"
OUT_MD = HERE / "out" / "transcripts.md"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
MAX_OUTPUT_TOKENS = 8000
MAX_ATTEMPTS = 4

MIN_TURNS, MAX_TURNS = 4, 8
SPEAKERS = ("A", "B")

# One count per condition, and the same count in both, so the two conditions never differ in
# how much non-speech audio is present — only in what kind.
MIN_VOCS, MAX_VOCS = 2, 4

POSITIONS = ("start", "end")
TONE_LABELS = ("amused", "teasing", "sympathetic", "consoling", "neutral", "curious")

# "[chuckle] haha" — a bracketed manner tag plus a short written vocalization for the voice
# to actually perform. The tag alone comes out as a thin "heh"; the written part is what
# makes it a real laugh.
TOKEN_RE = re.compile(r"^\[[a-z ]{3,20}\]\s+[a-z]{1,12}[a-z\-—…]*$")

# The manner tag was checked but not the written sound, so "[sigh] hmm" got through and the
# voice produced a thinking noise instead of an exhale. Constrain both halves.
LAUGH_SOUNDS = re.compile(r"^(h[aeiou]{1,3})+h*$")          # ha, haha, hehe, hee, hoho
SIGH_SOUNDS = re.compile(r"^(ugh+|u+h+|h+|h[aou]+h*|a+h+|oof|phew|hoo+)$")

SYSTEM = """You write short, natural conversations for a speech benchmark.

Two friends, A and B, are talking. A third friend is standing with them and will speak next;
you never write that third person's line.

The same conversation will later be heard three ways: told through laughter, told through
sighs, and told plainly. The non-speech sounds are added afterwards, by a separate process —
your job is the words, and the words must work in all three.

Rules:
- Exactly the number of turns you are told, alternating A, B, A, B, starting with A.
- A is the one the situation happened to. B is the friend responding.
- Ordinary spoken English, one or two sentences a turn, no stage directions, no emoji.
- No brackets, no written laughter, no written sighs. The words must read as neutral on the
  page: they must not settle whether this is funny or bleak. If a line only works when read
  as amused, or only when read as glum, rewrite it.
- The situation must be recognisable, but do not have anyone say how they feel about it.
"""


def schema() -> dict:
    """Words only. Placement is drawn by replan_vocalizations.py and the gold answers are
    written by write_gold.py, from the conversation as it will actually be heard."""
    return {
        "type": "object",
        "properties": {
            "turns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "speaker": {"type": "string", "enum": list(SPEAKERS)},
                        "text": {"type": "string"},
                    },
                    "required": ["speaker", "text"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["turns"],
        "additionalProperties": False,
    }


def check(payload: dict, turns_wanted: int) -> list[str]:
    """Everything the schema cannot express. Returns the reasons it is unusable."""
    problems: list[str] = []
    turns = payload.get("turns", [])
    if len(turns) != turns_wanted:
        problems.append(f"wrote {len(turns)} turns, not {turns_wanted}")
    for index, turn in enumerate(turns):
        expected = SPEAKERS[index % 2]
        if turn.get("speaker") != expected:
            problems.append(f"turn {index + 1} is {turn.get('speaker')}, expected {expected}")
        text = turn.get("text", "")
        if "[" in text or "]" in text:
            problems.append(f"turn {index + 1} has a bracket in the words")
        if re.search(r"(?i)\b(ha+ha+|hehe+|heh|ugh+|sigh|chuckl\w*|laugh\w*)\b", text):
            problems.append(f"turn {index + 1} writes a vocalization into the words")

    return problems


def render(turns: list[dict], insertions: list[dict]) -> list[str]:
    """The condition as it reads on the page — words untouched, tokens at the boundaries."""
    by_turn: dict[int, dict[str, list[str]]] = {}
    for ins in insertions:
        by_turn.setdefault(ins["turn"], {}).setdefault(ins["position"], []).append(
            ins["token"])
    lines = []
    for index, turn in enumerate(turns, 1):
        slots = by_turn.get(index, {})
        text = turn["text"]
        parts = [*slots.get("start", []), text, *slots.get("end", [])]
        lines.append(f"{turn['speaker']}: {' '.join(parts)}")
    return lines


def prompt_for(seed: dict, turns_wanted: int, problems: list[str]) -> str:
    lines = [
        f"Situation (what happened to A): {seed['situation']}",
        "",
        f"Write exactly {turns_wanted} turns, alternating A, B, starting with A.",

    ]
    if problems:
        lines += ["", "Your previous attempt was rejected because:",
                  *(f"- {p}" for p in problems), "", "Fix all of it."]
    return "\n".join(lines)


def call(client: OpenAI, prompt: str, model: str, effort: str) -> dict:
    kwargs = dict(
        model=model, instructions=SYSTEM, input=prompt,
        text={"format": {"type": "json_schema", "name": "benchmark_item",
                         "schema": schema(), "strict": True}},
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    if not re.match(r"^gpt-(4|3\.5)", model):
        kwargs["reasoning"] = {"effort": effort}
    response = client.responses.create(**kwargs)
    if response.status != "completed":
        raise RuntimeError(f"status={response.status} "
                           f"{getattr(response, 'incomplete_details', None)}")
    return json.loads(response.output_text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--only", action="append")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--effort", default=EFFORT)
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seeds = json.loads(SEEDS.read_text(encoding="utf-8"))["items"]
    if args.only:
        seeds = [s for s in seeds if s["item_id"] in args.only]
    if args.limit:
        seeds = seeds[: args.limit]

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip())
    rng = random.Random(args.seed)
    items, failures = [], 0

    for seed in seeds:
        turns_wanted = rng.randint(MIN_TURNS, MAX_TURNS)
        print(f"\n{'=' * 78}\n{seed['item_id']}  ({turns_wanted} turns)\n{'=' * 78}")
        print(f"{seed['situation'][:96]}", flush=True)
        problems: list[str] = []
        payload = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                payload = call(client, prompt_for(seed, turns_wanted, problems),
                               args.model, args.effort)
            except Exception as exc:
                print(f"  attempt {attempt}: {type(exc).__name__}: {exc}", flush=True)
                time.sleep(2 ** attempt)
                continue
            problems = check(payload, turns_wanted)
            if not problems:
                break
            print(f"  attempt {attempt} rejected: {'; '.join(problems[:3])}", flush=True)
            payload = None
        if payload is None:
            failures += 1
            items.append({**seed, "turns_wanted": turns_wanted,
                          "error": "; ".join(problems) or "no usable output"})
            continue

        item = {**seed, "turns_wanted": turns_wanted, **payload,
                "rendered": {"neutral": render(payload["turns"], [])}}
        items.append(item)
        for line in item["rendered"]["neutral"]:
            print(f"    {line}", flush=True)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    if (args.only or args.limit) and OUT_JSON.exists():
        existing = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        rebuilt = {i["item_id"]: i for i in items}
        items = [rebuilt.pop(i["item_id"], i) for i in existing["items"]]
        items += list(rebuilt.values())
        print(f"  merged {len(rebuilt) or len(items) - len(existing['items']) + 1} "
              f"regenerated item(s) into the existing set", flush=True)
    OUT_JSON.write_text(json.dumps({
        "model": args.model, "effort": args.effort, "seed": args.seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "turn_range": [MIN_TURNS, MAX_TURNS], "voc_range": [MIN_VOCS, MAX_VOCS],
        "system": SYSTEM, "items": items,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    good = [i for i in items if "error" not in i]
    md = ["# Benchmark transcripts", "",
          f"{len(good)}/{len(items)} items · `{args.model}` · words identical across "
          "conditions by construction: the turns are written once and the conditions are "
          "insertion lists.", ""]
    for item in good:
        md += [f"## {item['item_id']} — {item['turns_wanted']} turns",
               "", f"*{item['situation']}*", ""]
        md += [f"> {line}" for line in
               [f'{t["speaker"]}: {t["text"]}' for t in item["turns"]]] + [""]
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\n{len(good)}/{len(items)} usable · wrote {OUT_JSON.name}, {OUT_MD.name}")


if __name__ == "__main__":
    main()
