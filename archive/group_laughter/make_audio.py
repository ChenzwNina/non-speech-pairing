"""One scene, two conditions: the room laughs with the story, or nobody does.

    A: "I get to the airport three hours early, for once in my life—" [chuckles]
       "—sitting there feeling proud of myself—" [chuckles]
       "—and then I look up at the board. Wrong airport."
       [A and B laugh together]
    A: "I just stood there holding my little coffee."
       [B giggles]

Speaker B never says a word. That is deliberate: in the first version B had a line — "Of
course it did. Only you." — and the model kept answering "Only me?", taking a remark aimed at
A as aimed at itself. A third person in the room cannot tell who "you" is. With B reduced to
laughter there is nothing to misaddress, and B's only contribution is the thing under test.

The laughs are separate takes, so the plain condition reuses the *same* speech and simply
drops them. The joint laugh is A's and B's takes mixed with B entering a beat later, not
concatenated — people laughing together overlap, and a tidy hand-off would sound like a
recording of two people taking turns.

Note what the plain condition therefore is: A recounting a bad afternoon deadpan, to a room
that makes no sound at all. B is not merely un-amused, B is inaudible. That is the honest
counterfactual to "B only laughs", but it does mean the conditions differ in how many people
are audibly present, which a model could in principle notice.

Usage:
    python group_laughter/make_audio.py
    python group_laughter/make_audio.py --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types.model_settings_response_model import ModelSettingsResponseModel
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "logo_sketch"))
load_dotenv(REPO / ".env")

from make_audio import build, duration_of  # noqa: E402

OUT_DIR = HERE / "out"
SEG_DIR = OUT_DIR / "segments"
LAUGH = OUT_DIR / "wrong_airport_laughter.mp3"
PLAIN = OUT_DIR / "wrong_airport_plain.mp3"
MANIFEST = OUT_DIR / "audio.json"

TTS_MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"
ASR_MODEL = "whisper-1"

VOICES = {"A": "s3TPKV1kjDlVtZbl4Ksh", "B": "aKw9UnnjRq5scbeeGI7Z"}
STABILITY = 0.3

TURN_GAP = 0.28      # into and out of B's laughter
CLAUSE_GAP = 0.12    # around a chuckle inside A's own turn
SEAM_GAP = 0.16      # where a laugh was removed, so the clauses do not jam together
JOINT_OFFSET = 0.32  # how long after A that B joins in

# kind: speech | laugh | joint. `joint` mixes the two takes instead of playing them in turn.
SEGMENTS: list[dict] = [
    {"id": "a1", "speaker": "A", "kind": "speech",
     "text": "So I get to the airport three hours early. For once in my life."},
    {"id": "a_chuckle1", "speaker": "A", "kind": "laugh", "text": "[chuckles] heh—"},
    {"id": "a2", "speaker": "A", "kind": "speech",
     "text": "And I'm sitting at the gate feeling very proud of myself."},
    {"id": "a_chuckle2", "speaker": "A", "kind": "laugh", "text": "[chuckles softly] hah—"},
    {"id": "a3", "speaker": "A", "kind": "speech",
     "text": "And then I look up at the board. Wrong airport. My flight was going out of "
             "the other one."},
    {"id": "joint", "speaker": "A+B", "kind": "joint",
     "text": {"A": "[laughs happily] hahahaha", "B": "[laughs warmly] hahahaha—ha"}},
    {"id": "a4", "speaker": "A", "kind": "speech",
     "text": "I just stood there holding my little coffee."},
    {"id": "b_giggle", "speaker": "B", "kind": "laugh", "text": "[giggles] hehehe"},
]


def synthesize(client: ElevenLabs, text: str, speaker: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"".join(client.text_to_speech.convert(
        voice_id=VOICES[speaker], text=text, model_id=TTS_MODEL,
        output_format=OUTPUT_FORMAT,
        voice_settings=ModelSettingsResponseModel(stability=STABILITY),
    )))


def mix(first: Path, second: Path, offset: float, dest: Path) -> None:
    """Overlay two laughs, the second entering `offset` seconds late."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    delay_ms = int(offset * 1000)
    filt = (
        "[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a];"
        f"[1:a]adelay={delay_ms}|{delay_ms},"
        "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[b];"
        # normalize=0 keeps both laughs at full level; amix would otherwise halve them
        "[a][b]amix=inputs=2:duration=longest:normalize=0[out]"
    )
    result = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(first),
         "-i", str(second), "-filter_complex", filt, "-map", "[out]",
         "-c:a", "libmp3lame", "-q:a", "2", str(dest)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-900:] or "ffmpeg mix failed")


def transcribe(client: OpenAI | None, path: Path) -> str | None:
    """Optional audit that each take came out as intended; an ASR outage degrades the
    check rather than blocking the build."""
    if client is None:
        return None
    try:
        with path.open("rb") as handle:
            return client.audio.transcriptions.create(
                model=ASR_MODEL, file=handle).text.strip()
    except Exception as exc:
        print(f"    (no ASR check: {type(exc).__name__})", flush=True)
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")
    eleven = ElevenLabs(api_key=key)
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    openai = OpenAI(api_key=openai_key) if openai_key else None

    rows: list[dict] = []
    for seg in SEGMENTS:
        path = SEG_DIR / f"{seg['id']}.mp3"
        if seg["kind"] == "joint":
            parts = {}
            for who, text in seg["text"].items():
                side = SEG_DIR / f"{seg['id']}_{who}.mp3"
                if not side.exists() or args.overwrite:
                    synthesize(eleven, text, who, side)
                parts[who] = side
            if not path.exists() or args.overwrite:
                mix(parts["A"], parts["B"], JOINT_OFFSET, path)
            detail = {who: round(duration_of(p), 3) for who, p in parts.items()}
        else:
            if not path.exists() or args.overwrite:
                synthesize(eleven, seg["text"], seg["speaker"], path)
            detail = None
        heard = transcribe(openai, path)
        rows.append({**{k: v for k, v in seg.items() if k != "text"},
                     "text": seg["text"], "seconds": round(duration_of(path), 3),
                     "parts": detail, "asr": heard})
        print(f"  {seg['id']:12} {seg['speaker']:3} {duration_of(path):5.2f}s"
              + (f"  asr={heard!r}" if heard else ""), flush=True)

    def assemble(dest: Path, keep_laughter: bool) -> None:
        pieces: list[tuple[str, object]] = []
        previous = None
        for seg in SEGMENTS:
            if not keep_laughter and seg["kind"] in {"laugh", "joint"}:
                continue
            if previous is not None:
                if not keep_laughter:
                    gap = SEAM_GAP
                elif seg["kind"] in {"laugh", "joint"} or previous["kind"] in {"laugh", "joint"}:
                    gap = CLAUSE_GAP if seg["speaker"].startswith("A") else TURN_GAP
                else:
                    gap = CLAUSE_GAP
                pieces.append(("silence", gap))
            pieces.append(("file", SEG_DIR / f"{seg['id']}.mp3"))
            previous = seg
        build(pieces, dest)

    assemble(LAUGH, True)
    assemble(PLAIN, False)

    MANIFEST.write_text(json.dumps({
        "scene": "wrong airport",
        "note": "B never speaks; B's only contribution is laughter",
        "tts_model": TTS_MODEL, "voices": VOICES, "stability": STABILITY,
        "gaps": {"turn": TURN_GAP, "clause": CLAUSE_GAP, "seam": SEAM_GAP,
                 "joint_offset": JOINT_OFFSET},
        "segments": rows,
        "laughter": {"path": str(LAUGH.relative_to(REPO)),
                     "seconds": round(duration_of(LAUGH), 3)},
        "plain": {"path": str(PLAIN.relative_to(REPO)),
                  "seconds": round(duration_of(PLAIN), 3)},
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nlaughter {duration_of(LAUGH):5.2f}s  {LAUGH.name}")
    print(f"plain    {duration_of(PLAIN):5.2f}s  {PLAIN.name}")


if __name__ == "__main__":
    main()
