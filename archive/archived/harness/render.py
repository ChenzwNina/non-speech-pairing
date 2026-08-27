"""Turn a curated item into TTS payloads.

Output shape matches the hand-written scripts this benchmark started from:

    [
        {"voice_id": SPEAKER_A_VOICE_ID, "text": "[amused] I ran all the way ..."},
        {"voice_id": SPEAKER_B_VOICE_ID, "text": "[happy laugh] oh no [loud funny laugh]"},
    ]

`consecutive` turns by the same speaker are merged, since most multi-speaker TTS APIs take one
block per speaker turn.
"""

import json
import os

VOICE_PLACEHOLDER = {"A": "SPEAKER_A_VOICE_ID", "B": "SPEAKER_B_VOICE_ID"}


def payload(turns, voices=None):
    """[{voice_id, text}] for one performance."""
    voices = voices or VOICE_PLACEHOLDER
    out = []
    for turn in turns:
        speaker = turn["speaker"]
        text = turn["text"].strip()
        if out and out[-1]["_speaker"] == speaker:
            out[-1]["text"] = "%s %s" % (out[-1]["text"], text)
            continue
        out.append({"_speaker": speaker, "voice_id": voices.get(speaker, speaker), "text": text})
    for entry in out:
        entry.pop("_speaker")
    return out


def payloads(item, voices=None):
    return {
        "performance_a": payload(item["performance_a"]["turns"], voices),
        "performance_b": payload(item["performance_b"]["turns"], voices),
    }


def as_python(item, voices=None):
    """A runnable snippet with the voice ids left as module-level names."""
    lines = [
        "# %s" % item.get("title", "untitled"),
        "# setting: %s" % item.get("setting", ""),
        "# %s" % ("-" * 68),
        "SPEAKER_A_VOICE_ID = \"\"  # fill in",
        "SPEAKER_B_VOICE_ID = \"\"  # fill in",
        "",
    ]
    for name in ("performance_a", "performance_b"):
        perf = item[name]
        fn = perf.get("function") or {}
        lines += [
            "# %s" % ("=" * 68),
            "# %s — %s" % (name.upper(), fn.get("name", "?")),
            "# branch:   %s" % fn.get("branch_name", "?"),
            "# framing:  %s" % perf.get("framing", ""),
            "# expected: %s" % perf.get("expected_answer", ""),
            "%s = [" % name.upper(),
        ]
        for entry in payload(perf["turns"], voices):
            var = "SPEAKER_A_VOICE_ID" if entry["voice_id"].startswith("SPEAKER_A") else "SPEAKER_B_VOICE_ID"
            lines += [
                "    {",
                "        \"voice_id\": %s," % var,
                "        \"text\": (",
                "            %s" % json.dumps(entry["text"], ensure_ascii=False),
                "        ),",
                "    },",
            ]
        lines += ["]", ""]
    return "\n".join(lines)


def as_markdown(item):
    fn_a = item["performance_a"].get("function") or {}
    fn_b = item["performance_b"].get("function") or {}
    lines = [
        "# %s" % item.get("title", "untitled"),
        "",
        "**Setting.** %s" % item.get("setting", ""),
        "",
        "**Pair.** `%s` (%s) vs `%s` (%s)%s"
        % (
            fn_a.get("key", "?"),
            fn_a.get("branch_name", "?"),
            fn_b.get("key", "?"),
            fn_b.get("branch_name", "?"),
            "  — crosses branches" if item.get("pair", {}).get("crosses_branch") else "",
        ),
        "",
        "## Shared transcript (no audio tags)",
        "",
        "```",
    ]
    for i, turn in enumerate(item["transcript"]):
        marker = "   <- target laugh" if i == item["laugh_turn"] else ""
        lines.append("%s: %s%s" % (turn["speaker"], turn["text"], marker))
    lines += ["```", ""]
    if item.get("why_ambiguous"):
        lines += ["*Why it is ambiguous on the page:* %s" % item["why_ambiguous"], ""]

    for name, fn in (("performance_a", fn_a), ("performance_b", fn_b)):
        perf = item[name]
        lines += [
            "## %s — %s" % (name.replace("_", " ").title(), fn.get("name", "?")),
            "",
            "- **Branch.** %s" % fn.get("branch_name", "?"),
            "- **Framing.** %s" % perf.get("framing", ""),
            "- **Laughable.** %s" % perf.get("laughable", ""),
            "- **Arousal.** %s" % perf.get("arousal", fn.get("arousal", "?")),
            "- **Expected answer.** %s" % perf.get("expected_answer", ""),
            "",
            "```",
        ]
        for turn in perf["turns"]:
            lines.append("%s: %s" % (turn["speaker"], turn["text"]))
        lines += ["```", ""]

    probe = item.get("probe") or {}
    if probe:
        lines += [
            "## Probe",
            "",
            "Open: %s" % probe.get("open_question", ""),
            "",
            "Forced choice:",
            "",
            "```",
            probe.get("forced_choice_question", ""),
            "```",
            "",
            "Gold: performance A -> `%s`, performance B -> `%s`"
            % (
                probe.get("forced_choice_gold", {}).get("performance_a"),
                probe.get("forced_choice_gold", {}).get("performance_b"),
            ),
            "",
            probe.get("grading_note", ""),
            "",
        ]
    return "\n".join(lines)


def write_bundle(item, report, out_dir, item_id):
    """Write item.json, tts.py, item.md and report.json. Returns the paths written."""
    base = os.path.join(out_dir, item_id)
    os.makedirs(base, exist_ok=True)
    paths = {}

    paths["item"] = os.path.join(base, "item.json")
    with open(paths["item"], "w") as fh:
        json.dump(item, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    paths["tts"] = os.path.join(base, "tts.py")
    with open(paths["tts"], "w") as fh:
        fh.write(as_python(item))

    paths["markdown"] = os.path.join(base, "item.md")
    with open(paths["markdown"], "w") as fh:
        fh.write(as_markdown(item))

    paths["report"] = os.path.join(base, "report.json")
    with open(paths["report"], "w") as fh:
        json.dump(report.as_dict(), fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    return paths


def append_jsonl(item, path):
    with open(path, "a") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")
