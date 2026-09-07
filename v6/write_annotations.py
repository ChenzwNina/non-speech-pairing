"""Write the reference annotations each evaluation task is scored against, with Claude.

Three kinds, one call per (item, condition, kind). The baseline gets none of them: with no
vocalization there is nothing to interpret, nothing a reply has to be appropriate *to*, and no
tone that is wrong. Its only jobs are to be a perception false-positive test and to supply an
opponent for the paired comparison.

    interpretations   the three defensible readings of this vocalization here. A model under
                      test answers in its own words and passes if it matches any of them, so
                      this set is the boundary of understanding rather than one right answer.

    response_guides   what the other speaker's reply should accomplish, written once per
                      interpretation. A model is scored against the guide for the reading it
                      actually held — a defensible minority reading is judged on whether the
                      reply follows from it, not against the majority reading.

    tone_exclusions   the tones that would clearly be wrong. Negative on purpose: several
                      deliveries are fine here and a prescribed profile would mark good replies
                      wrong, but some are unmistakably out of step and those can be listed.

`response_guides` depends on `interpretations`, so it refuses to run before them and the default
order respects that.

Claude has no structured-output mode over its own transports, so a reply is stored before it is
parsed, then validated, then re-requested with the errors quoted. A reply that never validates
is kept with `status: invalid` rather than dropped.

    python v6/write_annotations.py --dry-run --item-id v6_01a
    python v6/write_annotations.py --kind interpretations
    python v6/write_annotations.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import evalkit as K
import text_models as T

# kind -> (prompt template, schema, needs interpretations first)
KINDS = {
    "interpretations": ("interpretation_writer", "interpretations", False),
    "response_guides": ("response_guide_writer", "response_guides", True),
    "tone_exclusions": ("tone_exclusion_writer", "tone_exclusions", False),
}
ORDER = ("interpretations", "response_guides", "tone_exclusions")
ATTEMPTS = 3
SYSTEM = "You return valid JSON only. No markdown fences, no commentary before or after."
AUTH_HINTS = ("failed to authenticate", "oauth", "credit balance", "authentication_error",
              "quota")


def responder(item: dict) -> str:
    """The speaker who replies: the one who did not make the sound."""
    return "B" if item["vocalization_speaker"] == "A" else "A"


def payload_for(kind: str, item: dict, condition: str, interpretations: dict | None) -> dict:
    block = item[condition]
    body = {
        "item_id": item["item_id"], "condition": condition,
        "vocalization": block["vocalization"],
        "tag": item["tag_a"] if condition == "condition_a" else item["tag_b"],
        "vocalization_turn": item["vocalization_turn"],
        "vocalization_speaker": item["vocalization_speaker"],
        "turns": block["turns"],
    }
    if kind in ("response_guides", "tone_exclusions"):
        body["responder"] = responder(item)
    if kind == "response_guides":
        body["acceptable_interpretations"] = interpretations["acceptable_interpretations"]
        body["shared_implication"] = interpretations["shared_implication"]
    return body


def ask(model: str, transport: str, prompt: str, max_tokens: int = 8000) -> str:
    K.guard(f"{transport} {model}")
    if transport == "cli":
        return T.ask_claude(model, SYSTEM, prompt)
    if transport == "api":
        import anthropic

        client = anthropic.Anthropic(api_key=T.key("ANTHROPIC_API_KEY"))
        reply = client.messages.create(model=model, max_tokens=max_tokens, system=SYSTEM,
                                       messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in reply.content
                       if getattr(b, "type", "") == "text").strip()
    if transport == "openai":
        raise K.ConfigError("the openai transport is not available for annotations; these are "
                            "Claude's per the design")
    raise K.ConfigError(f"unknown transport {transport!r}")


def preflight(model: str, transport: str) -> None:
    """One cheap call, so a dead account costs a sentence instead of a stack trace."""
    try:
        ask(model, transport, "Reply with the single word READY.", max_tokens=16)
    except K.DryRunViolation:
        raise
    except Exception as exc:                                  # noqa: BLE001 - reported plainly
        detail = str(exc)
        remedy = ("if the login expired, run `claude login` in an interactive terminal; if it "
                  "is the balance, the account needs credit or an active subscription"
                  if transport == "cli" else "add Anthropic credit, or use --transport cli")
        if any(h in detail.lower() for h in AUTH_HINTS):
            raise K.ConfigError(f"the {transport} transport cannot reach {model}: "
                                f"{detail.splitlines()[0][:160]}\n  fix: {remedy}") from exc
        raise K.ConfigError(f"{transport} preflight failed: {detail[:200]}") from exc


def write_one(item: dict, condition: str, kind: str, model: str, transport: str, run: str,
              interpretations: dict | None) -> dict:
    template_name, schema_name, _ = KINDS[kind]
    template, version = K.prompt(template_name)
    body = json.dumps(payload_for(kind, item, condition, interpretations), indent=2,
                      ensure_ascii=False)
    prompt = K.fill(template, INPUT=body)
    errors: list[str] = []
    raw_path = ""

    for attempt in range(1, ATTEMPTS + 1):
        text = T.retry(ask, model, transport, prompt)
        raw_path = K.save_raw("writer_raw",
                              f"{item['item_id']}__{condition}__{kind}__attempt{attempt}", text)
        parsed = K.json_object(text)
        if parsed is None:
            errors = ["the reply contained no JSON object"]
        else:
            errors = K.schema_errors(schema_name, parsed)
            if not errors and parsed.get("item_id") != item["item_id"]:
                errors = [f"item_id is {parsed.get('item_id')!r}"]
            if not errors and parsed.get("condition") != condition:
                errors = [f"condition is {parsed.get('condition')!r}, expected {condition!r}"]
            if not errors and parsed.get("vocalization") != item[condition]["vocalization"]:
                errors = [f"vocalization is {parsed.get('vocalization')!r}, expected "
                          f"{item[condition]['vocalization']!r}"]
            if not errors and kind == "response_guides":
                if parsed.get("responder") != responder(item):
                    errors = [f"responder is {parsed.get('responder')!r}, expected "
                              f"{responder(item)!r} — the speaker who did not make the sound"]
                elif [g["interpretation_index"] for g in parsed["guides"]] != [1, 2, 3]:
                    errors = ["guides must be indexed 1, 2, 3 in order"]
            if not errors:
                return K.provenance(
                    run=run, item_id=item["item_id"], condition=condition, task_type=kind,
                    prompt_version=version, model_provider="anthropic", model_name=model,
                    settings={"transport": transport}, raw_path=raw_path, parsed=parsed,
                    status="ok", attempts=attempt)
        prompt = (K.fill(template, INPUT=body) + "\n\nYour previous answer was rejected:\n"
                  + "\n".join(f"- {line}" for line in errors[:8])
                  + "\nReturn corrected JSON only.")
    return K.provenance(run=run, item_id=item["item_id"], condition=condition, task_type=kind,
                        prompt_version=version, model_provider="anthropic", model_name=model,
                        settings={"transport": transport}, raw_path=raw_path, parsed=None,
                        status="invalid", errors=errors, attempts=ATTEMPTS)


def load_existing(kind: str, out_dir: Path) -> dict:
    path = out_dir / f"{kind}.json"
    if not path.exists():
        return {}
    return {f"{r['item_id']}__{r['condition']}": r
            for r in json.loads(path.read_text())["items"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    parser.add_argument("--output", help="directory; default is out/eval/rubrics")
    parser.add_argument("--item-id", action="append")
    parser.add_argument("--condition", action="append", choices=list(K.CONDITIONS))
    parser.add_argument("--kind", action="append", choices=list(KINDS))
    parser.add_argument("--writer-model")
    parser.add_argument("--transport", choices=["cli", "api"])
    parser.add_argument("--run-id")
    parser.add_argument("--redo", action="store_true",
                        help="rewrite annotations already on disk")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    K.set_dry_run(args.dry_run)

    try:
        config = K.load_config(Path(args.config) if args.config else None)
        _source, items = K.load_items(config)
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    writer = config["writers"].get("rubric", {})
    model = args.writer_model or writer.get("model")
    transport = args.transport or writer.get("transport", "cli")
    if not model:
        print("error: writers.rubric.model is not configured", file=sys.stderr)
        return 2
    if args.item_id:
        items = [i for i in items if i["item_id"] in set(args.item_id)]
    if not items:
        print(f"error: no items match {args.item_id}", file=sys.stderr)
        return 2
    conditions = tuple(args.condition) if args.condition else K.response_conditions(config)
    kinds = [k for k in ORDER if k in (args.kind or ORDER)]
    out_dir = Path(args.output) if args.output else K.stage_dir("rubrics")
    on_disk = {kind: load_existing(kind, out_dir) for kind in KINDS}

    plan = [(item, condition, kind) for kind in kinds for item in items
            for condition in conditions
            if args.redo or f"{item['item_id']}__{condition}" not in on_disk[kind]]

    if args.dry_run:
        for item, condition, kind in plan[:2]:
            interp = on_disk["interpretations"].get(f"{item['item_id']}__{condition}")
            body = payload_for(kind, item, condition,
                               (interp or {}).get("parsed") if interp else None)
            template, version = K.prompt(KINDS[kind][0])
            print(f"\n{'=' * 78}\n{item['item_id']} · {condition} · {kind} · {version} · "
                  f"{model} over {transport}\n{'=' * 78}")
            print(K.fill(template, INPUT=json.dumps(body, indent=2, ensure_ascii=False)))
        K.report("write-annotations", planned=len(plan), completed=0, skipped=0, failed=0,
                 invalid=0)
        print(f"\nkinds {kinds} · {len(items)} item(s) x {len(conditions)} condition(s)")
        print("dry run: nothing called, nothing written")
        return 0

    if not plan:
        print("nothing to write; pass --redo to rewrite")
        return 0
    try:
        preflight(model, transport)
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    failed = 0
    for item, condition, kind in plan:
        key = f"{item['item_id']}__{condition}"
        interp = None
        if KINDS[kind][2]:
            source = on_disk["interpretations"].get(key)
            if not source or source["status"] != "ok":
                print(f"  {key} · {kind} · skipped, no valid interpretations yet")
                continue
            interp = source["parsed"]
        record = write_one(item, condition, kind, model, transport, K.run_id(args.run_id),
                           interp)
        on_disk[kind][key] = record
        if record["status"] != "ok":
            failed += 1
            print(f"  {key} · {kind} · {record['status']} · "
                  f"{'; '.join(record['errors'][:2])[:100]}", flush=True)
        else:
            print(f"  {key} · {kind} · ok · attempt {record['attempts']}", flush=True)
        K.write_json(out_dir / f"{kind}.json",
                     {"written_at": K.now(), "writer": model, "transport": transport,
                      "prompt_version": record["prompt_version"],
                      "transcripts": config["dataset"]["transcripts"],
                      "items": [on_disk[kind][k] for k in sorted(on_disk[kind])]},
                     overwrite=True)

    K.report("write-annotations", planned=len(plan), completed=len(plan) - failed, skipped=0,
             failed=failed, invalid=failed)
    if T.cli_spend():
        print(f"  claude CLI spend: ${T.cli_spend():.3f}")
    for kind in kinds:
        print(f"  {kind}: {len(on_disk[kind])} on disk")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
