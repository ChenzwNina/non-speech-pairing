"""Measure whether each item's two versions pull replies apart, before the freeze.

The question is preference, not exclusivity. A non-speech vocalization usually changes the
stance a reply takes rather than the action it performs: a laugh and a sigh on the same words
can both leave the other speaker saying "that spot is easy to miss", the laugh inviting shared
amusement and the sigh commiseration. Asking whether a reply appropriate for one version is
*inappropriate* for the other therefore fails almost every well-written item — the earlier
binary check failed 23 of 24 — while the benchmark only needs the two versions to prefer
different replies.

So this measures the preference instead of asking a model to declare it.

    1. Each condition already has one to three interpretations of its own, written without
       sight of the other condition, and one guide per interpretation.
    2. One natural reply is written per interpretation, from the reading alone rather than
       from the guide, so scoring it against the guides measures fit and not recall.
    3. Every reply is scored under both conditions, blind: the judge sees one version, one
       unlabelled reply, and no sign that another version exists.
    4. A reply's score under a condition is its score against that condition's best-matching
       guide. The two conditions' interpretations are never paired up — they are separate sets
       of different sizes, and nothing needs to correspond across them.
    5. A reply's preference is `home - away`: its score under the condition it was written for
       minus its score under the other. A version-specific reply is positive, a generic reply
       that fits both equally is zero and simply carries no information, and a negative reply
       leans the wrong way.

An item separates when both sides lean the right way. Generic replies do not count against
it; they abstain.

The verdict is computed from the stored scores, so changing the threshold costs no calls:
`--stage report` rewrites it from what is already on disk.

    python3 v6/measure_separability.py --dry-run
    python3 v6/measure_separability.py                     # responses, scores, report
    python3 v6/measure_separability.py --stage report      # recompute the verdict only
    python3 v6/measure_separability.py --only v6_02b --redo
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import evalkit as K
import text_models as T

RESPONSES = "reference_responses"
FITS = "response_fit"
VERDICT = "pair_separability"
OTHER = {"condition_a": "condition_b", "condition_b": "condition_a"}
SYSTEM = "You return valid JSON only. No markdown fences, no commentary."
ATTEMPTS = 3


def responder(item: dict) -> str:
    return "B" if item["vocalization_speaker"] == "A" else "A"


def ask(model: str, transport: str, prompt: str, max_tokens: int = 2000) -> str:
    K.guard(f"{transport} {model}")
    if transport == "cli":
        return T.ask_claude(model, SYSTEM, prompt)
    import anthropic

    reply = anthropic.Anthropic(api_key=T.key("ANTHROPIC_API_KEY")).messages.create(
        model=model, max_tokens=max_tokens, system=SYSTEM,
        messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in reply.content
                   if getattr(b, "type", "") == "text").strip()


def attempt_loop(build_prompt, validate, schema_name: str, model: str, transport: str,
                 raw_name: str):
    """Ask, parse, validate, re-ask with the errors quoted. Returns (parsed|None, errors, n)."""
    prompt = build_prompt()
    errors: list[str] = []
    for n in range(1, ATTEMPTS + 1):
        text = T.retry(ask, model, transport, prompt)
        K.save_raw("writer_raw", f"{raw_name}__attempt{n}", text)
        parsed = K.json_object(text)
        if parsed is None:
            errors = ["the reply contained no JSON object"]
        else:
            errors = K.schema_errors(schema_name, parsed) or validate(parsed)
            if not errors:
                return parsed, [], n
        prompt = (build_prompt() + "\n\nYour previous answer was rejected:\n"
                  + "\n".join(f"- {e}" for e in errors[:6]) + "\nReturn corrected JSON only.")
    return None, errors, ATTEMPTS


# ---------------------------------------------------------------- stage 1: reference replies

def response_payload(item: dict, condition: str, interps: dict) -> str:
    body = K.condition_payload(item, condition)
    body["responder"] = responder(item)
    body["readings"] = [
        {"interpretation_index": n, "reading": x["reading"],
         "interactional_function": x["interactional_function"],
         "supported_by": x["supported_by"]}
        for n, x in enumerate(interps["acceptable_interpretations"], 1)]
    body["shared_implication"] = interps["shared_implication"]
    return json.dumps(body, indent=2, ensure_ascii=False)


def write_responses(item: dict, condition: str, interps: dict, model: str, transport: str,
                    run: str) -> dict:
    template, version = K.prompt("reference_response_writer")
    wanted = len(interps["acceptable_interpretations"])

    def build():
        return K.fill(template, INPUT=response_payload(item, condition, interps))

    def validate(parsed):
        if parsed.get("item_id") != item["item_id"]:
            return [f"item_id is {parsed.get('item_id')!r}"]
        if parsed.get("condition") != condition:
            return [f"condition is {parsed.get('condition')!r}, expected {condition!r}"]
        if parsed.get("responder") != responder(item):
            return [f"responder is {parsed.get('responder')!r}, expected {responder(item)!r}"]
        got = [r["interpretation_index"] for r in parsed["responses"]]
        if got != list(range(1, wanted + 1)):
            return [f"replies are indexed {got}; there are {wanted} reading(s), so they must "
                    f"be {list(range(1, wanted + 1))} in order"]
        return []

    parsed, errors, n = attempt_loop(build, validate, RESPONSES, model, transport,
                                     f"{item['item_id']}__{condition}__{RESPONSES}")
    return K.provenance(run=run, item_id=item["item_id"], condition=condition,
                        task_type=RESPONSES, prompt_version=version,
                        model_provider="anthropic", model_name=model,
                        settings={"transport": transport}, parsed=parsed,
                        status="ok" if parsed else "invalid",
                        errors=None if parsed else errors, attempts=n)


# --------------------------------------------------------------------- stage 2: cross-scoring

def guides_shown(guides: dict) -> str:
    """The guides as the judge sees them. `example` is withheld: the schema calls it human
    inspection only, and a judge shown it scores similarity to the example instead of fit."""
    return json.dumps([{"guide_index": g["interpretation_index"],
                        "response_function": g["response_function"],
                        "required_content": g["required_content"],
                        "acceptable_variations": g["acceptable_variations"],
                        "must_avoid": g["must_avoid"]} for g in guides["guides"]],
                      indent=2, ensure_ascii=False)


def score_one(item: dict, under: str, reply: str, guides: dict, model: str, transport: str,
              run: str, raw_name: str) -> dict:
    """Score `reply` under `under`. The judge learns nothing about where the reply came from."""
    template, version = K.prompt("response_fit_judge")
    block = K.condition_payload(item, under)
    transcript = "\n".join(f"{t['speaker']}: {t['text']}" for t in block["turns"])
    voc = (f"{block['vocalization']} — produced by speaker {item['vocalization_speaker']} in "
           f"turn {item['vocalization_turn']}. This label is authoritative.")
    shown = guides_shown(guides)
    n_guides = len(guides["guides"])

    def build():
        return K.fill(template, TRANSCRIPT=transcript, VOCALIZATION=voc, GUIDES=shown,
                      RESPONSE=reply)

    def validate(parsed):
        if not 1 <= parsed["best_guide_index"] <= n_guides:
            return [f"best_guide_index is {parsed['best_guide_index']}; this version has "
                    f"{n_guides} guide(s), so it must be between 1 and {n_guides}"]
        return []

    parsed, errors, n = attempt_loop(build, validate, FITS, model, transport, raw_name)
    return K.provenance(run=run, item_id=item["item_id"], condition=under, task_type=FITS,
                        prompt_version=version, model_provider="anthropic", model_name=model,
                        settings={"transport": transport}, parsed=parsed,
                        status="ok" if parsed else "invalid",
                        errors=None if parsed else errors, attempts=n)


# -------------------------------------------------------------------------- stage 3: verdict

def side_stats(deltas: list[int]) -> dict:
    n = len(deltas)
    up = sum(1 for d in deltas if d > 0)
    flat = sum(1 for d in deltas if d == 0)
    down = sum(1 for d in deltas if d < 0)
    mean = round(sum(deltas) / n, 2) if n else 0.0
    return {"n": n, "prefers_own": up, "generic": flat, "prefers_other": down,
            "mean_delta": mean, "leans_right_way": bool(n and mean > 0 and up > down),
            "deltas": deltas}


def verdict_for(item_id: str, scores: dict, responses: dict) -> dict | None:
    """Per-side preference for one item, or None when a score is missing."""
    sides = {}
    for cond in ("condition_a", "condition_b"):
        source = responses.get(f"{item_id}__{cond}")
        if not source or source["status"] != "ok":
            return None
        deltas = []
        for r in source["parsed"]["responses"]:
            idx = r["interpretation_index"]
            home = scores.get(f"{item_id}__{cond}__{idx}__under__{cond}")
            away = scores.get(f"{item_id}__{cond}__{idx}__under__{OTHER[cond]}")
            if not home or not away:
                return None
            deltas.append(home["parsed"]["score"] - away["parsed"]["score"])
        sides[cond] = side_stats(deltas)
    both = sides["condition_a"]["deltas"] + sides["condition_b"]["deltas"]
    return {"separable": all(s["leans_right_way"] for s in sides.values()),
            "margin": round(sum(both) / len(both), 2) if both else 0.0,
            "condition_a": sides["condition_a"], "condition_b": sides["condition_b"]}


def load(name: str, out_dir: Path, key) -> dict:
    path = out_dir / f"{name}.json"
    if not path.exists():
        return {}
    return {key(r): r for r in json.loads(path.read_text())["items"]}


def save(name: str, out_dir: Path, records: dict, **head) -> None:
    K.write_json(out_dir / f"{name}.json",
                 {"written_at": K.now(), **head,
                  "items": [records[k] for k in sorted(records)]}, overwrite=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", action="append")
    parser.add_argument("--stage", action="append", choices=["responses", "scores", "report"])
    parser.add_argument("--model")
    parser.add_argument("--transport", choices=["cli", "api"])
    parser.add_argument("--redo", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    K.set_dry_run(args.dry_run)
    stages = args.stage or ["responses", "scores", "report"]

    try:
        config = K.load_config()
        _source, items = K.load_items(config)
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    writer = config["writers"].get("verifier", {})
    model = args.model or writer.get("model", "claude-opus-5")
    transport = args.transport or writer.get("transport", "cli")
    out_dir = K.stage_dir("rubrics")

    need = {}
    for name in ("interpretations", "response_guides"):
        path = out_dir / f"{name}.json"
        if not path.exists():
            print(f"error: no {name} at {path}; run write_annotations.py first",
                  file=sys.stderr)
            return 2
        need[name] = {f"{r['item_id']}__{r['condition']}": r["parsed"]
                      for r in json.loads(path.read_text())["items"] if r["status"] == "ok"}

    if args.only:
        items = [i for i in items if i["item_id"] in set(args.only)]
    if not items:
        print(f"error: no items match {args.only}", file=sys.stderr)
        return 2

    responses = load(RESPONSES, out_dir, lambda r: f"{r['item_id']}__{r['condition']}")
    scores = load(FITS, out_dir, lambda r: r["task_id"])
    run = K.run_id(args.run_id)
    invalid = 0

    # ---- stage 1
    if "responses" in stages:
        plan = [(i, c) for i in items for c in ("condition_a", "condition_b")
                if args.redo or f"{i['item_id']}__{c}" not in responses]
        if args.dry_run and plan:
            item, cond = plan[0]
            template, version = K.prompt("reference_response_writer")
            print(f"{'=' * 78}\n{item['item_id']} · {cond} · {version} · {model}\n{'=' * 78}")
            print(K.fill(template,
                         INPUT=response_payload(item, cond, need["interpretations"][
                             f"{item['item_id']}__{cond}"])))
        elif plan:
            print(f"stage 1: {len(plan)} reference-reply call(s)")
            for item, cond in plan:
                key = f"{item['item_id']}__{cond}"
                if key not in need["interpretations"]:
                    print(f"  {key} · skipped, no valid interpretations")
                    continue
                rec = write_responses(item, cond, need["interpretations"][key], model,
                                      transport, run)
                responses[key] = rec
                invalid += rec["status"] != "ok"
                n = len(rec["parsed"]["responses"]) if rec["status"] == "ok" else 0
                print(f"  {key} · {rec['status']} · {n} reply(s) · attempt {rec['attempts']}",
                      flush=True)
                save(RESPONSES, out_dir, responses, writer=model, transport=transport)

    # ---- stage 2
    if "scores" in stages:
        plan = []
        for item in items:
            for cond in ("condition_a", "condition_b"):
                source = responses.get(f"{item['item_id']}__{cond}")
                if not source or source["status"] != "ok":
                    continue
                for r in source["parsed"]["responses"]:
                    for under in (cond, OTHER[cond]):
                        tid = (f"{item['item_id']}__{cond}__{r['interpretation_index']}"
                               f"__under__{under}")
                        if args.redo or tid not in scores:
                            plan.append((item, cond, r, under, tid))
        if args.dry_run and plan:
            item, cond, r, under, _tid = plan[0]
            template, version = K.prompt("response_fit_judge")
            block = K.condition_payload(item, under)
            print(f"\n{'=' * 78}\n{item['item_id']} · reply from {cond} scored under {under} · "
                  f"{version}\n{'=' * 78}")
            print(K.fill(
                template,
                TRANSCRIPT="\n".join(f"{t['speaker']}: {t['text']}" for t in block["turns"]),
                VOCALIZATION=f"{block['vocalization']} — produced by speaker "
                             f"{item['vocalization_speaker']} in turn "
                             f"{item['vocalization_turn']}. This label is authoritative.",
                GUIDES=guides_shown(need["response_guides"][f"{item['item_id']}__{under}"]),
                RESPONSE=r["text"]))
        elif plan:
            print(f"stage 2: {len(plan)} scoring call(s)")
            for item, cond, r, under, tid in plan:
                guides = need["response_guides"].get(f"{item['item_id']}__{under}")
                if not guides:
                    print(f"  {tid} · skipped, no guides for {under}")
                    continue
                rec = score_one(item, under, r["text"], guides, model, transport, run, tid)
                rec["task_id"] = tid
                rec["response_from"] = cond
                rec["interpretation_index"] = r["interpretation_index"]
                scores[tid] = rec
                invalid += rec["status"] != "ok"
                mark = (f"{rec['parsed']['score']} @guide "
                        f"{rec['parsed']['best_guide_index']}"
                        if rec["status"] == "ok" else rec["status"])
                print(f"  {tid} · {mark}", flush=True)
                save(FITS, out_dir, scores, judge=model, transport=transport)

    # ---- stage 3
    if "report" in stages:
        if args.dry_run:
            K.report("separability", planned=0, completed=0, skipped=0, failed=0, invalid=0)
            print("dry run: nothing called, nothing written")
            return 0
        table, missing = {}, []
        for item in items:
            v = verdict_for(item["item_id"], scores, responses)
            if v is None:
                missing.append(item["item_id"])
                continue
            v.update({"item_id": item["item_id"], "voc_a": item["voc_a"],
                      "voc_b": item["voc_b"]})
            table[item["item_id"]] = v

        print(f"\n{'item':9s} {'pair':13s} {'A: n up/flat/down mean':26s} "
              f"{'B: n up/flat/down mean':26s} margin  verdict")
        for iid in sorted(table):
            v = table[iid]
            cell = lambda s: (f"{s['n']}  {s['prefers_own']}/{s['generic']}/"
                              f"{s['prefers_other']}  {s['mean_delta']:+.2f}")
            print(f"{iid:9s} {v['voc_a'] + '/' + v['voc_b']:13s} "
                  f"{cell(v['condition_a']):26s} {cell(v['condition_b']):26s} "
                  f"{v['margin']:+.2f}   "
                  f"{'separable' if v['separable'] else 'NOT SEPARABLE'}")

        bad = sorted(i for i, v in table.items() if not v["separable"])
        K.write_json(out_dir / f"{VERDICT}.json",
                     {"measured_at": K.now(), "judge": model, "transport": transport,
                      "method": "cross-scored reference replies; preference = home - away, "
                                "max over each condition's guides",
                      "rule": "an item separates when both sides have mean delta > 0 and more "
                              "replies preferring their own condition than the other; generic "
                              "replies (delta 0) abstain",
                      "not_separable": bad,
                      "items": [table[k] for k in sorted(table)]}, overwrite=True)
        K.report("separability", planned=len(items), completed=len(table), skipped=len(missing),
                 failed=0, invalid=invalid)
        if missing:
            print(f"  {len(missing)} item(s) not yet scored: {missing[:6]}")
        if bad:
            print(f"\n  {len(bad)} item(s) do not separate: {bad}")
            print("  a side that leans the wrong way is the side to change; a side that is all "
                  "generic replies means the sound is doing nothing there.")
        print(f"wrote {(out_dir / f'{VERDICT}.json').relative_to(K.HERE.parent)}")
    if T.cli_spend():
        print(f"  claude CLI spend: ${T.cli_spend():.3f}")
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
