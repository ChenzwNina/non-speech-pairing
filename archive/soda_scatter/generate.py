"""12-turn conversations seeded from SODA, with 6-12 vocalizations scattered through them.

The seed is a real scenario from allenai/soda — its `narrative` field plus the two speaker
names — fetched live from the HuggingFace datasets server.

The harness, not the model, decides how many vocalizations there are, which turns carry
them, and which sound each one is. They are drawn with replacement from
[laughter, yawn, sob, sigh] and scattered across the twelve turns, and the model then has to
write a natural conversation that realizes that placement. Letting the writer choose instead
produces clumps wherever they were easiest and one sound repeated for convenience.

Gasp is not in the set. It was dropped after a synthesis pass: brief intakes of breath are
the least reliably produced of the five and the hardest to hear once mixed, so items built
around them were mostly unverifiable.

The density means most vocalizations sit inside a turn alongside speech, the way people
actually vocalize, rather than standing alone as a whole turn. Each gets a descriptive audio
tag — [weary sigh], [shaky sob] — documenting the intended reading and giving the TTS
something to perform.

The labels written here are provisional. verify_audio.py listens to each rendered turn and
prunes any vocalization that cannot actually be heard, so the gold that survives is grounded
in the audio rather than in the plan.

Usage:
    python soda_scatter/generate.py
    python soda_scatter/generate.py --verbose
    python soda_scatter/generate.py --seed 7 --n-vocalizations 9
    python soda_scatter/generate.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent.parent / ".env")
DEFAULT_OUT = HERE / "out" / "items.json"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
MAX_OUTPUT_TOKENS = 8000
MAX_ATTEMPTS = 4

N_TURNS = 12
MIN_VOCALIZATIONS = 6
MAX_VOCALIZATIONS = 12
VOC_TYPES = ["laughter", "yawn", "sob", "sigh"]

MAX_TURN_WORDS = 44
MAX_TARGET_WORDS = 8
MAX_INTENTION_WORDS = 22

SODA_URL = "https://datasets-server.huggingface.co/rows"
SODA_SIZE_URL = "https://datasets-server.huggingface.co/size"
SODA_SPLIT = "train"


def supports_reasoning_effort(model: str) -> bool:
    return not re.match(r"^gpt-(4|3\.5)", model)


# ------------------------------------------------------------------------ the seed

def soda_row_count(timeout: float = 30.0) -> int:
    query = urllib.parse.urlencode({"dataset": "allenai/soda"})
    with urllib.request.urlopen(f"{SODA_SIZE_URL}?{query}", timeout=timeout) as response:
        payload = json.loads(response.read())
    for split in payload.get("size", {}).get("splits", []):
        if split.get("config") == "default" and split.get("split") == SODA_SPLIT:
            return int(split["num_rows"])
    raise RuntimeError("could not determine the SODA row count")


def fetch_soda(offset: int, timeout: float = 30.0) -> dict:
    query = urllib.parse.urlencode({
        "dataset": "allenai/soda", "config": "default", "split": SODA_SPLIT,
        "offset": offset, "length": 1,
    })
    with urllib.request.urlopen(f"{SODA_URL}?{query}", timeout=timeout) as response:
        payload = json.loads(response.read())
    rows = payload.get("rows") or []
    if not rows:
        raise RuntimeError(f"no SODA row at offset {offset}")
    return rows[0]["row"]


# generic role labels read oddly as names in dialogue ("Rival: Agreed.")
ROLE_NAME_RE = re.compile(
    r"(?i)^(rival|friend|mother|father|mom|dad|boss|teacher|doctor|nurse|priest|"
    r"stranger|neighbor|neighbour|manager|clerk|waiter|officer|coach|student|"
    r"customer|patient|parent|sister|brother|son|daughter|wife|husband|"
    r"interviewer|interviewee|receptionist|landlord|tenant|barista|cashier|"
    r"salesman|saleswoman|employee|employer|colleague|classmate|roommate|"
    r"grandmother|grandfather|grandma|grandpa|aunt|uncle|cousin|therapist|"
    r"counselor|counsellor|principal|professor|assistant|secretary|driver|"
    r"guard|host|hostess|server|vendor|agent|client|kid|child|boy|girl|man|woman)$")


def seed_from_row(row: dict) -> dict | None:
    """Reduce a SODA row to a usable seed, or None if it is not a clean two-speaker scene."""
    narrative = " ".join((row.get("narrative") or "").split())
    speakers = [s for s in (row.get("speakers") or []) if s]
    unique: list[str] = []
    for name in speakers:
        if name not in unique:
            unique.append(name)
    if len(unique) != 2 or len(narrative.split()) < 15:
        return None
    if any(ROLE_NAME_RE.match(name.strip()) for name in unique):
        return None
    return {
        "narrative": narrative,
        "speaker_a": unique[0],
        "speaker_b": unique[1],
        "relation": row.get("relation"),
        "literal": " ".join((row.get("literal") or "").split()),
        "original_index": row.get("original_index"),
    }


def pick_seed(rng: random.Random, tries: int = 25) -> dict:
    total = soda_row_count()
    print(f"  allenai/soda {SODA_SPLIT}: {total:,} rows", flush=True)
    for _ in range(tries):
        seed = seed_from_row(fetch_soda(rng.randrange(0, total)))
        if seed is not None:
            return seed
    raise SystemExit("could not find a clean two-speaker SODA scene")


# ------------------------------------------------------------------- the voc plan

def speaker_of(turn: int, seed: dict) -> str:
    """Turn 1 is speaker A; the two alternate from there."""
    return seed["speaker_a"] if turn % 2 == 1 else seed["speaker_b"]


def longest_run(turns: list[int]) -> int:
    best = run = 1
    for previous, current in zip(turns, turns[1:]):
        run = run + 1 if current == previous + 1 else 1
        best = max(best, run)
    return best


def sample_plan(rng: random.Random, count: int | None, require: list[str]) -> list[dict]:
    """Draw the vocalizations and scatter them.

    Turn 1 is kept clear where possible — a sound with no preceding context reads as noise.
    At high densities that becomes impossible, and so does any limit on consecutive turns,
    so both constraints relax as the count rises rather than making the draw unsatisfiable.
    """
    for _ in range(8000):
        n = count or rng.randint(MIN_VOCALIZATIONS, MAX_VOCALIZATIONS)
        pool = list(range(2, N_TURNS + 1)) if n <= N_TURNS - 1 else list(range(1, N_TURNS + 1))
        if n > len(pool):
            continue
        kinds = [rng.choice(VOC_TYPES) for _ in range(n)]
        if any(name not in kinds for name in require):
            continue
        turns = sorted(rng.sample(pool, n))
        run_cap = 3 if n <= 8 else N_TURNS
        if longest_run(turns) > run_cap:
            continue
        odd = sum(1 for t in turns if t % 2 == 1)
        if min(odd, n - odd) < 2:
            continue
        rng.shuffle(kinds)
        return [{"turn": t, "vocalization": k} for t, k in zip(turns, kinds)]
    raise SystemExit("could not sample a valid layout")


# --------------------------------------------------------------------- the schema

def output_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "turns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "turn": {"type": "integer"},
                        "speaker": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["turn", "speaker", "text"],
                    "additionalProperties": False,
                },
            },
            "vocalizations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "turn": {"type": "integer"},
                        "vocalization": {"type": "string", "enum": VOC_TYPES},
                        "audio_tag": {"type": "string"},
                        "target": {"type": "string"},
                        "intention_after": {"type": "string"},
                    },
                    "required": ["turn", "vocalization", "audio_tag", "target",
                                 "intention_after"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["turns", "vocalizations"],
        "additionalProperties": False,
    }


SYSTEM_PROMPT = f"""
You are writing data for a benchmark on non-speech vocalizations in conversation.

You will be given a scenario, two speaker names, and a fixed plan saying which turns contain
a vocalization and which vocalization each one is. Write the conversation that realizes that
plan.

THE FORMAT

Exactly {N_TURNS} turns. The first speaker takes turn 1 and the two alternate, so odd turns
belong to the first speaker and even turns to the second.

The plan tells you which turns carry a vocalization and whether each is laughter, a yawn, a
sob or a sigh. That assignment is not negotiable. Do not move a vocalization to a different
turn, swap one for another, add one to a turn that was not assigned, or drop one.

VOCALIZATIONS SIT INSIDE SPEECH

Many turns carry a sound, so most of them must occur within a turn that also has words —
which is how people really vocalize. Put the tag where the sound actually happens: at the
start of a turn if the speaker reacts before speaking, mid-sentence if it interrupts them,
at the end if it trails off.

    Ravi: [weary sigh] Fine. I'll call them back in the morning.
    Ravi: I told them it was finished, and — [nervous laugh] — it very much was not.
    Ravi: We could still make the last train. [yawn] If you feel like running.

A turn may be the vocalization alone, but only occasionally, and only where saying nothing
is genuinely the most natural response.

AUDIO TAGS

Write each vocalization as a bracketed tag. The exact wording matters, because the voice
engine performs some phrasings and ignores others. Use these forms:

  * laughter — an adjective plus the word "laugh". Never the noun "laughter" on its own.
        [happy laugh]  [nervous laugh]  [bitter laugh]  [surprised laugh]
        [tired laugh]  [delighted laugh]  [embarrassed laugh]
  * sob — write it as CRYING. The word "sob" does not render as a sound.
        [crying]  [crying with relief]  [voice breaking, crying]  [crying openly]
  * sigh — an adjective or phrase plus "sigh".
        [weary sigh]  [sigh of relief]  [impatient sigh]  [long sigh]
  * yawn — an adjective plus "yawn".
        [wide yawn]  [long yawn]  [sleepy yawn]

Vary the qualities — identical tags mean identical readings, which is the opposite of the
point. Avoid tags built on faintness ("small", "stifled", "quiet"): a sound that has to be
strained for cannot be heard once the line is spoken aloud, and the item is thrown away.

THE SAME SOUND MEANS DIFFERENT THINGS

A laugh can be delight, teasing, disbelief, embarrassment, or bitterness. A sigh can be
relief, resignation, impatience or exhaustion. A sob can be grief, overwhelm, or relief so
sharp it breaks. A yawn can be exhaustion, boredom, or disengagement from a topic someone
would rather avoid. Where the plan repeats a sound, give the repeats clearly different
readings that the surrounding conversation supports. Ground each one in what has been said.

NATURALNESS

The conversation must read like two real people talking, following naturally from the
scenario. It needs an arc — something develops, shifts, or gets resolved. Do not let it
become a list of reactions, and do not have anyone comment on the sounds themselves ("why
are you sighing"). Never use the words laughter, laugh, sigh, sob or yawn in the spoken words
of any turn; they belong only inside the bracketed tags.

FOR EACH VOCALIZATION, ALSO REPORT

  * `target` — what the vocalization is aimed at or about, as a SHORT PHRASE of at most
    {MAX_TARGET_WORDS} words. Not a sentence. Examples: "her own excuse", "the size of the
    bill", "his third apology", "how long they have waited".
  * `intention_after` — one short sentence saying what the speaker is trying to do with the
    words that follow the sound. Examples: "Soften the refusal before turning the offer
    down." "Concede the point without admitting the whole argument." "Change the subject
    before the topic gets heavier."

Both must be specific to this conversation. `target` says what the sound is directed at;
`intention_after` says what the speaker does next with it.

OUTPUT

Return one JSON object matching the schema: `turns` (all {N_TURNS}, each with `turn`,
`speaker`, `text`, the text including any bracketed tag inline) and `vocalizations`, one
record per planned turn, each with `turn`, `vocalization`, `audio_tag`, `target`,
`intention_after`.
""".strip()


def user_prompt(seed: dict, plan: list[dict]) -> str:
    lines = [
        "Write the conversation.",
        "",
        "SCENARIO (from the SODA dataset):",
        f"  {seed['narrative']}",
        "",
        f"Speaker on odd turns:  {seed['speaker_a']}",
        f"Speaker on even turns: {seed['speaker_b']}",
        "",
        f"Vocalization plan — exactly these {len(plan)} turns, exactly these sounds:",
    ]
    for item in plan:
        lines.append(
            f"  turn {item['turn']:>2}  ({speaker_of(item['turn'], seed)})  "
            f"{item['vocalization']}"
        )
    quiet = [t for t in range(1, N_TURNS + 1) if t not in {i["turn"] for i in plan}]
    lines += [
        "",
        f"Turns with no vocalization at all: "
        + (", ".join(str(t) for t in quiet) if quiet else "none"),
        "",
        "Where a sound repeats, the repeats must mean clearly different things.",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------- checking

TAG_RE = re.compile(r"\[([^\[\]]+)\]")
VOC_WORD_RE = re.compile(r"(?i)\b(laughter|laugh(?:s|ed|ing)?|sigh(?:s|ed|ing)?|"
                         r"sob(?:s|bed|bing)?|yawn(?:s|ed|ing)?|"
                         r"cr(?:y|ies|ied|ying)|tears|weep(?:s|ing)?)\b")
# The tag wording is what eleven_v3 actually responds to, and it is not the category name.
# "sob" renders as nothing or as a vague exhale; "crying" renders. Bare "laughter" is weak;
# an adjective plus "laugh" performs. So the tag vocabulary is decoupled from the label.
TAG_WORD = {
    "laughter": r"laugh",
    "sigh": r"sigh",
    "sob": r"cry|crying|tears|weep",
    "yawn": r"yawn",
}
FAINT_RE = re.compile(r"(?i)\b(small|stifled|quiet|slight|faint|tiny|barely|suppressed)\b")


def normalize(text: str) -> str:
    return " ".join((text or "").split())


def validate(payload: dict, seed: dict, plan: list[dict]) -> list[str]:
    problems: list[str] = []
    turns = payload.get("turns") or []
    if len(turns) != N_TURNS:
        problems.append(f"expected {N_TURNS} turns, got {len(turns)}")
        return problems

    planned = {item["turn"]: item["vocalization"] for item in plan}
    by_turn: dict[int, str] = {}

    for index, turn in enumerate(turns, start=1):
        number, speaker = turn.get("turn"), normalize(turn.get("speaker") or "")
        text = normalize(turn.get("text") or "")
        if number != index:
            problems.append(f"turn {index} is numbered {number}")
            continue
        by_turn[index] = text
        expected = speaker_of(index, seed)
        if speaker != expected:
            problems.append(f"turn {index} should be spoken by {expected}")
        if not text:
            problems.append(f"turn {index} is empty")
            continue

        tags = TAG_RE.findall(text)
        spoken = normalize(TAG_RE.sub(" ", text))
        if index in planned:
            if len(tags) != 1:
                problems.append(f"turn {index} should carry exactly one tag, found {len(tags)}")
            elif not re.search(TAG_WORD[planned[index]], tags[0], re.I):
                problems.append(
                    f"turn {index} tag {tags[0]!r} does not name the assigned {planned[index]}"
                )
            elif FAINT_RE.search(tags[0]):
                problems.append(
                    f"turn {index} tag {tags[0]!r} describes a faint sound, which will not "
                    "survive being spoken aloud"
                )
            elif planned[index] == "laughter" and len(tags[0].split()) < 2:
                problems.append(
                    f"turn {index} tag {tags[0]!r} needs an adjective before \"laugh\"; "
                    "a bare laughter tag does not perform"
                )
            elif planned[index] == "sob" and re.search(r"(?i)\bsob", tags[0]):
                problems.append(
                    f"turn {index} tag {tags[0]!r} uses \"sob\", which does not render; "
                    "write it as crying"
                )
        elif tags:
            problems.append(f"turn {index} has a tag but no vocalization was assigned to it")

        if VOC_WORD_RE.search(spoken):
            problems.append(f"turn {index} names a sound in its spoken words")
        if len(spoken.split()) > MAX_TURN_WORDS:
            problems.append(f"turn {index} is too long for natural speech")

    entries = payload.get("vocalizations") or []
    if len(entries) != len(plan):
        problems.append(f"expected {len(plan)} vocalization records, got {len(entries)}")

    seen: set[int] = set()
    for entry in entries:
        turn = entry.get("turn")
        if turn not in planned:
            problems.append(f"vocalization record for unplanned turn {turn}")
            continue
        if turn in seen:
            problems.append(f"duplicate vocalization record for turn {turn}")
        seen.add(turn)
        if entry.get("vocalization") != planned[turn]:
            problems.append(
                f"turn {turn} should be {planned[turn]}, got {entry.get('vocalization')}")
        tag = normalize(entry.get("audio_tag") or "")
        if not (tag.startswith("[") and tag.endswith("]")):
            problems.append(f"turn {turn} audio_tag should be bracketed, got {tag!r}")
        elif turn in by_turn and tag not in by_turn[turn]:
            problems.append(f"turn {turn} audio_tag does not appear in the turn text")

        target = normalize(entry.get("target") or "")
        if not target:
            problems.append(f"turn {turn} target is empty")
        elif len(target.split()) > MAX_TARGET_WORDS:
            problems.append(f"turn {turn} target should be a short phrase, not a sentence")

        intention = normalize(entry.get("intention_after") or "")
        if len(intention.split()) < 4:
            problems.append(f"turn {turn} intention_after is too thin")
        elif len(intention.split()) > MAX_INTENTION_WORDS:
            problems.append(f"turn {turn} intention_after should be one short sentence")

    missing = sorted(set(planned) - seen)
    if missing:
        problems.append(f"no vocalization record for turn(s): {missing}")

    tags = [normalize(e.get("audio_tag") or "").lower() for e in entries]
    if tags and len(set(tags)) < max(3, len(tags) - 3):
        problems.append("audio tags are too repetitive; vary the described qualities")

    return problems


# ---------------------------------------------------------------------- plumbing

def call_model(client: OpenAI, prompt: str, model: str, effort: str) -> tuple[dict, dict]:
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    last: Exception | None = None
    for attempt in range(4):
        try:
            kwargs = dict(
                model=model, instructions=SYSTEM_PROMPT, input=prompt,
                text={"format": {"type": "json_schema", "name": "soda_scatter_item",
                                 "schema": output_schema(), "strict": True}},
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )
            if supports_reasoning_effort(model):
                kwargs["reasoning"] = {"effort": effort}
            response = client.responses.create(**kwargs)
            if response.status != "completed":
                raise RuntimeError(f"status={response.status}")
            return json.loads(response.output_text), {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        except Exception as exc:
            last = exc
            if attempt == 3:
                break
            time.sleep(2 ** attempt)
            print(f"    retry: {exc}", flush=True)
    raise last  # type: ignore[misc]


def print_item(payload: dict, plan: list[dict]) -> None:
    planned = {i["turn"]: i["vocalization"] for i in plan}
    for turn in payload.get("turns") or []:
        mark = f"  <- {planned[turn['turn']]}" if turn["turn"] in planned else ""
        print(f"    {turn['turn']:>2}. {turn['speaker']}: {turn['text']}{mark}", flush=True)


def render_markdown(record: dict) -> str:
    seed, entries = record["seed"], record["vocalizations"]
    marked = {v["turn"] for v in entries}
    lines = [
        f"# {record['item_id']}",
        "",
        f"**Scenario (SODA #{seed.get('original_index')})** — {seed['narrative']}",
        "",
        f"**Speakers** — {seed['speaker_a']} (odd turns), {seed['speaker_b']} (even turns)",
        "",
        f"{len(entries)} vocalizations across {N_TURNS} turns, placement fixed before the "
        "conversation was written. Labels are provisional until verify_audio.py confirms "
        "each one is audible in the render.",
        "",
        "## Transcript",
        "",
    ]
    for turn in record["turns"]:
        mark = " ←" if turn["turn"] in marked else ""
        lines.append(f"{turn['turn']}. **{turn['speaker']}:** {turn['text']}{mark}")
    lines += ["", "## Vocalizations", "",
              "| turn | speaker | sound | audio tag | target | intention after |",
              "| --- | --- | --- | --- | --- | --- |"]
    for entry in sorted(entries, key=lambda e: e["turn"]):
        lines.append(
            f"| {entry['turn']} | {speaker_of(entry['turn'], seed)} | "
            f"{entry['vocalization']} | `{entry['audio_tag']}` | {entry['target']} | "
            f"{entry['intention_after']} |")
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["vocalization"]] = counts.get(entry["vocalization"], 0) + 1
    lines += ["", "Draw: " + ", ".join(f"{k}×{v}" for k, v in sorted(counts.items())), ""]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--effort", default=EFFORT)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--n-vocalizations", type=int,
                        help=f"fix the count (default: random {MIN_VOCALIZATIONS}-"
                             f"{MAX_VOCALIZATIONS})")
    parser.add_argument("--require", action="append", default=[], choices=VOC_TYPES,
                        help="sounds that must appear in the draw")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.out = args.out.resolve()
    if args.n_vocalizations is not None and not (
            MIN_VOCALIZATIONS <= args.n_vocalizations <= MAX_VOCALIZATIONS):
        raise SystemExit(
            f"--n-vocalizations must be {MIN_VOCALIZATIONS}-{MAX_VOCALIZATIONS}")
    return args


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)

    print("fetching a SODA scenario…", flush=True)
    seed = pick_seed(rng)
    plan = sample_plan(rng, args.n_vocalizations, args.require)

    counts: dict[str, int] = {}
    for item in plan:
        counts[item["vocalization"]] = counts.get(item["vocalization"], 0) + 1
    print(f"\nSODA #{seed.get('original_index')}  ({seed.get('relation')})", flush=True)
    print(f"  {seed['narrative']}", flush=True)
    print(f"  speakers: {seed['speaker_a']} / {seed['speaker_b']}", flush=True)
    print(f"\n{len(plan)} vocalizations: "
          f"{', '.join(f'{k}x{v}' for k, v in sorted(counts.items()))}", flush=True)
    print("plan: " + ", ".join(f"t{i['turn']}={i['vocalization']}" for i in plan), flush=True)

    if args.dry_run:
        print("\n" + "=" * 74)
        print(user_prompt(seed, plan))
        return

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)

    prompt = user_prompt(seed, plan)
    totals = {"input_tokens": 0, "output_tokens": 0}
    record: dict | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        payload, usage = call_model(client, prompt, args.model, args.effort)
        totals["input_tokens"] += usage["input_tokens"]
        totals["output_tokens"] += usage["output_tokens"]
        problems = validate(payload, seed, plan)
        if args.verbose:
            print(f"\n-- attempt {attempt}/{MAX_ATTEMPTS} --", flush=True)
            print_item(payload, plan)
        if not problems:
            record = {
                "item_id": f"soda_{seed.get('original_index')}",
                "seed": seed, "plan": plan,
                "turns": payload["turns"],
                "vocalizations": payload["vocalizations"],
                "attempts": attempt, "usage": totals,
                "labels_verified": False,
            }
            break
        print(f"  attempt {attempt} rejected: {problems[:4]}", flush=True)
        prompt = user_prompt(seed, plan) + (
            "\n\nThe previous attempt failed these checks:\n- " + "\n- ".join(problems)
            + "\nKeep the vocalization plan exactly as given and return a corrected object.")

    if record is None:
        raise SystemExit("could not produce a valid item")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({
            "model": args.model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "seed_dataset": "allenai/soda",
            "turns_per_item": N_TURNS,
            "vocalizations_range": [MIN_VOCALIZATIONS, MAX_VOCALIZATIONS],
            "vocalization_types": VOC_TYPES,
            "rng_seed": args.seed,
            "results": [record],
        }, indent=2, ensure_ascii=False),
        encoding="utf-8")
    md = args.out.with_suffix(".md")
    md.write_text(render_markdown(record), encoding="utf-8")

    print("\n" + "=" * 74)
    print_item(record, plan)
    print("\n" + "=" * 74)
    for entry in sorted(record["vocalizations"], key=lambda e: e["turn"]):
        print(f"  t{entry['turn']:>2} {entry['vocalization']:9} {entry['audio_tag']}")
        print(f"       target    : {entry['target']}")
        print(f"       intention : {entry['intention_after']}")
    print(f"\nwrote {args.out} and {md}  (attempt {record['attempts']})", flush=True)
    print("next: make_audio.py, then verify_audio.py", flush=True)


if __name__ == "__main__":
    main()
