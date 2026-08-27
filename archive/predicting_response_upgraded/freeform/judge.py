"""Score the free-form replies collected by run.py.

Two separate judgements, because a free-form reply can fail in two different ways.

1. ALIGNMENT, per trial. Show the judge turn 1 and the model's reply, plus the pair's two
   gold interpretations in randomized order, and ask which one the reply is pragmatically
   consistent with — or neither. The judge is never told which vocalization played, so it
   cannot be swayed by knowing the intended answer. A reply "aligned" when the chosen
   interpretation is the one belonging to the sound that actually played.

   This is the free-form analogue of the MCQ's Q3, minus the giveaway: the model under
   test never saw these options.

2. DIFFERENTIATION, per pair. Show the judge turn 1 and BOTH of the model's replies (the
   one after vocalization A and the one after vocalization B), in randomized order, and
   ask whether they perform clearly different conversational functions. A model that
   answers the same way regardless of the sound scores near zero here even if alignment
   looks respectable — you can score 50% alignment by always producing the same reply.

Also flagged per trial: whether the reply names or comments on the sound (a dodge the
prompt forbids) and whether it is a plausible thing B would say at all.

Usage:
    python predicting_response_upgraded/freeform/judge.py
    python predicting_response_upgraded/freeform/judge.py --model gpt-5.6-terra
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
load_dotenv(REPO / ".env")

DEFAULT_IN = HERE / "out" / "responses.json"
DEFAULT_OUT = HERE / "out" / "scored.json"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
MAX_OUTPUT_TOKENS = 3000

VOC_ORDER = ["gasp", "grunt", "laughter", "sigh", "sob", "yawn"]


def supports_reasoning_effort(model: str) -> bool:
    return not re.match(r"^gpt-(4|3\.5)", model)


ALIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {"type": "string", "enum": ["A", "B", "NEITHER"]},
        "confident": {"type": "boolean"},
        "names_the_sound": {"type": "boolean"},
        "plausible_next_line": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["matches", "confident", "names_the_sound", "plausible_next_line", "reason"],
    "additionalProperties": False,
}

ALIGN_SYSTEM = """
You are scoring a free-form conversational continuation.

You are given:
  * `turn1` — what Speaker A said.
  * `reply` — what a model, playing Speaker B, said next. Before saying it, B reacted to
    turn 1 with a non-speech sound. You are NOT told which sound it was.
  * `interpretation_A` and `interpretation_B` — two candidate readings of what B's reaction
    communicated. Exactly one of them corresponds to the sound that actually played.

Decide which interpretation the reply is pragmatically consistent with.

Judge by conversational function: what is B actually doing in that line — teasing,
reproaching, celebrating, objecting, reluctantly agreeing, expressing alarm, asking to cut
something short, expressing relief, and so on. Match on that, not on shared topic words.
Both interpretations describe the same situation, so surface vocabulary overlap tells you
nothing.

Return:
  * `matches` — "A" if the reply fits interpretation_A better, "B" if it fits
    interpretation_B better, "NEITHER" if it is genuinely compatible with both about
    equally, or with neither.
  * `confident` — true if one interpretation is clearly the better fit; false if you are
    close to a coin flip. Use `matches` = "NEITHER" for a real tie; use
    `confident` = false when you have a lean you do not trust.
  * `names_the_sound` — true if the reply describes, names, or asks about the sound itself
    (for example "why are you sighing", "no need to laugh", "you sound exhausted") rather
    than simply continuing the conversation.
  * `plausible_next_line` — true if this is a natural thing a person could actually say at
    that point, false if it is stilted, meta, an explanation of reasoning, a refusal, or
    otherwise not a real conversational turn.
  * `reason` — one concise sentence naming the conversational function you saw and what
    decided it.

Be strict about NEITHER. A reply that is generic enough to follow either reading — a bland
acknowledgement, a neutral question, a hedge — is NEITHER, not a weak match. Do not award
a match for topical relevance alone.
""".strip()

DIFF_SCHEMA = {
    "type": "object",
    "properties": {
        "clearly_different": {"type": "boolean"},
        "reply_1_function": {"type": "string"},
        "reply_2_function": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["clearly_different", "reply_1_function", "reply_2_function", "reason"],
    "additionalProperties": False,
}

DIFF_SYSTEM = """
You are comparing two conversational continuations.

You are given `turn1` — what Speaker A said — and two replies, `reply_1` and `reply_2`,
both produced by the same model playing Speaker B after the same turn 1. In each case B
first reacted with a non-speech sound, and the two sounds were different. You are not told
which sounds they were.

Decide whether the two replies perform clearly different conversational functions.

Name the function of each reply in a few words — teasing, reproaching, celebrating,
objecting, reluctantly agreeing, expressing alarm, asking to shorten something, expressing
relief, sympathizing, challenging, and so on.

Set `clearly_different` to true only if the two replies do different conversational work.
Set it to false if they perform the same move, even when the wording differs — two
differently phrased expressions of the same sympathy, two versions of the same agreement,
or two neutral acknowledgements are NOT different functions. Differences in politeness,
intensity, or sentence length are not differences in function.

Give one concise sentence in `reason`.
""".strip()


def call_json(client, system, payload, schema, name, model, effort):
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    last: Exception | None = None
    for attempt in range(4):
        try:
            kwargs = dict(
                model=model,
                instructions=system,
                input=json.dumps(payload, ensure_ascii=False),
                text={"format": {"type": "json_schema", "name": name,
                                 "schema": schema, "strict": True}},
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )
            if supports_reasoning_effort(model):
                kwargs["reasoning"] = {"effort": effort}
            response = client.responses.create(**kwargs)
            if response.status != "completed":
                raise RuntimeError(f"status={response.status}")
            return json.loads(response.output_text)
        except Exception as exc:
            last = exc
            if attempt == 3:
                break
            time.sleep(2 ** attempt)
            print(f"    judge retry: {exc}", flush=True)
    raise last  # type: ignore[misc]


def pct(correct: int, n: int) -> float:
    return round(100 * correct / n, 1) if n else 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--effort", default=EFFORT)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    args.infile = args.infile.resolve()
    args.out = args.out.resolve()
    return args


def main() -> None:
    args = parse_args()
    data = json.loads(args.infile.read_text(encoding="utf-8"))
    rows = [r for r in data["rows"] if r.get("reply_text") and not r.get("error")]
    if not rows:
        raise SystemExit(f"no usable replies in {args.infile}")

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)
    rng = random.Random(args.seed)

    by_pair: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        by_pair[row["pair_id"]][row["version"]] = row

    voc_rows = [r for r in rows if r["condition"] == "vocalization"]
    control_rows = [r for r in rows if r["condition"] == "turn1_only"]
    print(
        f"scoring {len(voc_rows)} vocalization trial(s)"
        + (f" + {len(control_rows)} control(s)" if control_rows else "")
        + f" · judge {args.model}",
        flush=True,
    )

    # ---- 1. alignment, per trial -------------------------------------------------
    scored: list[dict] = []
    for index, row in enumerate(voc_rows, start=1):
        pair = by_pair[row["pair_id"]]
        other_version = "v2" if row["version"] == "v1" else "v1"
        other = pair.get(other_version)
        if other is None:
            print(f"[{index}] {row['trial_id']}: no sibling version, skipped", flush=True)
            continue

        # randomize which gold interpretation is presented as A, so the judge cannot
        # inherit a position bias from the dataset's v1/v2 ordering
        own, opp = row["gold_interpretation"], other["gold_interpretation"]
        own_is_a = rng.random() < 0.5
        payload = {
            "turn1": row["turn1"],
            "reply": row["reply_text"],
            "interpretation_A": own if own_is_a else opp,
            "interpretation_B": opp if own_is_a else own,
        }
        try:
            verdict = call_json(
                client, ALIGN_SYSTEM, payload, ALIGN_SCHEMA,
                "freeform_alignment", args.model, args.effort,
            )
        except Exception as exc:
            print(f"[{index}] {row['trial_id']}: judge failed: {exc}", flush=True)
            scored.append({**row, "align_error": str(exc)})
            continue

        own_letter = "A" if own_is_a else "B"
        chose = verdict["matches"]
        aligned = chose == own_letter
        scored.append({
            **row,
            "align": {
                **verdict,
                "own_letter": own_letter,
                "chose": chose,
                "aligned": aligned,
                "verdict": "aligned" if aligned else ("neither" if chose == "NEITHER" else "swapped"),
            },
        })
        label = {"aligned": "ok     ", "swapped": "SWAPPED", "neither": "neither"}[
            scored[-1]["align"]["verdict"]
        ]
        print(f"[{index}/{len(voc_rows)}] {row['trial_id']:26} {label} ({row['vocalization']})", flush=True)

    # ---- 2. differentiation, per pair --------------------------------------------
    diffs: dict[str, dict] = {}
    pair_ids = sorted(pid for pid, versions in by_pair.items() if "v1" in versions and "v2" in versions)
    for index, pair_id in enumerate(pair_ids, start=1):
        v1, v2 = by_pair[pair_id]["v1"], by_pair[pair_id]["v2"]
        first_is_v1 = rng.random() < 0.5
        payload = {
            "turn1": v1["turn1"],
            "reply_1": v1["reply_text"] if first_is_v1 else v2["reply_text"],
            "reply_2": v2["reply_text"] if first_is_v1 else v1["reply_text"],
        }
        try:
            verdict = call_json(
                client, DIFF_SYSTEM, payload, DIFF_SCHEMA,
                "freeform_differentiation", args.model, args.effort,
            )
        except Exception as exc:
            print(f"[{index}] {pair_id}: diff judge failed: {exc}", flush=True)
            continue
        diffs[pair_id] = {**verdict, "first_shown": "v1" if first_is_v1 else "v2"}
        mark = "differs" if verdict["clearly_different"] else "SAME   "
        print(f"[{index}/{len(pair_ids)}] {pair_id:26} {mark}", flush=True)

    # ---- summary -----------------------------------------------------------------
    ok = [r for r in scored if "align" in r]
    aligned = [r for r in ok if r["align"]["aligned"]]
    swapped = [r for r in ok if r["align"]["verdict"] == "swapped"]
    neither = [r for r in ok if r["align"]["verdict"] == "neither"]
    confident = [r for r in ok if r["align"]["confident"]]

    by_voc: dict[str, list[dict]] = defaultdict(list)
    for r in ok:
        by_voc[r["vocalization"]].append(r)

    differed = [p for p, v in diffs.items() if v["clearly_different"]]

    # ---- 3. did the sound change the answer at all? ------------------------------
    # Compare each vocalization reply against the same pair's control reply (turn 1 with
    # no reaction). If they do the same conversational work, the sound moved nothing —
    # the reply came from A's words. This is the floor the other numbers sit on.
    vs_control: dict[str, dict] = {}
    control_by_pair = {r["pair_id"]: r for r in control_rows if r.get("reply_text")}
    if control_by_pair:
        todo = [
            (r, control_by_pair[r["pair_id"]])
            for r in voc_rows
            if r["pair_id"] in control_by_pair
        ]
        print(f"\ncomparing {len(todo)} reply/control pair(s)", flush=True)
        for index, (row, control) in enumerate(todo, start=1):
            voc_first = rng.random() < 0.5
            payload = {
                "turn1": row["turn1"],
                "reply_1": row["reply_text"] if voc_first else control["reply_text"],
                "reply_2": control["reply_text"] if voc_first else row["reply_text"],
            }
            try:
                verdict = call_json(
                    client, DIFF_SYSTEM, payload, DIFF_SCHEMA,
                    "freeform_vs_control", args.model, args.effort,
                )
            except Exception as exc:
                print(f"[{index}] {row['trial_id']}: control compare failed: {exc}", flush=True)
                continue
            vs_control[row["trial_id"]] = {
                **verdict,
                "vocalization": row["vocalization"],
                "voc_shown_first": voc_first,
            }
            mark = "differs" if verdict["clearly_different"] else "SAME AS CONTROL"
            print(f"[{index}/{len(todo)}] {row['trial_id']:26} {mark}", flush=True)

    moved = [t for t, v in vs_control.items() if v["clearly_different"]]

    # a pair only really passes when BOTH of its replies align — that is the free-form
    # equivalent of getting the contrast right rather than winning one side of a coin flip
    both_aligned = [
        pid for pid in pair_ids
        if all(
            any(r["trial_id"] == f"{pid}_{v}" and r["align"]["aligned"] for r in ok)
            for v in ("v1", "v2")
        )
    ]

    summary = {
        "n_trials": len(ok),
        "aligned": f"{len(aligned)}/{len(ok)} = {pct(len(aligned), len(ok))}%",
        "swapped": f"{len(swapped)}/{len(ok)} = {pct(len(swapped), len(ok))}%",
        "neither": f"{len(neither)}/{len(ok)} = {pct(len(neither), len(ok))}%",
        "aligned_when_judge_confident": (
            f"{sum(1 for r in confident if r['align']['aligned'])}/{len(confident)} = "
            f"{pct(sum(1 for r in confident if r['align']['aligned']), len(confident))}%"
        ),
        "named_the_sound": f"{sum(1 for r in ok if r['align']['names_the_sound'])}/{len(ok)}",
        "implausible_line": f"{sum(1 for r in ok if not r['align']['plausible_next_line'])}/{len(ok)}",
        "pairs_with_both_aligned": f"{len(both_aligned)}/{len(pair_ids)} = {pct(len(both_aligned), len(pair_ids))}%",
        "pairs_replies_clearly_different": (
            f"{len(differed)}/{len(diffs)} = {pct(len(differed), len(diffs))}%"
        ),
        "reply_differed_from_no_sound_control": (
            f"{len(moved)}/{len(vs_control)} = {pct(len(moved), len(vs_control))}%"
            if vs_control else "no control trials"
        ),
        "aligned_by_vocalization": {
            v: f"{sum(1 for r in by_voc[v] if r['align']['aligned'])}/{len(by_voc[v])} = "
               f"{pct(sum(1 for r in by_voc[v] if r['align']['aligned']), len(by_voc[v]))}%"
            for v in VOC_ORDER if by_voc.get(v)
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "source": str(args.infile.relative_to(REPO)),
                "responder_model": data.get("model"),
                "judge_model": args.model,
                "seed": args.seed,
                "scored_at": datetime.now(timezone.utc).isoformat(),
                "summary": summary,
                "differentiation": diffs,
                "vs_control": vs_control,
                "rows": scored,
                "control_rows": control_rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\n" + "=" * 70)
    print(f"aligned with the sound that played : {summary['aligned']}")
    print(f"aligned with the OTHER sound       : {summary['swapped']}")
    print(f"fit neither / too generic          : {summary['neither']}")
    print(f"  when the judge was confident     : {summary['aligned_when_judge_confident']}")
    print(f"both replies aligned, per pair     : {summary['pairs_with_both_aligned']}")
    print(f"two replies did different work     : {summary['pairs_replies_clearly_different']}")
    print(f"reply differed from no-sound control: {summary['reply_differed_from_no_sound_control']}")
    print(f"named the sound instead of replying: {summary['named_the_sound']}")
    print(f"not a plausible line               : {summary['implausible_line']}")
    print("\naligned by vocalization:")
    for voc, rate in summary["aligned_by_vocalization"].items():
        print(f"  {voc:9} {rate}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
