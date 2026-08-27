"""Build web/v5/ — documents curation, metrics, and results for predicting_response_upgraded.

Merges three sources into one page:
  - out/pairs_v2.json         the writer's output + judge verdicts (curation)
  - out/audio_manifest.json   two separate audio files per pair (Dialogue candidates)
  - out/eval_realtime.json    the gpt-realtime-2.1 4-question results, randomized dialogue order

Usage:
    python predicting_response_upgraded/make_viewer.py
    python predicting_response_upgraded/make_viewer.py --no-audio
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DEFAULT_OUT_DIR = REPO / "web" / "v5"

VOC_ORDER = ["gasp", "grunt", "laughter", "sigh", "sob", "yawn"]
VOC_LABEL = {v: v.capitalize() for v in VOC_ORDER}

JUDGE_PROPERTIES = [
    (
        "vocalizations_both_plausible",
        "Both vocalizations are plausible reactions to Turn 1, which does not give either away.",
    ),
    (
        "interpretations_clearly_contrastive",
        "The two gold interpretations express meaningfully different pragmatic meanings — "
        "swapping them would clearly make the pair worse.",
    ),
    (
        "responses_clearly_contrastive",
        "The two gold responses perform different conversational functions and would sound "
        "wrong if swapped onto the other reaction.",
    ),
    (
        "negative_vocalization_semantics_preserved",
        "For grunt/sigh/sob/yawn, the interpretation and response still register the "
        "reluctance, fatigue, or distress — never plain cheerful agreement.",
    ),
]

Q_DEFS = [
    ("q1a", "Q1a", "Identify Dialogue 1's sound", "6-way", 16.7,
     "Right after playing audio 1, which non-speech sound did Speaker B produce?"),
    ("q1b", "Q1b", "Identify Dialogue 2's sound", "6-way", 16.7,
     "Right after playing audio 2 (a separate clip — Turn 1 repeated, different reaction), same question."),
    ("q2", "Q2", "Match interpretations to dialogues", "2-way", 50.0,
     "Having heard both, given the pair's two gold interpretations, which one describes Dialogue 1 and which describes Dialogue 2?"),
    ("q3", "Q3", "Match responses to dialogues", "2-way", 50.0,
     "Given the pair's two gold spoken continuations, which one follows Dialogue 1 and which follows Dialogue 2?"),
]


def pct(correct: int, n: int) -> float:
    return round(100 * correct / n, 1) if n else 0.0


def build_payload(pairs: dict, manifest: dict, evaluation: dict) -> dict:
    by_pair = {r["pair_id"]: r for r in pairs["results"] if "shared_turn1" in r}
    clips_by_pair: dict[str, dict[str, dict]] = defaultdict(dict)
    for c in manifest["clips"]:
        clips_by_pair[c["pair_id"]][c["version"]] = c
    rows = {r["pair_id"]: r for r in evaluation["rows"] if not r.get("error")}

    def dialogue_view(clip: dict, version: str) -> dict:
        return {
            "version": version,
            "audio": Path(clip["prompt"]).name,
            "audio_seconds": clip["prompt_seconds"],
            "vocalization": clip["vocalization"].strip("[]"),
            "voc_tag": clip["vocalization"],
            "interpretation": clip["interpretation"],
            "response": clip["response"],
            "clip_file": Path(clip["clip"]).name,
            "clip_seconds": clip["clip_seconds"],
        }

    items: list[dict] = []
    for pair_id, record in sorted(by_pair.items()):
        clips = clips_by_pair.get(pair_id)
        row = rows.get(pair_id)
        if not clips or row is None or "v1" not in clips or "v2" not in clips:
            continue

        d1 = dialogue_view(clips[row["d1_is_version"]], row["d1_is_version"])
        d2 = dialogue_view(clips[row["d2_is_version"]], row["d2_is_version"])

        items.append({
            "pair_id": pair_id,
            "contrast": record.get("contrast"),
            "attempts": record.get("attempts"),
            "shared_turn1": record["shared_turn1"],
            "turn1_voice_label": clips["v1"].get("turn1_voice_label"),
            "contrastive_rationale": record.get("contrastive_rationale"),
            "judge": record.get("judge"),
            "dialogue1": d1,
            "dialogue2": d2,
            "questions": {
                qkey: {
                    "options": row[f"{qkey}_options"],
                    "gold": row[f"{qkey}_gold"],
                    "predicted": row.get(f"{qkey}_predicted"),
                    "correct": bool(row.get(f"{qkey}_correct")),
                }
                for qkey, *_ in Q_DEFS
            },
        })

    n = len(items)
    q_summary = {}
    for qkey, *_ in Q_DEFS:
        correct = sum(1 for item in items if item["questions"][qkey]["correct"])
        q_summary[qkey] = {"correct": correct, "n": n, "pct": pct(correct, n)}

    all_four = sum(
        1 for item in items if all(item["questions"][qk]["correct"] for qk, *_ in Q_DEFS)
    )
    both_ids_correct = [
        item for item in items
        if item["questions"]["q1a"]["correct"] and item["questions"]["q1b"]["correct"]
    ]
    an_id_wrong = [item for item in items if item not in both_ids_correct]

    # accuracy by vocalization, pooling whichever dialogue slot (1 or 2) it landed in —
    # order is randomized per item, so this is now a fair per-sound comparison
    by_voc: dict[str, list[bool]] = defaultdict(list)
    for item in items:
        by_voc[item["dialogue1"]["vocalization"]].append(item["questions"]["q1a"]["correct"])
        by_voc[item["dialogue2"]["vocalization"]].append(item["questions"]["q1b"]["correct"])

    attempts_hist = Counter(item["attempts"] for item in items)
    judge_pass_rate = {
        key: pct(sum(1 for item in items if item["judge"] and item["judge"].get(key)), n)
        for key, _ in JUDGE_PROPERTIES
    }
    voice_counts = Counter(item["turn1_voice_label"] for item in items)

    return {
        "writer": pairs.get("model"),
        "eval_model": evaluation.get("model"),
        "seed": evaluation.get("seed"),
        "tts_model": manifest.get("tts_model"),
        "voice_pool": manifest.get("voice_pool"),
        "voice_counts": dict(voice_counts),
        "gap_after_turn1": manifest.get("gap_after_turn1"),
        "attempts_histogram": {str(k): v for k, v in sorted(attempts_hist.items())},
        "judge_properties": [{"key": k, "text": t} for k, t in JUDGE_PROPERTIES],
        "judge_pass_rate": judge_pass_rate,
        "q_defs": [
            {"key": k, "label": lbl, "title": title, "shape": shape, "chance": chance, "desc": desc}
            for k, lbl, title, shape, chance, desc in Q_DEFS
        ],
        "summary": {
            "n": n,
            "q": q_summary,
            "all_four": {"correct": all_four, "n": n, "pct": pct(all_four, n)},
            "matching_when_both_ids_correct": {
                "correct": sum(1 for i in both_ids_correct if i["questions"]["q2"]["correct"]),
                "n": len(both_ids_correct),
                "pct": pct(sum(1 for i in both_ids_correct if i["questions"]["q2"]["correct"]), len(both_ids_correct)),
            },
            "matching_when_an_id_wrong": {
                "correct": sum(1 for i in an_id_wrong if i["questions"]["q2"]["correct"]),
                "n": len(an_id_wrong),
                "pct": pct(sum(1 for i in an_id_wrong if i["questions"]["q2"]["correct"]), len(an_id_wrong)) if an_id_wrong else 0.0,
            },
            "id_by_vocalization": {
                v: {"n": len(results), "correct": sum(results), "pct": pct(sum(results), len(results))}
                for v, results in sorted(by_voc.items())
            },
        },
        "voc_order": VOC_ORDER,
        "voc_label": VOC_LABEL,
        "items": items,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, default=HERE / "out" / "pairs_v2.json")
    parser.add_argument("--manifest", type=Path, default=HERE / "out" / "audio_manifest.json")
    parser.add_argument("--eval", type=Path, default=HERE / "out" / "eval_realtime.json")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--no-audio", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    evaluation = json.loads(args.eval.read_text(encoding="utf-8"))
    payload = build_payload(pairs, manifest, evaluation)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    if not args.no_audio:
        dest_dir = args.out_dir / "audio_prompt"
        dest_dir.mkdir(parents=True, exist_ok=True)
        source_dir = HERE / "out" / "audio_prompt"
        copied = 0
        for item in payload["items"]:
            for key in ("dialogue1", "dialogue2"):
                name = item[key]["audio"]
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
    print(f"wrote {dest}  ({len(payload['items'])} pairs)")


if __name__ == "__main__":
    main()
