"""Build web/v3/ — the viewer for the predicting_response eval.

Pulls the pairs, the audio manifest, and the eval results into one static page:
headline scores, accuracy by vocalization, the Q1 confusion table, and a card per pair
showing the shared context, both audio clips, and the options the model was given.

Usage:
    python predicting_response/make_viewer.py
    python predicting_response/make_viewer.py --no-audio   # page only, skip copying mp3s
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DEFAULT_OUT_DIR = REPO / "web" / "v3"

VOC_ORDER = ["gasp", "grunt", "laughter", "sigh", "sob", "yawn"]
VOC_LABEL = {
    "gasp": "Gasp",
    "grunt": "Grunt",
    "laughter": "Laughter",
    "sigh": "Sigh",
    "sob": "Sob",
    "yawn": "Yawn",
}


def pct(correct: int, n: int) -> float:
    return round(100 * correct / n, 1) if n else 0.0


def build_payload(pairs_list: list[dict], manifest: dict, evaluation: dict) -> dict:
    by_pair: dict[str, dict] = {}
    for pairs in pairs_list:
        for r in pairs["results"]:
            if "shared_context" in r:
                by_pair[r["pair_id"]] = r
    clips = {(c["pair_id"], c["version"]): c for c in manifest["clips"]}
    rows = {(r["pair_id"], r["version"]): r for r in evaluation["rows"] if not r.get("error")}

    items: list[dict] = []
    for pair_id, record in by_pair.items():
        versions = []
        for key, label in (("version_1", "v1"), ("version_2", "v2")):
            version = record[key]
            clip = clips.get((pair_id, label))
            row = rows.get((pair_id, label))
            if clip is None or row is None:
                continue
            voc = version["vocalization"].strip("[]")
            versions.append(
                {
                    "version": label,
                    "vocalization": voc,
                    "voc_tag": version["vocalization"],
                    "interpretation": version["intended_interpretation"],
                    "responder": version["responder"],
                    "reply": version["response"],
                    "clip_file": Path(clip["clip"]).name,
                    "clip_seconds": clip["clip_seconds"],
                    "voice_id": clip.get("voice_id"),
                    "prompt_audio": Path(clip["prompt"]).name,
                    "full_audio": Path(clip["full"]).name if clip.get("full") else None,
                    "prompt_seconds": clip["prompt_seconds"],
                    "q1_options": row["q1_options"],
                    "q1_gold": row["q1_gold"],
                    "q1_predicted": row.get("q1_predicted"),
                    "q1_correct": bool(row.get("q1_correct")),
                    "q2_options": row["q2_options"],
                    "q2_gold": row["q2_gold"],
                    "q2_predicted": row.get("q2_predicted"),
                    "q2_correct": bool(row.get("q2_correct")),
                }
            )
        if len(versions) != 2:
            continue
        items.append(
            {
                "pair_id": pair_id,
                "theme": record.get("theme"),
                "contrast": record.get("contrast"),
                "scenario": record.get("scenario"),
                "trigger_note": record.get("trigger_note"),
                "why": record.get("why_the_vocalization_changes_the_response"),
                "context": record["shared_context"],
                "versions": versions,
            }
        )
    items.sort(key=lambda item: item["pair_id"])

    flat = []
    for item in items:
        for v in item["versions"]:
            flat.append({**v, "theme": item.get("theme")})
    by_voc: dict[str, list[dict]] = defaultdict(list)
    by_theme: dict[str, list[dict]] = defaultdict(list)
    for version in flat:
        by_voc[version["vocalization"]].append(version)
        if version.get("theme"):
            by_theme[version["theme"]].append(version)

    q1_right = [v for v in flat if v["q1_correct"]]
    q1_wrong = [v for v in flat if not v["q1_correct"]]
    confusion: dict[str, dict[str, int]] = {
        voc: defaultdict(int) for voc in VOC_ORDER
    }
    for version in flat:
        heard = version["q1_options"].get(version["q1_predicted"]) or "unparsed"
        confusion[version["vocalization"]][heard] += 1

    n = len(flat)
    summary = {
        "n": n,
        "q1": {"correct": len(q1_right), "n": n, "pct": pct(len(q1_right), n), "chance": 16.7},
        "q2": {
            "correct": sum(1 for v in flat if v["q2_correct"]),
            "n": n,
            "pct": pct(sum(1 for v in flat if v["q2_correct"]), n),
            "chance": 50.0,
        },
        "both": {
            "correct": sum(1 for v in flat if v["q1_correct"] and v["q2_correct"]),
            "n": n,
            "pct": pct(sum(1 for v in flat if v["q1_correct"] and v["q2_correct"]), n),
            "chance": 8.3,
        },
        "q2_when_q1_correct": {
            "correct": sum(1 for v in q1_right if v["q2_correct"]),
            "n": len(q1_right),
            "pct": pct(sum(1 for v in q1_right if v["q2_correct"]), len(q1_right)),
        },
        "q2_when_q1_wrong": {
            "correct": sum(1 for v in q1_wrong if v["q2_correct"]),
            "n": len(q1_wrong),
            "pct": pct(sum(1 for v in q1_wrong if v["q2_correct"]), len(q1_wrong)),
        },
        "by_vocalization": {
            voc: {
                "n": len(vs),
                "q1": pct(sum(1 for v in vs if v["q1_correct"]), len(vs)),
                "q1_correct": sum(1 for v in vs if v["q1_correct"]),
                "q2": pct(sum(1 for v in vs if v["q2_correct"]), len(vs)),
                "q2_correct": sum(1 for v in vs if v["q2_correct"]),
            }
            for voc, vs in sorted(by_voc.items())
        },
        "confusion": {voc: dict(heard) for voc, heard in confusion.items()},
        "by_theme": (
            {
                theme: {
                    "n": len(vs),
                    "q1": pct(sum(1 for v in vs if v["q1_correct"]), len(vs)),
                    "q1_correct": sum(1 for v in vs if v["q1_correct"]),
                    "q2": pct(sum(1 for v in vs if v["q2_correct"]), len(vs)),
                    "q2_correct": sum(1 for v in vs if v["q2_correct"]),
                }
                for theme, vs in sorted(by_theme.items())
            }
            if by_theme
            else None
        ),
    }

    missing = [
        r["pair_id"]
        for pairs in pairs_list
        for r in pairs["results"]
        if r.get("error")
    ]
    writers = sorted({p.get("model") for p in pairs_list if p.get("model")})
    themes = sorted({p.get("theme") for p in pairs_list if p.get("theme")})
    voices = manifest.get("voice_pool") or (
        [manifest["voice_a"]] if manifest.get("voice_a") else []
    )
    return {
        "writer": writers[0] if len(writers) == 1 else writers,
        "eval_model": evaluation.get("model"),
        "seed": evaluation.get("seed"),
        "separate_sessions": evaluation.get("separate_sessions", False),
        "tts_model": manifest.get("tts_model"),
        "voices": voices,
        "gaps": manifest.get("gaps"),
        "context_turns": pairs_list[0].get("context_turns"),
        "total_turns": pairs_list[0].get("total_turns"),
        "speakers": pairs_list[0].get("speakers"),
        "themes": themes,
        "contrasts_without_a_pair": missing,
        "voc_order": VOC_ORDER,
        "voc_label": VOC_LABEL,
        "summary": summary,
        "items": items,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pairs", type=Path, nargs="+", default=[HERE / "out" / "pairs.json"],
        help="one or more pairs.json files (e.g. one per theme)",
    )
    parser.add_argument("--manifest", type=Path, default=HERE / "out" / "audio_manifest.json")
    parser.add_argument("--eval", type=Path, default=HERE / "out" / "eval_realtime.json")
    parser.add_argument(
        "--audio-source-dir", type=Path, default=HERE / "out",
        help="directory containing audio_prompt/ (and audio_full/ if present)",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--no-audio", action="store_true", help="skip copying mp3s")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pairs_list = [json.loads(p.read_text(encoding="utf-8")) for p in args.pairs]
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    evaluation = json.loads(args.eval.read_text(encoding="utf-8"))
    payload = build_payload(pairs_list, manifest, evaluation)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    if not args.no_audio:
        for kind, key in (("audio_prompt", "prompt_audio"), ("audio_full", "full_audio")):
            source_dir = args.audio_source_dir / kind
            if not source_dir.is_dir():
                continue
            dest_dir = args.out_dir / kind
            dest_dir.mkdir(parents=True, exist_ok=True)
            copied = 0
            for item in payload["items"]:
                for version in item["versions"]:
                    name = version[key]
                    if not name:
                        continue
                    source = source_dir / name
                    if source.exists():
                        shutil.copy2(source, dest_dir / name)
                        copied += 1
            print(f"copied {copied} file(s) into {dest_dir}")

    template = (HERE / "viewer_template.html").read_text(encoding="utf-8")
    html = template.replace(
        "__PAYLOAD__", json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )
    dest = args.out_dir / "index.html"
    dest.write_text(html, encoding="utf-8")
    print(f"wrote {dest}  ({len(payload['items'])} pairs, {payload['summary']['n']} clips)")


if __name__ == "__main__":
    main()
