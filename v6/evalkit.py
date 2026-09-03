"""Shared machinery for the v6 evaluation: config, provenance, records, schemas, seeded draws.

Every stage of the evaluation is a separate script, as elsewhere in this repository, and they
agree through this module rather than by importing each other. What lives here is the part that
has to be identical everywhere: where outputs go, how a task is named, how a record carries
enough provenance to be reproduced, and how a random choice is made so that it comes out the
same on the next run and on another machine.

Three habits are enforced rather than documented:

`guard()` is called by anything that is about to reach a paid API. Under `--dry-run` it raises,
so a dry run cannot silently spend money — and a test can assert that.

`write_json()` refuses to overwrite. Task sets and option orders are frozen once and shared by
every evaluated model; a stage that quietly rewrote them would make two models' scores
incomparable without leaving a trace.

`stable_rng()` never uses `hash()`. Python salts string hashing per process, so a seeded draw
keyed on an item id would reshuffle between runs. Keying on sha256 instead makes the draw
reproducible and independent of iteration order.
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
OUT = HERE / "out" / "eval"
PROMPTS = HERE / "prompts"
SCHEMAS = HERE / "schemas"
CONFIG = HERE / "eval_config.yaml"

STAGES = ("validation", "tasks", "writer_raw", "rubrics", "responses", "judgments", "scores")
CONDITIONS = ("baseline", "condition_a", "condition_b")
RESPONSE_CODE = {"baseline": "R0", "condition_a": "RA", "condition_b": "RB"}


class ConfigError(RuntimeError):
    """The configuration or source data is unusable. Callers exit nonzero."""


class DryRunViolation(RuntimeError):
    """Something tried to reach a paid API during a dry run."""


_dry_run = False


def set_dry_run(on: bool) -> None:
    global _dry_run
    _dry_run = bool(on)


def dry_run() -> bool:
    return _dry_run


def guard(what: str) -> None:
    """Call immediately before any paid API request."""
    if _dry_run:
        raise DryRunViolation(f"dry run: refused to call {what}")


# ---------------------------------------------------------------- config and prompts

REQUIRED = ("dataset", "seed", "inventory", "writers", "evaluated_models", "judges")


def load_config(path: Path | None = None) -> dict:
    path = path or CONFIG
    if not path.exists():
        raise ConfigError(f"no configuration at {path}")
    config = yaml.safe_load(path.read_text())
    missing = [key for key in REQUIRED if key not in config]
    if missing:
        raise ConfigError(f"{path.name} is missing {missing}")
    for key in ("transcripts", "renderers", "default_renderer"):
        if key not in config["dataset"]:
            raise ConfigError(f"{path.name}: dataset.{key} is not set")
    for name, block in config["dataset"]["renderers"].items():
        for key in ("audio_root", "audio_path_template"):
            if key not in block:
                raise ConfigError(f"{path.name}: renderers.{name}.{key} is not set")
    if config["dataset"]["default_renderer"] not in config["dataset"]["renderers"]:
        raise ConfigError(f"{path.name}: default_renderer "
                          f"{config['dataset']['default_renderer']!r} is not a configured "
                          f"renderer")
    config["_path"] = str(path)
    return config


def prompt(name: str) -> tuple[str, str]:
    """A prompt template and a version stamp for it, so a record names the exact text used."""
    path = PROMPTS / f"{name}.txt"
    if not path.exists():
        raise ConfigError(f"no prompt template at {path}")
    text = path.read_text()
    return text, f"{name}@{hashlib.sha256(text.encode()).hexdigest()[:12]}"


def fill(template: str, **values: str) -> str:
    for token, value in values.items():
        template = template.replace(f"{{{{{token}}}}}", value)
    return template


def schema(name: str) -> dict:
    """`"content_rubric"` for a whole file, `"judge_outputs:content_absolute"` for one $def."""
    file, _, part = name.partition(":")
    path = SCHEMAS / f"{file}.schema.json"
    if not path.exists():
        raise ConfigError(f"no schema at {path}")
    whole = json.loads(path.read_text())
    if not part:
        return whole
    if part not in whole.get("$defs", {}):
        raise ConfigError(f"{path.name} has no $defs/{part}")
    return {"$ref": f"#/$defs/{part}", "$defs": whole["$defs"]}


def strict(node):
    """The same schema, tightened for providers that constrain generation.

    The schema files are validation contracts and leave genuinely optional fields optional —
    confidence, for one. Structured-output modes require every property to be required and
    additional properties closed, so a request builds its constraint from this instead.
    """
    if isinstance(node, list):
        return [strict(child) for child in node]
    if not isinstance(node, dict):
        return node
    out = {key: strict(value) for key, value in node.items()}
    if out.get("type") == "object" and "properties" in out:
        out["additionalProperties"] = False
        out["required"] = list(out["properties"])
    return out


def schema_errors(name: str, payload) -> list[str]:
    """Every way `payload` fails `name`, as readable lines. Empty means valid."""
    import jsonschema

    validator = jsonschema.Draft202012Validator(schema(name))
    return [f"{'/'.join(str(p) for p in error.path) or '<root>'}: {error.message}"
            for error in sorted(validator.iter_errors(payload), key=lambda e: list(e.path))]


# ---------------------------------------------------------------- identity and provenance

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_id(explicit: str | None = None) -> str:
    """Pass `--run-id` to group records across stages; otherwise one per invocation."""
    return explicit or f"r{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def task_id(item_id: str, condition: str, task_type: str, *extra: str) -> str:
    return "__".join([item_id, condition, task_type, *extra])


def stable_rng(seed: int, *parts) -> random.Random:
    """A generator keyed on `parts`, reproducible across processes and machines.

    Deliberately not `hash()`: string hashing is salted per process, so a draw keyed on an item
    id would differ between runs unless PYTHONHASHSEED were pinned everywhere.
    """
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).digest()
    return random.Random(int(seed) ^ int.from_bytes(digest[:8], "big"))


def provenance(*, run: str, item_id: str, condition: str, task_type: str,
               prompt_version: str = "", stimulus_audio_path: str = "",
               model_provider: str = "", model_name: str = "", model_version: str = "",
               settings: dict | None = None, seed: int | None = None,
               raw_path: str = "", parsed=None, status: str = "ok",
               errors: list[str] | None = None, **extra) -> dict:
    """The envelope every generated record carries, per the spec's provenance list."""
    return {"run_id": run, "item_id": item_id, "condition": condition,
            "task_type": task_type, "task_id": task_id(item_id, condition, task_type),
            "stimulus_audio_path": stimulus_audio_path, "prompt_version": prompt_version,
            "model_provider": model_provider, "model_name": model_name,
            "model_version": model_version, "settings": settings or {}, "seed": seed,
            "timestamp": now(), "raw_response_path": raw_path, "parsed": parsed,
            "status": status, "errors": errors or [], **extra}


# ---------------------------------------------------------------- records on disk

def stage_dir(stage: str) -> Path:
    if stage not in STAGES:
        raise ConfigError(f"unknown stage {stage!r}; expected one of {STAGES}")
    path = OUT / stage
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload, overwrite: bool = False) -> Path:
    if path.exists() and not overwrite:
        raise ConfigError(f"{path} exists; pass --overwrite to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return path


def append_jsonl(path: Path, record: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def save_raw(stage: str, name: str, text: str) -> str:
    """Store a model's response before anything tries to parse it."""
    path = stage_dir(stage) / f"{name}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return str(path.relative_to(HERE))


# ---------------------------------------------------------------- the dataset

def load_items(config: dict) -> tuple[dict, list[dict]]:
    path = HERE / config["dataset"]["transcripts"]
    if not path.exists():
        raise ConfigError(f"no transcripts at {path}")
    data = json.loads(path.read_text())
    if not data.get("items"):
        raise ConfigError(f"{path} has no items")
    return data, data["items"]


WRITER_FIELDS = ("item_id", "scenario", "vocalization_turn", "vocalization_speaker",
                 "voc_a", "emotion_a", "tag_a", "voc_b", "emotion_b", "tag_b")


def writer_payload(item: dict) -> dict:
    """What a writer is shown: the stimulus, and nothing about how it was made.

    The generation metadata is withheld on purpose — `seed_label` above all, the
    EmpatheticDialogues emotion the scenario was sampled from. That label is a property of the
    sampling, not of the stimulus: a writer told the seed was `proud` would build rubrics around
    pride whether the four turns support it or not. `situation`, `writer_id` and the pre-rewrite
    transcript are dropped for the same reason, being facts about construction rather than about
    the conversation a model will hear.
    """
    payload = {key: item[key] for key in WRITER_FIELDS if key in item}
    for condition in CONDITIONS:
        block = item[condition]
        payload[condition] = {"vocalization": block["vocalization"],
                              "target_emotion": block["target_emotion"],
                              "turns": block["turns"]}
    return payload


def json_object(text: str):
    """The first JSON object in a reply, fences and commentary tolerated. None if there is none."""
    import re

    stripped = re.sub(r"^\s*```(?:json)?|```\s*$", "", text.strip(), flags=re.M)
    match = re.search(r"\{.*\}", stripped, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def renderers(config: dict) -> dict:
    return config["dataset"]["renderers"]


def default_renderer(config: dict) -> str:
    return config["dataset"]["default_renderer"]


def audio_path(config: dict, item_id: str, condition: str,
               renderer: str | None = None) -> Path:
    dataset = config["dataset"]
    renderer = renderer or dataset["default_renderer"]
    block = dataset["renderers"].get(renderer)
    if block is None:
        raise ConfigError(f"unknown renderer {renderer!r}; configured: "
                          f"{sorted(dataset['renderers'])}")
    name = block["audio_path_template"].format(
        item_id=item_id, condition=condition, response=RESPONSE_CODE[condition],
        renderer=renderer)
    return HERE / block["audio_root"] / name


def stimuli(items: list[dict]):
    """Every (item, condition) pair, in a fixed order: the evaluation's unit of work."""
    for item in items:
        for condition in CONDITIONS:
            yield item, condition


def gold_vocalization(item: dict, condition: str) -> str:
    return {"baseline": "none", "condition_a": item["voc_a"],
            "condition_b": item["voc_b"]}[condition]


def gold_emotion(item: dict, condition: str) -> str:
    return {"baseline": "ambiguous", "condition_a": item["emotion_a"],
            "condition_b": item["emotion_b"]}[condition]


def lexical_turns(item: dict, condition: str = "baseline") -> list[dict]:
    return item[condition]["turns"]


def transcript_text(item: dict, condition: str) -> str:
    return "\n".join(f"{t['speaker']}: {t['text']}" for t in item[condition]["turns"])


# ---------------------------------------------------------------- terminal reporting

def report(label: str, **counts: int) -> None:
    """The counts line every command is required to print."""
    body = "  ".join(f"{name} {value}" for name, value in counts.items())
    print(f"{label}: {body}")
