"""Listen to each rendered turn and prune vocalization labels that are not actually audible.

TTS does not reliably produce what a tag asks for. A turn labelled [weary sigh] may come out
as ordinary speech with a slightly long breath, and a label the audio does not support is
worse than no label — it scores a model wrong for not hearing something that is not there.

So every vocalization turn is played to gpt-realtime-2.1 on its own — the single turn, not
the sewn conversation, so one sound is judged in isolation rather than competing with eleven
others. Five independent sessions per turn. If a majority do not identify the intended sound,
the label is dropped from the gold.

The question is a forced-choice identification, not "do you hear a sigh?". Asking about the
target directly invites agreement; asking what sound is present, if any, makes the model
commit. A turn only keeps its label when the sound is identifiable without being named.

Turns with no planned vocalization are checked too, in the other direction: if the model
reliably hears a sound where none was scripted, that is worth knowing before the audio is
used as ground truth.

Writes items_verified.json — the same records with unverifiable labels removed, the votes
attached, and the dropped labels preserved for inspection.

Usage:
    python soda_scatter/verify_audio.py
    python soda_scatter/verify_audio.py --runs 5 --check-quiet-turns
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "logo_sketch"))
load_dotenv(REPO / ".env")

from eval_realtime import (  # noqa: E402
    PCM_RATE, event_error_message, mp3_to_pcm16_24k, recv_event, wait_for,
    AUDIO_TRANSCRIPT_DELTA, AUDIO_TRANSCRIPT_DONE, TEXT_DELTA, TEXT_DONE,
)

DEFAULT_ITEMS = HERE / "out" / "items.json"
DEFAULT_OUT = HERE / "out" / "items_verified.json"

MODEL = "gpt-realtime-2.1"
RUNS = 5
SESSION_TIMEOUT = 120.0
MAX_OUTPUT_TOKENS = 120

VOC_TYPES = ["laughter", "yawn", "sob", "sigh"]

# Forced choice over the four categories plus "other" and "none". The target is never named,
# so a label survives only if the sound is identifiable on its own terms.
#
# "crying" is offered alongside "sob" because the audio is authored as crying — the tag
# [crying] renders where [sob] does not — and a listener naturally reports crying. Scoring
# folds the two together, so the option list matches what is actually in the audio rather
# than forcing the label's vocabulary onto the listener.
INSTRUCTIONS = (
    "You will hear one short clip of a single person speaking. Your job is to report "
    "whether the speaker also makes a non-speech vocal sound in the clip — laughing, "
    "yawning, crying, or sighing.\n\n"
    "Judge only what you actually hear. Do not infer from the words or the situation what "
    "sound would fit; many clips contain no vocal sound at all, and reporting one that is "
    "not there is the main error to avoid.\n\n"
    "Answer in exactly this format, two lines and nothing else:\n"
    "SOUND: <laughter | yawn | crying | sigh | other | none>\n"
    "CLARITY: <clear | faint | none>\n\n"
    "Use `other` only for a clear non-speech vocal sound that is none of the four. Use "
    "`none` when the clip is only speech and breathing."
)

# what counts as naming each category, so "crying" verifies a sob label and "laugh"
# verifies laughter
ALIASES = {
    "laughter": {"laughter", "laugh", "laughing", "chuckle", "chuckling", "giggle"},
    "yawn": {"yawn", "yawning"},
    "sob": {"sob", "sobbing", "crying", "cry", "weeping", "tears"},
    "sigh": {"sigh", "sighing", "exhale"},
}


def names_target(vote: str | None, target: str) -> bool:
    return bool(vote) and vote.lower() in ALIASES[target]

QUESTION = "Does the speaker make a non-speech vocal sound in this clip?"

SOUND_RE = re.compile(r"SOUND\s*:\s*([a-z]+)", re.I)
CLARITY_RE = re.compile(r"CLARITY\s*:\s*([a-z]+)", re.I)


def ask_once(client: OpenAI, pcm: bytes, model: str) -> dict:
    """One fresh session, one clip, one answer."""
    deadline = time.time() + SESSION_TIMEOUT
    conn = client.realtime.connect(model=model).enter()
    try:
        conn.session.update(session={
            "type": "realtime",
            "instructions": INSTRUCTIONS,
            "output_modalities": ["text"],
            "audio": {"input": {"format": {"type": "audio/pcm", "rate": PCM_RATE},
                                "turn_detection": None}},
        })
        wait_for(conn, deadline, "session.updated")
        conn.conversation.item.create(item={
            "type": "message", "role": "user",
            "content": [
                {"type": "input_audio", "audio": base64.b64encode(pcm).decode("ascii")},
                {"type": "input_text", "text": QUESTION},
            ],
        })
        conn.response.create(response={"output_modalities": ["text"],
                                       "max_output_tokens": MAX_OUTPUT_TOKENS})
        texts: list[str] = []
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError("timed out waiting for response.done")
            event = recv_event(conn, remaining)
            etype = getattr(event, "type", None)
            if etype == "error":
                raise RuntimeError(event_error_message(event))
            if etype in TEXT_DELTA or etype in AUDIO_TRANSCRIPT_DELTA:
                texts.append(getattr(event, "delta", "") or "")
            elif etype in TEXT_DONE:
                final = getattr(event, "text", None)
                if final:
                    texts = [final]
            elif etype in AUDIO_TRANSCRIPT_DONE:
                final = getattr(event, "transcript", None)
                if final:
                    texts = [final]
            elif etype == "response.done":
                break
    finally:
        try:
            conn.close()
        except Exception:
            pass

    raw = "".join(texts).strip()
    sound = SOUND_RE.search(raw)
    clarity = CLARITY_RE.search(raw)
    return {
        "raw": raw,
        "sound": sound.group(1).lower() if sound else None,
        "clarity": clarity.group(1).lower() if clarity else None,
    }


def poll(client: OpenAI, pcm: bytes, model: str, runs: int) -> list[dict]:
    votes: list[dict] = []
    for _ in range(runs):
        for attempt in range(1, 4):
            try:
                votes.append(ask_once(client, pcm, model))
                break
            except Exception as exc:
                if attempt == 3:
                    votes.append({"raw": "", "sound": None, "clarity": None,
                                  "error": str(exc)})
                else:
                    time.sleep(2 ** attempt)
    return votes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=Path, default=DEFAULT_ITEMS)
    parser.add_argument("--timing", type=Path,
                        help="timing json with per-turn paths (default: derived from item id)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--runs", type=int, default=RUNS)
    parser.add_argument("--check-quiet-turns", action="store_true",
                        help="also test turns with no planned vocalization, for false positives")
    args = parser.parse_args()
    args.items = args.items.resolve()
    args.out = args.out.resolve()
    return args


def main() -> None:
    args = parse_args()
    data = json.loads(args.items.read_text(encoding="utf-8"))
    record = data["results"][args.index]
    item_id = record["item_id"]

    timing_path = (args.timing or HERE / "out" / f"{item_id}_timing.json").resolve()
    if not timing_path.exists():
        raise SystemExit(f"missing {timing_path}; run make_audio.py first")
    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    path_by_turn = {
        row["turn"]: row["path"] for row in timing["segments"]
        if row.get("kind") == "line" and row.get("path")
    }
    if not path_by_turn:
        raise SystemExit(
            f"{timing_path} has no per-turn paths; re-run make_audio.py to record them")

    entries = sorted(record["vocalizations"], key=lambda e: e["turn"])
    quiet_turns = [t["turn"] for t in record["turns"]
                   if t["turn"] not in {e["turn"] for e in entries}]
    print(f"{item_id} · {args.model} · {args.runs} runs per turn", flush=True)
    print(f"  {len(entries)} labelled turn(s)"
          + (f" + {len(quiet_turns)} quiet turn(s)" if args.check_quiet_turns else ""),
          flush=True)

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)

    kept: list[dict] = []
    dropped: list[dict] = []
    verdicts: list[dict] = []

    for entry in entries:
        turn = entry["turn"]
        target = entry["vocalization"]
        pcm = mp3_to_pcm16_24k(REPO / path_by_turn[turn])
        votes = poll(client, pcm, args.model, args.runs)
        heard = Counter(v["sound"] for v in votes if v.get("sound"))
        hits = sum(1 for v in votes if names_target(v.get("sound"), target))
        usable = sum(1 for v in votes if v.get("sound"))
        verified = usable > 0 and hits * 2 > usable

        verdict = {
            "turn": turn, "target": target, "audio_tag": entry["audio_tag"],
            "audio": path_by_turn[turn],
            "hits": hits, "runs": len(votes), "usable_votes": usable,
            "votes": [v.get("sound") for v in votes],
            "clarity": [v.get("clarity") for v in votes],
            "verified": verified,
        }
        verdicts.append(verdict)
        (kept if verified else dropped).append(entry)

        tally = ", ".join(f"{k}x{v}" for k, v in heard.most_common()) or "no parseable votes"
        print(f"  t{turn:>2} {target:9} {hits}/{usable} -> "
              f"{'KEEP' if verified else 'DROP'}   [{tally}]", flush=True)

    quiet_verdicts: list[dict] = []
    if args.check_quiet_turns:
        print("\nquiet turns (expect none):", flush=True)
        for turn in quiet_turns:
            pcm = mp3_to_pcm16_24k(REPO / path_by_turn[turn])
            votes = poll(client, pcm, args.model, args.runs)
            heard = Counter(v["sound"] for v in votes if v.get("sound"))
            usable = sum(1 for v in votes if v.get("sound"))
            spurious = usable - heard.get("none", 0)
            quiet_verdicts.append({
                "turn": turn, "runs": len(votes), "usable_votes": usable,
                "votes": [v.get("sound") for v in votes],
                "majority_heard_something": spurious * 2 > usable if usable else False,
            })
            tally = ", ".join(f"{k}x{v}" for k, v in heard.most_common()) or "unparseable"
            flag = "  <-- false positive" if spurious * 2 > usable else ""
            print(f"  t{turn:>2} {'':9} [{tally}]{flag}", flush=True)

    verified_record = {
        **record,
        "vocalizations": kept,
        "vocalizations_dropped": dropped,
        "labels_verified": True,
        "verification": {
            "model": args.model, "runs_per_turn": args.runs,
            "rule": "a label is kept when a strict majority of parseable votes name it",
            "verdicts": verdicts,
            "quiet_turns": quiet_verdicts,
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({
            **{k: v for k, v in data.items() if k != "results"},
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "verifier": args.model,
            "results": [verified_record],
        }, indent=2, ensure_ascii=False),
        encoding="utf-8")

    print("\n" + "=" * 70)
    print(f"kept    {len(kept)}/{len(entries)} labels")
    if dropped:
        print("dropped: " + ", ".join(
            f"t{e['turn']}={e['vocalization']}" for e in
            sorted(dropped, key=lambda e: e["turn"])))
    surviving = Counter(e["vocalization"] for e in kept)
    print("surviving draw: " + (", ".join(f"{k}x{v}" for k, v in sorted(surviving.items()))
                                or "nothing"))
    print(f"\nwrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
