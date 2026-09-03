"""Write the content and tone reference rubrics, one pair per item, with Claude.

The two prompts are the spec's sections 5 and 6, stored verbatim in prompts/ and filled only at
{{ITEM_JSON}}. Their hash goes into every record, so an annotation can always be traced to the
exact instruction that produced it.

What the writer is shown is deliberately narrower than the item on disk: `evalkit.writer_payload`
strips the generation metadata, and in particular the EmpatheticDialogues seed label. That label
describes how the scenario was sampled, not what a listener will hear, and a writer told the
seed was `proud` writes rubrics about pride whether the four turns support it or not.

Claude has no structured-output mode over either of its transports, so the reply is stored before
it is parsed, then parsed, then validated against the schema, and a failure is re-requested with
the validation errors quoted. A reply that never validates is kept with `status: invalid` rather
than being dropped — the spec's rule, and the only way the count of failures stays honest.

Three transports: `cli` bills the Claude subscription through the claude CLI, `api` bills
Anthropic credit, and `openai` exists so the stage can be exercised when neither Claude route is
available on the account. The spec's writer is Claude and the config says so; `openai` is a
stand-in, and every record names the model that actually wrote it.

These are reference annotations, not ground truth. `ambiguity_flag` and `item_level_review_note`
are the writer's own doubts, and human_review.md is where they get adjudicated.

    python v6/write_rubrics.py --dry-run --item-id v6_01a     # preview both payloads
    python v6/write_rubrics.py --item-id v6_01a               # the smoke test
    python v6/write_rubrics.py                                # all 20 items
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import evalkit as K
import text_models as T

KINDS = {"content": ("content_rubric_writer", "content_rubric"),
         "tone": ("tone_rubric_writer", "tone_rubric")}
ATTEMPTS = 3
SYSTEM = "You return valid JSON only. No markdown fences, no commentary before or after."


# Matched case-insensitively: the CLI says "Credit balance is too low" and the API says
# "credit balance is too low", and the two are the same problem.
AUTH_HINTS = ("failed to authenticate", "oauth", "credit balance", "authentication_error",
              "quota")


def preflight(model: str, transport: str) -> None:
    """One cheap call before the run, so a broken transport fails in a sentence.

    Without it an unreachable writer costs three attempts times three retries per item and
    surfaces as a traceback from deep inside the provider. The failure modes here are account
    state rather than code — an expired CLI login, an empty API balance — so the message says
    which one it is and what to do about it.
    """
    try:
        ask(model, transport, "Reply with the single word READY.", max_tokens=16)
    except K.DryRunViolation:
        raise
    except Exception as exc:                                  # noqa: BLE001 - reported plainly
        detail = str(exc)
        remedy = {
            "cli": "if the login expired, run `claude login` in an interactive terminal; if it "
                   "is the balance, the account needs credit or an active subscription",
            "api": "add Anthropic credit, or use --transport cli",
            "openai": "check OPENAI_API_KEY",
        }[transport]
        if any(hint in detail.lower() for hint in AUTH_HINTS):
            raise K.ConfigError(
                f"the {transport} transport cannot reach {model}: "
                f"{detail.splitlines()[0][:160]}\n  fix: {remedy}") from exc
        raise K.ConfigError(f"{transport} transport failed its preflight: "
                            f"{detail[:200]}") from exc


def ask_structured(model: str, template: str, payload: str, schema_name: str) -> dict:
    """The openai transport, which can constrain generation instead of validating afterwards."""
    K.guard(f"openai {model}")
    return T.retry(T.json_call, model, K.fill(template, ITEM_JSON=payload),
                   "Return the JSON for the item above.", K.strict(K.schema(schema_name)),
                   schema_name, "high", 20000)


def ask(model: str, transport: str, prompt: str, max_tokens: int = 8000) -> str:
    K.guard(f"{transport} {model}")
    if transport == "cli":
        return T.ask_claude(model, SYSTEM, prompt)
    if transport == "api":
        import anthropic

        client = anthropic.Anthropic(api_key=T.key("ANTHROPIC_API_KEY"))
        reply = client.messages.create(
            model=model, max_tokens=max_tokens, system=SYSTEM,
            messages=[{"role": "user", "content": prompt}])
        return "".join(block.text for block in reply.content
                       if getattr(block, "type", "") == "text").strip()
    raise K.ConfigError(f"unknown transport {transport!r}; expected cli, api or openai")


def write_one(item: dict, kind: str, model: str, transport: str, run: str) -> dict:
    template_name, schema_name = KINDS[kind]
    template, version = K.prompt(template_name)
    payload = json.dumps(K.writer_payload(item), indent=2, ensure_ascii=False)
    prompt = K.fill(template, ITEM_JSON=payload)

    provider = "openai" if transport == "openai" else "anthropic"
    errors: list[str] = []
    raw_path = ""
    for attempt in range(1, ATTEMPTS + 1):
        if transport == "openai":
            parsed = ask_structured(model, template, payload, schema_name)
            raw_path = K.save_raw("writer_raw", f"{item['item_id']}__{kind}_rubric",
                                  json.dumps(parsed, indent=2, ensure_ascii=False))
        else:
            text = T.retry(ask, model, transport, prompt)
            raw_path = K.save_raw(
                "writer_raw", f"{item['item_id']}__{kind}_rubric__attempt{attempt}", text)
            parsed = K.json_object(text)
        if parsed is None:
            errors = ["the reply contained no JSON object"]
        else:
            errors = K.schema_errors(schema_name, parsed)
            if not errors and parsed.get("item_id") != item["item_id"]:
                errors = [f"item_id is {parsed.get('item_id')!r}, expected "
                          f"{item['item_id']!r}"]
            if not errors:
                conditions = [r["condition"] for r in parsed["rubrics"]]
                if sorted(conditions) != sorted(K.CONDITIONS):
                    errors = [f"rubrics cover {conditions}, expected all three conditions"]
            if not errors:
                record = K.provenance(
                    run=run, item_id=item["item_id"], condition="all",
                    task_type=f"{kind}_rubric", prompt_version=version,
                    model_provider=provider, model_name=model,
                    settings={"transport": transport}, raw_path=raw_path,
                    parsed=parsed, status="ok", attempts=attempt)
                return record
        prompt = (K.fill(template, ITEM_JSON=payload)
                  + "\n\nYour previous answer was rejected:\n"
                  + "\n".join(f"- {line}" for line in errors[:8])
                  + "\nReturn corrected JSON only.")
    return K.provenance(run=run, item_id=item["item_id"], condition="all",
                        task_type=f"{kind}_rubric", prompt_version=version,
                        model_provider=provider, model_name=model,
                        settings={"transport": transport}, raw_path=raw_path,
                        parsed=None, status="invalid", errors=errors, attempts=ATTEMPTS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input")
    parser.add_argument("--output", help="directory; default is out/eval/rubrics")
    parser.add_argument("--config")
    parser.add_argument("--item-id", action="append")
    parser.add_argument("--kind", action="append", choices=list(KINDS))
    parser.add_argument("--writer-model")
    parser.add_argument("--transport", choices=["cli", "api", "openai"])
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

    writer = config["writers"].get("rubric", {})
    model = args.writer_model or writer.get("model")
    transport = args.transport or writer.get("transport", "cli")
    if not model:
        print("error: writers.rubric.model is not configured", file=sys.stderr)
        return 2
    if args.item_id:
        keep = set(args.item_id)
        items = [i for i in items if i["item_id"] in keep]
        if not items:
            print(f"error: no items match {args.item_id}", file=sys.stderr)
            return 2
    kinds = args.kind or list(KINDS)
    run = K.run_id(args.run_id)
    out_dir = Path(args.output) if args.output else K.stage_dir("rubrics")

    if args.dry_run:
        for item in items:
            for kind in kinds:
                template, version = K.prompt(KINDS[kind][0])
                prompt = K.fill(template, ITEM_JSON=json.dumps(
                    K.writer_payload(item), indent=2, ensure_ascii=False))
                print(f"\n{'=' * 78}\n{item['item_id']} · {kind} rubric · {version} · "
                      f"{model} over {transport} · {len(prompt)} chars")
                print(f"{'=' * 78}")
                print(prompt)
        K.report("write-rubrics", planned=len(items) * len(kinds), completed=0,
                 skipped=0, failed=0, invalid=0)
        print("dry run: nothing called, nothing written")
        return 0

    try:
        preflight(model, transport)
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    written: dict[str, list[dict]] = {kind: [] for kind in kinds}
    failed = 0
    for item in items:
        for kind in kinds:
            record = write_one(item, kind, model, transport, run)
            written[kind].append(record)
            flags = []
            if record["status"] == "ok":
                flags = [r["condition"] for r in record["parsed"]["rubrics"]
                         if r.get("ambiguity_flag")]
                note = record["parsed"].get("item_level_review_note", "")
            else:
                failed += 1
                note = "; ".join(record["errors"][:2])
            print(f"  {item['item_id']} · {kind:7} · {record['status']} · "
                  f"attempt {record['attempts']}"
                  + (f" · flagged {flags}" if flags else "")
                  + (f" · {note[:70]}" if note else ""), flush=True)

    for kind, records in written.items():
        if not records:
            continue
        path = out_dir / f"{kind}_rubrics.json"
        existing = {}
        if path.exists():
            if not args.overwrite:
                print(f"error: {path} exists; pass --overwrite", file=sys.stderr)
                return 2
            existing = {r["item_id"]: r for r in json.loads(path.read_text())["items"]}
        existing.update({r["item_id"]: r for r in records})
        K.write_json(path, {"written_at": K.now(), "run_id": run,
                            "writer": model, "transport": transport,
                            "prompt_version": records[0]["prompt_version"],
                            "items": [existing[k] for k in sorted(existing)]},
                     overwrite=True)
        print(f"wrote {path.relative_to(K.HERE.parent)} · {len(existing)} item(s)")

    K.report("write-rubrics", planned=len(items) * len(kinds),
             completed=len(items) * len(kinds) - failed, skipped=0, failed=failed,
             invalid=failed)
    if T.cli_spend():
        print(f"  claude CLI spend: ${T.cli_spend():.3f}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
