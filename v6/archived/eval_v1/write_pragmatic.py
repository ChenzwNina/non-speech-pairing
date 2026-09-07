"""Write the pragmatic multiple-choice options: one correct reading, three matched distractors.

Section 4.2's requirement is that the distractors be close. Three unrelated emotions make the
question answerable without hearing anything, so the writer is given a structure instead: the
first distractor is the reading intended for this item's *other* vocalization condition, the
second keeps the valence and moves the pragmatic function, and the third is plausible for the
situation but unsupported by this version of it. A model that has heard the sound has to
separate readings that are all defensible on the transcript alone.

All three conditions are written in one call, because the first distractor for `condition_a` is
the correct answer for `condition_b`. Writing them separately would let the two drift into
paraphrases of each other.

A different family writes these from the one that writes the rubrics: a distractor by the same
model as the correct answer tends to differ in style rather than in substance, and style is what
an evaluated model would learn to spot. Structured output enforces the schema at the request, so
a malformed answer is a validation error rather than something that flows downstream.

Option order and correct-answer position are not decided here — build_tasks.py assigns and
freezes them once these exist.

    python v6/write_pragmatic.py --dry-run --item-id v6_01a
    python v6/write_pragmatic.py --item-id v6_01a
    python v6/write_pragmatic.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import evalkit as K
import text_models as T

SCHEMA = "pragmatic_options"
MAX_TOKENS = 20000


def write_one(item: dict, model: str, effort: str, run: str) -> dict:
    template, version = K.prompt("pragmatic_writer")
    payload = json.dumps(K.writer_payload(item), indent=2, ensure_ascii=False)
    system = K.fill(template, ITEM_JSON=payload)
    K.guard(f"openai {model}")
    try:
        parsed = T.retry(T.json_call, model, system, "Return the JSON for the item above.",
                         K.strict(K.schema(SCHEMA)), "pragmatic_options", effort, MAX_TOKENS)
    except Exception as exc:                                  # noqa: BLE001 - recorded, not hidden
        return K.provenance(run=run, item_id=item["item_id"], condition="all",
                            task_type="pragmatic_options", prompt_version=version,
                            model_provider="openai", model_name=model,
                            settings={"effort": effort}, parsed=None, status="error",
                            errors=[f"{type(exc).__name__}: {exc}"[:300]])
    raw_path = K.save_raw("writer_raw", f"{item['item_id']}__pragmatic_options",
                          json.dumps(parsed, indent=2, ensure_ascii=False))
    errors = K.schema_errors(SCHEMA, parsed)
    if parsed.get("item_id") != item["item_id"]:
        errors.append(f"item_id is {parsed.get('item_id')!r}, expected {item['item_id']!r}")
    covered = sorted(block["condition"] for block in parsed.get("conditions", []))
    if covered != sorted(K.CONDITIONS):
        errors.append(f"conditions cover {covered}, expected all three")
    for block in parsed.get("conditions", []):
        kinds = [d["kind"] for d in block["distractors"]]
        if sorted(kinds) != sorted(["paired_condition", "wrong_function",
                                    "scenario_plausible"]):
            errors.append(f"{block['condition']} distractor kinds are {kinds}")
        texts = [block["correct"]] + [d["text"] for d in block["distractors"]]
        if len({t.strip().lower() for t in texts}) != 4:
            errors.append(f"{block['condition']} repeats an option")
    return K.provenance(run=run, item_id=item["item_id"], condition="all",
                        task_type="pragmatic_options", prompt_version=version,
                        model_provider="openai", model_name=model,
                        settings={"effort": effort}, raw_path=raw_path, parsed=parsed,
                        status="ok" if not errors else "invalid", errors=errors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input")
    parser.add_argument("--output", help="directory; default is out/eval/rubrics")
    parser.add_argument("--config")
    parser.add_argument("--item-id", action="append")
    parser.add_argument("--writer-model")
    parser.add_argument("--effort")
    parser.add_argument("--run-id")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the payloads that would be sent and call nothing")
    args = parser.parse_args()
    K.set_dry_run(args.dry_run)

    try:
        config = K.load_config(Path(args.config) if args.config else None)
        if args.input:
            config["dataset"]["transcripts"] = args.input
        _source, items = K.load_items(config)
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    writer = config["writers"].get("pragmatic", {})
    model = args.writer_model or writer.get("model")
    effort = args.effort or writer.get("effort", "high")
    if not model:
        print("error: writers.pragmatic.model is not configured", file=sys.stderr)
        return 2
    if args.item_id:
        keep = set(args.item_id)
        items = [i for i in items if i["item_id"] in keep]
        if not items:
            print(f"error: no items match {args.item_id}", file=sys.stderr)
            return 2
    run = K.run_id(args.run_id)
    out_dir = Path(args.output) if args.output else K.stage_dir("rubrics")

    if args.dry_run:
        template, version = K.prompt("pragmatic_writer")
        for item in items:
            prompt = K.fill(template, ITEM_JSON=json.dumps(
                K.writer_payload(item), indent=2, ensure_ascii=False))
            print(f"\n{'=' * 78}\n{item['item_id']} · pragmatic options · {version} · "
                  f"{model} at effort {effort} · {len(prompt)} chars\n{'=' * 78}")
            print(prompt)
        K.report("write-pragmatic", planned=len(items), completed=0, skipped=0,
                 failed=0, invalid=0)
        print("dry run: nothing called, nothing written")
        return 0

    records, failed = [], 0
    for item in items:
        record = write_one(item, model, effort, run)
        records.append(record)
        if record["status"] != "ok":
            failed += 1
            print(f"  {item['item_id']} · {record['status']} · "
                  f"{'; '.join(record['errors'][:2])[:110]}", flush=True)
            continue
        flagged = [b["condition"] for b in record["parsed"]["conditions"]
                   if b.get("ambiguity_flag")]
        note = record["parsed"].get("item_level_review_note", "")
        print(f"  {item['item_id']} · ok"
              + (f" · flagged {flagged}" if flagged else "")
              + (f" · {note[:70]}" if note else ""), flush=True)

    path = out_dir / "pragmatic_options.json"
    existing = {}
    if path.exists():
        if not args.overwrite:
            print(f"error: {path} exists; pass --overwrite", file=sys.stderr)
            return 2
        existing = {r["item_id"]: r for r in json.loads(path.read_text())["items"]}
    existing.update({r["item_id"]: r for r in records})
    K.write_json(path, {"written_at": K.now(), "run_id": run, "writer": model,
                        "effort": effort,
                        "prompt_version": records[0]["prompt_version"],
                        "items": [existing[k] for k in sorted(existing)]}, overwrite=True)
    print(f"wrote {path.relative_to(K.HERE.parent)} · {len(existing)} item(s)")
    K.report("write-pragmatic", planned=len(items), completed=len(items) - failed,
             skipped=0, failed=failed, invalid=failed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
