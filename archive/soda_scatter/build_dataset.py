"""Build a dataset of SODA-seeded conversations end to end: write, voice, verify.

Runs three stages per item and writes everything into one folder:

    1. pick a SODA scenario, draw 6-12 vocalizations, scatter them, write the 12 turns
    2. render each turn with eleven_v3 (inline audio tags) and sew the conversation
    3. play each vocalization turn to gpt-realtime-2.1 three times; a label is kept as
       ground truth when a majority of votes identify that sound, and dropped otherwise

Everything is eleven_v3 — no real recordings are spliced in. Splicing produced audible
sounds but a different voice from the speaker, which sounded wrong, so the trade taken here
is the opposite one: the voice stays consistent and labels that the synthesis fails to
realize are simply pruned. Expect attrition, and expect it to fall unevenly — eleven_v3
renders laughter and sighs far more reliably than sobs and yawns, so the surviving
distribution will not match the planned draw.

Written incrementally, so a run that dies partway can be resumed without repaying for
completed items.

Usage:
    python soda_scatter/build_dataset.py --n 20
    python soda_scatter/build_dataset.py --n 20 --resume
    python soda_scatter/build_dataset.py --n 2 --runs 3 --verbose
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types.model_settings_response_model import ModelSettingsResponseModel
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "logo_sketch"))
sys.path.insert(0, str(HERE))
load_dotenv(REPO / ".env")

# The ffmpeg splicer lives in logo_sketch/make_audio.py, but soda_scatter has a file of the
# same name that would shadow it and self-import. Load it by path under a distinct name.
def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_splice = _load("logo_splice", HERE.parent / "logo_sketch" / "make_audio.py")
build, duration_of, timestamp = _splice.build, _splice.duration_of, _splice.timestamp

# stage 1 lives in generate.py; stage 3's polling lives in verify_audio.py
from generate import (  # noqa: E402
    N_TURNS, VOC_TYPES, call_model, pick_seed, sample_plan, speaker_of, user_prompt,
    validate,
)
from verify_audio import names_target, poll  # noqa: E402

DEFAULT_DIR = HERE / "dataset"

WRITER_MODEL = "gpt-5.6-terra"
EFFORT = "high"
VERIFIER_MODEL = "gpt-realtime-2.1"
VERIFY_RUNS = 3

TTS_MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"
STABILITY = 0.4
TURN_GAP = 0.36

VOICE_FEMALE = "aKw9UnnjRq5scbeeGI7Z"
VOICE_MALE = "s3TPKV1kjDlVtZbl4Ksh"

MAX_WRITE_ATTEMPTS = 4


def synthesize(client: ElevenLabs, text: str, voice_id: str, dest: Path) -> None:
    """Local copy rather than an import: soda_scatter/make_audio.py shadows the logo_sketch
    module of the same name, so importing it here would collide."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    audio = b"".join(client.text_to_speech.convert(
        voice_id=voice_id, text=text, model_id=TTS_MODEL, output_format=OUTPUT_FORMAT,
        voice_settings=ModelSettingsResponseModel(stability=STABILITY)))
    dest.write_bytes(audio)


def write_transcript(client: OpenAI, seed: dict, plan: list[dict], model: str,
                     effort: str, verbose: bool) -> dict | None:
    prompt = user_prompt(seed, plan)
    usage_total = {"input_tokens": 0, "output_tokens": 0}
    for attempt in range(1, MAX_WRITE_ATTEMPTS + 1):
        payload, usage = call_model(client, prompt, model, effort)
        usage_total["input_tokens"] += usage["input_tokens"]
        usage_total["output_tokens"] += usage["output_tokens"]
        problems = validate(payload, seed, plan)
        if not problems:
            return {"turns": payload["turns"], "vocalizations": payload["vocalizations"],
                    "attempts": attempt, "usage": usage_total}
        if verbose:
            print(f"      write attempt {attempt} rejected: {problems[:3]}", flush=True)
        prompt = user_prompt(seed, plan) + (
            "\n\nThe previous attempt failed these checks:\n- " + "\n- ".join(problems)
            + "\nKeep the vocalization plan exactly as given and return a corrected object.")
    return None


def voice_turns(client: ElevenLabs, record: dict, out_dir: Path,
                swap: bool) -> dict[int, Path]:
    """Render every turn. Sewing waits until after verification, because a retaken turn
    changes its own length and the conversation has to be assembled from the final takes."""
    seed, item_id = record["seed"], record["item_id"]
    voice_a = VOICE_MALE if swap else VOICE_FEMALE
    voice_b = VOICE_FEMALE if swap else VOICE_MALE
    voices = {seed["speaker_a"]: voice_a, seed["speaker_b"]: voice_b}
    line_dir = out_dir / "lines" / item_id

    paths: dict[int, Path] = {}
    for turn in record["turns"]:
        number, speaker, text = turn["turn"], turn["speaker"], turn["text"]
        path = line_dir / f"{number:02d}_{speaker.lower().replace(' ', '_')}.mp3"
        if not path.exists():
            synthesize(client, text, voices[speaker], path)
            time.sleep(0.2)
        paths[number] = path
    record["_voices"] = {seed["speaker_a"]: voice_a, seed["speaker_b"]: voice_b}
    return paths


def sew_item(record: dict, paths: dict[int, Path], out_dir: Path
             ) -> tuple[Path, list[dict], float]:
    voc_by_turn = {v["turn"]: v for v in record["plan"]}
    pieces: list[tuple[str, object]] = []
    rows: list[dict] = []
    for turn in record["turns"]:
        number = turn["turn"]
        path = paths[number]
        if pieces:
            pieces.append(("silence", TURN_GAP))
            rows.append({"kind": "gap", "seconds": TURN_GAP})
        pieces.append(("file", path))
        voc = voc_by_turn.get(number)
        rows.append({
            "kind": "line", "turn": number, "speaker": turn["speaker"], "text": turn["text"],
            "seconds": round(duration_of(path), 3), "path": str(path.relative_to(REPO)),
            "vocalization": voc["vocalization"] if voc else None,
        })
    final = out_dir / "audio" / f"{record['item_id']}.mp3"
    build(pieces, final)
    total = duration_of(final)
    clock = 0.0
    for row in rows:
        if row["kind"] == "line":
            row["starts_at_seconds"] = round(clock, 2)
            row["starts_at"] = timestamp(clock)
        clock += row["seconds"]
    return final, rows, total


def verify_labels(client: OpenAI, eleven: ElevenLabs, record: dict,
                  paths: dict[int, Path], model: str, runs: int, retakes: int,
                  verbose: bool) -> tuple[list[dict], list[dict], list[dict]]:
    """Keep a label when a majority of parseable votes name its sound.

    eleven_v3 is nondeterministic, so a sound absent from one take may be present in the
    next. A failing turn is therefore re-synthesized up to `retakes` times, and the first
    take that verifies is kept. This spends TTS calls to buy back labels that a single-take
    pipeline throws away — at 3 votes per attempt, the verification cost per vocalization
    turn is up to runs x (1 + retakes).
    """
    from verify_audio import mp3_to_pcm16_24k

    voices = record["_voices"]
    text_by_turn = {t["turn"]: t["text"] for t in record["turns"]}
    speaker_by_turn = {t["turn"]: t["speaker"] for t in record["turns"]}

    kept: list[dict] = []
    dropped: list[dict] = []
    verdicts: list[dict] = []

    for entry in sorted(record["vocalizations"], key=lambda e: e["turn"]):
        turn, target = entry["turn"], entry["vocalization"]
        attempts: list[dict] = []
        verified = False

        for take in range(1, retakes + 2):
            votes = poll(client, mp3_to_pcm16_24k(paths[turn]), model, runs)
            heard = Counter(v["sound"] for v in votes if v.get("sound"))
            usable = sum(1 for v in votes if v.get("sound"))
            hits = sum(1 for v in votes if names_target(v.get("sound"), target))
            verified = usable > 0 and hits * 2 > usable
            attempts.append({
                "take": take, "hits": hits, "usable_votes": usable,
                "votes": [v.get("sound") for v in votes],
            })
            if verbose:
                tally = ", ".join(f"{k}x{v}" for k, v in heard.most_common()) or "unparseable"
                print(f"      t{turn:>2} {target:9} take {take}: {hits}/{usable} "
                      f"{'keep' if verified else 'miss'}  [{tally}]", flush=True)
            if verified or take > retakes:
                break
            # re-render this turn and try again
            synthesize(eleven, text_by_turn[turn], voices[speaker_by_turn[turn]], paths[turn])
            time.sleep(0.2)

        verdicts.append({
            "turn": turn, "target": target, "audio_tag": entry["audio_tag"],
            "audio": str(paths[turn].relative_to(REPO)),
            "takes": attempts, "verified": verified,
        })
        (kept if verified else dropped).append(entry)
    return kept, dropped, verdicts


def render_dataset_markdown(records: list[dict]) -> str:
    lines = [
        "# SODA-seeded vocalization dataset",
        "",
        f"{len(records)} conversations of {N_TURNS} turns each. Vocalization placement was "
        "fixed before the dialogue was written; the labels below are only those a majority "
        "of verifier runs could actually hear in the rendered audio.",
        "",
    ]
    total_planned = sum(len(r["plan"]) for r in records)
    total_kept = sum(len(r["vocalizations"]) for r in records)
    kept_types = Counter(v["vocalization"] for r in records for v in r["vocalizations"])
    planned_types = Counter(p["vocalization"] for r in records for p in r["plan"])
    lines += [
        f"**{total_kept} of {total_planned} planned vocalizations survived verification "
        f"({100 * total_kept / total_planned:.0f}%).**",
        "",
        "| sound | planned | verified | survival |",
        "| --- | --- | --- | --- |",
    ]
    for voc in VOC_TYPES:
        planned, kept = planned_types.get(voc, 0), kept_types.get(voc, 0)
        rate = f"{100 * kept / planned:.0f}%" if planned else "—"
        lines.append(f"| {voc} | {planned} | {kept} | {rate} |")
    lines.append("")

    for record in records:
        seed = record["seed"]
        marked = {v["turn"] for v in record["vocalizations"]}
        lines += [
            "---", "",
            f"## {record['item_id']}",
            "",
            f"*SODA #{seed.get('original_index')}* — {seed['narrative']}",
            "",
            f"**Audio** `{record['audio']}` · {record['audio_seconds']:.1f}s · "
            f"{seed['speaker_a']} / {seed['speaker_b']}",
            "",
            f"{len(record['vocalizations'])} verified of {len(record['plan'])} planned",
            "",
        ]
        for turn in record["turns"]:
            mark = " ←" if turn["turn"] in marked else ""
            lines.append(f"{turn['turn']}. **{turn['speaker']}:** {turn['text']}{mark}")
        lines.append("")
        if record["vocalizations"]:
            lines += ["| turn | at | sound | tag | target | intention after |",
                      "| --- | --- | --- | --- | --- | --- |"]
            starts = {r["turn"]: r.get("starts_at", "") for r in record["segments"]
                      if r.get("kind") == "line"}
            for entry in sorted(record["vocalizations"], key=lambda e: e["turn"]):
                lines.append(
                    f"| {entry['turn']} | {starts.get(entry['turn'], '')} | "
                    f"{entry['vocalization']} | `{entry['audio_tag']}` | "
                    f"{entry['target']} | {entry['intention_after']} |")
            lines.append("")
        if record["vocalizations_dropped"]:
            dropped = ", ".join(f"t{e['turn']}={e['vocalization']}"
                                for e in record["vocalizations_dropped"])
            lines += [f"*Dropped as inaudible: {dropped}*", ""]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--writer-model", default=WRITER_MODEL)
    parser.add_argument("--effort", default=EFFORT)
    parser.add_argument("--verifier-model", default=VERIFIER_MODEL)
    parser.add_argument("--runs", type=int, default=VERIFY_RUNS)
    parser.add_argument("--retakes", type=int, default=2,
                        help="re-render a turn this many times if its sound is not heard")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    args.dir = args.dir.resolve()
    return args


def main() -> None:
    args = parse_args()
    args.dir.mkdir(parents=True, exist_ok=True)
    dataset_path = args.dir / "dataset.json"

    records: list[dict] = []
    seen_indices: set = set()
    if args.resume and dataset_path.exists():
        previous = json.loads(dataset_path.read_text(encoding="utf-8"))
        records = previous.get("results", [])
        seen_indices = {r["seed"].get("original_index") for r in records}
        print(f"resuming with {len(records)} existing item(s)", flush=True)

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    eleven_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not openai_key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    if not eleven_key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")
    openai_client = OpenAI(api_key=openai_key)
    eleven_client = ElevenLabs(api_key=eleven_key)

    rng = random.Random(args.seed)
    # advance the rng past seeds already consumed so a resume does not redraw them
    for _ in range(len(records)):
        rng.random()

    print(f"building {args.n} item(s) into {args.dir}", flush=True)
    print(f"  writer {args.writer_model} · tts {TTS_MODEL} · "
          f"verifier {args.verifier_model} x{args.runs}", flush=True)

    while len(records) < args.n:
        index = len(records) + 1
        print(f"\n[{index}/{args.n}] picking a scenario…", flush=True)
        try:
            seed = pick_seed(rng)
            if seed.get("original_index") in seen_indices:
                print("    duplicate scenario, redrawing", flush=True)
                continue
            plan = sample_plan(rng, None, [])
            item_id = f"soda_{seed.get('original_index')}"
            print(f"    {item_id}: {seed['speaker_a']} / {seed['speaker_b']} · "
                  f"{len(plan)} planned", flush=True)
            if args.verbose:
                print(f"    {seed['narrative'][:150]}", flush=True)

            written = write_transcript(openai_client, seed, plan, args.writer_model,
                                       args.effort, args.verbose)
            if written is None:
                print("    could not write a valid transcript, skipping", flush=True)
                seen_indices.add(seed.get("original_index"))
                continue

            record = {"item_id": item_id, "seed": seed, "plan": plan, **written}
            paths = voice_turns(eleven_client, record, args.dir, swap=index % 2 == 0)
            print(f"    voiced {len(paths)} turns", flush=True)

            if args.skip_verify:
                record.update({"vocalizations_dropped": [], "labels_verified": False})
            else:
                kept, dropped, verdicts = verify_labels(
                    openai_client, eleven_client, record, paths, args.verifier_model,
                    args.runs, args.retakes, True)
                record.update({
                    "vocalizations": kept,
                    "vocalizations_dropped": dropped,
                    "labels_verified": True,
                    "verification": {
                        "model": args.verifier_model, "runs_per_turn": args.runs,
                        "retakes_allowed": args.retakes,
                        "rule": "kept when a majority of parseable votes name the sound; "
                                "a failing turn is re-rendered and retried",
                        "verdicts": verdicts,
                    },
                })
                print(f"    verified: {len(kept)}/{len(plan)} labels kept", flush=True)

            # sew after verification, so the mix uses the final take of every turn
            final, rows, total = sew_item(record, paths, args.dir)
            record.pop("_voices", None)
            record.update({
                "audio": str(final.relative_to(REPO)),
                "audio_seconds": round(total, 3),
                "segments": rows,
            })
            print(f"    sewed: {timestamp(total)}", flush=True)

            records.append(record)
            seen_indices.add(seed.get("original_index"))
        except Exception as exc:
            print(f"    failed: {type(exc).__name__}: {exc}", flush=True)
            continue

        dataset_path.write_text(json.dumps({
            "built_at": datetime.now(timezone.utc).isoformat(),
            "seed_dataset": "allenai/soda",
            "writer_model": args.writer_model,
            "tts_model": TTS_MODEL,
            "verifier_model": args.verifier_model,
            "verify_runs": args.runs,
            "turns_per_item": N_TURNS,
            "vocalization_types": VOC_TYPES,
            "rng_seed": args.seed,
            "n_items": len(records),
            "results": records,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        # rewritten every item, not just at the end, so the readable transcript exists
        # while a long build is still running
        (args.dir / "dataset.md").write_text(
            render_dataset_markdown(records), encoding="utf-8")

    (args.dir / "dataset.md").write_text(render_dataset_markdown(records), encoding="utf-8")

    planned = sum(len(r["plan"]) for r in records)
    kept = sum(len(r["vocalizations"]) for r in records)
    kept_types = Counter(v["vocalization"] for r in records for v in r["vocalizations"])
    planned_types = Counter(p["vocalization"] for r in records for p in r["plan"])

    print("\n" + "=" * 70)
    print(f"{len(records)} items · {kept}/{planned} labels survived "
          f"({100 * kept / planned:.0f}%)" if planned else "no labels")
    for voc in VOC_TYPES:
        p, k = planned_types.get(voc, 0), kept_types.get(voc, 0)
        print(f"  {voc:9} {k:>3}/{p:<3} " + (f"{100 * k / p:.0f}%" if p else "—"))
    print(f"\nwrote {dataset_path}")
    print(f"      {args.dir / 'dataset.md'}")


if __name__ == "__main__":
    main()
