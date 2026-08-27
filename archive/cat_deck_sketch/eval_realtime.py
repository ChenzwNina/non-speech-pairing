"""Play the cat-slide sketch to gpt-realtime-2.1 and probe all five laughs.

The logo sketch had one laugh to read. This has five, all the same category, and the test is
whether the model separates them by function rather than lumping them as "they laugh a lot."

    Q1  open — describe what happens. Unprimed. Also the tag-leak check: if eleven_v3 spoke
        an audio tag aloud instead of rendering it, the model will transcribe the tag words
        here and the audio needs rebuilding.
    Q2  the count and the function of each laugh. The question never says how many there
        are, so both segmentation and interpretation are under test.
    Q3  forced discrimination — which two laughs are most unlike each other. A model that
        heard five interchangeable laughs cannot answer this, and a model that read the
        conversation can.

Ground truth: 5 laughs — Maya warm/genuine at 0:05, then Dan nervous at 0:20, sarcastic at
0:35, helpless at 0:45, apologetic at 0:51.

Usage:
    python cat_deck_sketch/eval_realtime.py --runs 3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "logo_sketch"))
load_dotenv(REPO / ".env")

# reuse the realtime session plumbing; questions and instructions are overridden below
import eval_realtime as ev  # noqa: E402

DEFAULT_AUDIO = HERE / "out" / "cat_deck_sketch.mp3"
DEFAULT_OUT = HERE / "out" / "eval_realtime.json"
MODEL = "gpt-realtime-2.1"

ev.INSTRUCTIONS = (
    "You are listening to a short audio recording of a conversation between two coworkers. "
    "Answer the questions you are asked about it. Be specific and concrete, and base what "
    "you say on what you actually hear in the recording."
)

ev.QUESTIONS = [
    (
        "describe",
        "Describe what happens in this conversation.",
    ),
    (
        "each_laugh",
        "In this recording there are several moments where someone laughs. For each one, "
        "say who laughs, roughly when it happens, and what that particular laugh "
        "communicates at that point in the conversation. Treat them separately — they are "
        "not all the same kind of laugh.",
    ),
    (
        "most_different",
        "Of the laughs you just described, which two are the most different from each "
        "other, and what is the difference?",
    ),
]

GROUND_TRUTH = [
    {"laugh_id": "laugh_1_genuine", "speaker": "MAYA", "at": "0:05", "means": "warm genuine amusement at Dan's joke"},
    {"laugh_id": "laugh_2_nervous", "speaker": "DAN", "at": "0:20", "means": "nervous dread on realising he sent the wrong file"},
    {"laugh_id": "laugh_3_sarcastic", "speaker": "DAN", "at": "0:35", "means": "dry sarcasm at the Comic Sans remark"},
    {"laugh_id": "laugh_4_helpless", "speaker": "DAN", "at": "0:45", "means": "suppressed laughter breaking into helpless real laughter"},
    {"laugh_id": "laugh_5_apologetic", "speaker": "DAN", "at": "0:51", "means": "laughing while apologising, knowing it is bad"},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, default=DEFAULT_AUDIO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    args.audio = args.audio.resolve()
    args.out = args.out.resolve()
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
    print(
        f"{args.audio.name} · {seconds:.1f}s · {args.model} · {args.runs} run(s) · "
        f"{len(GROUND_TRUTH)} laughs to find",
        flush=True,
    )

    runs: list[dict] = []
    for run_index in range(1, args.runs + 1):
        print(f"\n{'=' * 78}\nRUN {run_index}\n{'=' * 78}", flush=True)
        try:
            answers = ev.run_session(client, pcm, args.model)
        except Exception as exc:
            print(f"  failed: {exc}", flush=True)
            runs.append({"run": run_index, "error": f"{type(exc).__name__}: {exc}"})
            continue
        for item in answers:
            print(f"\n[{item['key']}]\n{item['answer']}", flush=True)
        runs.append({"run": run_index, "answers": answers})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({
            "model": args.model,
            "audio": str(args.audio.relative_to(REPO)),
            "audio_seconds": round(seconds, 2),
            "instructions": ev.INSTRUCTIONS,
            "questions": [{"key": k, "question": q} for k, q in ev.QUESTIONS],
            "ground_truth": GROUND_TRUTH,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "runs": runs,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nwrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
