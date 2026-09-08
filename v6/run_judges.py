"""Run the judge panels: interpretation match, response content, ranking, and tone.

Four stages, in dependency order. `interp` must precede `content`, because a reply is scored
against the guide for the interpretation the model actually held, and which one that was is
decided by the interpretation panel.

    interp    3 text judges — does the model's own account match any acceptable reading?
              Two agreeing carries it; a tie is recorded, never rounded.
    content   3 text judges — 1 to 5 against the guide for the reading it held.
    rank      3 text judges — R_A against R_B, in both conditions' contexts.
    tone      2 audio judges — is any clearly-wrong tone audible in the reply?

Every judge is blind to which model produced what it is judging, and is given the authoritative
vocalization label so its own perception cannot become a confound in someone else's score.

The tone judges hear the reply and nothing else. They are given the conversation as text, which
is all the rubric was ever based on — `tone_exclusions` is written from the transcript by a model
that never heard the audio, so playing the conversation would judge a text-derived list against
an audio comparison. One recording per session also removes the question of how a judge
distinguishes the reply from the stimulus, which matters because the turn adjacent to it is the
one carrying the vocalization.

    python v6/run_judges.py --dry-run
    python v6/run_judges.py --stage interp --limit 2
    python v6/run_judges.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import evalkit as K
import providers as P
import text_models as T

CONTRACT = {"interp": "judge_outputs:interpretation_match",
            "content": "judge_outputs:content_match",
            "rank": "judge_outputs:content_pairwise",
            "tone": "judge_outputs:tone_judgement"}
PROMPT = {"interp": "interpretation_match_judge", "content": "content_match_judge",
          "rank": "content_pairwise_judge", "tone": "tone_judge"}
ORDER = ("interp", "content", "rank", "tone")
ATTEMPTS = 2
SYSTEM = "You return valid JSON only. No markdown fences, no commentary."


def ask_text(judge: dict, prompt: str) -> str:
    K.guard(f"{judge['provider']} {judge['model']}")
    if judge["provider"] == "anthropic":
        return T.ask_claude(judge["model"], SYSTEM, prompt)
    return T.ask(judge["model"], SYSTEM, prompt, max_tokens=900)


def ask_audio(judge: dict, audio: Path, prompt: str) -> str:
    K.guard(f"{judge['provider']} {judge['model']}")
    return P.ask(judge["provider"], audio, SYSTEM, prompt, judge["model"])


def judge_once(judge: dict, prompt: str, kind: str, audio: Path | None,
               name: str) -> tuple[dict | None, str, list[str]]:
    """One judgement, validated. The reply is stored before anything parses it."""
    errors: list[str] = []
    raw = ""
    for attempt in range(1, ATTEMPTS + 1):
        raw = (ask_audio(judge, audio, prompt) if audio is not None
               else ask_text(judge, prompt))
        parsed = K.json_object(raw)
        if parsed is None:
            errors = ["the reply contained no JSON object"]
        else:
            errors = K.schema_errors(CONTRACT[kind], parsed)
            if not errors:
                return parsed, raw, []
        prompt += ("\n\nYour previous answer was rejected:\n"
                   + "\n".join(f"- {e}" for e in errors[:5]) + "\nReturn corrected JSON only.")
    return None, raw, errors


def transcript_of(item: dict, condition: str) -> str:
    return K.transcript_text(item, condition)


def vocalization_of(item: dict, condition: str) -> str:
    block = item[condition]
    tag = item["tag_a"] if condition == "condition_a" else item["tag_b"]
    return (f"A {block['vocalization']} ({tag}), produced by speaker "
            f"{item['vocalization_speaker']} in turn {item['vocalization_turn']}.")


def load(stage: str) -> dict:
    """The annotations a stage is judged against, keyed by item and condition."""
    path = K.stage_dir("rubrics") / f"{stage}.json"
    if not path.exists():
        return {}
    return {f"{r['item_id']}__{r['condition']}": r["parsed"]
            for r in json.loads(path.read_text())["items"] if r["status"] == "ok"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", action="append", choices=list(CONTRACT))
    parser.add_argument("--judge", action="append", help="judge ids")
    parser.add_argument("--model", action="append", help="evaluated model ids")
    parser.add_argument("--item-id", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--config")
    parser.add_argument("--run-id")
    parser.add_argument("--redo", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    K.set_dry_run(args.dry_run)

    try:
        config = K.load_config(Path(args.config) if args.config else None)
        _source, items = K.load_items(config)
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    by_id = {i["item_id"]: i for i in items}
    stages = [s for s in ORDER if s in (args.stage or ORDER)]
    text_panel = [j for j in config["judges"]["text"]
                  if not args.judge or j["id"] in set(args.judge)]
    audio_panel = [j for j in config["judges"]["audio"]
                   if not args.judge or j["id"] in set(args.judge)]
    run = K.run_id(args.run_id)

    interps = load("interpretations")
    guides = load("response_guides")
    tones = load("tone_exclusions")
    answers = K.read_jsonl(K.stage_dir("responses") / "interpretations.jsonl")
    replies = K.read_jsonl(K.stage_dir("responses") / "responses.jsonl")
    trials = K.read_jsonl(K.stage_dir("tasks") / "content_pairs.jsonl")

    def keep(rows):
        out = [r for r in rows if r.get("status") in (None, "ok")]
        if args.model:
            out = [r for r in out if r.get("evaluated_model") in set(args.model)]
        if args.item_id:
            out = [r for r in out if r.get("item_id") in set(args.item_id)]
        if args.limit:
            out = out[:args.limit]
        return out

    work: dict[str, list] = {
        "interp": keep(answers), "content": keep(replies),
        "rank": keep(trials), "tone": keep(replies)}
    planned = {s: len(work[s]) * len(audio_panel if s == "tone" else text_panel)
               for s in stages}

    print("  panels: text " + ", ".join(j["id"] for j in text_panel)
          + " · audio " + ", ".join(j["id"] for j in audio_panel))
    for stage in stages:
        print(f"  {stage:8} {len(work[stage]):4} unit(s) x "
              f"{len(audio_panel if stage == 'tone' else text_panel)} judge(s) = "
              f"{planned[stage]:4} call(s)")
    if not any(planned.values()):
        print("  nothing to judge — run run_models.py and build_pairs.py first")
    if args.dry_run:
        K.report("run-judges", planned=sum(planned.values()), completed=0, skipped=0,
                 failed=0, invalid=0)
        print("dry run: nothing called, nothing written")
        return 0

    matched: dict[tuple, int] = {}
    for row in K.read_jsonl(K.stage_dir("judgments") / "interpretation.jsonl"):
        if row.get("status") == "ok" and row["parsed"]["matched"]:
            key = (row.get("evaluated_model"), row["item_id"], row["condition"])
            matched.setdefault(key, row["parsed"]["interpretation_index"])

    counts = {"done": 0, "skipped": 0, "failed": 0, "invalid": 0}
    for stage in stages:
        out_file = K.stage_dir("judgments") / f"{stage_name(stage)}.jsonl"
        already = {(r.get("judge"), r.get("task_id"), r.get("evaluated_model"))
                   for r in K.read_jsonl(out_file)}
        panel = audio_panel if stage == "tone" else text_panel
        template, version = K.prompt(PROMPT[stage])
        for unit in work[stage]:
            item = by_id.get(unit["item_id"])
            if item is None:
                continue
            key = f"{unit['item_id']}__{unit['condition']}"
            built = build_prompt(stage, template, unit, item, key, interps, guides, tones,
                                 matched)
            if built is None:
                counts["skipped"] += 1
                continue
            prompt, audio = built
            for judge in panel:
                stamp = (judge["id"], unit.get("task_id"), unit.get("evaluated_model"))
                if stamp in already and not args.redo:
                    counts["skipped"] += 1
                    continue
                name = f"{stage}__{judge['id']}__{unit.get('evaluated_model','?')}__{key}"
                try:
                    parsed, raw, errors = judge_once(judge, prompt, stage, audio, name)
                except Exception as exc:                      # noqa: BLE001 - recorded
                    counts["failed"] += 1
                    print(f"    {name} FAILED {type(exc).__name__}: {exc}"[:140], flush=True)
                    continue
                record = K.provenance(
                    run=run, item_id=unit["item_id"], condition=unit["condition"],
                    task_type=stage_name(stage), prompt_version=version,
                    model_provider=judge["provider"], model_name=judge["model"],
                    parsed=parsed, status="ok" if parsed else "invalid", errors=errors,
                    raw_path=K.save_raw("judgments", name, raw))
                record.update({"task_id": unit.get("task_id"), "judge": judge["id"],
                               "evaluated_model": unit.get("evaluated_model"),
                               "renderer": unit.get("renderer"),
                               "gold_vocalization": unit.get("gold_vocalization")})
                K.append_jsonl(out_file, record)
                counts["done" if parsed else "invalid"] += 1
        print(f"  {stage}: wrote {out_file.name}")

    K.report("run-judges", planned=sum(planned.values()), completed=counts["done"],
             skipped=counts["skipped"], failed=counts["failed"], invalid=counts["invalid"])
    return 1 if counts["failed"] else 0


def stage_name(stage: str) -> str:
    """The task_type score.py expects for each stage."""
    return {"interp": "interpretation", "content": "content_match",
            "rank": "content_pair", "tone": "tone"}[stage]


def build_prompt(stage, template, unit, item, key, interps, guides, tones, matched):
    """The filled prompt and, for tone, the audio to play. None means skip this unit."""
    condition = unit["condition"]
    common = {"TRANSCRIPT": transcript_of(item, condition),
              "VOCALIZATION": vocalization_of(item, condition)}
    if stage == "interp":
        source = interps.get(key)
        if not source:
            return None
        readings = "\n".join(
            f"{n}. {i['reading']} — {i['interactional_function']}"
            for n, i in enumerate(source["acceptable_interpretations"], 1))
        return K.fill(template, **common, INTERPRETATIONS=readings,
                      SHARED_IMPLICATION=source["shared_implication"],
                      ANSWER=unit["parsed"]["answer"]), None
    if stage == "content":
        source, guide_set = interps.get(key), guides.get(key)
        index = matched.get((unit.get("evaluated_model"), unit["item_id"], condition))
        if not source or not guide_set or not index:
            return None
        reading = source["acceptable_interpretations"][index - 1]
        guide = next(g for g in guide_set["guides"] if g["interpretation_index"] == index)
        return K.fill(template, **common,
                      INTERPRETATION=f"{reading['reading']} — "
                                     f"{reading['interactional_function']}",
                      GUIDE=json.dumps(guide, indent=2, ensure_ascii=False),
                      RESPONSE=unit["response_text"]), None
    if stage == "rank":
        return K.fill(template, **common,
                      RUBRIC=interps.get(key, {}).get("shared_implication", ""),
                      RESPONSE_A=unit["candidates"]["A"]["response_text"],
                      RESPONSE_B=unit["candidates"]["B"]["response_text"]), None
    source = tones.get(key)
    if not source or not unit.get("response_audio_path"):
        return None
    listed = "\n".join(f"- {t['tone']}: {t['sounds_like']} (wrong because {t['why_wrong']})"
                       for t in source["inappropriate_tones"])
    return K.fill(template, **common, INAPPROPRIATE_TONES=listed,
                  ACCEPTABLE_RANGE_NOTE=source["acceptable_range_note"]), (
        K.HERE / unit["response_audio_path"])


if __name__ == "__main__":
    raise SystemExit(main())
