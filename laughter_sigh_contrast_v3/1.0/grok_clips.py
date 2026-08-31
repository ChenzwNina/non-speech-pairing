"""Grok's share of the clip vote, one call at a time in the main thread.

Grok answers in about five seconds standalone and hangs indefinitely inside verify_clips.py's
worker loop — verified by running both at the same moment, one returning while the other sat
wedged. The cause is somewhere in that process; this sidesteps it rather than chasing it, and
writes into the same clip_verdicts.jsonl so the tally is unchanged.

Usage:
    python benchmark/grok_clips.py
"""

from __future__ import annotations

import contextlib
import io
import json
import time
from pathlib import Path

import providers as P
from verify_clips import ANSWERS, QUESTION, recorded, verdict_of

HERE = Path(__file__).resolve().parent
FAMILY = HERE.parent          # laughter_sigh_contrast/, holding both versions
REPO = FAMILY.parent         # the repository root, where .env and archive/ live


def main() -> None:
    manifest = json.loads((HERE / "out" / "audio_manifest.json").read_text(encoding="utf-8"))
    clips = [{**c, "item_id": i["item_id"]} for i in manifest["items"] for c in i["clips"]]
    done = {path for path, provider, _ in recorded() if provider == "grok"}
    todo = [c for c in clips if c["path"] not in done]
    print(f"{len(clips)} clips · {len(done)} already answered · {len(todo)} to go", flush=True)

    answered = failed = 0
    for index, clip in enumerate(todo, 1):
        start = time.time()
        row = None
        # about one session in three never answers; a short deadline makes retrying cheap
        for attempt in range(1, 7):
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    answer = P.ask("grok", FAMILY / clip["path"], QUESTION[clip["condition"]])
                row = {"path": clip["path"], "provider": "grok", "round": 1,
                       "answer": answer.strip()[:200], "verdict": verdict_of(answer),
                       "attempts": attempt}
                answered += 1
                break
            except Exception as exc:
                last = f"{type(exc).__name__}: {str(exc)[:150]}"
        if row is None:
            row = {"path": clip["path"], "provider": "grok", "round": 1,
                   "error": last, "verdict": "error"}
            failed += 1
        with ANSWERS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"  [{index:3}/{len(todo)}] {time.time()-start:5.1f}s  {row['verdict']:7} "
              f"{Path(clip['path']).name}", flush=True)

    print(f"\n{answered} answered · {failed} failed", flush=True)


if __name__ == "__main__":
    main()
