"""Generate v6 minimal-pair stimuli: one conversation, one vocalization slot, three versions.

The writer prompt is prompt.txt, used verbatim — the {{...}} placeholders are filled and
nothing else is touched. It asks for four turns (A, B, A, B), a single Dia tag inside one
spoken turn, and all three versions returned in full:

    condition_a   the tag for vocalization A, which carries emotion A
    condition_b   the tag for vocalization B, at exactly the same location
    baseline      nothing at that location

One call per pair of vocalizations, ten pairs, `--per-pair` items each.

Because the writer returns three transcripts rather than one transcript plus an insertion
point, the minimal pair is a claim rather than a construction, and a claim can be wrong. So
`problems()` checks what the prompt's own quality checks 1-6 assert: four turns, A-B-A-B,
exactly one tag in each vocalized version and none in the baseline, the tag at the same lexical
boundary in both, and the three transcripts identical once the tags come out. Items that fail
are discarded and re-requested, which is what the prompt says to do with them. Checks 7-10 are
about meaning and are left to the verification stage.

Seeds come from EmpatheticDialogues via the user message, since prompt.txt has no seed slot.
`--no-seeds` lets the writer invent its own situations instead.

    python v6/generate.py --per-pair 1       # a pilot, one item per pair
    python v6/generate.py                    # the full set
    python v6/generate.py --only v6_003 --redo
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path

import text_models as T

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
VOCS_FILE = HERE / "vocalization_emotions.json"
PROMPT_FILE = HERE / "prompt.txt"

TURNS = 4
ATTEMPTS = 3
MAX_TOKENS = 30000

PAREN = re.compile(r"\([^)]*\)")


def system_prompt(pair: tuple[dict, dict], n_items: int) -> str:
    """prompt.txt with its placeholders filled. The text itself is not modified."""
    a, b = pair
    filled = PROMPT_FILE.read_text()
    for token, value in (("{{VOCALIZATION_A}}", a["vocalization"]),
                         ("{{EMOTION_A}}", a["emotion"]),
                         ("{{TAG_A}}", a["dia_tag"]),
                         ("{{VOCALIZATION_B}}", b["vocalization"]),
                         ("{{EMOTION_B}}", b["emotion"]),
                         ("{{TAG_B}}", b["dia_tag"]),
                         ("{{N_ITEMS}}", str(n_items))):
        filled = filled.replace(token, value)
    return filled


def user_message(seeds: list[dict], rejected: list[str]) -> str:
    parts = []
    if seeds:
        parts.append("Seed situations from EmpatheticDialogues. Use one per contrast set, in "
                     "order, as the situation the conversation is about. Take the situation "
                     "and the relationship from it, not the wording.\n"
                     + "\n".join(f"{n}. {s['situation']}" for n, s in enumerate(seeds, 1)))
    else:
        parts.append("Choose your own everyday situations.")
    if rejected:
        parts.append("Items from your previous answer were discarded for failing the quality "
                     "checks:\n" + "\n".join(f"- {line}" for line in rejected)
                     + "\nGenerate replacements that pass every check.")
    return "\n\n".join(parts)


def version_schema() -> dict:
    return {
        "type": "object", "additionalProperties": False,
        "required": ["vocalization", "target_emotion", "turns"],
        "properties": {
            "vocalization": {"type": "string"},
            "target_emotion": {"type": "string"},
            "turns": {
                "type": "array", "minItems": TURNS, "maxItems": TURNS,
                "items": {"type": "object", "additionalProperties": False,
                          "required": ["turn", "speaker", "text"],
                          "properties": {
                              "turn": {"type": "integer",
                                       "enum": list(range(1, TURNS + 1))},
                              "speaker": {"type": "string", "enum": ["A", "B"]},
                              "text": {"type": "string"}}}}},
    }


def schema(n_items: int) -> dict:
    return {
        "type": "object", "additionalProperties": False, "required": ["items"],
        "properties": {"items": {
            "type": "array", "minItems": n_items, "maxItems": n_items,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["id", "scenario", "condition_a", "condition_b", "baseline",
                             "vocalization_turn", "vocalization_speaker"],
                "properties": {
                    "id": {"type": "string"},
                    "scenario": {"type": "string"},
                    "condition_a": version_schema(),
                    "condition_b": version_schema(),
                    "baseline": version_schema(),
                    "vocalization_turn": {"type": "integer",
                                          "enum": list(range(1, TURNS + 1))},
                    "vocalization_speaker": {"type": "string", "enum": ["A", "B"]}}}}},
    }


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def stripped(turns: list[dict]) -> list[tuple[str, str]]:
    """The transcript with every parenthetical removed — what the three versions must share."""
    return [(t["speaker"], norm(PAREN.sub("", t["text"]))) for t in turns]


def tags_in(turns: list[dict]) -> list[tuple[int, str, str]]:
    """(turn number, tag, normalized text before the tag) for every parenthetical found."""
    found = []
    for turn in turns:
        for match in PAREN.finditer(turn["text"]):
            found.append((turn["turn"], match.group(0), norm(turn["text"][:match.start()])))
    return found


def problems(item: dict, pair: tuple[dict, dict]) -> list[str]:
    """The prompt's quality checks 1-6, which are about form and so are checkable here."""
    a, b = pair
    found: list[str] = []
    versions = {"condition_a": a["dia_tag"], "condition_b": b["dia_tag"], "baseline": None}

    for name in versions:
        turns = item[name]["turns"]
        if [t["turn"] for t in turns] != list(range(1, TURNS + 1)):
            found.append(f"{name}: turns are not numbered 1..{TURNS}")
        speakers = [t["speaker"] for t in turns]
        if speakers != ["A", "B"] * (TURNS // 2):
            found.append(f"{name}: speaker order is {speakers}, not A-B-A-B")

    for name, want in versions.items():
        got = tags_in(item[name]["turns"])
        if want is None:
            if got:
                found.append(f"baseline contains {[t for _, t, _ in got]}; it must contain "
                             "no vocalization")
        elif len(got) != 1:
            found.append(f"{name} contains {len(got)} parentheticals "
                         f"({[t for _, t, _ in got]}); it must contain exactly one, {want}")
        elif got[0][1] != want:
            found.append(f"{name} contains {got[0][1]} rather than {want}")

    ta, tb = tags_in(item["condition_a"]["turns"]), tags_in(item["condition_b"]["turns"])
    if len(ta) == 1 and len(tb) == 1:
        if ta[0][0] != tb[0][0]:
            found.append(f"the tag is in turn {ta[0][0]} in condition_a but turn {tb[0][0]} "
                         "in condition_b; it must be the same turn")
        elif ta[0][2] != tb[0][2]:
            found.append("the tag sits at a different lexical boundary in the two conditions")
        elif ta[0][0] != item["vocalization_turn"]:
            found.append(f"vocalization_turn says {item['vocalization_turn']} but the tag is "
                         f"in turn {ta[0][0]}")
        else:
            turn = next(t for t in item["condition_a"]["turns"] if t["turn"] == ta[0][0])
            if turn["speaker"] != item["vocalization_speaker"]:
                found.append(f"vocalization_speaker says {item['vocalization_speaker']} but "
                             f"turn {ta[0][0]} is spoken by {turn['speaker']}")
            if not norm(PAREN.sub("", turn["text"])):
                found.append(f"turn {ta[0][0]} is the tag and nothing else; a vocalization "
                             "must never be its own standalone turn")

    base = stripped(item["baseline"]["turns"])
    for name in ("condition_a", "condition_b"):
        other = stripped(item[name]["turns"])
        if other != base:
            differs = [n + 1 for n, (x, y) in enumerate(zip(other, base)) if x != y]
            found.append(f"{name} and baseline differ in words once the tags are removed "
                         f"(turn {differs or '?'}); the three transcripts must be identical")
    return found


def normalize(item: dict, pair: tuple[dict, dict], item_id: str, seed: dict | None) -> dict:
    a, b = pair
    return {
        "item_id": item_id, "writer_id": item["id"],
        "seed_id": (seed or {}).get("seed_id"), "seed_label": (seed or {}).get("label"),
        "situation": (seed or {}).get("situation"),
        "scenario": item["scenario"],
        "voc_a": a["vocalization"], "emotion_a": a["emotion"], "tag_a": a["dia_tag"],
        "voc_b": b["vocalization"], "emotion_b": b["emotion"], "tag_b": b["dia_tag"],
        "vocalization_turn": item["vocalization_turn"],
        "vocalization_speaker": item["vocalization_speaker"],
        "condition_a": item["condition_a"], "condition_b": item["condition_b"],
        "baseline": item["baseline"],
    }


def write_pair(pair: tuple[dict, dict], seeds: list[dict],
               args) -> tuple[list[tuple[dict, dict | None]], list[str]]:
    """`len(seeds)` items for one pair of vocalizations, re-requesting any that fail a check."""
    a, b = pair
    kept: list[dict] = []
    rejected: list[str] = []
    for _ in range(ATTEMPTS):
        want = len(seeds) - len(kept)
        if want <= 0:
            break
        pending = seeds[len(kept):]
        result = T.retry(T.json_call, args.writer, system_prompt(pair, want),
                         user_message(pending if args.seeds else [], rejected[-6:]),
                         schema(want), "v6_contrast_sets", args.effort, MAX_TOKENS)
        for index, raw in enumerate(result["items"]):
            found = problems(raw, pair)
            if found:
                rejected += [f"{raw.get('id', '?')}: {line}" for line in found]
                print(f"      discarded {raw.get('id', '?')} · {found[0]}"[:150], flush=True)
                continue
            if len(kept) < len(seeds):
                seed = pending[index] if args.seeds and index < len(pending) else None
                kept.append((raw, seed))
    return kept, rejected


def render(item: dict) -> str:
    voc_turn = item["vocalization_turn"]
    lines = [f"## {item['item_id']} · {item['voc_a']} vs {item['voc_b']} · "
             f"{item['emotion_a']} vs {item['emotion_b']}", ""]
    if item["situation"]:
        lines += [f"**Seed** (`{item['seed_label']}`): {item['situation']}", ""]
    lines += [f"**Scenario:** {item['scenario']}", "",
              f"The tag sits in turn {voc_turn}, spoken by "
              f"{item['vocalization_speaker']}. Every other word is identical across the "
              f"three versions.", ""]
    for turn in item["baseline"]["turns"]:
        if turn["turn"] != voc_turn:
            lines.append(f"{turn['turn']}. **{turn['speaker']}:** {turn['text']}")
            continue
        lines.append(f"{turn['turn']}. **{turn['speaker']}:** {turn['text']}  ← baseline")
        for name, key in ((item["tag_a"], "condition_a"), (item["tag_b"], "condition_b")):
            tagged = next(t for t in item[key]["turns"] if t["turn"] == voc_turn)
            lines.append(f"{turn['turn']}. **{turn['speaker']}:** {tagged['text']}")
    lines += ["", "---", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-pair", type=int, default=2,
                        help="items per pair of vocalizations; ten pairs")
    parser.add_argument("--only", action="append", help="item ids")
    parser.add_argument("--redo", action="store_true", help="rewrite existing items")
    parser.add_argument("--no-seeds", dest="seeds", action="store_false",
                        help="let the writer invent situations instead of seeding from "
                             "EmpatheticDialogues")
    parser.add_argument("--writer", default=T.WRITER)
    parser.add_argument("--effort", default="high")
    parser.add_argument("--out-tag", default="", help="suffix for the output files")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    vocs = json.loads(VOCS_FILE.read_text())
    pool = json.loads((OUT / "seeds.json").read_text())["items"]
    suffix = f"_{args.out_tag}" if args.out_tag else ""
    pairs_json, pairs_md = OUT / f"pairs{suffix}.json", OUT / f"pairs{suffix}.md"

    all_pairs = list(itertools.combinations(vocs, 2))
    # Tied to the pair, not to a running count, so growing --per-pair adds ids instead of
    # renumbering the ones already written.
    ids = {pair_index: [f"v6_{pair_index + 1:02d}{chr(97 + n)}"
                        for n in range(args.per_pair)]
           for pair_index in range(len(all_pairs))}

    existing = json.loads(pairs_json.read_text())["items"] if pairs_json.exists() else []
    by_id = {e["item_id"]: e for e in existing}
    used = {e["situation"] for e in by_id.values() if e.get("situation")}
    queue = [s for s in pool if s["situation"] not in used]
    random.Random(args.seed).shuffle(queue)

    order = {item_id: n for n, item_id in enumerate(
        [i for pair_index in range(len(all_pairs)) for i in ids[pair_index]])}

    for pair_index, pair in enumerate(all_pairs):
        wanted = ids[pair_index]
        if args.only:
            wanted = [i for i in wanted if i in args.only]
        elif not args.redo:
            wanted = [i for i in wanted if i not in by_id]
        if not wanted:
            continue
        seeds = [queue.pop() for _ in range(min(len(wanted), len(queue)))]
        print(f"  {pair[0]['vocalization']}/{pair[1]['vocalization']} · "
              f"{len(seeds)} item(s)", flush=True)
        kept, _ = write_pair(pair, seeds, args)
        for item_id, (raw, seed) in zip(wanted, kept):
            by_id[item_id] = normalize(raw, pair, item_id, seed)
            print(f"    {item_id} · tag in turn {raw['vocalization_turn']} "
                  f"({raw['vocalization_speaker']}) · {raw['scenario'][:60]}", flush=True)
        ordered = sorted(by_id.values(), key=lambda e: order.get(e["item_id"], 999))
        pairs_json.write_text(json.dumps(
            {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "writer": args.writer, "effort": args.effort,
             "prompt": "prompt.txt, verbatim, placeholders filled",
             "seeded": "EmpatheticDialogues, via the user message" if args.seeds else False,
             "vocalizations": vocs, "items": ordered}, indent=2, ensure_ascii=False) + "\n")
        pairs_md.write_text("# v6 · minimal-pair contrast sets\n\n"
                            + "".join(render(e) for e in ordered))

    print(f"\n{pairs_json.relative_to(HERE.parent)} · {len(by_id)} items")


if __name__ == "__main__":
    main()
