"""Draft one design condition per laughter-function pair, for you to review.

Runs BEFORE transcript generation. For each pair of functions it asks Claude
Opus 5 a single question: what must be true of a situation for BOTH readings of
the laughter to be genuinely available? The answer is one sentence, plus a
judgement of whether the pair is workable at all.

The output is a CSV you are meant to edit. Rows you have already changed are
kept on a re-run - only missing pairs are drafted - so your edits are never
overwritten unless you pass --overwrite.

generate_transcripts.py then looks up each pair's row and puts the condition
into the writer's prompt, skipping pairs you have marked impossible.

Usage:
    python pair_conditions.py                  # draft any missing rows
    python pair_conditions.py --dry-run        # print the prompts, no API calls
    python pair_conditions.py --overwrite      # redraft everything, discarding edits
"""

import argparse
import csv
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from generate_transcripts import PAIR_MODE, load_functions, make_pairs

load_dotenv()  # reads ANTHROPIC_API_KEY from .env

MODEL = "claude-opus-5"
EFFORT = "high"
MAX_TOKENS = 4000
CSV_PATH = Path("laughter_definitions.csv")
DEFAULT_OUT = Path("pair_conditions.csv")
WORKERS = 6

# A condition is a hint, not a template. Past ~25 words the model starts naming
# specific content ("an institution, client or rule...") and every generated
# dialogue inherits it. Over the cap, the draft is retried once.
MAX_CONDITION_WORDS = 25
MAX_LENGTH_ATTEMPTS = 2
BETAS = ["server-side-fallback-2026-07-01"]
MAX_RETRIES = 4
RETRY_BASE_DELAY = 2.0

FIELDNAMES = ["function_1", "function_2", "viability", "condition", "note"]

SYSTEM_PROMPT = """
You are designing stimuli for an experiment on the pragmatics of laughter, using the
taxonomy of Mazzocconi, Tian & Ginzburg (2020).

The stimuli work like this. A short spoken dialogue ends on a turn where someone
laughs. The words alone must NOT reveal what the laughter is doing - a reader seeing
only the transcript should be unable to tell which of two target functions is intended.
Only the sound of the laughter, added later, resolves it.

You will be given two target laughter functions. Your job is to state, in ONE SHORT
sentence of AT MOST 25 WORDS, what must be true of the SITUATION for both readings to
be genuinely available at once.

The 25-word limit is strict and it matters. This sentence goes into the prompt of the
model that writes the dialogues. If it is long or names specific content - a workplace,
an institution, a particular object - every dialogue inherits it and they all come out
the same. Name the abstract requirement and stop. Do not add examples, do not explain
your reasoning, do not hedge.

This is the target length and level of abstraction:
    "Something mildly bad happens to the teller - small enough to laugh at, real enough
    to feel sorry for."

Write about the situation, not about the wording. Say what has to happen, who it
happens to, and what it costs them. Do not describe how the turn should be phrased,
and do not write a dialogue.

Two findings from earlier rounds worth knowing:

- A reading is only available if the situation gives it something to attach to. For
  example, sympathy needs the teller to have suffered a genuine, if small, cost; if
  nothing bad happens to them, no laughter can be heard as sympathetic no matter how
  it sounds.
- Some functions modify the utterance itself rather than expressing a stance towards
  an event - marking irony, scare-quoting, and especially lexical uncertainty. These
  need a trigger in the words (a repair, a re-used phrase, a say/mean mismatch).
  Because the words must stay neutral, pairs involving them are much harder, and in
  testing, laughter meant as lexical uncertainty was never the preferred reading.

Also judge whether the pair can work at all:
- "workable"   - a natural everyday situation can support both readings.
- "hard"       - possible, but it needs an unusual configuration; say what in the note.
- "impossible" - the two functions' preconditions cannot both hold in one situation;
                 say why in the note.

Use "impossible" whenever you cannot write a condition that a natural everyday
situation could satisfy. Do not retreat to "hard" to avoid committing - "hard" means
you CAN state the requirement and it is merely unusual. If the two functions need
incompatible things from the same moment - one needs the laugher to be the source of
the trouble while the other needs them to be responding to someone else's, or one
needs a visible feature of the wording that must stay absent - that is impossible, and
saying so saves a wasted generation call. An earlier round found that laughter meant
as lexical uncertainty was never once the preferred reading against any partner.
"""

USER_TEMPLATE = """
[Function 1]
{function_1}

[Function 2]
{function_2}

What must be true of the situation for laughter at a single turn to be genuinely
readable as either of these two functions?
"""

CONDITION_SCHEMA = {
    "type": "object",
    "properties": {
        "condition": {
            "type": "string",
            "description": "ONE sentence describing what the situation must provide for both readings to be available.",
        },
        "viability": {
            "type": "string",
            "enum": ["workable", "hard", "impossible"],
        },
        "note": {
            "type": "string",
            "description": "Short reason, required when viability is 'hard' or 'impossible'; otherwise may be empty.",
        },
    },
    "required": ["condition", "viability", "note"],
    "additionalProperties": False,
}


def describe(fn):
    return (
        f"Name - {fn['function']}\n"
        f"Laughable type - {fn['laughable_type']}\n"
        f"Definition - {fn['definition']}\n"
        f"Example - {fn['example']}\n"
        f"Example explanation - {fn['example_explanation']}"
    )


def build_user_prompt(fn_a, fn_b):
    return USER_TEMPLATE.format(function_1=describe(fn_a), function_2=describe(fn_b))


LENGTH_RETRY_NOTE = """

Your previous answer was {words} words, over the {cap}-word limit. Cut it to the
abstract requirement only - no examples, no explanation, no clauses naming specific
content. Aim for the length of the model sentence you were given.
"""


def draft_condition(client, fn_a, fn_b, args, use_fallbacks=True, extra=""):
    """One call. Returns (parsed dict, usage dict)."""
    body = {
        "output_config": {
            "effort": args.effort,
            "format": {"type": "json_schema", "schema": CONDITION_SCHEMA},
        }
    }
    kwargs = {
        "model": args.model,
        "max_tokens": args.max_tokens,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user",
                      "content": build_user_prompt(fn_a, fn_b) + extra}],
        "thinking": {"type": "adaptive"},
        "extra_body": body,
    }
    if use_fallbacks:
        kwargs["betas"] = BETAS
        body["fallbacks"] = "default"

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.beta.messages.create(**kwargs)
            if response.stop_reason == "refusal":
                raise RuntimeError("model declined the request")
            if response.stop_reason == "max_tokens":
                raise RuntimeError("hit max_tokens - raise --max-tokens")
            text = next((b.text for b in response.content if b.type == "text"), None)
            if text is None:
                raise RuntimeError(f"no text block (stop_reason={response.stop_reason})")
            usage = response.usage
            return json.loads(text), {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            }
        except anthropic.BadRequestError as exc:
            if use_fallbacks and "fallback" in str(exc).lower():
                use_fallbacks = False
                kwargs.pop("betas", None)
                body.pop("fallbacks", None)
                continue
            raise
        except (anthropic.RateLimitError, anthropic.APIConnectionError,
                anthropic.InternalServerError, RuntimeError) as exc:
            last_error = exc
            if attempt == MAX_RETRIES - 1:
                break
            time.sleep(RETRY_BASE_DELAY * (2**attempt))
    raise last_error


def draft_within_limit(client, fn_a, fn_b, args):
    """Draft a condition, retrying once if it blows the word cap."""
    extra = ""
    result = None
    for attempt in range(MAX_LENGTH_ATTEMPTS):
        result, _ = draft_condition(client, fn_a, fn_b, args, extra=extra)
        words = len(result["condition"].split())
        if words <= args.max_words:
            return result
        extra = LENGTH_RETRY_NOTE.format(words=words, cap=args.max_words)
    return result


def load_existing(path):
    """Rows already in the CSV, keyed by (function_1, function_2). Your edits live here."""
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {
            (row["function_1"], row["function_2"]): row
            for row in csv.DictReader(f)
            if row.get("function_1") and row.get("function_2")
        }


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows([r for r in rows if r])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=CSV_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--effort", default=EFFORT,
                        choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    parser.add_argument("--pair-mode", default=PAIR_MODE,
                        choices=["combinations", "permutations",
                                 "combinations_with_replacement"])
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument("--max-words", type=int, default=MAX_CONDITION_WORDS,
                        help="word cap on each condition; over it, the draft is retried")
    parser.add_argument("--limit", type=int, help="only draft the first N pairs")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true",
                        help="redraft every pair, discarding any edits you made")
    args = parser.parse_args()

    functions = load_functions(args.csv)
    pairs = make_pairs(functions, args.pair_mode)
    if args.limit:
        pairs = pairs[: args.limit]

    existing = {} if args.overwrite else load_existing(args.out)
    todo = [p for p in pairs if (p[0]["function"], p[1]["function"]) not in existing]

    print(f"{len(pairs)} pair(s) ({args.pair_mode})")
    if existing:
        print(f"keeping {len(existing)} row(s) already in {args.out}")
    print(f"drafting {len(todo)} with {args.model}")

    if args.dry_run:
        for fn_a, fn_b in todo[:2]:
            print("\n" + "=" * 70)
            print(f"{fn_a['function']}  x  {fn_b['function']}")
            print("=" * 70)
            print(SYSTEM_PROMPT)
            print(build_user_prompt(fn_a, fn_b))
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY is empty - set it in .env (see .env.example)")

    client = anthropic.Anthropic(api_key=api_key)
    rows = [None] * len(pairs)
    lock = threading.Lock()
    done_count = 0

    def work(index):
        fn_a, fn_b = pairs[index]
        key = (fn_a["function"], fn_b["function"])
        if key in existing:
            return index, existing[key], True
        try:
            result = draft_within_limit(client, fn_a, fn_b, args)
            row = {"function_1": key[0], "function_2": key[1],
                   "viability": result["viability"], "condition": result["condition"],
                   "note": result["note"]}
        except Exception as exc:
            row = {"function_1": key[0], "function_2": key[1],
                   "viability": "ERROR", "condition": "", "note": f"{type(exc).__name__}: {exc}"}
        return index, row, False

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(work, i) for i in range(len(pairs))]
        for future in as_completed(futures):
            index, row, kept = future.result()
            with lock:
                rows[index] = row
                done_count += 1
                if not kept:
                    print(f"[{done_count}/{len(pairs)}] {row['viability']:<10} "
                          f"{row['function_1']} x {row['function_2']}")
                write_csv(args.out, rows)

    write_csv(args.out, rows)

    counts = {}
    for row in rows:
        counts[row["viability"]] = counts.get(row["viability"], 0) + 1
    lengths = [len((r["condition"] or "").split()) for r in rows if r["condition"]]
    print(f"\nwrote {len(rows)} row(s) to {args.out}")
    for key in sorted(counts):
        print(f"  {key:<11} {counts[key]}")
    if lengths:
        over = sum(1 for n in lengths if n > args.max_words)
        print(f"  condition length: mean {sum(lengths)/len(lengths):.0f} words, "
              f"max {max(lengths)}, {over} over the {args.max_words}-word cap")
    print(f"\nReview and edit {args.out} before generating transcripts.")
    if counts.get("ERROR"):
        print(f"{counts['ERROR']} pair(s) failed", file=sys.stderr)


if __name__ == "__main__":
    main()
