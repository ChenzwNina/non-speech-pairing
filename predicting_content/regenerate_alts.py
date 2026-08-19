"""Rewrite the single opposite-stance alternative; keep gold frozen.

Usage:
    python predicting_content/regenerate_alts.py
    python predicting_content/regenerate_alts.py --limit 1
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from generate import (
    DEFAULT_OUT,
    EFFORT,
    HERE,
    MODEL,
    VOCALIZATIONS,
    lexical_of,
    load_dotenv,
    render_markdown,
)

load_dotenv(HERE.parent / ".env")

SPEC_BY_ID = {spec["id"]: spec for spec in VOCALIZATIONS}

ALT_SCHEMA = {
    "type": "object",
    "properties": {
        "alternatives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "content_type": {"type": "string"},
                    "text": {"type": "string"},
                    "why_mismatch": {"type": "string"},
                },
                "required": ["content_type", "text", "why_mismatch"],
                "additionalProperties": False,
            },
        },
        "quality_check": {
            "type": "object",
            "properties": {
                "opposite_stance": {"type": "boolean"},
                "same_situation": {"type": "boolean"},
                "not_a_paraphrase": {"type": "boolean"},
            },
            "required": ["opposite_stance", "same_situation", "not_a_paraphrase"],
            "additionalProperties": False,
        },
    },
    "required": ["alternatives", "quality_check"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """
You rewrite ONLY the alternative Turn 3 completion for a frozen benchmark
item. Do not change Turns 1–2 or the gold Turn 3.

Write exactly ONE alternative. It must be the opposite stance of gold.

Examples of opposite:
- unwilling / reluctant accept → glad, willing accept
- protest / rejection → eager yes
- joke / tease → earnest, unironic
- tentative / uncertain → firm decision
- engaged follow-up → shut the topic down
- criticism / disbelief → sincere endorsement
- sensitive correction → nothing is wrong
- relieved "we're done" → still unresolved
- postpone / stop → keep going now
- distressed bid for comfort → confident, I have this

RULES

- Keep the exact formula prefix.
- Copy opposite content_type exactly.
- Stay in the same situation as gold; flip the attitude or reasoning.
- Do not joke, ask a follow-up, or paraphrase gold.
- The line must still make sense after Turns 1–2.
- Do not name the vocalization in the spoken words.

Return JSON only. alternatives has length 1.
""".strip()


def validate_alts(item: dict, spec: dict, alts: list[dict]) -> list[str]:
    problems = []
    formula = spec["formula"]
    gold_lex = item["gold"]["lexical"]
    required = spec["opposite_type"].strip().lower()
    if len(alts) != 1:
        return [f"need 1 alternative, got {len(alts)}"]
    alt = alts[0]
    text = (alt.get("text") or "").strip()
    lex = lexical_of(text, formula)
    ctype = (alt.get("content_type") or "").strip().lower()
    if not text.startswith(formula):
        problems.append(f"alternative must start with {formula!r}")
    if not lex:
        problems.append("alternative has empty lexical content")
    if lex.lower() == gold_lex.lower():
        problems.append("alternative duplicates gold")
    if ctype != required:
        problems.append(f"content_type must be {spec['opposite_type']!r}")
    return problems


def user_prompt(item: dict, spec: dict) -> str:
    t1, t2, t3 = item["transcript"]
    return "\n".join(
        [
            f"item_id: {item['item_id']}",
            f"domain: {item['domain']}",
            f"formula: {spec['formula']}",
            f"gold content_type: {item['content_type']}",
            f"opposite content_type (copy exactly): {spec['opposite_type']}",
            spec["opposite_hint"],
            "",
            "FROZEN SCRIPT",
            f"A: {t1['text']}",
            f"B: {t2['text']}",
            f"A gold: {t3['text']}",
            "",
            "Write one opposite-stance alternative.",
            "alternatives[0].text is formula + new sentence.",
        ]
    )


def call_model(client: OpenAI, prompt: str, model: str, effort: str) -> tuple[dict, dict]:
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = client.responses.create(
                model=model,
                instructions=SYSTEM_PROMPT,
                input=prompt,
                reasoning={"effort": effort},
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "predicting_content_alts",
                        "schema": ALT_SCHEMA,
                        "strict": True,
                    }
                },
                max_output_tokens=1500,
            )
            if response.status != "completed":
                raise RuntimeError(
                    f"status={response.status} details={getattr(response, 'incomplete_details', None)}"
                )
            payload = json.loads(response.output_text)
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            return payload, usage
        except Exception as exc:
            last_error = exc
            if attempt == 3:
                break
            wait = 2 ** attempt
            print(f"    retry in {wait}s: {exc}")
            time.sleep(wait)
    raise last_error  # type: ignore[misc]


def rewrite_one(client: OpenAI, item: dict, spec: dict, args: argparse.Namespace) -> list[dict]:
    prompt = user_prompt(item, spec)
    last_problems: list[str] = []
    for attempt in range(1, 4):
        payload, _usage = call_model(client, prompt, args.model, args.effort)
        alts = payload.get("alternatives") or []
        problems = validate_alts(item, spec, alts)
        qc = payload.get("quality_check") or {}
        for key, value in qc.items():
            if value is not True:
                problems.append(f"quality_check.{key} is not true")
        if not problems:
            return alts
        last_problems = problems
        prompt = (
            user_prompt(item, spec)
            + "\n\nThe previous JSON failed these checks:\n- "
            + "\n- ".join(problems)
            + "\nReturn a corrected alternatives object."
        )
        print(f"    check failed ({problems[0]}); regenerating {attempt}/2")
    raise RuntimeError("still invalid after retries: " + "; ".join(last_problems))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="src", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--effort", default=EFFORT)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")

    data = json.loads(args.src.read_text())
    items = [row for row in data["results"] if "gold" in row]
    if args.limit:
        items = items[: args.limit]

    client = OpenAI(api_key=key)
    print(f"rewrite 1 opposite alternative  n={len(items)}  model={args.model}")
    by_id = {row["item_id"]: row for row in data["results"]}

    for index, item in enumerate(items, start=1):
        spec = SPEC_BY_ID[item["vocalization_id"]]
        print(f"[{index}/{len(items)}] {item['item_id']}")
        try:
            alts = rewrite_one(client, item, spec, args)
            item = dict(item)
            item["alternatives"] = alts
            item["alts_rewritten_at"] = datetime.now(timezone.utc).isoformat()
            by_id[item["item_id"]] = item
            print(f"    gold: {item['gold']['text']}")
            print(f"    alt:  {alts[0]['text']}")
        except Exception as exc:
            print(f"    failed: {exc}")
            item = dict(item)
            item["alts_error"] = f"{type(exc).__name__}: {exc}"
            by_id[item["item_id"]] = item

    data["results"] = [by_id[row["item_id"]] for row in data["results"]]
    data["alts_rewritten_at"] = datetime.now(timezone.utc).isoformat()
    data["alts_model"] = args.model
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    ok = [row for row in data["results"] if "gold" in row]
    args.out.with_suffix(".md").write_text(render_markdown(ok, args.model), encoding="utf-8")
    failures = sum(1 for row in data["results"] if row.get("alts_error"))
    print(f"\nwrote {args.out}" + (f" ({failures} failed)" if failures else ""))


if __name__ == "__main__":
    main()
