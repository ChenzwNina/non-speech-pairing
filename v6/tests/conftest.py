from __future__ import annotations

import sys
from pathlib import Path

# v6/tests/ holds two suites with different import roots. The audio-pipeline tests import
# `pipeline.*` from v6/, which pytest already puts on sys.path (tests/ is a package, so the
# basedir it inserts is v6/). The evaluation tests were written for
# `unittest discover -t v6/tests` and import `fixtures` as a top-level module, which that
# insertion does not cover — so add tests/ itself. Both suites then collect under one pytest run.
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pytest

from pipeline.schema import parse_item

SAMPLE_RATE = 44100


def _turn(turn, speaker, text):
    return {"turn": turn, "speaker": speaker, "text": text}


def make_raw_item(**overrides) -> dict:
    """A minimal valid v6 item, matching out/pairs_spoken.json's schema. `overrides` replaces
    top-level keys wholesale (e.g. baseline={...})."""
    raw = {
        "item_id": "t_01a",
        "scenario": "Two people talk about a trip.",
        "voc_a": "laugh", "emotion_a": "amusement", "tag_a": "(laughs)",
        "voc_b": "sigh", "emotion_b": "resignation", "tag_b": "(sighs)",
        "vocalization_turn": 2, "vocalization_speaker": "B",
        "baseline": {"turns": [
            _turn(1, "A", "The kids are crawling around the living room like lions."),
            _turn(2, "B", "Looks like the safari gave them a new game."),
            _turn(3, "A", "They've been playing it since we got home."),
            _turn(4, "B", "I'll move the coffee table out of their way."),
        ]},
        "condition_a": {"turns": [
            _turn(1, "A", "The kids are crawling around the living room like lions."),
            _turn(2, "B", "(laughs) Looks like the safari gave them a new game."),
            _turn(3, "A", "They've been playing it since we got home."),
            _turn(4, "B", "I'll move the coffee table out of their way."),
        ]},
        "condition_b": {"turns": [
            _turn(1, "A", "The kids are crawling around the living room like lions."),
            _turn(2, "B", "(sighs) Looks like the safari gave them a new game."),
            _turn(3, "A", "They've been playing it since we got home."),
            _turn(4, "B", "I'll move the coffee table out of their way."),
        ]},
    }
    raw.update(overrides)
    return raw


@pytest.fixture
def valid_item():
    return parse_item(make_raw_item())


def sine_wave(duration_s: float, freq: float = 220.0, sample_rate: int = SAMPLE_RATE,
              amplitude: float = 0.5) -> np.ndarray:
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    return amplitude * np.sin(2 * np.pi * freq * t)


def silence(duration_s: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    return np.zeros(int(sample_rate * duration_s), dtype=np.float64)
