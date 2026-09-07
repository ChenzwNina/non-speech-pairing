"""Sew the ElevenLabs per-turn takes into three full dialogues per item.

The renderer (make_audio.py) leaves one file per turn, and three files for the tagged turn:
clean, tag A, tag B. This turns that into the three conversations the benchmark actually asks
a model to listen to:

    <item>__baseline.mp3      the clean takes, in order, no vocalization
    <item>__condition_a.mp3   that same audio with vocalization A cut from its own take and
                              spliced into the clean tagged turn
    <item>__condition_b.mp3   the same for vocalization B

Names and location come from eval_config.yaml — `audio_root` and `audio_path_template` — because
out/audio/<renderer>/ is a handoff the evaluation reads directly (see out/audio/README.md), not
a scratch directory.

WhisperX force-aligns the known words of the tagged turn in both the vocalized take and the
clean take. The vocalization is cut from the silence the vocalized take's words bracket, and
inserted at the clean take's own onset of the same anchor word. Nothing is removed, so every
lexical word is bit-identical across all three files — the clip is the only difference, which
is the whole point of a minimal pair.

Two stages, because only one of them needs a GPU:

    --stage neutral   pure concatenation; no model, no torch, runs anywhere
    --stage sewn      needs WhisperX (torch + wav2vec2); run it where Dia runs
    --stage all       both (default)

    python sew_elevenlabs.py --dry-run                 # plan only, no audio written
    python sew_elevenlabs.py --stage neutral           # the 20 neutral dialogues
    python sew_elevenlabs.py --stage all --device cuda # everything
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import soundfile as sf

from pipeline.audio_ops import AudioClip
from pipeline.extraction import locate_tag
from pipeline.schema import load_items
from pipeline.turn_sew import (CONDITIONS, VARIANT_OF, SewOptions, build_neutral,
                                load_turn_takes, sew_item)

DEFAULT_MANIFEST = "out/audio_turns/elevenlabs/manifest.json"
DEFAULT_TRANSCRIPTS = "out/pairs_spoken.json"
DEFAULT_DEST = "out/audio/elevenlabs"
CONDITION_NAME = {"neutral": "baseline", "a": "condition_a", "b": "condition_b"}
# 128 kbps, matching the takes' own mp3_44100_128.
MP3_COMPRESSION = 0.0


def write_audio(path: Path, samples, sample_rate: int) -> None:
    """Write `samples` as mp3 or WAV, chosen by the suffix.

    The splice itself happens in float arrays and is verified there, so encoding is the last
    step and costs the guarantee nothing: what is checked is that the assembled waveform is the
    baseline plus one clip, before anything is written. mp3 is what eval_config.yaml asks for,
    and lossless copies of 21 minutes of speech are 108 MB against 20 MB.
    """
    clip = AudioClip(samples=samples, sample_rate=sample_rate)
    peak = float(max(abs(clip.samples.min()), abs(clip.samples.max()))) if clip.samples.size else 0.0
    if peak > 1.0:
        raise ValueError(f"refusing to write clipped audio: peak={peak:.4f} > 1.0")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".mp3":
        sf.write(str(path), clip.samples, sample_rate, format="MP3",
                  subtype="MPEG_LAYER_III", compression_level=MP3_COMPRESSION)
    else:
        sf.write(str(path), clip.samples, sample_rate, subtype="PCM_16")

README = """Three conversations per item, {items} items.

  <item>__baseline.{ext}      the clean turn takes in order, no vocalization
  <item>__condition_a.{ext}   that same audio with vocalization A spliced into the tagged turn
  <item>__condition_b.{ext}   the same for B
  clips/                    the extracted vocalizations on their own, with --save-clips

Names and location follow eval_config.yaml (audio_root, audio_path_template) so the evaluation
resolves a stimulus straight from this directory; see ../README.md.

All three files for an item share one waveform and differ only by the inserted clip: the
untagged turns are the same decoded takes, the tagged turn is the same clean take, and the
vocalization is INSERTED rather than swapped in. Nothing is removed, so every lexical word is
bit-identical across neutral and both sewn versions.

The clip is cut from that item's own vocalized take of the tagged turn, at boundaries WhisperX
force-aligned:

  prefix tag   [take start .. onset of the first lexical word]
  inline tag   [end of the word before .. onset of the word after]

and inserted at the clean take's own onset of that same anchor word, followed by {gap:.0f} ms of
silence before the words resume.

Unlike the Dia path, the speaking voice is not a variable here: ElevenLabs was given a pinned
voice_id per speaker, and the clean take of the tagged turn is a sibling generation of the two
vocalized takes.

The splice is done and verified in float arrays, and encoded once at the end, so the guarantee
above is established before anything is written and does not depend on the output format.
manifest.json records every cut window, insert point, clip length and loudness delta, plus any
item the cut could not be made for.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST,
                        help=f"the renderer's manifest (default {DEFAULT_MANIFEST})")
    parser.add_argument("--transcripts", default=None,
                        help="the dataset the takes were rendered from. Default: whatever the "
                             "render manifest says it rendered, which is the only answer that "
                             "cannot pair takes with the wrong dataset.")
    parser.add_argument("--dest", default=DEFAULT_DEST,
                        help=f"where the conversations go (default {DEFAULT_DEST}, which is "
                             "eval_config.yaml's audio_root for this renderer)")
    parser.add_argument("--ext", choices=["mp3", "wav"], default="mp3",
                        help="mp3 (default) is what eval_config.yaml's audio_path_template "
                             "asks for. wav writes the unencoded splice instead, for "
                             "inspection; it is about five times the size.")
    parser.add_argument("--root", default=".",
                        help="directory the manifest's relative take paths are rooted at")
    parser.add_argument("--items", nargs="*", metavar="ITEM_ID",
                        help="only these items (default: every item in the manifest)")
    parser.add_argument("--stage", choices=["neutral", "sewn", "all"], default="all",
                        help="'neutral' needs no model and runs anywhere; 'sewn' needs "
                             "WhisperX. Default 'all'.")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan — tag position, anchor word, source and output "
                             "paths — and write nothing. Never loads a model.")
    parser.add_argument("--device", default="cuda",
                        help="torch device for the aligner (default cuda)")
    parser.add_argument("--align-model", default=None,
                        help="wav2vec2 model name; default is torchaudio's for the language")
    parser.add_argument("--gap-ms", type=float, default=75.0,
                        help="silence inserted after the clip, before the words resume "
                             "(default 75)")
    parser.add_argument("--fade-ms", type=float, default=5.0,
                        help="fade in/out on the clip, to stop clicks (default 5)")
    parser.add_argument("--pad-ms", type=float, default=75.0,
                        help="padding kept around the clip when trimming silence (default 75)")
    parser.add_argument("--threshold-db", type=float, default=-40.0,
                        help="energy floor for the trim (default -40)")
    parser.add_argument("--match-loudness", action="store_true",
                        help="scale the clip toward the clean take's speech RMS (clamped to "
                             "+/-6 dB). Off by default: one pinned voice rendered both takes, "
                             "so the level is already comparable and forcing it would change "
                             "how loud the vocalization actually was. The delta is recorded "
                             "either way.")
    parser.add_argument("--save-clips", action="store_true",
                        help="also write each extracted vocalization on its own, into a clips/ "
                             "subdirectory so it never looks like a stimulus")
    return parser


def _plan_rows(item, takes) -> list[dict]:
    """What --dry-run can know without touching audio: where the tag sits in the transcript."""
    rows = []
    for condition in CONDITIONS:
        variant = VARIANT_OF[condition]
        location = locate_tag(item, condition, renumber_to=1)
        take = takes.variants[variant]
        rows.append({
            "condition": condition, "variant": variant,
            "vocalization": item.voc_a if condition == "condition_a" else item.voc_b,
            "tag": item.tag_a if condition == "condition_a" else item.tag_b,
            "position": location.position, "words_before": location.words_before,
            "take": str(take.path), "take_seconds": take.seconds,
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dest = Path(args.dest)

    takes_by_item = load_turn_takes(args.manifest, root=args.root)
    if args.transcripts is None:
        # The renderer records the dataset it rendered. Trusting that beats defaulting to a
        # fixed filename, which is how a retired dataset gets silently paired with new takes.
        recorded = json.loads(Path(args.manifest).read_text(encoding="utf-8")).get("transcripts")
        args.transcripts = recorded or DEFAULT_TRANSCRIPTS
        print(f"transcripts: {args.transcripts} (from the render manifest)")
    items = {item.item_id: item for item in load_items(args.transcripts)}

    wanted = args.items or sorted(takes_by_item)
    unknown = [i for i in wanted if i not in takes_by_item]
    if unknown:
        print(f"not in the manifest: {', '.join(unknown)}")
        return 2
    missing_transcript = [i for i in wanted if i not in items]
    if missing_transcript:
        print(f"not in {args.transcripts}: {', '.join(missing_transcript)}")
        return 2

    want_neutral = args.stage in ("neutral", "all")
    want_sewn = args.stage in ("sewn", "all")

    if args.dry_run:
        for item_id in wanted:
            takes, item = takes_by_item[item_id], items[item_id]
            print(f"{item_id}  turn {takes.vocalization_turn} (speaker "
                  f"{takes.vocalization_speaker})  gap {takes.gap_seconds}s")
            print(f"  clean takes: {', '.join(p.name for p in takes.clean_paths())}")
            for row in _plan_rows(item, takes):
                anchor = ("first word" if row["position"] == "prefix"
                          else f"word {row['words_before'] + 1}")
                print(f"  {row['variant']}: {row['vocalization']:7s} {row['tag']:11s} "
                      f"{row['position']:6s} cut ends at {anchor:11s} "
                      f"<- {Path(row['take']).name} ({row['take_seconds']}s)")
            if want_neutral:
                print(f"  -> {dest / f'{item_id}__baseline.{args.ext}'}")
            if want_sewn:
                for cond in CONDITIONS:
                    voc = item.voc_a if cond == "condition_a" else item.voc_b
                    print(f"  -> {dest / f'{item_id}__{cond}.{args.ext}'}   ({voc})")
        print(f"\n{len(wanted)} item(s) planned; nothing written (--dry-run)")
        return 0

    options = SewOptions(gap_ms=args.gap_ms, fade_ms=args.fade_ms, pad_ms=args.pad_ms,
                          threshold_db=args.threshold_db, match_loudness=args.match_loudness)

    aligner = None
    if want_sewn:
        # Imported here, not at module scope: --stage neutral and --dry-run must not need torch.
        from pipeline.whisperx_backend import WhisperXAligner, WhisperXConfig
        aligner = WhisperXAligner(WhisperXConfig(device=args.device,
                                                  model_name=args.align_model))
        # WhisperXAligner imports whisperx lazily inside load(), so a missing dependency would
        # otherwise surface once per item, mid-run, looking like a data problem. Load the model
        # up front: it is needed for every item anyway, and it fails here or not at all.
        try:
            aligner.load()
        except Exception as exc:  # noqa: BLE001 - ImportError, CUDA errors, missing weights
            print(f"--stage {args.stage} needs WhisperX, and it could not be loaded on this "
                  f"machine:\n  {type(exc).__name__}: {exc}\n"
                  "The cut depends on forced alignment, so there is no offline substitute for "
                  "it.\nInstall torch + whisperx where the GPU is (see "
                  "requirements-pipeline.txt), or run\n--stage neutral, which needs no model "
                  "and writes the no-vocalization dialogues.")
            return 3

    dest.mkdir(parents=True, exist_ok=True)
    # A run is merged into whatever is already here rather than replacing it: --stage neutral
    # needs no GPU and --stage sewn does, so the two halves are normally produced by separate
    # runs on separate machines, and --items runs on subsets.
    manifest_path = dest / "manifest.json"
    previous: dict = {}
    runs: list[dict] = []
    if manifest_path.exists():
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            old = {}
        runs = list(old.get("runs", []))
        previous = {entry["item_id"]: entry for entry in old.get("items", [])}

    failures: list[str] = []
    written = 0

    for item_id in wanted:
        takes, item = takes_by_item[item_id], items[item_id]
        record: dict = previous.get(item_id) or {"item_id": item_id, "outputs": {},
                                                  "conditions": {}}
        record.update({"item_id": item_id, "vocalization_turn": takes.vocalization_turn,
                        "vocalization_speaker": takes.vocalization_speaker,
                        "gap_seconds": takes.gap_seconds, "issues": []})
        record.setdefault("outputs", {})
        record.setdefault("conditions", {})
        previous[item_id] = record
        try:
            if want_sewn:
                result = sew_item(item, takes, aligner, options)
            else:
                result = build_neutral(takes)
        except Exception as exc:  # noqa: BLE001 - one bad item must not kill the batch
            print(f"{item_id}: FAILED  {type(exc).__name__}: {exc}")
            failures.append(f"{item_id}: {type(exc).__name__}: {exc}")
            record["issues"].append(f"{type(exc).__name__}: {exc}")
            continue

        record["sample_rate"] = result.sample_rate
        if want_neutral:
            path = dest / f"{item_id}__baseline.{args.ext}"
            write_audio(path, result.neutral, result.sample_rate)
            record["outputs"]["neutral"] = {"path": str(path), "condition": "baseline",
                                             "seconds": len(result.neutral) / result.sample_rate}
            written += 1

        # Every condition that got as far as a cut plan is recorded, whether or not it was
        # sewn; a refused one has no file but must still say why in the manifest.
        for variant in sorted(set(result.plans) | set(result.failed)):
            plan = result.plans.get(variant)
            turn = result.turns.get(variant)
            entry: dict = {"condition": f"condition_{variant}",
                            "source_take": str(takes.variants[variant].path),
                            "sewn": variant in result.sewn}
            if plan is not None:
                entry.update({
                    "vocalization": plan.vocalization, "position": plan.position,
                    "words_before": plan.words_before, "anchor_word": plan.anchor_word,
                    "cut": {"start": plan.cut.left, "end": plan.cut.right,
                             "seconds": plan.cut.duration},
                    "insert_at_seconds": plan.insert_at,
                })
            if turn is not None:
                entry.update({
                    "clip_seconds": turn.clip_seconds,
                    "insert_sample": turn.insert_sample,
                    "inserted_samples": turn.inserted_length,
                    "waveform_preserved": turn.preserved,
                    "loudness_delta_db": round(turn.loudness_delta_db, 2),
                    "loudness_applied": bool(args.match_loudness),
                    "issues": turn.issues,
                })
            if variant in result.failed:
                entry["refused"] = result.failed[variant]
            record["conditions"][variant] = entry

        for variant, dialogue in result.sewn.items():
            plan, turn = result.plans[variant], result.turns[variant]
            condition = CONDITION_NAME[variant]
            path = dest / f"{item_id}__{condition}.{args.ext}"
            write_audio(path, dialogue, result.sample_rate)
            written += 1
            if args.save_clips and turn.inserted_length:
                # In a subdirectory, not beside the stimuli: the evaluation resolves a stimulus
                # by filename from this directory, and a clip is not one.
                clip_path = (dest / "clips" /
                              f"{item_id}__{condition}__{plan.vocalization}.{args.ext}")
                start = turn.insert_sample
                write_audio(clip_path, turn.samples[start:start + turn.inserted_length],
                             result.sample_rate)
                written += 1
            record["outputs"][variant] = {
                "path": str(path), "condition": condition,
                "vocalization": plan.vocalization,
                "seconds": len(dialogue) / result.sample_rate}

        record["issues"].extend(result.issues)

        sewn_summary = "  ".join(
            f"{v}:{result.turns[v].clip_seconds:.2f}s@{result.plans[v].insert_at:.2f}s"
            for v in sorted(result.sewn))
        refused_summary = "  ".join(f"{v}:REFUSED" for v in sorted(result.failed))
        summary = "  ".join(p for p in (sewn_summary, refused_summary) if p) or "neutral only"
        print(f"{item_id}  {summary}")

    records = [previous[key] for key in sorted(previous)]
    runs.append({
        "sewn_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage": args.stage,
        "items": wanted,
        "aligner": "whisperx" if want_sewn else None,
        "options": {"gap_ms": args.gap_ms, "fade_ms": args.fade_ms, "pad_ms": args.pad_ms,
                     "threshold_db": args.threshold_db,
                     "match_loudness": args.match_loudness},
    })
    manifest = {
        "source_manifest": args.manifest,
        "transcripts": args.transcripts,
        "runs": runs,
        "items": records,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (dest / "README.txt").write_text(
        README.format(items=len(records), gap=args.gap_ms, ext=args.ext), encoding="utf-8")

    if aligner is not None:
        aligner.unload()

    # Scoped to this run's items: a refusal recorded by an earlier run on other items is
    # history, and must not decide this run's exit code.
    touched = set(wanted)
    refused = [(r["item_id"], variant, entry["refused"])
                for r in records if r["item_id"] in touched
                for variant, entry in r.get("conditions", {}).items()
                if "refused" in entry]
    print(f"\n{written} file(s) -> {dest}/   manifest.json written")
    if refused:
        print(f"{len(refused)} condition(s) refused — no file written for these:")
        for item_id, variant, why in refused:
            print(f"  {item_id} {variant}: {why}")
    if failures:
        print(f"{len(failures)} item(s) failed outright:")
        for row in failures:
            print(f"  {row}")
    # A partial dataset is a non-zero outcome: the caller should not treat it as a clean run.
    return 1 if (refused or failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
