"""Write the content and tone reference rubrics, one per condition, with Claude.

**One call per (item, condition, kind), and the writer sees one version only.** An earlier
design handed it all three versions at once and asked for three rubrics together. That
guaranteed contrast and thereby destroyed it as evidence: a writer that knows it is looking at
a laugh *and* a sigh can always phrase two requirements that differ, whether or not the
conversation supports the difference. Shown one version alone, it has to read that conversation
on its own terms — which is the thing the benchmark is actually claiming can be done. Whether
the two rubrics then differ becomes a measurement about the item rather than a constraint
imposed by the prompt, and the cross-condition fields (`contrastive_requirement`,
`contrastive_cue`) are gone because nothing can honestly fill them any more.

The baseline gets no rubric. Content and tone are only scored on the two vocalization
conditions: with no vocalization there is nothing for a response to be appropriate *to*, so
nearly any sensible reply fits and the score measures fluency. The baseline keeps its place in
perception, where it is the false-positive test.

The prompts are in prompts/ and filled only at {{ITEM_JSON}}. Their hash goes into every
record, so an annotation can always be traced to the exact instruction that produced it.

What the writer is shown is `evalkit.condition_payload`: this condition's turns with its tag in
place, its vocalization and intended emotion, and nothing else. No other version, no other tag,
and not the EmpatheticDialogues seed label — that describes how the scenario was sampled rather
than what a listener will hear, and a writer told the seed was `proud` writes rubrics about
pride whether the four turns support it or not.

Claude has no structured-output mode over either of its transports, so the reply is stored before
it is parsed, then parsed, then validated against the schema, and a failure is re-requested with
the validation errors quoted. A reply that never validates is kept with `status: invalid` rather
than being dropped — the spec's rule, and the only way the count of failures stays honest.

Three transports: `cli` bills the Claude subscription through the claude CLI, `api` bills
Anthropic credit, and `openai` exists so the stage can be exercised when neither Claude route is
available on the account. The spec's writer is Claude and the config says so; `openai` is a
stand-in, and every record names the model that actually wrote it.

These are reference annotations, not ground truth. `ambiguity_flag` and `review_note` are the
writer's own doubts about the condition in front of it, and human review is where they get
adjudicated.

    python v6/write_rubrics.py --dry-run --item-id v6_01a     # preview every payload
    python v6/write_rubrics.py --item-id v6_01a               # 4 calls: 2 conditions x 2 kinds
    python v6/write_rubrics.py                                # 80 calls
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


def write_one(item: dict, condition: str, kind: str, model: str, transport: str,
              run: str) -> dict:
    template_name, schema_name = KINDS[kind]
    template, version = K.prompt(template_name)
    payload = json.dumps(K.condition_payload(item, condition), indent=2, ensure_ascii=False)
    prompt = K.fill(template, ITEM_JSON=payload)

    provider = "openai" if transport == "openai" else "anthropic"
    errors: list[str] = []
    raw_path = ""
    for attempt in range(1, ATTEMPTS + 1):
        if transport == "openai":
            parsed = ask_structured(model, template, payload, schema_name)
            raw_path = K.save_raw(
                "writer_raw", f"{item['item_id']}__{condition}__{kind}_rubric",
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
            if not errors and parsed.get("condition") != condition:
                errors = [f"condition is {parsed.get('condition')!r}, expected "
                          f"{condition!r}"]
            if not errors:
                want = item[condition]["vocalization"]
                if parsed.get("vocalization") != want:
                    errors = [f"vocalization is {parsed.get('vocalization')!r}, expected "
                              f"{want!r}"]
            if not errors:
                record = K.provenance(
                    run=run, item_id=item["item_id"], condition=condition,
                    task_type=f"{kind}_rubric", prompt_version=version,
                    model_provider=provider, model_name=model,
                    settings={"transport": transport}, raw_path=raw_path,
                    parsed=parsed, status="ok", attempts=attempt)
                return record
        prompt = (K.fill(template, ITEM_JSON=payload)
                  + "\n\nYour previous answer was rejected:\n"
                  + "\n".join(f"- {line}" for line in errors[:8])
                  + "\nReturn corrected JSON only.")
    return K.provenance(run=run, item_id=item["item_id"], condition=condition,
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
    parser.add_argument("--condition", action="append", choices=list(K.CONDITIONS),
                        help="default is the config's response_conditions")
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
    conditions = tuple(args.condition) if args.condition else K.response_conditions(config)
    run = K.run_id(args.run_id)
    out_dir = Path(args.output) if args.output else K.stage_dir("rubrics")
    planned = len(items) * len(conditions) * len(kinds)

    if args.dry_run:
        for item in items:
            for condition in conditions:
                for kind in kinds:
                    template, version = K.prompt(KINDS[kind][0])
                    prompt = K.fill(template, ITEM_JSON=json.dumps(
                        K.condition_payload(item, condition), indent=2, ensure_ascii=False))
                    print(f"\n{'=' * 78}\n{item['item_id']} · {condition} · {kind} rubric · "
                          f"{version} · {model} over {transport} · {len(prompt)} chars")
                    print(f"{'=' * 78}")
                    print(prompt)
        K.report("write-rubrics", planned=planned, completed=0, skipped=0, failed=0, invalid=0)
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
        for condition in conditions:
            for kind in kinds:
                record = write_one(item, condition, kind, model, transport, run)
                written[kind].append(record)
                flagged = False
                if record["status"] == "ok":
                    flagged = record["parsed"].get("ambiguity_flag", False)
                    note = record["parsed"].get("review_note", "")
                else:
                    failed += 1
                    note = "; ".join(record["errors"][:2])
                print(f"  {item['item_id']} · {condition:11} · {kind:7} · "
                      f"{record['status']} · attempt {record['attempts']}"
                      + (" · AMBIGUOUS" if flagged else "")
                      + (f" · {note[:64]}" if note else ""), flush=True)

    for kind, records in written.items():
        if not records:
            continue
        path = out_dir / f"{kind}_rubrics.json"
        key = lambda r: f"{r['item_id']}__{r['condition']}"
        existing = {}
        if path.exists():
            if not args.overwrite:
                print(f"error: {path} exists; pass --overwrite", file=sys.stderr)
                return 2
            existing = {key(r): r for r in json.loads(path.read_text())["items"]}
        existing.update({key(r): r for r in records})
        K.write_json(path, {"written_at": K.now(), "run_id": run,
                            "writer": model, "transport": transport,
                            "prompt_version": records[0]["prompt_version"],
                            "one_condition_per_call": True,
                            "items": [existing[k] for k in sorted(existing)]},
                     overwrite=True)
        print(f"wrote {path.relative_to(K.HERE.parent)} · {len(existing)} rubric(s)")

    K.report("write-rubrics", planned=planned, completed=planned - failed, skipped=0,
             failed=failed, invalid=failed)
    if T.cli_spend():
        print(f"  claude CLI spend: ${T.cli_spend():.3f}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
