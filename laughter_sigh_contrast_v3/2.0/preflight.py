"""Play every provider a real sentence and require the words back, before trusting a verdict.

This is 1.0's most expensive lesson. Grok's 190 clip verdicts were collected while its audio
was never arriving: it answered every question confidently, and "I heard no laughter" is
indistinguishable from "I heard nothing" unless you ask it to repeat words it should have
heard. A model that cannot echo a sentence it was just played is in no position to say whether
a clip contains a sigh, and everything it says looks exactly like data.

Run this before each collection pass, not once at the start.

    python 2.0/preflight.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import providers as P

HERE = Path(__file__).resolve().parent
FAMILY = HERE.parent          # laughter_sigh_contrast/, holding both versions
REPO = FAMILY.parent         # the repository root, where .env and archive/ live

QUESTION = ("You will hear one short clip of a person speaking. Write down the words you "
            "heard, exactly, and nothing else. If you heard no audio at all, reply "
            "NO AUDIO.")
PASS_OVERLAP = 0.5      # half the content words is plenty to prove the audio arrived


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", (text or "").lower()) if len(w) > 3}


def main() -> None:
    items = json.loads((HERE / "out" / "items.json").read_text())["items"]
    item = items[0]
    turn = item["turns"][0]
    clip = FAMILY / "1.0" / "out" / "audio_turns" / turn["take"].split("/")[-1]
    expected = words(turn["text"])
    print(f"clip: {clip.name}\nsaid: {turn['text']}\n")

    failures = []
    for provider in P.PROVIDERS:
        try:
            answer = P.ask(provider, clip, QUESTION)
        except Exception as exc:                        # noqa: BLE001 - reported below
            print(f"  {provider:8} FAILED  {type(exc).__name__}: {str(exc)[:90]}")
            failures.append(provider)
            continue
        heard = words(answer)
        overlap = len(heard & expected) / max(1, len(expected))
        verdict = "ok" if overlap >= PASS_OVERLAP else "NO AUDIO REACHING IT"
        if overlap < PASS_OVERLAP:
            failures.append(provider)
        print(f"  {provider:8} {overlap:4.0%} of the words · {verdict}")
        print(f"           {(answer or '').strip()[:110]!r}")

    if failures:
        print(f"\n{len(failures)} provider(s) failed: {', '.join(failures)}")
        print("Do not collect verdicts from a provider that cannot echo a sentence.")
        sys.exit(1)
    print("\nall providers hear speech")


if __name__ == "__main__":
    main()
