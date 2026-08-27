"""Text-only models: the writers behind stages 2, 4 and 5, and the Q1 judge panel.

providers.py speaks to the four speech-to-speech models over realtime websockets. This module
is the other half — ordinary request/response text calls, kept separate because nothing here
touches audio and none of it needs the realtime machinery.

Writers return JSON against a schema, so a malformed answer is a validation error rather than
something that quietly flows downstream. Judges return free text, because ranking a pair of
responses has no schema worth imposing.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
load_dotenv(REPO / ".env")
for extra in (REPO.parent / "non-speech-vocalization" / ".env",
              REPO.parent / "non-speech-vocalization2" / ".env",
              REPO.parent / "multi-people-voice-agent" / ".env"):
    if not os.environ.get("XAI_API_KEY") and extra.exists():
        load_dotenv(extra)

XAI_BASE = "https://api.x.ai/v1"

# Stage 4 is GPT-4o per the spec, where every other writing stage is GPT-5.6-Terra. Kept as
# written rather than quietly upgraded.
WRITER = "gpt-5.6-terra"
PLACER = "gpt-4o"
VERIFIER = "claude-opus-5"

# The Q1 panel: three judges from three vendors, one judgement each, averaged. Vendor
# diversity is the point — a panel of one family agrees with itself.
JUDGES = {"opus": "claude-opus-5", "terra": "gpt-5.6-terra", "grok": "grok-4.6"}

MAX_OUTPUT_TOKENS = 8000
ATTEMPTS = 3


def key(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is empty; set it in .env")
    return value


def _openai() -> OpenAI:
    return OpenAI(api_key=key("OPENAI_API_KEY"))


def _xai() -> OpenAI:
    return OpenAI(api_key=key("XAI_API_KEY"), base_url=XAI_BASE)


def _anthropic():
    from anthropic import Anthropic
    return Anthropic(api_key=key("ANTHROPIC_API_KEY"))


def retry(call, *args, **kwargs):
    """Transient API failures are common enough that one attempt is not a measurement."""
    last = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return call(*args, **kwargs)
        except Exception as exc:                      # noqa: BLE001 - reported, then retried
            last = exc
            if attempt < ATTEMPTS:
                time.sleep(2.0 * attempt)
    raise last


def json_call(model: str, system: str, prompt: str, schema: dict, name: str,
              effort: str | None = None) -> dict:
    """A writer call that must come back as JSON matching `schema`."""
    kwargs = dict(model=model, instructions=system, input=prompt,
                  text={"format": {"type": "json_schema", "name": name,
                                   "schema": schema, "strict": True}},
                  max_output_tokens=MAX_OUTPUT_TOKENS)
    # The gpt-4 family has no reasoning parameter; sending one is an error, not a no-op.
    if effort and not re.match(r"^gpt-(4|3\.5)", model):
        kwargs["reasoning"] = {"effort": effort}
    response = _openai().responses.create(**kwargs)
    if response.status != "completed":
        raise RuntimeError(f"status={response.status} "
                           f"{getattr(response, 'incomplete_details', None)}")
    return json.loads(response.output_text)


def ask(judge: str, system: str, prompt: str, max_tokens: int = 1200) -> str:
    """One text judgement from one judge, at its default effort. Returns raw text."""
    model = JUDGES.get(judge, judge)
    if model.startswith("claude"):
        message = _anthropic().messages.create(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": prompt}])
        return "".join(block.text for block in message.content
                       if getattr(block, "type", "") == "text").strip()
    client = _xai() if model.startswith("grok") else _openai()
    response = client.responses.create(model=model, instructions=system, input=prompt,
                                       max_output_tokens=max_tokens)
    return (response.output_text or "").strip()


def ask_json(judge: str, system: str, prompt: str, keys: tuple[str, ...],
             max_tokens: int = 1200) -> dict:
    """A judgement that must parse as a JSON object carrying `keys`.

    Judges are asked for JSON in the prompt rather than constrained by a schema, because the
    three vendors do not share one structured-output mechanism and a panel whose members are
    constrained differently is not a panel of equals.
    """
    text = ask(judge, system, prompt, max_tokens)
    blob = re.search(r"\{.*\}", text, re.S)
    if not blob:
        raise ValueError(f"{judge}: no JSON object in {text[:200]!r}")
    data = json.loads(blob.group(0))
    missing = [k for k in keys if k not in data]
    if missing:
        raise ValueError(f"{judge}: missing {missing} in {data}")
    return data


if __name__ == "__main__":
    # Smoke test: every writer and judge reachable, before anything depends on them.
    print(f"{'model':22} {'role':10} reply")
    for role, model in (("writer", WRITER), ("placer", PLACER), ("verifier", VERIFIER)):
        try:
            out = ask(model, "Reply with one word.", "Say READY.")
            print(f"  {model:20} {role:10} {out[:40]!r}")
        except Exception as exc:
            print(f"  {model:20} {role:10} FAILED {type(exc).__name__}: {exc}"[:150])
    for judge, model in JUDGES.items():
        try:
            out = ask(judge, "Reply with one word.", "Say READY.")
            print(f"  {model:20} {'judge/' + judge:10} {out[:40]!r}")
        except Exception as exc:
            print(f"  {model:20} {'judge/' + judge:10} FAILED {type(exc).__name__}: {exc}"[:150])
