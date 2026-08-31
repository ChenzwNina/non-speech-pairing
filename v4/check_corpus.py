"""Do the corpus recordings read as the emotion they are labelled with?

The whole design assumes a listener hearing `pleasure` will read the conversation one way and
a listener hearing `sadness` another. That assumption is about the recordings, not about the
transcripts, and it is worth testing before forty transcripts are written on top of it.

Some labels carry more risk than others. `pleasure` in corpora of this kind is often a sensual
vocalization, which would sit oddly against a Christmas morning or a camping trip; `achievement`
and `amusement` can be hard to tell apart out of context. If a label does not read as itself,
the pairs that depend on it are unusable however well written they are.

Each clip is played to a model with the eight labels as a closed set. No transcript, no
context — just the sound.

    python v4/check_corpus.py --per-label 2
"""

from __future__ import annotations

import argparse
import json
import random
import re
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import providers as P

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "VocalizationsCorpus"
OUT = HERE / "out"
RESULT = OUT / "corpus_check.json"

LABELS = ("achievement", "amusement", "pleasure", "relief",
          "anger", "disgust", "fear", "sadness")

QUESTION = ("You will hear one short non-speech vocalization made by a person — no words. "
            "Which emotion is it expressing?\n"
            + "\n".join(f"{chr(65+n)}. {label}" for n, label in enumerate(LABELS))
            + "\n\nAnswer with one letter and nothing else.")

_lock = threading.Lock()


def letter(answer: str) -> str | None:
    text = (answer or "").strip()
    match = re.match(r"^\W*(?:answer\s*[:\-]?\s*)?([A-H])\b", text, re.I)
    return match.group(1).upper() if match else None


def ask(provider: str, clip: Path, truth: str) -> dict:
    try:
        answer = P.ask(provider, clip, QUESTION)
        chose = letter(answer)
        heard = LABELS[ord(chose) - 65] if chose else None
    except Exception as exc:                        # noqa: BLE001 - reported in the table
        return {"clip": clip.name, "provider": provider, "truth": truth,
                "error": f"{type(exc).__name__}: {str(exc)[:100]}"}
    return {"clip": clip.name, "provider": provider, "truth": truth,
            "heard": heard, "correct": heard == truth,
            "raw": (answer or "").strip()[:40]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-label", type=int, default=2)
    parser.add_argument("--providers", default="openai")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    picks = []
    for label in LABELS:
        clips = sorted(CORPUS.glob(f"{label}_*.wav"))
        picks += [(c, label) for c in rng.sample(clips, min(args.per_label, len(clips)))]
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]

    print(f"{len(picks)} clips x {len(providers)} listener(s), eight labels to choose from\n")
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(ask, provider, clip, label)
                   for clip, label in picks for provider in providers]
        for future in as_completed(futures):
            rows.append(future.result())

    good = [r for r in rows if "error" not in r]
    per_label = defaultdict(lambda: [0, 0])
    confusion = defaultdict(Counter)
    for r in good:
        per_label[r["truth"]][0] += r["correct"]
        per_label[r["truth"]][1] += 1
        confusion[r["truth"]][r["heard"] or "?"] += 1

    print(f"{'label':13} {'heard as itself':>16}   most common answer when not")
    for label in LABELS:
        right, total = per_label[label]
        others = Counter({k: v for k, v in confusion[label].items() if k != label})
        common = ", ".join(f"{k} x{v}" for k, v in others.most_common(2)) or "-"
        print(f"  {label:11} {right}/{total} = {right/max(1,total):5.0%}   {common}")

    overall = sum(v[0] for v in per_label.values()) / max(1, sum(v[1] for v in per_label.values()))
    print(f"\noverall {overall:.0%} · chance 12.5%")
    errors = [r for r in rows if "error" in r]
    if errors:
        print(f"{len(errors)} call(s) failed")

    OUT.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "labels": list(LABELS), "per_label": {k: {"right": v[0], "of": v[1]}
                                              for k, v in per_label.items()},
        "confusion": {k: dict(v) for k, v in confusion.items()},
        "rows": rows}, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote out/{RESULT.name}")


if __name__ == "__main__":
    main()
