"""Put the three user-turn conditions of each task side by side.

The proposal is regenerated live in every run, so the conditions are not matched pairs —
the model is answering a slightly different plan of its own each time. What is comparable is
the *move* its second turn makes: whether it scales the plan back, softens it, defends it, or
carries on unchanged.

Usage:
    python assistant_proposal/compare.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
REPO = HERE.parent.parent

CONDITIONS = [
    ("none", "session.json", "sound only"),
    ("attitude", "session_line.json", "attitude line + sound"),
    ("neutral", "session_neutral.json", "attitude-free line + sound"),
    ("mismatch", "session_mismatch.json", "positive line + negative sound"),
    ("mismatch_run2", "session_mismatch_run2.json",
     "positive line + negative sound, repeat run"),
    ("voc_first", "session_vocfirst.json", "\"[sigh] ughh\" first, then a positive line"),
    ("voc_first_natural", "session_vocfirst_natural.json",
     "\"[sigh] ughh\", a one-second beat, then plain assent"),
    ("lexical_first", "session_words.json",
     "\"I don't want to do this, but...\" in words, a one-second beat, then plain assent"),
    ("tease", "session_tease.json", "a warm laugh, then a cutting line"),
    ("tease_plain", "session_teaseplain.json", "the same cutting line, laugh removed"),
    ("tease_harsh", "session_tease_harsh.json",
     "harsh line, laughed through (one ElevenLabs take)"),
    ("tease_plain_harsh", "session_teaseplain_harsh.json",
     "the same harsh line, said straight"),
    ("tease_tempt2", "session_tease_tempt2.json",
     "mock-reproach after a tempting proposal, laughed"),
    ("tease_plain_tempt2", "session_teaseplain_tempt2.json",
     "the same reproach, said flat"),
]


def main() -> None:
    loaded = [(mode, label, json.loads((OUT / name).read_text(encoding="utf-8")))
              for mode, name, label in CONDITIONS if (OUT / name).exists()]
    by_task: dict[str, dict[str, dict]] = {}
    for mode, _, session in loaded:
        for item in session["items"]:
            if "error" not in item:
                by_task.setdefault(item["task"], {})[mode] = item

    lines = [
        "# assistant_proposal — the same task, three ways of answering the proposal",
        "",
        "Every row is one live session: the model got one line of context, proposed something "
        "of its own, heard the user, and took another turn. The vocalization is the same real "
        "recording across all three conditions of a task.",
        "",
    ]
    for task, conditions in by_task.items():
        any_item = next(iter(conditions.values()))
        sounds = sorted({item["vocalization"] for item in conditions.values()})
        lines += [
            f"## {task} — {' / '.join(sounds)}",
            "",
            f"*{any_item['context']}*",
            "",
        ]
        for mode, _, label in [(m, n, l) for m, n, l in CONDITIONS]:
            item = conditions.get(mode)
            if not item:
                continue
            lines += [
                f"**{label}** — [`{Path(item['audio']).name}`]"
                f"(audio/{Path(item['audio']).name}) · "
                + (f"laugh `{Path(item['clip']).name}` ({item['clip_seconds']:.1f}s)"
                   if item.get("line_mode") == "tease" and item.get("clip") else
                   f"laughed take ({item['line_seconds']:.1f}s vs "
                   f"{item['words_only_seconds']:.1f}s of words)"
                   if item.get("line_mode") == "tease" else
                   "no sound, words only" if item.get("line_mode") == "tease_plain" else
                   f"synthesized `{item['voc_token']}` ({item['clip_seconds']:.1f}s)"
                   if item.get("voc_token") and item.get("line_mode") != "lexical_first"
                   else f"spoken `{item['voc_token']}` ({item['clip_seconds']:.1f}s)"
                   if item.get("voc_token") else
                   f"recording `{Path(item['clip']).name}` ({item['clip_seconds']:.1f}s)"),
                "",
                f"- *proposed:* {item['proposal']}",
            ]
            if item.get("line_mode") in ("tease", "tease_plain"):
                laughed = (item.get("turn_text") or item["line"]) != item["line"]
                lines.append(
                    f"- *speaker said:* "
                    + ("*(a real laugh)* then " if item.get("clip") else "")
                    + f"“{item['line']}”"
                    + ("  — laughed through, one take"
                       if laughed else
                       "  — said straight, no laugh" if not item.get("clip") else ""))
            elif item.get("voc_token"):
                kind = ("spoken" if item.get("line_mode") == "lexical_first"
                        else f"synthesized, heard back as {item['voc_asr']!r}")
                lines.append(f"- *speaker said:* “{item['voc_token']}” ({kind}) then "
                             f"“{item['line']}”")
            elif item.get("line"):
                lines.append(f"- *user said:* “{item['line']}” then the "
                             f"{item['vocalization']}")
            else:
                lines.append(f"- *user said:* nothing — just the {item['vocalization']}")
            lines.append(f"- *replied:* {item['reply']}")
            if item.get("speakers_heard"):
                lines.append(f"- *asked afterwards, how many people did you hear:* "
                             f"{item['speakers_heard']}")
            lines.append("")
    dest = OUT / "compare.md"
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {dest.relative_to(REPO)} · {len(by_task)} task(s) × "
          f"{len(loaded)} condition(s)")


if __name__ == "__main__":
    main()
