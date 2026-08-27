"""Render the missed-train exchange twice from ONE set of takes: with laughter, and without.

    A: "I ran all the way to the station—" [laugh] "—and I still missed the train."
    B: [laugh] "Oh no— you and trains, honestly. Every single time."

The point of the segmented build is the control. Each line is synthesized in pieces, with
the laughter in its own piece, so the no-laughter version reuses the *identical* speech audio
and simply drops the laugh segments. Nothing else changes — same take, same prosody, same
timing. An earlier version of this script synthesized the two conditions separately, which
meant the speech differed too (A's line came out 4.72s with laughter and 3.44s without), so
any behavioural difference could have come from delivery rather than from laughter.

The cost of excisability: A's laugh is a discrete burst at the clause boundary rather than
laughter running through the words. True speech-laughter lives in the phonation and cannot
be cut out without re-synthesizing, so it is unavailable if the control has to share audio.

B's tone is affectionate teasing, not a put-down — "you and trains, honestly" rather than
"you have never once made a train in your life." The register being tested is friends
joking, and a line with real bite invites a third party to defend A on the merits, which
confounds register-matching with conflict de-escalation.

Both files are written in one run, so they can never drift apart.

Usage:
    python missed_train_sketch/make_audio.py
    python missed_train_sketch/make_audio.py --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types.model_settings_response_model import ModelSettingsResponseModel

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "logo_sketch"))
load_dotenv(REPO / ".env")

from make_audio import build, duration_of, timestamp  # noqa: E402

OUT_DIR = HERE / "out"
SEG_DIR = OUT_DIR / "segments_warm"
FINAL_LAUGH = OUT_DIR / "missed_train_warm_laughter.mp3"
FINAL_PLAIN = OUT_DIR / "missed_train_warm_plain.mp3"
TRANSCRIPT = OUT_DIR / "missed_train_warm_transcript.md"
TIMING = OUT_DIR / "timing_warm.json"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"

VOICES = {"A": "s3TPKV1kjDlVtZbl4Ksh", "B": "aKw9UnnjRq5scbeeGI7Z"}
STABILITY = {"A": 0.3, "B": 0.3}

TURN_GAP = 0.28      # between A's turn and B's
CLAUSE_GAP = 0.10    # around a laugh burst inside a turn
SEAM_GAP = 0.12      # where a laugh was removed, so the clauses do not jam together

# (segment_id, speaker, text, is_laughter)
SEGMENTS: list[tuple[str, str, str, bool]] = [
    ("a1", "A", "I ran all the way to the station—", False),
    ("a_laugh", "A", "[laughs] hah— hahaha—", True),
    ("a2", "A", "and I still missed the train.", False),
    ("b_laugh", "B", "[laughs warmly] ahahaha—", True),
    ("b1", "B", "Oh no— you and trains, honestly. Every single time.", False),
]

TURN_OF = {"a1": "A", "a_laugh": "A", "a2": "A", "b_laugh": "B", "b1": "B"}


def synthesize(client: ElevenLabs, text: str, speaker: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    audio = b"".join(
        client.text_to_speech.convert(
            voice_id=VOICES[speaker], text=text, model_id=MODEL,
            output_format=OUTPUT_FORMAT,
            voice_settings=ModelSettingsResponseModel(stability=STABILITY[speaker]),
        )
    )
    dest.write_bytes(audio)


def assemble(keep_laughter: bool, paths: dict[str, Path]) -> list[tuple[str, object]]:
    """Lay out the pieces, inserting a turn gap between speakers.

    Where a laugh is dropped, a short seam gap replaces it so the surrounding clauses do not
    butt straight together.
    """
    chosen = [s for s in SEGMENTS if keep_laughter or not s[3]]
    pieces: list[tuple[str, object]] = []
    previous_turn: str | None = None
    dropped_before = False

    for seg_id, speaker, _text, is_laugh in chosen:
        turn = TURN_OF[seg_id]
        if previous_turn is None:
            gap = 0.0
        elif turn != previous_turn:
            gap = TURN_GAP
        elif dropped_before:
            gap = SEAM_GAP
        else:
            gap = CLAUSE_GAP
        if gap > 0:
            pieces.append(("silence", gap))
        pieces.append(("file", paths[seg_id]))
        previous_turn = turn
        dropped_before = False

        if not keep_laughter:
            # note whether the next segment follows an excised laugh
            index = [s[0] for s in SEGMENTS].index(seg_id)
            following = SEGMENTS[index + 1: index + 2]
            dropped_before = bool(following and following[0][3])

    return pieces


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    laughs = [s for s in SEGMENTS if s[3]]
    print(
        f"{len(SEGMENTS)} segment(s), {len(laughs)} of them laughter · "
        "one set of takes, two renders",
        flush=True,
    )

    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")
    client = ElevenLabs(api_key=key)

    paths: dict[str, Path] = {}
    for seg_id, speaker, text, is_laugh in SEGMENTS:
        path = SEG_DIR / f"{seg_id}.mp3"
        if not path.exists() or args.overwrite:
            synthesize(client, text, speaker, path)
            time.sleep(0.25)
        paths[seg_id] = path
        mark = "LAUGH" if is_laugh else "     "
        print(f"  {seg_id:8} {speaker}  {mark}  {duration_of(path):5.2f}s  {text}", flush=True)

    build(assemble(True, paths), FINAL_LAUGH)
    build(assemble(False, paths), FINAL_PLAIN)
    with_laughter, without = duration_of(FINAL_LAUGH), duration_of(FINAL_PLAIN)

    lines = [
        "# Missed the train — warm version",
        "",
        "Two renders from one set of takes. The speech segments are byte-identical between",
        "them; the laughter version simply includes two extra segments.",
        "",
        f"- **with laughter** `{FINAL_LAUGH.name}` — {timestamp(with_laughter)}",
        f"- **laughter removed** `{FINAL_PLAIN.name}` — {timestamp(without)}",
        f"- difference: **{with_laughter - without:.2f}s**, which is the laughter",
        "",
        "| segment | speaker | laughter | seconds | text |",
        "| --- | --- | --- | --- | --- |",
    ]
    for seg_id, speaker, text, is_laugh in SEGMENTS:
        lines.append(
            f"| `{seg_id}` | {speaker} | {'yes' if is_laugh else ''} | "
            f"{duration_of(paths[seg_id]):.2f} | {text.replace('|', '-')} |"
        )
    TRANSCRIPT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    TIMING.write_text(
        json.dumps({
            "with_laughter_seconds": round(with_laughter, 3),
            "laughter_removed_seconds": round(without, 3),
            "laughter_seconds": round(with_laughter - without, 3),
            "voices": VOICES, "stability": STABILITY,
            "turn_gap": TURN_GAP, "clause_gap": CLAUSE_GAP, "seam_gap": SEAM_GAP,
            "segments": [
                {"id": s[0], "speaker": s[1], "text": s[2], "is_laughter": s[3],
                 "seconds": round(duration_of(paths[s[0]]), 3)}
                for s in SEGMENTS
            ],
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nwith laughter    {FINAL_LAUGH.name}  {timestamp(with_laughter)}")
    print(f"laughter removed {FINAL_PLAIN.name}  {timestamp(without)}")
    print(f"difference       {with_laughter - without:.2f}s of laughter")
    print(f"transcript: {TRANSCRIPT}", flush=True)


if __name__ == "__main__":
    main()
