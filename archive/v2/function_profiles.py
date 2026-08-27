"""Break each laughter function into its structural parts, one row per function.

Runs before transcript generation. For each of the 10 functions it asks Claude
Opus 5 to fill in the components a writer needs in order to build a situation
that supports that reading:

    who laughs, whose event triggered it, what the laugh is trying to do,
    what must be true for the reading to exist at all, whether it needs a
    hook in the wording, and what the next speaker would naturally do.

Two columns are NOT asked of the model. `laughable_type` is copied from
laughter_definitions.csv, and `typical_arousal` is filled in from the corpus
findings in Mazzocconi, Tian & Ginzburg (2020) - high arousal occurs only with
pleasant incongruity, pragmatic incongruity is low and never high, and low
arousal is the most common realization across every function.

The output is a CSV you are meant to edit. Existing rows are kept on a re-run.

Usage:
    python function_profiles.py              # fill any missing rows
    python function_profiles.py --dry-run    # print the prompt, no API calls
    python function_profiles.py --overwrite  # redraft everything
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

from generate_transcripts import load_functions

load_dotenv()  # reads ANTHROPIC_API_KEY from .env

MODEL = "claude-opus-5"
EFFORT = "high"
MAX_TOKENS = 4000
CSV_PATH = Path("laughter_definitions.csv")
DEFAULT_OUT = Path("function_profiles.csv")
WORKERS = 6
MAX_FIELD_WORDS = 14
BETAS = ["server-side-fallback-2026-07-01"]
MAX_RETRIES = 4
RETRY_BASE_DELAY = 2.0

MODEL_FIELDS = [
    "laugher_role", "laughable_origin", "trigger_event", "intention",
    "manages_face_of", "precondition", "needs_lexical_hook", "lexical_hook",
    "likely_next_move",
]
FIELDNAMES = ["function", "laughable_type", "typical_arousal"] + MODEL_FIELDS

# Corpus findings, Mazzocconi et al. (2020) Table 5 and section 6.2.5. Filled in
# by branch rather than asked of the model, so the values stay faithful to the data.
AROUSAL_BY_BRANCH = {
    "pleasant": "low or medium; the only branch where high occurs",
    "social": "low or medium; never high",
    "pragmatic": "low; never high",
    "pleasantness": "low",
}


def arousal_for(laughable_type):
    t = laughable_type.lower()
    if "pragmatic" in t:
        return AROUSAL_BY_BRANCH["pragmatic"]
    if "social" in t:
        return AROUSAL_BY_BRANCH["social"]
    if "pleasant incongruity" in t:
        return AROUSAL_BY_BRANCH["pleasant"]
    return AROUSAL_BY_BRANCH["pleasantness"]


SYSTEM_PROMPT = """
You are analysing the laughter taxonomy of Mazzocconi, Tian & Ginzburg (2020) so that a
writer can construct dialogues in which laughter carries a specific function.

You will be given ONE function: its name, laughable type, definition, an example from
the paper, and an explanation of that example. Break it into the structural parts a
writer needs.

Answer about the STRUCTURE of the situation, not about wording, and not with examples.
Every free-text field must be at most 14 words. Short and abstract beats complete.

Fields:

- laugher_role: who laughs, relative to the thing being laughed at.
    "producer"  - the laugher produced the laughable (their own act, admission, wording)
    "recipient" - the laugher is responding to something the other person did or said
    "either"    - both configurations occur naturally

- laughable_origin: whose event the laughter attaches to - "self", "partner",
  "external", or "either".

- trigger_event: what must just have happened for this reading to be live.

- intention: what the laugher is trying to do to the interaction.

- manages_face_of: whose comfort or standing the laughter is protecting -
  "self", "partner", "both", or "neither".

- precondition: what must be true of the situation for this reading to exist at all.
  This is the most important field. Be concrete about what the situation must supply -
  a cost, a clash, an awkwardness, a re-usable phrase. If the situation does not supply
  it, no laughter can carry this function however it sounds.

- needs_lexical_hook: "yes" if the reading requires something visible in the words
  themselves (a repair, a re-used expression, a mismatch between said and meant),
  "no" if it only requires the right situation.

- lexical_hook: what that hook is, or "" when needs_lexical_hook is "no".

- likely_next_move: what the OTHER speaker would naturally do in the following turn,
  once they have read the laughter this way. Be specific about the social action -
  this is what distinguishes functions downstream, so avoid generic answers.
"""

USER_TEMPLATE = """
[Function]
Name - {function}
Laughable type - {laughable_type}
Definition - {definition}
Example - {example}
Example explanation - {example_explanation}

Break this function into its structural parts.
"""

PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "laugher_role": {"type": "string", "enum": ["producer", "recipient", "either"]},
        "laughable_origin": {"type": "string",
                             "enum": ["self", "partner", "external", "either"]},
        "trigger_event": {"type": "string"},
        "intention": {"type": "string"},
        "manages_face_of": {"type": "string",
                            "enum": ["self", "partner", "both", "neither"]},
        "precondition": {"type": "string"},
        "needs_lexical_hook": {"type": "string", "enum": ["yes", "no"]},
        "lexical_hook": {"type": "string"},
        "likely_next_move": {"type": "string"},
    },
    "required": MODEL_FIELDS,
    "additionalProperties": False,
}

LENGTH_RETRY_NOTE = """

These fields were over the {cap}-word limit: {fields}. Rewrite them shorter, keeping
only the abstract requirement.
"""


def build_user_prompt(fn):
    return USER_TEMPLATE.format(**fn)


def call_model(client, fn, args, use_fallbacks=True, extra=""):
    body = {
        "output_config": {
            "effort": args.effort,
            "format": {"type": "json_schema", "schema": PROFILE_SCHEMA},
        }
    }
    kwargs = {
        "model": args.model,
        "max_tokens": args.max_tokens,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": build_user_prompt(fn) + extra}],
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
            return json.loads(text)
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


def draft_profile(client, fn, args):
    """Fill one function's profile, retrying once if fields run long."""
    prose = ["trigger_event", "intention", "precondition", "lexical_hook",
             "likely_next_move"]
    extra, result = "", None
    for _ in range(2):
        result = call_model(client, fn, args, extra=extra)
        over = [f for f in prose if len(result[f].split()) > args.max_words]
        if not over:
            return result
        extra = LENGTH_RETRY_NOTE.format(cap=args.max_words, fields=", ".join(over))
    return result


def load_existing(path):
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {row["function"]: row for row in csv.DictReader(f) if row.get("function")}


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
    parser.add_argument("--max-words", type=int, default=MAX_FIELD_WORDS)
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    functions = load_functions(args.csv)
    existing = {} if args.overwrite else load_existing(args.out)
    todo = [fn for fn in functions if fn["function"] not in existing]

    print(f"{len(functions)} function(s); {len(existing)} kept, {len(todo)} to draft")

    if args.dry_run:
        print(SYSTEM_PROMPT)
        print(build_user_prompt(functions[0]))
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY is empty - set it in .env (see .env.example)")

    client = anthropic.Anthropic(api_key=api_key)
    rows = [None] * len(functions)
    lock = threading.Lock()
    done = 0

    def work(index):
        fn = functions[index]
        if fn["function"] in existing:
            return index, existing[fn["function"]], True
        base = {"function": fn["function"], "laughable_type": fn["laughable_type"],
                "typical_arousal": arousal_for(fn["laughable_type"])}
        try:
            base.update(draft_profile(client, fn, args))
        except Exception as exc:
            base.update({f: "" for f in MODEL_FIELDS})
            base["precondition"] = f"ERROR {type(exc).__name__}: {exc}"
        return index, base, False

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(work, i) for i in range(len(functions))]
        for future in as_completed(futures):
            index, row, kept = future.result()
            with lock:
                rows[index] = row
                done += 1
                if not kept:
                    print(f"[{done}/{len(functions)}] {row['function']}")
                write_csv(args.out, rows)

    write_csv(args.out, rows)
    hooks = sum(1 for r in rows if r.get("needs_lexical_hook") == "yes")
    print(f"\nwrote {len(rows)} row(s) to {args.out}")
    print(f"  {hooks} function(s) need a hook in the wording")
    print(f"\nReview and edit {args.out} before generating transcripts.")


if __name__ == "__main__":
    main()
