"""Probe: does the model's reading of LAUGHTER follow the context it sits in?

Two scenarios, both ending in B laughing and nothing else:

    mocking  — the situation makes B's laughter read as "you cannot be serious"
    genuine  — the situation makes B's laughter read as delight, warmth, being in on it

The vocalization category is identical in both. The same laughter recordings are used for
both scenarios, so the only thing that differs is the surrounding situation. If the model's
inferred state and response flip between the two, it is reading the sound against the
context rather than applying a fixed laughter -> X rule. If they do not flip, we have found
the ceiling.

Each scenario is run against several different laughter clips, so a single recording that
happens to sound sharp or warm cannot carry the result.

Stages:
    generate  write the two scenarios (shown for review before anything is spent on audio)
    audio     one TTS take of each proposal, spliced against N laughter clips
    eval      gpt-realtime-2.1 plays Speaker A, one fresh session per trial

Usage:
    python make_response/laughter_probe.py --stage generate
    python make_response/laughter_probe.py --stage audio
    python make_response/laughter_probe.py --stage eval
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
load_dotenv(REPO / ".env")

OUT_DIR = HERE / "out" / "laughter_probe"
SCENARIOS_PATH = OUT_DIR / "scenarios.json"
MANIFEST_PATH = OUT_DIR / "audio_manifest.json"
EVAL_PATH = OUT_DIR / "eval.json"

WRITER_MODEL = "gpt-5.6-terra"
EFFORT = "high"
EVAL_MODEL = "gpt-realtime-2.1"
MAX_OUTPUT_TOKENS = 4000
MAX_ATTEMPTS = 4

CLIPS_PER_SCENARIO = 3
GAP_AFTER_PROPOSAL = 0.40

CONDITIONS = ["mocking", "genuine"]


def supports_reasoning_effort(model: str) -> bool:
    return not re.match(r"^gpt-(4|3\.5)", model)


# ------------------------------------------------------------------ stage: generate

SCENARIO_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string"},
        "relationship": {"type": "string"},
        "shared_context": {"type": "string"},
        "proposal": {"type": "string"},
        "why_laughter_reads_this_way": {"type": "string"},
        "expected_inferred_state": {"type": "string"},
        "expected_response_function": {"type": "string"},
        "gold_response": {"type": "string"},
    },
    "required": [
        "domain", "relationship", "shared_context", "proposal",
        "why_laughter_reads_this_way", "expected_inferred_state",
        "expected_response_function", "gold_response",
    ],
    "additionalProperties": False,
}

WRITER_SYSTEM = """
You are building a controlled probe for a benchmark on non-speech vocalizations.

The format is three turns:

    Speaker A proposes something to Speaker B.
    Speaker B answers with laughter and no words at all.
    Speaker A responds.

Laughter is the only vocalization used. What varies is the situation it lands in. You will
be asked for ONE of two conditions.

CONDITION "mocking"
The situation must make B's laughter read as disbelief or derision — "you cannot possibly
be serious." Build a context where A's proposal, on its face, sounds overreaching, naive,
or at odds with something already established: A has tried and failed at this before, A is
underestimating something B knows well, the numbers or the timeline obviously do not work,
or A is proposing something the two of them have previously treated as a joke.
The response function A should then perform is to establish that the proposal is serious,
push back, or justify why it deserves consideration.

CONDITION "genuine"
The situation must make B's laughter read as delight or being in on something — laughter of
the "yes, obviously" kind, not the "you're joking" kind.

This arm is harder to write than it looks. Laughter needs something to laugh AT. Merely
welcome, sensible good news produces thanks or relief, not laughter — if your proposal would
most naturally draw "oh thank goodness" rather than a laugh, the scenario is wrong and you
must rebuild it. What actually produces warm laughter is a payoff: a running joke between
them finally coming true, an absurdly lucky coincidence, a surprise that is delightful
BECAUSE it is over the top, or A proposing the very thing the two of them have been
half-joking about doing for ages. Give the context the specific fact that makes the proposal
land as a punchline rather than as a favour.

The response function A should then perform is to take the laughter as buy-in and carry the
plan forward, share the joke, or move to the practical next step.

RULES THAT APPLY TO BOTH

The context must set up circumstances, never announce the reaction. Do not write that B
finds the idea ridiculous, or that B has been hoping for this, or anything about how B feels
or will feel. A reader should be able to see why laughter would mean what it means WITHOUT
being told. If you find yourself describing B's attitude, replace it with the fact that
would produce that attitude.

Never use the words laugh, laughter, laughing, chuckle, giggle, or funny anywhere in the
context or the proposal.

Refer to the two people as A and B throughout the context. Do not invent first names for
them. The model under test is told only that it is Speaker A, so a context that says "Jordan's
parents are visiting" leaves it unable to tell whether it is Jordan. Other people in the
scene may be named; the two speakers may not.

The two conditions will be compared directly, so keep them structurally similar: comparable
length, comparable stakes, an everyday setting, and two people with an established
relationship. Do not make the mocking one high-stakes and the genuine one trivial.

A's proposal must be one or two sentences of natural speech, and must be something a real
person would actually say out loud.

FIELDS

  * `shared_context` — the situation, three to five sentences. Circumstances only.
  * `proposal` — A's line, no speaker label.
  * `why_laughter_reads_this_way` — what specifically in the context licenses the intended
    reading of the laughter, and why the other reading is the less natural one here.
  * `expected_inferred_state` — one sentence on what A should infer B means by it.
  * `expected_response_function` — a short phrase naming the conversational action A should
    take.
  * `gold_response` — one short natural sentence A could say, realizing that function.
    Do not mention the sound.

Return exactly one scenario matching the schema.
""".strip()


def writer_prompt(condition: str, other: dict | None) -> str:
    lines = [
        f'Write the "{condition}" scenario.',
        "",
    ]
    if condition == "mocking":
        lines += [
            "The context must make laughter read as disbelief or derision, and A should",
            "then have to establish seriousness or push back.",
        ]
    else:
        lines += [
            "The context must make laughter read as delight or warm agreement, and A should",
            "then take it as buy-in and carry the plan forward.",
        ]
    if other is not None:
        lines += [
            "",
            "The other condition in this pair is already written. Keep the two comparable in",
            "length and stakes, but use a clearly different situation and relationship:",
            f"  domain: {other.get('domain')}",
            f"  relationship: {other.get('relationship')}",
            f"  proposal: {other.get('proposal')}",
        ]
    return "\n".join(lines)


LAUGH_WORD_RE = re.compile(r"(?i)\b(laugh(?:s|ed|ing|ter)?|chuckl\w*|giggl\w*|funny|humou?r\w*)\b")
FEELING_RE = re.compile(
    r"(?i)\bB (?:finds|thinks|feels|believes|considers|has (?:always|long|been)|would|will|"
    r"is (?:not )?(?:sure|convinced|excited|skeptical|delighted|hoping)|has been hoping|wants)\b"
)


def normalize(text: str) -> str:
    return " ".join((text or "").split())


def validate_scenario(payload: dict) -> list[str]:
    problems: list[str] = []
    context = normalize(payload.get("shared_context") or "")
    proposal = normalize(payload.get("proposal") or "")
    gold = normalize(payload.get("gold_response") or "")

    if len(context.split()) < 30:
        problems.append("shared_context is too thin to license a reading")
    if len(context.split()) > 130:
        problems.append("shared_context is too long")
    for label, text in (("shared_context", context), ("proposal", proposal),
                        ("gold_response", gold)):
        if LAUGH_WORD_RE.search(text):
            problems.append(f"{label} names the sound, which the probe forbids")
    if FEELING_RE.search(context):
        problems.append(
            "shared_context announces B's attitude instead of the circumstances that "
            "would produce it"
        )
    if not proposal:
        problems.append("proposal is empty")
    elif len(proposal.split()) > 45:
        problems.append("proposal is too long")
    if not gold:
        problems.append("gold_response is empty")
    elif len(gold.split()) > 34:
        problems.append("gold_response is too long")
    for field in ("expected_inferred_state", "expected_response_function",
                  "why_laughter_reads_this_way"):
        if len(normalize(payload.get(field) or "").split()) < 4:
            problems.append(f"{field} is too thin")
    return problems


def call_json(client, system, prompt, schema, name, model, effort=EFFORT):
    last: Exception | None = None
    for attempt in range(4):
        try:
            kwargs = dict(
                model=model, instructions=system, input=prompt,
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
            print(f"    retry: {exc}", flush=True)
    raise last  # type: ignore[misc]


def stage_generate(args) -> None:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)

    scenarios: dict[str, dict] = {}
    for condition in CONDITIONS:
        print(f"\n=== {condition} ===", flush=True)
        other = scenarios.get("mocking" if condition == "genuine" else "genuine")
        for attempt in range(1, MAX_ATTEMPTS + 1):
            prompt = writer_prompt(condition, other)
            if attempt > 1:
                prompt += (
                    "\n\nThe previous attempt failed these checks:\n- "
                    + "\n- ".join(problems)
                    + "\nReturn a corrected scenario."
                )
            payload = call_json(
                client, WRITER_SYSTEM, prompt, SCENARIO_SCHEMA,
                "laughter_probe_scenario", args.writer_model,
            )
            problems = validate_scenario(payload)
            if not problems:
                payload["condition"] = condition
                scenarios[condition] = payload
                break
            print(f"  attempt {attempt} rejected: {problems}", flush=True)
        else:
            raise SystemExit(f"could not write the {condition} scenario: {problems}")

        record = scenarios[condition]
        print(f"  domain      : {record['domain']}", flush=True)
        print(f"  relationship: {record['relationship']}", flush=True)
        print(f"  context     : {record['shared_context']}", flush=True)
        print(f"  A proposes  : {record['proposal']}", flush=True)
        print(f"  why         : {record['why_laughter_reads_this_way']}", flush=True)
        print(f"  A should    : {record['expected_response_function']}", flush=True)
        print(f"  gold        : {record['gold_response']}", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SCENARIOS_PATH.write_text(
        json.dumps({
            "writer_model": args.writer_model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "vocalization": "laughter",
            "design": (
                "two contexts, one vocalization category, the same laughter recordings used "
                "in both; only the situation differs"
            ),
            "scenarios": scenarios,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nwrote {SCENARIOS_PATH}", flush=True)


# --------------------------------------------------------------------- stage: audio

def stage_audio(args) -> None:
    from generate_audio import (  # noqa: E402 — same-folder reuse
        VOICE_POOL, clips_for, duration_of, sew, synthesize,
    )
    from elevenlabs import ElevenLabs

    data = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    scenarios = data["scenarios"]

    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")
    client = ElevenLabs(api_key=key)

    rng = random.Random(args.seed)
    # the SAME laughter clips in both conditions, so the sound is held constant
    pool = clips_for("laughter")
    chosen = rng.sample(pool, min(CLIPS_PER_SCENARIO, len(pool)))
    print(f"using {len(chosen)} laughter clip(s) in both conditions:", flush=True)
    for clip in chosen:
        print(f"  {clip.name}  {round(duration_of(clip), 2)}s", flush=True)

    # one voice for both proposals, so voice is not confounded with condition
    voice_label = rng.choice(list(VOICE_POOL))
    voice_id = VOICE_POOL[voice_label]
    print(f"proposal voice for both conditions: {voice_label}", flush=True)

    entries: list[dict] = []
    for condition in CONDITIONS:
        record = scenarios[condition]
        proposal_path = OUT_DIR / "audio_proposal" / condition / "proposal.mp3"
        if not proposal_path.exists() or args.overwrite:
            synthesize(client, record["proposal"], voice_id, proposal_path)
            time.sleep(0.3)
        for clip in chosen:
            stem = clip.stem.replace(" ", "")
            dest = OUT_DIR / "audio_prompt" / f"{condition}_{stem}.mp3"
            sew([(proposal_path, 0.0), (clip, GAP_AFTER_PROPOSAL)], dest)
            entries.append({
                "trial_id": f"{condition}_{stem}",
                "condition": condition,
                "clip_name": clip.name,
                "clip": str(clip.relative_to(REPO)),
                "clip_seconds": round(duration_of(clip), 3),
                "domain": record["domain"],
                "relationship": record["relationship"],
                "shared_context": record["shared_context"],
                "proposal": record["proposal"],
                "expected_inferred_state": record["expected_inferred_state"],
                "expected_response_function": record["expected_response_function"],
                "gold_response": record["gold_response"],
                "proposal_voice_label": voice_label,
                "prompt": str(dest.relative_to(REPO)),
                "prompt_seconds": round(duration_of(dest), 3),
            })
            print(f"  {condition:8} {clip.name:16} -> {entries[-1]['prompt_seconds']}s", flush=True)

    MANIFEST_PATH.write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "seed": args.seed,
            "proposal_voice_label": voice_label,
            "clips_shared_across_conditions": [c.name for c in chosen],
            "gap_after_proposal": GAP_AFTER_PROPOSAL,
            "clips": entries,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nwrote {len(entries)} clips · manifest {MANIFEST_PATH}", flush=True)


# ---------------------------------------------------------------------- stage: eval

def stage_eval(args) -> None:
    from eval_realtime import ask_once, mp3_to_pcm16_24k  # noqa: E402 — same-folder reuse

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    trials = list(manifest["clips"])
    random.Random(args.seed).shuffle(trials)

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)
    print(f"{len(trials)} trial(s) · {args.eval_model} · one fresh session each", flush=True)

    rows: list[dict] = []
    for index, entry in enumerate(trials, start=1):
        row = dict(entry)
        try:
            pcm = mp3_to_pcm16_24k(REPO / entry["prompt"])
            result = None
            for attempt in range(1, 4):
                try:
                    result = ask_once(client, entry, pcm, args.eval_model)
                    if result.get("response"):
                        break
                except Exception as exc:
                    if attempt == 3:
                        raise
                    time.sleep(2 ** attempt)
                    print(f"    retry: {exc}", flush=True)
            assert result is not None
            row.update({
                "raw_text": result["raw_text"],
                "inferred_state": result["inferred_state"],
                "response_function": result["response_function"],
                "response": result["response"],
            })
            print(f"[{index}/{len(trials)}] {entry['trial_id']}", flush=True)
            print(f"    infers  : {result['inferred_state']}", flush=True)
            print(f"    function: {result['response_function']}", flush=True)
            print(f"    says    : {result['response']}", flush=True)
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            print(f"[{index}/{len(trials)}] {entry['trial_id']} failed: {exc}", flush=True)
        rows.append(row)

    EVAL_PATH.write_text(
        json.dumps({
            "eval_model": args.eval_model,
            "seed": args.seed,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "rows": rows,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 78)
    print("SAME LAUGHTER CLIPS, DIFFERENT CONTEXT")
    print("=" * 78)
    for condition in CONDITIONS:
        sub = [r for r in rows if r["condition"] == condition and r.get("response")]
        if not sub:
            continue
        print(f"\n--- {condition} ---")
        print(f"A proposed: {sub[0]['proposal']}")
        print(f"gold function: {sub[0]['expected_response_function']}")
        for row in sub:
            print(f"\n  clip {row['clip_name']}")
            print(f"    infers  : {row['inferred_state']}")
            print(f"    function: {row['response_function']}")
            print(f"    says    : {row['response']}")
    print(f"\nwrote {EVAL_PATH}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=["generate", "audio", "eval"])
    parser.add_argument("--writer-model", default=WRITER_MODEL)
    parser.add_argument("--eval-model", default=EVAL_MODEL)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    {"generate": stage_generate, "audio": stage_audio, "eval": stage_eval}[args.stage](args)


if __name__ == "__main__":
    main()
