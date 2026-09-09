"""Check whether each item's two conditions call for different replies. Before the freeze.

Both vocalizations can be individually plausible and the pair still be useless for ranking. If a
natural reply appropriate for the laugh version is also fully appropriate for the sigh version,
then a judge asked which reply suits which version is choosing between two equally good answers,
and the ranking score measures the coin-flip rather than the model's understanding.

That cannot be seen from either condition alone, which is why this runs after the
interpretations exist: it compares what each version asks a *reply* to do. Two readings can
differ in what the speaker feels while calling for the same thing from the other person, and
that is the case that fails.

A failure means the item is regenerated from a **new seed** — not the same one. The situation
itself is what failed to separate the two sounds, so rewriting the same situation would produce
the same overlap. `which_side_is_weaker` names the condition the transcript supports least,
which is the side worth changing.

    python v6/check_separability.py --dry-run
    python v6/check_separability.py
    python v6/check_separability.py --only v6_02b
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import evalkit as K
import text_models as T

OUT = K.stage_dir("rubrics") / "pair_separability.json"
SYSTEM = "You return valid JSON only. No markdown fences, no commentary."
ATTEMPTS = 2


def payload(item: dict, interps: dict) -> str:
    body = {"item_id": item["item_id"], "scenario": item["scenario"],
            "shared_turns_1_to_4": [
                {"turn": t["turn"], "speaker": t["speaker"], "text": t["text"]}
                for t in item["baseline"]["turns"] if t["turn"] != item["vocalization_turn"]],
            "replying_speaker": "B" if item["vocalization_speaker"] == "A" else "A"}
    for cond in ("condition_a", "condition_b"):
        source = interps.get(f"{item['item_id']}__{cond}")
        final = next(t for t in item[cond]["turns"] if t["turn"] == item["vocalization_turn"])
        body[cond] = {
            "vocalization": item[cond]["vocalization"],
            "final_turn": f"{final['speaker']}: {final['text']}",
            "acceptable_interpretations": (source or {}).get("acceptable_interpretations", []),
            "shared_implication": (source or {}).get("shared_implication", ""),
        }
    return json.dumps(body, indent=2, ensure_ascii=False)


def check(item: dict, interps: dict, args, run: str) -> dict:
    template, version = K.prompt("pair_separability_check")
    prompt = K.fill(template, ITEM=payload(item, interps))
    errors: list[str] = []
    raw = ""
    for attempt in range(1, ATTEMPTS + 1):
        K.guard(f"{args.transport} {args.model}")
        if args.transport == "cli":
            raw = T.ask_claude(args.model, SYSTEM, prompt)
        else:
            import anthropic
            reply = anthropic.Anthropic(api_key=T.key("ANTHROPIC_API_KEY")).messages.create(
                model=args.model, max_tokens=700, system=SYSTEM,
                messages=[{"role": "user", "content": prompt}])
            raw = "".join(b.text for b in reply.content
                          if getattr(b, "type", "") == "text").strip()
        parsed = K.json_object(raw)
        if parsed is None:
            errors = ["the reply contained no JSON object"]
        else:
            errors = K.schema_errors("pair_separability", parsed)
            if not errors:
                record = K.provenance(
                    run=run, item_id=item["item_id"], condition="pair",
                    task_type="pair_separability", prompt_version=version,
                    model_provider="anthropic", model_name=args.model,
                    settings={"transport": args.transport}, parsed=parsed, status="ok",
                    raw_path=K.save_raw("writer_raw",
                                        f"{item['item_id']}__pair_separability", raw),
                    attempts=attempt)
                record.update({"voc_a": item["voc_a"], "voc_b": item["voc_b"]})
                return record
        prompt = (K.fill(template, ITEM=payload(item, interps))
                  + "\n\nYour previous answer was rejected:\n"
                  + "\n".join(f"- {e}" for e in errors[:5]) + "\nReturn corrected JSON only.")
    # An unparseable verdict is not a pass: an item that may fail must not reach the freeze
    # marked separable.
    return K.provenance(run=run, item_id=item["item_id"], condition="pair",
                        task_type="pair_separability", prompt_version=version,
                        model_provider="anthropic", model_name=args.model,
                        settings={"transport": args.transport}, parsed=None,
                        status="invalid", errors=errors, attempts=ATTEMPTS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append")
    parser.add_argument("--model")
    parser.add_argument("--transport", choices=["cli", "api"])
    parser.add_argument("--redo", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    K.set_dry_run(args.dry_run)

    try:
        config = K.load_config()
        _source, items = K.load_items(config)
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    verifier = config["writers"].get("verifier", {})
    args.model = args.model or verifier.get("model", "claude-opus-5")
    args.transport = args.transport or verifier.get("transport", "cli")

    path = K.stage_dir("rubrics") / "interpretations.json"
    if not path.exists():
        print(f"error: no interpretations at {path}; run write_annotations.py first",
              file=sys.stderr)
        return 2
    interps = {f"{r['item_id']}__{r['condition']}": r["parsed"]
               for r in json.loads(path.read_text())["items"] if r["status"] == "ok"}

    existing = ({r["item_id"]: r for r in json.loads(OUT.read_text())["items"]}
                if OUT.exists() else {})
    if args.only:
        items = [i for i in items if i["item_id"] in set(args.only)]
    elif not args.redo:
        items = [i for i in items if i["item_id"] not in existing]
    if not items:
        print("nothing to check; pass --redo to recheck")
        return 0

    if args.dry_run:
        template, version = K.prompt("pair_separability_check")
        print(f"{'=' * 78}\n{items[0]['item_id']} · {version} · {args.model}\n{'=' * 78}")
        print(K.fill(template, ITEM=payload(items[0], interps)))
        K.report("separability", planned=len(items), completed=0, skipped=0, failed=0,
                 invalid=0)
        print("dry run: nothing called, nothing written")
        return 0

    run = K.run_id(args.run_id)
    bad, invalid = [], 0
    for item in items:
        record = check(item, interps, args, run)
        existing[item["item_id"]] = record
        if record["status"] != "ok":
            invalid += 1
            print(f"  {item['item_id']} · invalid · {record['errors'][:1]}"[:130], flush=True)
            continue
        p = record["parsed"]
        if not p["separable"]:
            bad.append(item["item_id"])
        print(f"  {item['item_id']} · {item['voc_a']}/{item['voc_b']} · "
              f"{'separable' if p['separable'] else 'NOT SEPARABLE'}"
              + (f" · weaker side {p['which_side_is_weaker']}" if not p["separable"] else "")
              + f" · {p['overlap'][:60]}", flush=True)
        K.write_json(OUT, {"checked_at": K.now(), "verifier": args.model,
                           "prompt_version": record["prompt_version"],
                           "not_separable": sorted(
                               i for i, r in existing.items()
                               if r["status"] == "ok" and not r["parsed"]["separable"]),
                           "items": [existing[k] for k in sorted(existing)]},
                     overwrite=True)

    K.report("separability", planned=len(items), completed=len(items) - invalid,
             skipped=0, failed=0, invalid=invalid)
    if bad:
        print(f"\n  {len(bad)} item(s) cannot support ranking: {sorted(bad)}")
        print("  regenerate each from a NEW seed — the situation is what failed to separate "
              "the sounds, so the same one would overlap again:")
        print("    python3 v6/sample_items.py --reseed "
              + " --reseed ".join(sorted(bad)))
        print("    python3 v6/plan_occasions.py "
              + " ".join(f"--only {i}" for i in sorted(bad)) + " --redo")
        print("    python3 v6/write_transcripts.py "
              + " ".join(f"--only {i}" for i in sorted(bad)) + " --redo")
        print("    python3 v6/write_annotations.py "
              + " ".join(f"--item-id {i}" for i in sorted(bad)) + " --redo")
        print("    python3 v6/check_separability.py "
              + " ".join(f"--only {i}" for i in sorted(bad)) + " --redo")
    print(f"wrote {OUT.relative_to(K.HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
