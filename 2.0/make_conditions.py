"""Stage 9 — the three condition audios, spliced from one set of takes.

    happy    the turns with laughter spliced in
    neutral  the turns alone
    sad      the turns with sighs spliced in, at exactly the same points

Because happy and sad share their slots, both are cut at identical split points and differ
only in which clip sits in the gap. The spoken samples either side of every splice come out
of the same file, so the words are not merely the same text — they are the same audio. That is
what makes a difference between the two conditions attributable to the sound.

A splice lands in the middle of the silence the speaker actually left after the chosen word,
taken from the character-level alignment rather than guessed.

**Every slot is spliced, whatever stage 8 said.** Stage 8's verdicts are recorded per slot in
the manifest rather than used as a filter: the clips that failed were failed almost entirely by
a judge that cannot hear sighs, so dropping them would shrink the sad condition on the strength
of a judge we have since removed from the panel. If a slot ever does need dropping, it goes
from **both** conditions at once — asymmetric dropping would leave happy and sad with different
splice points, which is the one thing this design cannot afford.

Neutral is assembled without the splice gaps, so it is shorter. It is never scored — it exists
to be a comparison in Q1 — so the length difference costs nothing, and adding empty gaps to
match would be a stranger artefact than the difference it removes.

    python 2.0/make_conditions.py
    python 2.0/make_conditions.py --only emb_003
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from make_audio import ALIGNMENT, TURN_DIR, duration_of
from sew import build

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "out"
CONV_DIR = OUT / "audio"
CUT_DIR = OUT / "audio_cuts"
MANIFEST = OUT / "audio_manifest.json"

TURN_GAP = 0.32      # between turns
SPLICE_GAP = 0.18    # between a clip and the words it sits against


def cut(source: Path, start: float, end: float | None, dest: Path) -> Path:
    """A slice of a turn take. Both halves come from the same file, so the samples either
    side of a splice are identical across the conditions that share the split point."""
    import subprocess
    dest.parent.mkdir(parents=True, exist_ok=True)
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
               "-ss", f"{start:.3f}"]
    if end is not None:
        command += ["-to", f"{end:.3f}"]
    command += ["-c:a", "libmp3lame", "-q:a", "2", str(dest)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-400:] or "ffmpeg cut failed")
    return dest


def split_point(words: list[dict], after_word: int) -> float | None:
    """Where to cut, in seconds — the middle of the silence the speaker left after word N."""
    if not words or after_word <= 0 or after_word >= len(words):
        return None
    word = words[after_word - 1]
    if word.get("gap_start") is None:
        return word["end"]
    return (word["gap_start"] + word["gap_end"]) / 2


def assemble(item: dict, condition: str, slots: list[dict], clips: dict,
             alignment: dict, dest: Path) -> dict:
    """One condition. `slots` is empty for neutral; `clips` maps slot order to a clip path."""
    by_turn: dict[int, list[dict]] = {}
    for slot in slots:
        by_turn.setdefault(slot["turn"], []).append(slot)

    pieces: list[tuple[str, object]] = []
    timeline: list[dict] = []
    clock = 0.0

    def add_file(path: Path, kind: str, turn: int, detail: dict | None = None) -> None:
        nonlocal clock
        seconds = duration_of(path)
        timeline.append({"kind": kind, "turn": turn, "start": round(clock, 3),
                         "end": round(clock + seconds, 3), **(detail or {})})
        pieces.append(("file", path))
        clock += seconds

    def add_gap(seconds: float) -> None:
        nonlocal clock
        if pieces:
            pieces.append(("silence", seconds))
            clock += seconds

    for index, turn in enumerate(item["turns"], start=1):
        take = TURN_DIR / turn["take"].split("/")[-1]
        words = alignment[turn["take"]]
        said = turn["text"].split()
        here = sorted(by_turn.get(index, []), key=lambda s: s["after_word"])
        add_gap(TURN_GAP)

        before = [s for s in here if s["after_word"] <= 0]
        inner = [s for s in here if 0 < s["after_word"] < len(words)]
        after = [s for s in here if s["after_word"] >= len(words)]

        for slot in before:
            add_file(clips[slot["order"]], "vocalization", index,
                     {"token": slot["token"], "where": "before the turn",
                      "after_word": 0})
            add_gap(SPLICE_GAP)

        previous, spoken_from = 0.0, 0
        for n, slot in enumerate(inner):
            at = split_point(words, slot["after_word"])
            stem = f"{item['item_id']}_{condition}_t{index:02d}_{n}"
            segment = cut(take, previous, at, CUT_DIR / f"{stem}.mp3")
            add_file(segment, "speech", index,
                     {"speaker": turn["speaker"],
                      "text": " ".join(said[spoken_from:slot["after_word"]])})
            add_gap(SPLICE_GAP)
            add_file(clips[slot["order"]], "vocalization", index,
                     {"token": slot["token"], "where": f"after word {slot['after_word']}",
                      "after_word": slot["after_word"], "cut_at": round(at, 3)})
            add_gap(SPLICE_GAP)
            previous, spoken_from = at, slot["after_word"]

        tail = (cut(take, previous, None,
                    CUT_DIR / f"{item['item_id']}_{condition}_t{index:02d}_tail.mp3")
                if inner else take)
        add_file(tail, "speech", index,
                 {"speaker": turn["speaker"], "text": " ".join(said[spoken_from:])})

        for slot in after:
            add_gap(SPLICE_GAP)
            add_file(clips[slot["order"]], "vocalization", index,
                     {"token": slot["token"], "where": "after the turn",
                      "after_word": slot["after_word"]})

    build(pieces, dest)
    return {"path": str(dest.relative_to(HERE)), "seconds": round(duration_of(dest), 3),
            "vocalizations": sum(1 for e in timeline if e["kind"] == "vocalization"),
            "timeline": timeline}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--drop-unresolved", action="store_true",
                        help="exclude slots whose clips did not pass stage 8, from both "
                             "conditions")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    items = json.loads((OUT / "items.json").read_text())["items"]
    plan = {e["item_id"]: e for e in json.loads((OUT / "plan.json").read_text())["items"]}
    verdict_file = OUT / "clip_verdicts.json"
    verdicts = (json.loads(verdict_file.read_text())["clips"]
                if verdict_file.exists() else [])
    manifest = json.loads((OUT / "clip_manifest.json").read_text())
    alignment = json.loads(ALIGNMENT.read_text())

    status = {v["path"]: v["status"] for v in verdicts}
    clip_rows = {(c["item_id"], c["condition"], c["order"]): c
                 for i in manifest["items"] for c in i["clips"]}

    wanted = [i for i in items if not args.only or i["item_id"] in args.only]
    if args.limit:
        wanted = wanted[: args.limit]

    records, dropped_total = [], 0
    for item in wanted:
        slots = plan[item["item_id"]]["slots"]
        # A slot survives only if both of its clips passed. Dropping asymmetrically would
        # leave happy and sad with different splice points, which is the one thing this
        # design cannot afford.
        kept, dropped = [], []
        for order, slot in enumerate(slots):
            paths = [clip_rows[(item["item_id"], c, order)]["path"]
                     for c in ("happy", "sad")]
            verdict = [status.get(p, "unjudged") for p in paths]
            if args.drop_unresolved and not all(v == "kept" for v in verdict):
                dropped.append(dict(slot, order=order, verdict=verdict))
            else:
                kept.append(dict(slot, order=order, verdict=verdict))
        dropped_total += len(dropped)

        clips = {"happy": {s["order"]: HERE / clip_rows[(item["item_id"], "happy",
                                                         s["order"])]["path"] for s in kept},
                 "sad": {s["order"]: HERE / clip_rows[(item["item_id"], "sad",
                                                       s["order"])]["path"] for s in kept}}
        conditions = {
            "neutral": assemble(item, "neutral", [], {}, alignment,
                                CONV_DIR / f"{item['item_id']}_neutral.mp3"),
            "happy": assemble(item, "happy",
                              [dict(s, token=s["laugh"]) for s in kept], clips["happy"],
                              alignment, CONV_DIR / f"{item['item_id']}_happy.mp3"),
            "sad": assemble(item, "sad",
                            [dict(s, token=s["sigh"]) for s in kept], clips["sad"],
                            alignment, CONV_DIR / f"{item['item_id']}_sad.mp3"),
        }
        records.append({"item_id": item["item_id"], "situation": item["situation"],
                        "situation_third_person": item["situation_third_person"],
                        "turns": item["turns"], "slots_used": len(kept),
                        "slots_unverified": sum(1 for s in kept
                                                if any(v != "kept" for v in s["verdict"])),
                        "slots_dropped": dropped, "conditions": conditions})
        print(f"  {item['item_id']} · {len(kept)}/{len(slots)} slots · "
              f"neutral {conditions['neutral']['seconds']:5.1f}s · "
              f"happy {conditions['happy']['seconds']:5.1f}s · "
              f"sad {conditions['sad']['seconds']:5.1f}s", flush=True)

    if (args.only or args.limit) and MANIFEST.exists():
        previous = json.loads(MANIFEST.read_text()).get("items", [])
        rebuilt = {r["item_id"]: r for r in records}
        records = [rebuilt.pop(r["item_id"], r) for r in previous] + list(rebuilt.values())

    MANIFEST.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "turn_gap": TURN_GAP, "splice_gap": SPLICE_GAP,
        "turn_audio": "1.0/out/audio_turns (stage 6 reused)",
        "note": ("happy and sad share every split point, so their speech is the same audio, "
                 "not merely the same words; neutral has no splice gaps and so is shorter"),
        "slot_filter": ("stage 8 verdicts recorded, not applied" if not args.drop_unresolved
                        else "slots failing stage 8 dropped from both conditions"),
        "items": records}, indent=2, ensure_ascii=False) + "\n")
    used = sum(r["slots_used"] for r in records)
    unverified = sum(r["slots_unverified"] for r in records)
    print(f"\n{len(records)} items · {used} slots spliced "
          f"({unverified} of them did not pass stage 8) · {dropped_total} dropped · "
          f"wrote {MANIFEST.name}")


if __name__ == "__main__":
    main()
