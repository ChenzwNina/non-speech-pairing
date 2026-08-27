"""Sew Turn 1 + Turn 2 + clipped Turn 3 vocalization (no Turn 3 words).

Usage:
    python predicting_content/sew_audio.py
    python predicting_content/sew_audio.py --overwrite
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DEFAULT_TURNS = HERE / "out" / "audio_turns"
DEFAULT_VOC = HERE / "out" / "audio_voc"
DEFAULT_OUT = HERE / "out" / "audio_sewn"

GAP_TURN = 0.35


def sew(turn1: Path, turn2: Path, voc: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    filt = (
        "[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a0];"
        f"anullsrc=r=44100:cl=stereo,atrim=0:{GAP_TURN},aformat=sample_fmts=fltp[g0];"
        "[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a1];"
        f"anullsrc=r=44100:cl=stereo,atrim=0:{GAP_TURN},aformat=sample_fmts=fltp[g1];"
        "[2:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a2];"
        "[a0][g0][a1][g1][a2]concat=n=5:v=0:a=1[out]"
    )
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(turn1),
            "-i", str(turn2),
            "-i", str(voc),
            "-filter_complex", filt,
            "-map", "[out]",
            "-c:a", "libmp3lame", "-q:a", "2",
            str(dest),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-800:] if result.stderr else "ffmpeg failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--turns-dir", type=Path, default=DEFAULT_TURNS)
    parser.add_argument("--voc-dir", type=Path, default=DEFAULT_VOC)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    voc_index = json.loads((args.voc_dir / "index.json").read_text(encoding="utf-8"))
    args.out_dir = args.out_dir.resolve()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    jobs = []
    for row in voc_index:
        if row.get("error"):
            continue
        item_id = row["item_id"]
        jobs.append(
            {
                "item_id": item_id,
                "domain": row.get("domain"),
                "formula": row.get("formula"),
                "turn1": args.turns_dir / f"{item_id}-turn1.mp3",
                "turn2": args.turns_dir / f"{item_id}-turn2.mp3",
                "voc": args.voc_dir / f"{item_id}-voc.mp3",
                "out": args.out_dir / f"{item_id}.mp3",
            }
        )

    print(f"clips: {len(jobs)}  dir: {args.out_dir}")
    manifest = []
    for i, job in enumerate(jobs, start=1):
        parts = (job["turn1"], job["turn2"], job["voc"])
        missing = [str(path) for path in parts if not path.exists()]
        record = {
            "id": job["item_id"],
            "item_id": job["item_id"],
            "domain": job["domain"],
            "formula": job["formula"],
            "audio": str(job["out"].relative_to(REPO)),
            "parts": {
                "turn1": str(job["turn1"].relative_to(REPO)),
                "turn2": str(job["turn2"].relative_to(REPO)),
                "voc": str(job["voc"].relative_to(REPO)),
            },
        }
        if missing:
            record["error"] = "missing " + ", ".join(missing)
            print(f"[{i}/{len(jobs)}] missing {job['out'].name}")
            manifest.append(record)
            continue
        if job["out"].exists() and not args.overwrite:
            print(f"[{i}/{len(jobs)}] skip {job['out'].name}")
            record["skipped"] = True
            manifest.append(record)
            continue
        print(f"[{i}/{len(jobs)}] {job['out'].name}")
        try:
            sew(job["turn1"], job["turn2"], job["voc"], job["out"])
            record["bytes"] = job["out"].stat().st_size
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            print(f"    failed: {exc}")
        manifest.append(record)

    index_path = args.out_dir / "index.json"
    index_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    failures = sum(1 for item in manifest if item.get("error"))
    print(f"\nwrote {index_path}" + (f" ({failures} failed)" if failures else ""))


if __name__ == "__main__":
    main()
