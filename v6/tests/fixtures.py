"""Synthetic items and judgements with known properties, for the tests to reason about."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

WORDS = ["The kids are asking to go back to the giraffes.",
         "I knew one visit wasn't enough.",
         "We still have twenty minutes.",
         "All right, let's take them over."]
SPEAKERS = ["A", "B", "A", "B"]
VOC_TURN = 2

TAGS = {"laugh": "(laughs)", "sigh": "(sighs)", "gasp": "(gasps)",
        "groan": "(groans)", "scream": "(screams)"}


def version(tag: str | None, vocalization: str, emotion: str) -> dict:
    turns = []
    for number, (speaker, text) in enumerate(zip(SPEAKERS, WORDS), start=1):
        if tag and number == VOC_TURN:
            text = f"{tag} {text}"
        turns.append({"turn": number, "speaker": speaker, "text": text})
    return {"vocalization": vocalization, "target_emotion": emotion, "turns": turns}


def item(item_id: str = "t_01a", voc_a: str = "laugh", voc_b: str = "sigh") -> dict:
    """A minimal item that passes every validation check."""
    return {
        "item_id": item_id, "scenario": "Two parents leaving a safari park.",
        "voc_a": voc_a, "emotion_a": "amusement", "tag_a": TAGS[voc_a],
        "voc_b": voc_b, "emotion_b": "resignation", "tag_b": TAGS[voc_b],
        "vocalization_turn": VOC_TURN, "vocalization_speaker": SPEAKERS[VOC_TURN - 1],
        "baseline": version(None, "none", "ambiguous"),
        "condition_a": version(TAGS[voc_a], voc_a, "amusement"),
        "condition_b": version(TAGS[voc_b], voc_b, "resignation"),
    }


def broken(what: str) -> dict:
    """The same item with one specific defect the validator is required to catch."""
    bad = copy.deepcopy(item())
    if what == "lexical_mismatch":
        bad["condition_b"]["turns"][2]["text"] = "We still have thirty minutes."
    elif what == "tag_in_baseline":
        bad["baseline"]["turns"][1]["text"] = "(sighs) I knew one visit wasn't enough."
    elif what == "tag_wrong_turn":
        turns = bad["condition_a"]["turns"]
        turns[1]["text"] = WORDS[1]
        turns[2]["text"] = f"(laughs) {WORDS[2]}"
    elif what == "tag_wrong_speaker":
        bad["vocalization_speaker"] = "A"
    elif what == "metadata_mismatch":
        bad["condition_a"]["target_emotion"] = "surprise"
    elif what == "unapproved_tag":
        bad["condition_a"]["turns"][1]["text"] = "(chuckles) I knew one visit wasn't enough."
        bad["tag_a"] = "(chuckles)"
    else:
        raise ValueError(what)
    return bad


def config(audio_root: str = "out/audio-does-not-exist") -> dict:
    return {"dataset": {"transcripts": "out/pairs_spoken.json",
                        "renderers": {"testrender": {
                            "audio_root": audio_root,
                            "audio_path_template": "{item_id}__{condition}.wav"}},
                        "default_renderer": "testrender"},
            "seed": 20260902,
            "inventory": ["laugh", "sigh", "gasp", "groan", "scream", "none"],
            "writers": {}, "evaluated_models": [], "judges": {},
            "scoring": {"bootstrap_resamples": 200, "confidence": 0.95}}


def mc_task(task_id: str, item_id: str, condition: str, correct_label: str,
            correct_option: str = "A") -> dict:
    others = iter([l for l in ("laugh", "sigh", "gasp", "groan", "none")
                   if l != correct_label][:3])
    options = []
    for option_id in "ABCD":
        label = correct_label if option_id == correct_option else next(others)
        options.append({"id": option_id, "label": label, "text": label})
    return {"task_id": task_id, "item_id": item_id, "condition": condition,
            "options": options, "correct_option": correct_option,
            "correct_label": correct_label, "gold_vocalization": correct_label}


def judgment(task_id: str, item_id: str, task_type: str, parsed: dict,
             judge: str = "gpt", condition: str = "condition_a",
             model: str = "openai", status: str = "ok") -> dict:
    return {"task_id": task_id, "item_id": item_id, "condition": condition,
            "task_type": task_type, "judge": judge, "evaluated_model": model,
            "parsed": parsed, "status": status, "gold_vocalization": "laugh"}


def response(item_id: str, condition: str, model: str = "openai") -> dict:
    return {"task_type": "response", "item_id": item_id, "condition": condition,
            "evaluated_model": model, "status": "ok",
            "response_text": f"{model} on {item_id} {condition}",
            "response_audio_path": f"out/eval/responses/{model}_{item_id}_{condition}.wav",
            "stimulus_audio_path": f"out/audio/{item_id}__{condition}.wav"}
