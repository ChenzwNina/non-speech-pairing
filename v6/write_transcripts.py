"""Stage two — write the dialogue from a plan, and build the three versions from it.

The writer returns the five turns ONCE, with `«VOC»` standing where the vocalization goes. The
three versions are then assembled here by substitution. That makes four of the design's
properties true by construction rather than things a validator has to catch: identical words,
identical speakers, identical marker position, and exactly one vocalization per version with
none in the baseline. What is left to check is the one thing construction cannot guarantee —
that the marker sits at a sentence boundary in the final turn rather than inside a clause.

The register is written here rather than fixed afterwards. An earlier design had a separate
GPT-4o pass rewrite stiff prose into speech; folding the requirement into this prompt removes a
call and a layer of semantic drift, at the cost of leaning on the writer to do both jobs at once.

`emotion_a` and `emotion_b` on the finished item are the *planner's* framings, not labels looked
up from the inventory. They are sentences, and downstream that is a feature: what the rubric
writer needs to know is what this sound does in this conversation, which a one-word label cannot
carry.

    python v6/write_transcripts.py --dry-run --only v6_01a
    python v6/write_transcripts.py --only v6_01a
    python v6/write_transcripts.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import evalkit as K
import text_models as T

OUT = K.HERE / "out"
PLANS = OUT / "occasions.json"
TRANSCRIPTS = OUT / "transcripts.json"
READABLE = OUT / "transcripts.md"

MARKER = "«VOC»"
TURNS = 5
SPEAKERS = ["A", "B"] * (TURNS // 2 + 1)
ATTEMPTS = 3
MAX_TOKENS = 20000
BRACKETED = re.compile(r"\([^)]*\)|\[[^\]]*\]")


def tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([,.!?;:])", r"\1", text)


def marker_position(text: str) -> str | None:
    """Where the marker sits, or None if it is inside a sentence."""
    index = text.find(MARKER)
    if index < 0:
        return None
    before = text[:index].rstrip()
    after = text[index + len(MARKER):].lstrip()
    if not before:
        return "turn-initial"
    if not after:
        return "turn-final"
    if before[-1] in ".!?":
        return "sentence-boundary"
    return None


def problems(result: dict) -> list[str]:
    found = []
    turns = result["turns"]
    if [t["turn"] for t in turns] != list(range(1, TURNS + 1)):
        found.append(f"turns are not numbered 1..{TURNS}")
    if [t["speaker"] for t in turns] != SPEAKERS[:TURNS]:
        found.append(f"speaker order is {[t['speaker'] for t in turns]}, "
                     f"expected {SPEAKERS[:TURNS]}")
    total = sum(t["text"].count(MARKER) for t in turns)
    if total != 1:
        found.append(f"{total} markers; there must be exactly one {MARKER}")
        return found
    carrier = next(t for t in turns if MARKER in t["text"])
    if carrier["turn"] != TURNS:
        found.append(f"the marker is in turn {carrier['turn']}; it must be in turn {TURNS}, "
                     f"the final one")
    elif marker_position(carrier["text"]) is None:
        found.append(f"the marker interrupts a sentence in {carrier['text']!r}; it must sit at "
                     f"the start of the turn, at the end, or between two complete sentences")
    for turn in turns:
        stray = BRACKETED.findall(turn["text"])
        if stray:
            found.append(f"turn {turn['turn']} contains {stray}; the marker is the only "
                         f"non-speech annotation allowed")
    return found


def version(turns: list[dict], tag: str | None) -> list[dict]:
    return [{"turn": t["turn"], "speaker": t["speaker"],
             "text": tidy(t["text"].replace(MARKER, tag or ""))} for t in turns]


def check_speakers(turns: list[dict], args) -> tuple[bool, str, list[int]]:
    """Claude reads the draft and says whether either speaker changed identity partway."""
    if args.no_verify:
        return True, "", []
    template, _version = K.prompt("speaker_consistency_verifier")
    body = "\n".join(f"{t['turn']} {t['speaker']}: {t['text'].replace(MARKER, '').strip()}"
                      for t in turns)
    K.guard(f"{args.verifier_transport} {args.verifier}")
    if args.verifier_transport == "cli":
        raw = T.ask_claude(args.verifier, "You return valid JSON only.",
                           K.fill(template, TRANSCRIPT=body))
    else:
        import anthropic
        reply = anthropic.Anthropic(api_key=T.key("ANTHROPIC_API_KEY")).messages.create(
            model=args.verifier, max_tokens=700, system="You return valid JSON only.",
            messages=[{"role": "user", "content": K.fill(template, TRANSCRIPT=body)}])
        raw = "".join(b.text for b in reply.content
                      if getattr(b, "type", "") == "text").strip()
    parsed = K.json_object(raw)
    if parsed is None or K.schema_errors("speaker_check", parsed):
        # A verifier that cannot be parsed must not silently pass a draft it may have failed.
        return False, f"the speaker check returned nothing usable: {raw[:120]!r}", []
    return parsed["consistent"], parsed["problem"], parsed["turns_involved"]


def write_one(plan: dict, args, run: str) -> dict:
    parsed = plan["parsed"]
    template, version_stamp = K.prompt("transcript_writer")
    payload = json.dumps({
        "situation": parsed["situation_summary"],
        "the_moment_the_sound_goes": parsed["shared_moment"],
        "what_reaches_the_final_speaker_there": parsed["what_lands"],
        "when_vocalization_a_is_produced": parsed["production_condition_a"],
        "when_vocalization_b_is_produced": parsed["production_condition_b"],
        "outline": parsed["outline"],
        "vocalization_a": parsed["framing_a"],
        "vocalization_b": parsed["framing_b"],
        "what_separates_the_two_framings": parsed["why_different"],
    }, indent=2, ensure_ascii=False)
    prompt = "Write the dialogue as JSON."
    system = K.fill(template, INPUT=payload)

    for attempt in range(1, ATTEMPTS + 1):
        K.guard(f"openai {args.writer}")
        result = T.retry(T.json_call, args.writer, system, prompt,
                         K.strict(K.schema("transcript")), "transcript", args.effort,
                         MAX_TOKENS)
        found = problems(result)
        if not found:
            consistent, problem, where = check_speakers(result["turns"], args)
            if not consistent:
                found = [f"a speaker changes identity partway through (turns {where}): "
                         f"{problem}"]
        if found:
            prompt = ("Write the dialogue as JSON.\n\nYour previous answer was rejected:\n"
                      + "\n".join(f"- {line}" for line in found)
                      + "\nRewrite so that none of those apply.")
            continue
        turns = result["turns"]
        carrier = next(t for t in turns if MARKER in t["text"])
        return {
            "item_id": plan["item_id"], "seed_id": plan["seed_id"],
            "seed_label": plan["seed_label"], "situation": plan["situation"],
            "scenario": parsed["situation_summary"],
            "voc_a": plan["voc_a"], "tag_a": plan["tag_a"],
            "emotion_a": parsed["framing_a"]["emotional_framing"],
            "speaker_state_a": parsed["framing_a"]["speaker_state"],
            "voc_b": plan["voc_b"], "tag_b": plan["tag_b"],
            "emotion_b": parsed["framing_b"]["emotional_framing"],
            "speaker_state_b": parsed["framing_b"]["speaker_state"],
            "why_different": parsed["why_different"],
            "shared_moment": parsed["shared_moment"],
            "what_lands": parsed["what_lands"],
            "production_condition_a": parsed["production_condition_a"],
            "production_condition_b": parsed["production_condition_b"],
            "vocalization_turn": TURNS, "vocalization_speaker": carrier["speaker"],
            "marker_position": marker_position(carrier["text"]),
            "how_a_lands": result["how_a_lands"], "how_b_lands": result["how_b_lands"],
            "still_open_without_sound": result["still_open_without_sound"],
            "attempts": attempt, "run_id": run,
            "speaker_check": {"verifier": args.verifier if not args.no_verify else None,
                              "consistent": True},
            "plan_prompt_version": plan["prompt_version"],
            "writer_prompt_version": version_stamp,
            "writer": args.writer,
            "baseline": {"vocalization": "none", "target_emotion": "ambiguous",
                         "turns": version(turns, None)},
            "condition_a": {"vocalization": plan["voc_a"],
                            "target_emotion": parsed["framing_a"]["emotional_framing"],
                            "turns": version(turns, plan["tag_a"])},
            "condition_b": {"vocalization": plan["voc_b"],
                            "target_emotion": parsed["framing_b"]["emotional_framing"],
                            "turns": version(turns, plan["tag_b"])},
        }
    raise RuntimeError(f"{plan['item_id']}: rejected after {ATTEMPTS} attempts: {found}")


def render(item: dict) -> str:
    lines = [f"## {item['item_id']} · {item['voc_a']} vs {item['voc_b']}", "",
             f"**Seed** (`{item['seed_label']}`): {item['situation']}", "",
             f"**Scenario:** {item['scenario']}", "",
             f"The tag sits in turn {item['vocalization_turn']} "
             f"({item['marker_position']}), spoken by {item['vocalization_speaker']}. "
             f"Every word is identical across the three versions.", ""]
    for turn in item["baseline"]["turns"]:
        if turn["turn"] != item["vocalization_turn"]:
            lines.append(f"{turn['turn']}. **{turn['speaker']}:** {turn['text']}")
            continue
        lines.append(f"{turn['turn']}. **{turn['speaker']}:** {turn['text']}  ← baseline")
        for key in ("condition_a", "condition_b"):
            tagged = next(t for t in item[key]["turns"]
                          if t["turn"] == item["vocalization_turn"])
            lines.append(f"{turn['turn']}. **{turn['speaker']}:** {tagged['text']}")
    lines += ["",
              "| version | framing |", "| --- | --- |",
              f"| none | {item['still_open_without_sound']} |",
              f"| `{item['tag_a']}` | {item['emotion_a']} |",
              f"| `{item['tag_b']}` | {item['emotion_b']} |", "",
              f"**Why the two differ:** {item['why_different']}", "",
              f"**How {item['voc_a']} lands:** {item['how_a_lands']}", "",
              f"**How {item['voc_b']} lands:** {item['how_b_lands']}", "", "---", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", help="item ids")
    parser.add_argument("--redo", action="store_true")
    parser.add_argument("--writer", default="gpt-5.6-terra")
    parser.add_argument("--effort", default=None,
                        help="reasoning effort; omitted by default, so the model runs at its "
                             "own. 2.0's convention: nothing in the pipeline sets it.")
    parser.add_argument("--verifier", help="default comes from writers.verifier")
    parser.add_argument("--verifier-transport", choices=["cli", "api"])
    parser.add_argument("--no-verify", action="store_true",
                        help="skip the speaker-consistency check")
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    K.set_dry_run(args.dry_run)

    try:
        config = K.load_config()
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    verifier = config["writers"].get("verifier", {})
    args.verifier = args.verifier or verifier.get("model", "claude-opus-5")
    args.verifier_transport = args.verifier_transport or verifier.get("transport", "cli")

    if not PLANS.exists():
        print(f"error: no plans at {PLANS}; run plan_occasions.py first", file=sys.stderr)
        return 2
    plans = [p for p in json.loads(PLANS.read_text())["items"] if p["status"] == "ok"]
    existing = json.loads(TRANSCRIPTS.read_text())["items"] if TRANSCRIPTS.exists() else []
    by_id = {r["item_id"]: r for r in existing}
    if args.only:
        plans = [p for p in plans if p["item_id"] in set(args.only)]
    elif not args.redo:
        plans = [p for p in plans if p["item_id"] not in by_id]
    if not plans:
        print("nothing to write")
        return 0

    if args.dry_run:
        template, version_stamp = K.prompt("transcript_writer")
        plan = plans[0]
        payload = json.dumps({"situation": plan["parsed"]["situation_summary"],
                              "the_moment_the_sound_goes": plan["parsed"]["shared_moment"],
                              "outline": plan["parsed"]["outline"],
                              "vocalization_a": plan["parsed"]["framing_a"],
                              "vocalization_b": plan["parsed"]["framing_b"]},
                             indent=2, ensure_ascii=False)
        print(f"{'=' * 78}\n{plan['item_id']} · {version_stamp} · {args.writer}\n{'=' * 78}")
        print(K.fill(template, INPUT=payload))
        K.report("write-transcripts", planned=len(plans), completed=0, skipped=0,
                 failed=0, invalid=0)
        print("dry run: nothing called, nothing written")
        return 0

    run = K.run_id(args.run_id)
    failed = 0
    order = {p["item_id"]: n for n, p in
             enumerate(json.loads(PLANS.read_text())["items"])}
    for plan in plans:
        try:
            item = write_one(plan, args, run)
        except RuntimeError as exc:
            failed += 1
            print(f"  {plan['item_id']} · FAILED · {exc}"[:170], flush=True)
            continue
        by_id[item["item_id"]] = item
        print(f"  {item['item_id']} · {item['voc_a']}/{item['voc_b']} · "
              f"{item['marker_position']:18} · attempt {item['attempts']}"
              + ("" if args.no_verify else " · speakers ok"), flush=True)
        ordered = sorted(by_id.values(), key=lambda r: order.get(r["item_id"], 999))
        K.write_json(TRANSCRIPTS, {"written_at": K.now(), "run_id": run,
                                   "writer": args.writer, "effort": args.effort or "default",
                                   "turns": TURNS,
                                   "design": "five turns written once; the vocalization sits "
                                             "at a sentence boundary in the final turn and the "
                                             "three versions are built by substitution",
                                   "items": ordered}, overwrite=True)
        READABLE.write_text("# v6 transcripts\n\n" + "".join(render(e) for e in ordered))

    K.report("write-transcripts", planned=len(plans), completed=len(plans) - failed,
             skipped=0, failed=failed, invalid=0)
    print(f"wrote {TRANSCRIPTS.relative_to(K.HERE.parent)} · {len(by_id)} item(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
