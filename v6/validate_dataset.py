"""Check the v6 transcripts before anything is built on them. Reports; never edits.

The twelve checks are the spec's. They exist because the benchmark's whole claim is that three
audio files differ in one sound and nothing else, and that claim is a property of the source
text. If `condition_b` says "the gate" where the baseline says "that gate", every score
computed from the pair is measuring a word as well as a sound, and no downstream stage can
tell.

Checks 1-11 are arithmetic on the transcript. Check 12 looks for the rendered audio and is the
one that depends on where the render ran: with no audio present it reports what is missing and
leaves the rest of the report valid, so this is usable before the audio exists and again after.
Pass --require-audio to make missing files an error rather than a note.

    python v6/validate_dataset.py
    python v6/validate_dataset.py --item-id v6_01a --require-audio
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import evalkit as K

PAREN = re.compile(r"\([^)]*\)")
TURNS = 4
EXPECTED_SPEAKERS = ["A", "B"] * (TURNS // 2)


def approved_tags() -> dict[str, str]:
    """vocalization -> Dia tag, from the mapping file that generation used."""
    rows = json.loads((K.HERE / "vocalization_emotions.json").read_text())
    return {row["vocalization"]: row["dia_tag"] for row in rows}


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def lexical(turn: dict) -> str:
    return norm(PAREN.sub("", turn["text"]))


def parentheticals(turns: list[dict]) -> list[tuple[int, str]]:
    return [(turn["turn"], match.group(0))
            for turn in turns for match in PAREN.finditer(turn["text"])]


def check_item(item: dict, tags: dict[str, str], config: dict,
               audio_required: bool, which: list[str] | None = None
               ) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []
    item_id = item.get("item_id")

    # 2 — all three conditions exist
    missing = [c for c in K.CONDITIONS if not isinstance(item.get(c), dict)
               or "turns" not in item.get(c, {})]
    if missing:
        return [f"missing conditions {missing}"], notes

    turns = {c: item[c]["turns"] for c in K.CONDITIONS}

    # 3 — four turns each
    for condition, rows in turns.items():
        if len(rows) != TURNS:
            errors.append(f"{condition} has {len(rows)} turns, expected {TURNS}")
    if errors:
        return errors, notes

    # 4, 5 — turn numbers and speakers agree, and run A-B-A-B
    for condition, rows in turns.items():
        numbers = [r["turn"] for r in rows]
        if numbers != list(range(1, TURNS + 1)):
            errors.append(f"{condition} turn numbers are {numbers}")
        speakers = [r["speaker"] for r in rows]
        if speakers != EXPECTED_SPEAKERS:
            errors.append(f"{condition} speaker order is {speakers}, "
                          f"expected {EXPECTED_SPEAKERS}")
    if errors:
        return errors, notes

    voc_turn, voc_speaker = item.get("vocalization_turn"), item.get("vocalization_speaker")
    if voc_turn not in range(1, TURNS + 1):
        errors.append(f"vocalization_turn is {voc_turn!r}")
        return errors, notes
    spoken_by = turns["baseline"][voc_turn - 1]["speaker"]
    if voc_speaker != spoken_by:
        errors.append(f"vocalization_speaker is {voc_speaker!r} but turn {voc_turn} "
                      f"is spoken by {spoken_by}")

    # 6, 7 — identical words everywhere once the tag is removed
    base = [lexical(r) for r in turns["baseline"]]
    for condition in ("condition_a", "condition_b"):
        other = [lexical(r) for r in turns[condition]]
        for index, (want, got) in enumerate(zip(base, other), start=1):
            if want != got:
                where = "the vocalization turn" if index == voc_turn else "a shared turn"
                errors.append(f"{condition} turn {index} differs from baseline in words "
                              f"({where}): {got!r} vs {want!r}")

    # 8, 9 — exactly the right tag, on the right turn, by the right speaker
    for condition, key in (("condition_a", "voc_a"), ("condition_b", "voc_b")):
        voc = item.get(key)
        want = item.get("tag_a" if key == "voc_a" else "tag_b")
        if voc not in tags:
            errors.append(f"{key} is {voc!r}, which is not in the approved inventory")
            continue
        if want != tags[voc]:
            errors.append(f"{condition} declares tag {want!r} but the approved tag for "
                          f"{voc} is {tags[voc]!r}")
        found = parentheticals(turns[condition])
        if len(found) != 1:
            errors.append(f"{condition} contains {len(found)} parentheticals "
                          f"{[t for _, t in found]}, expected exactly one")
            continue
        at_turn, tag = found[0]
        if tag != want:
            errors.append(f"{condition} contains {tag!r}, expected {want!r}")
        if at_turn != voc_turn:
            errors.append(f"{condition} carries its tag on turn {at_turn}, but "
                          f"vocalization_turn is {voc_turn}")
        if not lexical(turns[condition][at_turn - 1]):
            errors.append(f"{condition} turn {at_turn} is the tag and nothing else")

    # 10 — the baseline carries no approved tag
    stray = [tag for _, tag in parentheticals(turns["baseline"])]
    if stray:
        errors.append(f"baseline contains {stray}; it must contain no vocalization")

    # 11 — per-condition metadata agrees with the item-level fields
    expected = {"baseline": ("none", "ambiguous"),
                "condition_a": (item.get("voc_a"), item.get("emotion_a")),
                "condition_b": (item.get("voc_b"), item.get("emotion_b"))}
    for condition, (voc, emotion) in expected.items():
        block = item[condition]
        if block.get("vocalization") != voc:
            errors.append(f"{condition}.vocalization is {block.get('vocalization')!r}, "
                          f"expected {voc!r}")
        if block.get("target_emotion") != emotion:
            errors.append(f"{condition}.target_emotion is "
                          f"{block.get('target_emotion')!r}, expected {emotion!r}")
    if item.get("voc_a") == item.get("voc_b"):
        errors.append(f"voc_a and voc_b are both {item.get('voc_a')!r}; "
                      "the two conditions must contrast")

    # 12 — the rendered audio, per renderer, when it is there. A renderer with nothing on disk
    # yet is a note; a renderer with a file that is empty or half-written is an error, because
    # that one would be silently asked about.
    for renderer in (which if which is not None else sorted(K.renderers(config))):
        for condition in K.CONDITIONS:
            path = K.audio_path(config, item_id, condition, renderer)
            if not path.exists():
                (errors if audio_required else notes).append(
                    f"{renderer}: no audio for {condition} at "
                    f"{path.relative_to(K.HERE)}")
            elif not path.stat().st_size:
                errors.append(f"{renderer}: audio for {condition} is empty: "
                              f"{path.relative_to(K.HERE)}")
    return errors, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="transcripts JSON; default comes from the config")
    parser.add_argument("--output", help="where to write the report")
    parser.add_argument("--config")
    parser.add_argument("--item-id", action="append")
    parser.add_argument("--require-audio", action="store_true",
                        help="treat missing rendered audio as an error")
    parser.add_argument("--renderer", action="append",
                        help="check only these renderers; default is all configured")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="accepted for symmetry; this stage never calls an API")
    args = parser.parse_args()
    K.set_dry_run(args.dry_run)

    try:
        config = K.load_config(Path(args.config) if args.config else None)
        if args.input:
            config["dataset"]["transcripts"] = args.input
        source, items = K.load_items(config)
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    tags = approved_tags()
    if args.item_id:
        items = [i for i in items if i.get("item_id") in set(args.item_id)]
        if not items:
            print(f"error: no items match {args.item_id}", file=sys.stderr)
            return 2

    # 1 — ids present and unique, across the whole file rather than the filtered subset
    seen: dict[str, int] = {}
    for item in source["items"]:
        seen[item.get("item_id", "<missing>")] = seen.get(item.get("item_id", "<missing>"), 0) + 1
    duplicates = sorted(k for k, n in seen.items() if n > 1)
    file_errors = []
    if duplicates:
        file_errors.append(f"duplicate item_id: {duplicates}")
    if "<missing>" in seen:
        file_errors.append(f"{seen['<missing>']} item(s) have no item_id")

    reports, bad, noted = [], 0, 0
    for item in items:
        errors, notes = check_item(item, tags, config, args.require_audio, args.renderer)
        reports.append({"item_id": item.get("item_id"), "errors": errors, "notes": notes,
                        "ok": not errors})
        bad += bool(errors)
        noted += bool(notes)

    payload = {"checked_at": K.now(), "transcripts": config["dataset"]["transcripts"],
               "renderers": args.renderer or sorted(K.renderers(config)),
               "require_audio": args.require_audio,
               "items_checked": len(reports), "items_with_errors": bad,
               "file_errors": file_errors, "items": reports}
    out = Path(args.output) if args.output else K.stage_dir("validation") / "dataset.json"
    try:
        K.write_json(out, payload, overwrite=args.overwrite or not args.output)
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    K.report("validate", checked=len(reports), passed=len(reports) - bad, failed=bad,
             with_notes=noted, file_errors=len(file_errors))
    for line in file_errors:
        print(f"  file: {line}")
    for entry in reports:
        for line in entry["errors"]:
            print(f"  {entry['item_id']}: {line}"[:200])
    if noted:
        example = next(e for e in reports if e["notes"])
        print(f"  note ({noted} item(s)): {example['notes'][0]}")
    print(f"\nwrote {out.relative_to(K.HERE.parent)}")
    return 1 if bad or file_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
