"""Render the three conditions of each item with ElevenLabs, from one set of turn takes.

**Turns without the vocalization are rendered once and reused.** A four-turn item costs six
takes, not twelve: the three plain turns, plus the vocalization turn three times — bare, with
tag A, with tag B. The three conditions are then sewn from those, so turns 1, 3 and 4 are
literally the same samples in all three files. Rendering three whole conversations instead
would let the speech drift in every turn, and a model answering differently could be responding
to that drift rather than to the sound.

**The vocalization turn is a different take in each condition, and that is the trade-off.** The
tag sits inside the line, so it colours the delivery of the words around it — which is what a
laughing person actually does, and what 2.0 could not do by splicing a discrete clip into a gap
("splicing is not amused delivery", its own caveat). The price is that the words of that one
turn are not byte-identical across conditions. The difference is confined to the tagged turn;
everything else is bit-for-bit shared.

**Two tag vocabularies.** The transcripts carry Dia's `(laughs)`, because that is what wrote
them. ElevenLabs wants `[laughs]`. vocalization_emotions.json holds both and this maps between
them; neither is ever spoken aloud.

One stability setting for every take, deliberately. 2.0 found a vocalization needs loose
stability to fire at all, and rendering the tagged turn loose while its plain counterpart was
tight would make the conditions differ in delivery as well as in sound.

**Whether a tag actually became a laugh is not decided here.** This stage renders and records
what it rendered — the text sent, the voice, the model, the stability, the duration of every
take. Judging the result needs a listener, the way 2.0 sent every clip to speech models before
trusting it, and that belongs in its own stage where a verdict can be recorded and revisited.
Take durations are in the manifest as measurements, not as evidence.

    python v6/make_audio.py --only v6_01a --dry-run   # what would be rendered
    python v6/make_audio.py --only v6_01a
    python v6/make_audio.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from elevenlabs import ElevenLabs
from elevenlabs.core.api_error import ApiError
from elevenlabs.types import ModelSettingsResponseModel

import evalkit as K
import sew

OUT = K.HERE / "out"
RENDERER = "elevenlabs"
# Two renderers are being compared over one dataset, so each owns a subtree and neither can
# overwrite the other. A stimulus is identified by (renderer, item, condition) from here on.
TAKE_DIR = OUT / "audio_turns" / RENDERER
AUDIO_DIR = OUT / "audio" / RENDERER
# Beside the takes, not beside the sewn output: the takes are what is committed and the
# manifest is what describes them. The sewn conversations are derived and are not in git.
MANIFEST = TAKE_DIR / "manifest.json"

TTS_MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"
VOICES = {"A": "s3TPKV1kjDlVtZbl4Ksh", "B": "aKw9UnnjRq5scbeeGI7Z"}
STABILITY = 0.30
GAP = 0.35

PAREN = re.compile(r"\([^)]*\)")


def api_detail(exc: ApiError) -> str:
    """The one line worth reading out of an ElevenLabs error body."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        detail = body.get("detail", body)
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("status") or detail)
        return str(detail)
    return str(exc)[:200]


def tag_map() -> dict[str, str]:
    rows = json.loads((K.HERE / "vocalization_emotions.json").read_text())
    return {row["dia_tag"]: row["elevenlabs_tag"] for row in rows}


def duration_of(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def synthesize(client: ElevenLabs, text: str, speaker: str, dest: Path,
               stability: float) -> None:
    K.guard(f"elevenlabs {TTS_MODEL}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"".join(client.text_to_speech.convert(
        voice_id=VOICES[speaker], text=text, model_id=TTS_MODEL,
        output_format=OUTPUT_FORMAT,
        voice_settings=ModelSettingsResponseModel(stability=stability))))


def take_path(item_id: str, turn: int, variant: str = "") -> Path:
    return TAKE_DIR / f"{item_id}__t{turn}{('__' + variant) if variant else ''}.mp3"


def planned_takes(item: dict, tags: dict[str, str]) -> list[dict]:
    """Every take this item needs: the plain turns, then the tagged variants of the voc turn."""
    voc_turn = item["vocalization_turn"]
    takes = []
    for turn in item["baseline"]["turns"]:
        takes.append({"turn": turn["turn"], "speaker": turn["speaker"],
                      "variant": "", "text": turn["text"],
                      "path": take_path(item["item_id"], turn["turn"])})
    for variant, condition in (("a", "condition_a"), ("b", "condition_b")):
        tagged = next(t for t in item[condition]["turns"] if t["turn"] == voc_turn)
        dia = PAREN.search(tagged["text"])
        if not dia or dia.group(0) not in tags:
            raise K.ConfigError(f"{item['item_id']} {condition}: no approved tag in "
                                f"{tagged['text']!r}")
        takes.append({"turn": voc_turn, "speaker": tagged["speaker"], "variant": variant,
                      "text": tagged["text"].replace(dia.group(0), tags[dia.group(0)]),
                      "dia_tag": dia.group(0), "elevenlabs_tag": tags[dia.group(0)],
                      "path": take_path(item["item_id"], voc_turn, variant)})
    return takes


def assembly(item: dict) -> dict:
    """Which take goes where, by filename, for whoever reassembles the conditions.

    The sewn conversations are not committed — they are rebuilt downstream — so the manifest
    has to carry the recipe rather than point at local files. Note that the vocalization turn
    is not always turn 2, so read `vocalization_turn` rather than assuming it.
    """
    voc = item["vocalization_turn"]
    plan = {"turn_order": [t["turn"] for t in item["baseline"]["turns"]]}
    for condition, variant in (("baseline", ""), ("condition_a", "a"), ("condition_b", "b")):
        plan[condition] = [take_path(item["item_id"], t["turn"],
                                     variant if t["turn"] == voc else "").name
                           for t in item["baseline"]["turns"]]
    return plan


def sew_conditions(item: dict, gap: float) -> list[dict]:
    """The three condition files, each a run of takes with a gap between turns."""
    voc_turn = item["vocalization_turn"]
    built = []
    for condition, variant in (("baseline", ""), ("condition_a", "a"), ("condition_b", "b")):
        pieces: list[tuple[str, object]] = []
        for turn in item["baseline"]["turns"]:
            if pieces:
                pieces.append(("silence", gap))
            use = variant if turn["turn"] == voc_turn else ""
            pieces.append(("file", take_path(item["item_id"], turn["turn"], use)))
        dest = AUDIO_DIR / f"{item['item_id']}__{condition}.mp3"
        sew.build(pieces, dest)
        built.append({"condition": condition, "path": str(dest.relative_to(K.HERE)),
                      "seconds": round(duration_of(dest), 2)})
    return built


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input")
    parser.add_argument("--config")
    parser.add_argument("--only", action="append", help="item ids")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--gap", type=float, default=GAP)
    parser.add_argument("--stability", type=float, default=STABILITY)
    parser.add_argument("--overwrite", action="store_true",
                        help="re-render takes that already exist")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    K.set_dry_run(args.dry_run)

    try:
        config = K.load_config(Path(args.config) if args.config else None)
        if args.input:
            config["dataset"]["transcripts"] = args.input
        _source, items = K.load_items(config)
        tags = tag_map()
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.only:
        keep = set(args.only)
        items = [i for i in items if i["item_id"] in keep]
    if args.limit:
        items = items[:args.limit]
    if not items:
        print("error: no items selected", file=sys.stderr)
        return 2

    client = None if args.dry_run else ElevenLabs(api_key=_key())
    existing = json.loads(MANIFEST.read_text())["items"] if MANIFEST.exists() else []
    by_id = {row["item_id"]: row for row in existing}

    try:
        full_chars = sum(len(take["text"]) for i in items
                         for take in planned_takes(i, tags))
    except K.ConfigError:
        full_chars = 0
    rendered = reused = failed = 0
    for item in items:
        try:
            takes = planned_takes(item, tags)
        except K.ConfigError as exc:
            print(f"  {item['item_id']} · {exc}", file=sys.stderr)
            failed += 1
            continue
        chars = sum(len(t["text"]) for t in takes)
        if args.dry_run:
            print(f"\n  {item['item_id']} · {len(takes)} takes · {chars} characters")
            for take in takes:
                mark = f" [{take['variant']}]" if take["variant"] else ""
                print(f"    t{take['turn']} {take['speaker']}{mark}: {take['text']}")
            continue

        def render(take: dict) -> bool:
            """Render into `take["path"]`. False means quota refused it and the run must stop."""
            try:
                synthesize(client, take["text"], take["speaker"], take["path"],
                           args.stability)
            except ApiError as exc:
                # Quota is not transient and retrying only burns time, so the run stops here
                # and says how much the whole job needs.
                take["path"].unlink(missing_ok=True)
                print(f"error: ElevenLabs refused the render: {api_detail(exc)}\n"
                      f"  this take was {len(take['text'])} characters; the full "
                      f"{len(items)}-item job is {full_chars:,} characters over "
                      f"{len(items) * 6} takes", file=sys.stderr)
                return False
            return True

        stopped = False
        for take in takes:
            if take["path"].exists() and not args.overwrite:
                reused += 1
            elif render(take):
                rendered += 1
            else:
                stopped = True
                break
            take["seconds"] = round(duration_of(take["path"]), 2)
        if stopped:
            return 2

        conditions = sew_conditions(item, args.gap)
        by_id[item["item_id"]] = {
            "item_id": item["item_id"], "rendered_at": K.now(),
            "model": TTS_MODEL, "output_format": OUTPUT_FORMAT, "voices": VOICES,
            "stability": args.stability, "gap_seconds": args.gap,
            "vocalization_turn": item["vocalization_turn"],
            "vocalization_speaker": item["vocalization_speaker"],
            "renderer": RENDERER,
            "takes": [{k: (str(v.relative_to(K.HERE)) if isinstance(v, Path) else v)
                       for k, v in take.items()} for take in takes],
            "assembly": {"gap_seconds": args.gap, **assembly(item)},
            # Locally sewn for inspection; rebuilt downstream, so not committed.
            "conditions_local": conditions}
        print(f"  {item['item_id']} · "
              + " · ".join(f"{c['condition'].replace('condition_', '')} {c['seconds']}s"
                           for c in conditions), flush=True)

    if args.dry_run:
        total = sum(len(planned_takes(i, tags)) for i in items)
        K.report("make-audio", planned=total, completed=0, skipped=0, failed=failed, invalid=0)
        print("dry run: nothing called, nothing written")
        return 0

    K.write_json(MANIFEST, {"rendered_at": K.now(), "renderer": RENDERER,
                            "model": TTS_MODEL,
                            "transcripts": config["dataset"]["transcripts"],
                            "items": [by_id[k] for k in sorted(by_id)]}, overwrite=True)
    K.report("make-audio", planned=rendered + reused, completed=rendered, skipped=reused,
             failed=failed, invalid=0)
    print(f"wrote {MANIFEST.relative_to(K.HERE.parent)}")
    return 1 if failed else 0


def _key() -> str:
    import os

    from dotenv import load_dotenv
    load_dotenv(K.HERE.parent / ".env")
    value = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not value:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
