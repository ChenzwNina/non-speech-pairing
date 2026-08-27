"""The model joins the conversation as a third participant and takes its turn.

Different task shape from the earlier probes. It is not describing the audio and not playing
one of the two speakers — it is a third person standing there who now has to say something.

The test is register. A frames their own misfortune as funny by laughing through the
sentence; B laughs and mocks. Both laughs establish that this is banter, not a complaint. A
third party who reads that joins in. A third party who missed it offers sympathy — which is
kind, socially wrong here, and exactly the accommodating default these models fall into.

Only one question is asked: the turn itself. Nothing else is put in front of the model, so
the reply is not shaped by having first been made to reason about tone — and the standing
role-play instruction no longer competes with an analysis question, which is what made the
earlier follow-ups get answered in character.

Usage:
    python missed_train_sketch/eval_realtime.py --runs 4
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "logo_sketch"))
load_dotenv(REPO / ".env")

import eval_realtime as ev  # noqa: E402  — realtime session plumbing

DEFAULT_AUDIO = HERE / "out" / "missed_train.mp3"
DEFAULT_OUT = HERE / "out" / "eval_realtime.json"
MODEL = "gpt-realtime-2.1"

ev.INSTRUCTIONS = (
    "You are one of three people in a conversation. The other two are A and B, and you are "
    "standing there with them as part of the group.\n\n"
    "You will hear A say something and then B respond. After that it is your turn to speak, "
    "as yourself, the third person in the group.\n\n"
    "When you take your turn, say only what you would actually say out loud — one or two "
    "sentences, the way a person talks. Do not describe the recording, do not narrate, do "
    "not explain yourself, and do not mention that you are an AI. Just say your line."
)

ev.QUESTIONS = [
    (
        "your_turn",
        "It's your turn now. What do you say?",
    ),
]

# crude register probes over the model's actual turn, reported alongside the raw text
TEASE_RE = re.compile(
    r"(?i)\b(classic|of course|typical|never|again|always|surprise|record|"
    r"cardio|training|marathon|at least you got|next time try|"
    r"speedrun|personal best|athlete|olympic)\b|\bha+\b|😂|😄"
)
SYMPATHY_RE = re.compile(
    r"(?i)\b(sorry|that sucks|that's rough|too bad|unlucky|shame|"
    r"are you okay|hope you|frustrating|annoying|bummer)\b"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, default=DEFAULT_AUDIO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--runs", type=int, default=8)
    parser.add_argument("--voice", default="marin", help="voice the model speaks its turn in")
    parser.add_argument("--reply-dir", type=Path,
                        help="where to save the model's spoken turns (default: beside --out)")
    parser.add_argument("--no-save-audio", action="store_true",
                        help="text-only output, do not record the model speaking")
    args = parser.parse_args()
    args.audio = args.audio.resolve()
    args.out = args.out.resolve()
    args.reply_dir = (args.reply_dir or args.out.parent / f"replies_{args.out.stem}").resolve()
    return args


def main() -> None:
    args = parse_args()
    if not args.audio.exists():
        raise SystemExit(f"missing audio: {args.audio}")

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)

    pcm = ev.mp3_to_pcm16_24k(args.audio)
    seconds = len(pcm) / (ev.PCM_RATE * 2)
    print(f"{args.audio.name} · {seconds:.1f}s · {args.model} · {args.runs} run(s)", flush=True)

    runs: list[dict] = []
    for run_index in range(1, args.runs + 1):
        print(f"\n{'=' * 78}\nRUN {run_index}\n{'=' * 78}", flush=True)
        try:
            answers = ev.run_session(
                client, pcm, args.model,
                capture_audio=not args.no_save_audio, voice=args.voice,
            )
        except Exception as exc:
            print(f"  failed: {exc}", flush=True)
            runs.append({"run": run_index, "error": f"{type(exc).__name__}: {exc}"})
            continue
        turn = next((a["answer"] for a in answers if a["key"] == "your_turn"), "")
        register = {
            "teasing_markers": bool(TEASE_RE.search(turn)),
            "sympathy_markers": bool(SYMPATHY_RE.search(turn)),
        }
        # keep the spoken turn: how it is said carries register that the transcript loses
        saved: list[str] = []
        for item in answers:
            spoken = item.pop("audio", None)
            if spoken:
                dest = args.reply_dir / f"run{run_index:02d}_{item['key']}.mp3"
                ev.pcm16_to_mp3(spoken, dest)
                item["audio_file"] = str(dest.relative_to(REPO))
                saved.append(item["audio_file"])
        for item in answers:
            print(f"\n[{item['key']}]\n{item['answer']}", flush=True)
        if saved:
            print(f"\n  saved: {', '.join(Path(p).name for p in saved)}", flush=True)
        print(f"  register: {register}", flush=True)
        runs.append({"run": run_index, "answers": answers, "register": register})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({
            "model": args.model,
            "audio": str(args.audio.relative_to(REPO)),
            "audio_seconds": round(seconds, 2),
            "instructions": ev.INSTRUCTIONS,
            "questions": [{"key": k, "question": q} for k, q in ev.QUESTIONS],
            "reply_audio_dir": str(args.reply_dir.relative_to(REPO)),
            "reply_voice": None if args.no_save_audio else args.voice,
            "design_note": (
                "A laughs through their own sentence and B mocks, so the register is banter; "
                "joining in is correct and sympathy is a misread"
            ),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "runs": runs,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    ok = [r for r in runs if "register" in r]
    if ok:
        teased = sum(1 for r in ok if r["register"]["teasing_markers"])
        symp = sum(1 for r in ok if r["register"]["sympathy_markers"])
        print("\n" + "=" * 78)
        print(f"turns with teasing markers  : {teased}/{len(ok)}")
        print(f"turns with sympathy markers : {symp}/{len(ok)}")
    print(f"\nwrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
