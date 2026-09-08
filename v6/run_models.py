"""Ask the evaluated models: what they heard, what it meant, and how they would reply.

Two stages, and the session boundary between them is the point.

**Stage `hear`** plays a stimulus and asks two questions in ONE session: which vocalization it
heard, then what that sound expresses. Sharing the session is deliberate — the second question
is asked of a model that has just committed to hearing a particular sound, which is what makes
the interpretation conditional on perception rather than independent of it.

**Stage `reply`** opens a FRESH session and elicits a reply as the other speaker. It must be
fresh, and its prompt must not mention a vocalization at all: the test is whether a model
notices the sound on its own, and having just been asked about it hands over the answer.

**Perception gates the rest.** A condition whose vocalization was misidentified has its
interpretation marked `gated_out` and no reply elicited. Asking whether a model understood a
laugh is meaningless if it did not hear which sound it was.

One caveat about the gate, honestly: the realtime providers send a session's follow-up questions
as a batch, so the interpretation question *is* asked even when perception was wrong. Its answer
is then discarded and marked `gated_out`, never reaching a judge. The recorded data is identical
to never having asked; the cost of one extra text turn per failure is not.

    python v6/run_models.py --dry-run
    python v6/run_models.py --stage hear --model openai --renderer elevenlabs --limit 2
    python v6/run_models.py --renderer elevenlabs
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import wave
from pathlib import Path

import evalkit as K
import providers as P

RESPONSES = "responses"
JUDGMENTS = "judgments"

# The session instruction for the `hear` stage. The providers always take one spoken turn after
# the audio before follow-ups can be asked, so this asks for that turn to be minimal — a reply
# invented here is not the elicited reply and must not be mistaken for one.
HEAR_TASK = ("You will hear a short conversation between two people, and then be asked "
             "questions about it. Do not reply to the conversation itself. Say only "
             "\"ready\" and wait for the questions.")

LETTER = re.compile(r"\b([A-E])\b")


def parse_choice(text: str) -> tuple[str | None, dict, list[str]]:
    """The chosen option letter, the parsed payload, and why it failed if it did."""
    payload = K.json_object(text)
    if isinstance(payload, dict) and "selected_option" in payload:
        errors = K.schema_errors("judge_outputs:mc_answer", payload)
        if not errors:
            return payload["selected_option"], payload, []
    # A model that answered in prose has still answered; a bare letter is recoverable, and the
    # raw text is kept either way so a recovery can be audited.
    found = LETTER.findall(text.upper())
    if len(set(found)) == 1:
        return found[0], {"selected_option": found[0]}, ["recovered from prose"]
    return None, {}, [f"no single option letter in {text[:120]!r}"]


def save_wav(pcm: bytes, rate: int, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm)
    return str(dest.relative_to(K.HERE))


def stimuli_for(items: list[dict], conditions: tuple[str, ...]):
    for item in items:
        for condition in conditions:
            yield item, condition


def hear(system: dict, renderer: str, item: dict, condition: str, task: dict, config: dict,
         run: str) -> tuple[dict, dict]:
    """One session: perception, then interpretation. Returns both records."""
    audio = K.audio_path(config, item["item_id"], condition, renderer)
    perception_q = task["question"]
    pragmatic_q, pragmatic_version = K.prompt("pragmatic_question")
    K.guard(f"{system['provider']} {system['model']}")
    result = P.converse(system["provider"], audio, HEAR_TASK,
                        [perception_q, pragmatic_q], system["model"])
    answers = result.get("answers") or []
    raw_perception = answers[0] if answers else ""
    raw_pragmatic = answers[1] if len(answers) > 1 else ""

    chosen, parsed, errors = parse_choice(raw_perception)
    correct = chosen == task["correct_option"] if chosen else False
    common = dict(run=run, item_id=item["item_id"], condition=condition,
                  model_provider=system["provider"], model_name=system["model"],
                  stimulus_audio_path=str(audio.relative_to(K.HERE)))

    heard = K.provenance(task_type="perception", prompt_version=task["prompt_version"],
                         parsed=parsed, status="ok" if chosen else "parse_error",
                         errors=errors,
                         raw_path=K.save_raw(JUDGMENTS,
                                             f"{system['id']}__{renderer}__{item['item_id']}"
                                             f"__{condition}__perception", raw_perception),
                         **common)
    heard.update({"task_id": task["task_id"], "evaluated_model": system["id"],
                  "renderer": renderer, "correct": correct,
                  "chosen_option": chosen, "correct_option": task["correct_option"],
                  "gold_vocalization": task["gold_vocalization"]})

    told = K.provenance(task_type="interpretation_answer", prompt_version=pragmatic_version,
                        parsed={"answer": raw_pragmatic},
                        status="ok" if correct else "gated_out",
                        errors=[] if correct else ["perception wrong; answer discarded"],
                        raw_path=K.save_raw(RESPONSES,
                                            f"{system['id']}__{renderer}__{item['item_id']}"
                                            f"__{condition}__interpretation", raw_pragmatic),
                        **common)
    told.update({"task_id": K.task_id(item["item_id"], condition, "interpretation"),
                 "evaluated_model": system["id"], "renderer": renderer,
                 "gold_vocalization": task["gold_vocalization"]})
    return heard, told


def reply(system: dict, renderer: str, item: dict, condition: str, config: dict,
          run: str) -> dict:
    """A fresh session, and a prompt that says nothing about any vocalization."""
    audio = K.audio_path(config, item["item_id"], condition, renderer)
    instruction, version = K.prompt("response_elicitation")
    K.guard(f"{system['provider']} {system['model']}")
    result = P.converse(system["provider"], audio, instruction, [], system["model"])
    text = (result.get("response") or "").strip()
    name = f"{system['id']}__{renderer}__{item['item_id']}__{condition}"
    audio_path = ""
    if result.get("response_pcm"):
        audio_path = save_wav(result["response_pcm"], result.get("pcm_rate", 24000),
                              K.stage_dir(RESPONSES) / f"{name}.wav")
    record = K.provenance(run=run, item_id=item["item_id"], condition=condition,
                          task_type="response", prompt_version=version,
                          model_provider=system["provider"], model_name=system["model"],
                          stimulus_audio_path=str(audio.relative_to(K.HERE)),
                          parsed={"response_text": text},
                          status="ok" if text else "empty",
                          raw_path=K.save_raw(RESPONSES, f"{name}__reply", text))
    record.update({"task_id": K.task_id(item["item_id"], condition, "response"),
                   "evaluated_model": system["id"], "renderer": renderer,
                   "response_text": text, "response_audio_path": audio_path})
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", action="append", choices=["hear", "reply"])
    parser.add_argument("--model", action="append", help="evaluated model ids")
    parser.add_argument("--renderer", action="append")
    parser.add_argument("--item-id", action="append")
    parser.add_argument("--limit", type=int, help="first N items, for a pilot")
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
    tasks_path = K.stage_dir("tasks") / "perception.json"
    if not tasks_path.exists():
        print(f"error: no frozen perception tasks at {tasks_path}; run build_tasks.py",
              file=sys.stderr)
        return 2
    tasks = {t["task_id"]: t for t in json.loads(tasks_path.read_text())["tasks"]}

    systems = [s for s in config["evaluated_models"]
               if not args.model or s["id"] in set(args.model)]
    renderers = [r for r in sorted(K.renderers(config))
                 if not args.renderer or r in set(args.renderer)]
    if args.item_id:
        items = [i for i in items if i["item_id"] in set(args.item_id)]
    if args.limit:
        items = items[:args.limit]
    stages = args.stage or ["hear", "reply"]
    voc = K.response_conditions(config)
    run = K.run_id(args.run_id)

    perception_file = K.stage_dir(JUDGMENTS) / "perception.jsonl"
    interp_file = K.stage_dir(RESPONSES) / "interpretations.jsonl"
    reply_file = K.stage_dir(RESPONSES) / "responses.jsonl"
    done = {p: {(r.get("evaluated_model"), r.get("renderer"), r["item_id"], r["condition"])
                for r in K.read_jsonl(p)}
            for p in (perception_file, interp_file, reply_file)}

    planned = len(systems) * len(renderers) * len(items)
    print(f"  {len(systems)} model(s) x {len(renderers)} renderer(s) x {len(items)} item(s)")
    print(f"  hear: {planned * len(K.CONDITIONS)} stimuli · "
          f"reply: up to {planned * len(voc)} (perception-gated)")
    if args.dry_run:
        K.report("run-models", planned=planned, completed=0, skipped=0, failed=0, invalid=0)
        print(f"  hear task instruction: {HEAR_TASK[:70]}…")
        print(f"  reply instruction: {K.prompt('response_elicitation')[0].splitlines()[0]}…")
        print("dry run: nothing called, nothing written")
        return 0

    counts = {"heard": 0, "gated": 0, "replied": 0, "skipped": 0, "failed": 0}
    for system in systems:
        for renderer in renderers:
            # Which stimuli this system heard correctly, read back from disk so a resumed
            # run gates on the same evidence a fresh one would.
            correct: set = set()
            for row in K.read_jsonl(perception_file):
                if row.get("correct") and row.get("evaluated_model") == system["id"] \
                        and row.get("renderer") == renderer:
                    correct.add((row["item_id"], row["condition"]))
            for item, condition in stimuli_for(items, K.CONDITIONS):
                key = (system["id"], renderer, item["item_id"], condition)
                if "hear" in stages:
                    if key in done[perception_file] and not args.redo:
                        counts["skipped"] += 1
                    else:
                        task = tasks.get(K.task_id(item["item_id"], condition, "perception"))
                        try:
                            heard, told = hear(system, renderer, item, condition, task,
                                               config, run)
                        except Exception as exc:              # noqa: BLE001 - recorded
                            counts["failed"] += 1
                            print(f"    {key} · hear FAILED {type(exc).__name__}: "
                                  f"{exc}"[:140], flush=True)
                            continue
                        K.append_jsonl(perception_file, heard)
                        K.append_jsonl(interp_file, told)
                        counts["heard"] += 1
                        counts["gated"] += heard["correct"] is False
                        if heard["correct"]:
                            correct.add((item["item_id"], condition))
                        print(f"    {system['id']}/{renderer}/{item['item_id']}/{condition}"
                              f" · heard {heard['chosen_option']} "
                              f"({'✓' if heard['correct'] else '✗ gated'})", flush=True)
                if "reply" in stages and condition in voc:
                    if (item["item_id"], condition) not in correct:
                        continue
                    if key in done[reply_file] and not args.redo:
                        counts["skipped"] += 1
                        continue
                    try:
                        record = reply(system, renderer, item, condition, config, run)
                    except Exception as exc:                  # noqa: BLE001 - recorded
                        counts["failed"] += 1
                        print(f"    {key} · reply FAILED {type(exc).__name__}: {exc}"[:140],
                              flush=True)
                        continue
                    K.append_jsonl(reply_file, record)
                    counts["replied"] += 1

    K.report("run-models", planned=planned, completed=counts["heard"] + counts["replied"],
             skipped=counts["skipped"], failed=counts["failed"], invalid=counts["gated"])
    print(f"  heard {counts['heard']} · gated out {counts['gated']} · "
          f"replies {counts['replied']}")
    for path in (perception_file, interp_file, reply_file):
        if path.exists():
            print(f"  {path.relative_to(K.HERE)} · {len(K.read_jsonl(path))} record(s)")
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
