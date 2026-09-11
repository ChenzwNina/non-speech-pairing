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
import subprocess
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent           # v6 sits directly under the repository root
load_dotenv(REPO / ".env")
for extra in (REPO.parent / "non-speech-vocalization" / ".env",
              REPO.parent / "non-speech-vocalization2" / ".env",
              REPO.parent / "multi-people-voice-agent" / ".env"):
    if not os.environ.get("XAI_API_KEY") and extra.exists():
        load_dotenv(extra)

XAI_BASE = "https://api.x.ai/v1"

# Claude runs through the Claude Code CLI rather than the Anthropic API, so it draws on the
# subscription instead of API credit. Two flags matter. --system-prompt replaces the agent
# prompt instead of appending to it, and --exclude-dynamic-system-prompt-sections drops the
# per-session sections: together they cut a one-word answer from $0.235 to $0.046. Do NOT add
# --disallowed-tools to trim further — changing the tool set invalidates the prompt cache
# every call, which costs four times more than the schemas do.
CLAUDE_CLI = "claude"
CLI_FLAGS = ("--output-format", "json", "--exclude-dynamic-system-prompt-sections")
CLI_TIMEOUT = 240

CLI_COST: list[float] = []
# Every model call appends one row. Without this the only record of what a run cost is the
# Claude CLI's dollar figure, which is per-process and never written down — so the transcript
# pipeline's usage was unrecoverable once it had finished. Reasoning tokens are counted
# separately because they do not appear in the text a call returns, which is what makes an
# estimate reconstructed from saved responses undercount. They are a subset of output_tokens,
# so a total must not add them again.
USAGE: list[dict] = []
_cost_lock = threading.Lock()

# Stage 4 is GPT-4o per the spec, where every other writing stage is GPT-5.6-Terra. Kept as
# written rather than quietly upgraded.
WRITER = "gpt-5.6-sol"
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


def ask_claude(model: str, system: str, prompt: str) -> str:
    """One judgement from Claude, via the CLI. The prompt goes in on stdin, so its length and
    contents need no quoting."""
    # The CLI prefers an API key over the OAuth subscription when one is in the environment,
    # and this module has just loaded .env into os.environ. Inheriting that key silently moves
    # billing off the team subscription and onto API credit — which reads as "Credit balance is
    # too low" from an account that has a perfectly good subscription. So the child does not
    # get to see it.
    env = {k: v for k, v in os.environ.items()
           if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    proc = subprocess.run(
        [CLAUDE_CLI, "-p", "--model", model, "--system-prompt", system, *CLI_FLAGS],
        input=prompt, capture_output=True, text=True, timeout=CLI_TIMEOUT, env=env)
    if proc.returncode != 0:
        # A failing CLI still answers in JSON, and the reason lives in `result`. Reporting the
        # raw first 200 characters instead buries it behind the usage block, which is how an
        # expired login reads as an unexplained exit 1.
        reason = (proc.stderr or "").strip()
        try:
            reason = str(json.loads(proc.stdout).get("result") or reason)
        except (json.JSONDecodeError, AttributeError):
            reason = reason or proc.stdout
        raise RuntimeError(f"claude cli exit {proc.returncode}: {reason[:200]}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"claude cli gave no JSON: {proc.stdout[:200]}") from exc
    if payload.get("is_error"):
        raise RuntimeError(f"claude cli reported an error: {str(payload.get('result'))[:200]}")
    with _cost_lock:
        CLI_COST.append(payload.get("total_cost_usd") or 0.0)
        used = payload.get("usage") or {}
        USAGE.append({"model": model, "transport": "cli",
                      "input_tokens": used.get("input_tokens", 0),
                      "output_tokens": used.get("output_tokens", 0),
                      "reasoning_tokens": 0,
                      "cache_read_tokens": used.get("cache_read_input_tokens", 0),
                      "cache_write_tokens": used.get("cache_creation_input_tokens", 0),
                      "cost_usd": payload.get("total_cost_usd") or 0.0})
    return (payload.get("result") or "").strip()


def cli_spend() -> float:
    return sum(CLI_COST)


def usage_rows() -> list[dict]:
    """Every call this process made. Cost is present only where the provider reported one."""
    return list(USAGE)


def _pricing() -> dict:
    """The config's price table, or empty. Loaded lazily so a missing config costs a report
    line rather than an import error in a stage that never prices anything."""
    try:
        import evalkit as K

        return K.load_config().get("pricing") or {}
    except Exception:                              # noqa: BLE001 - pricing is never essential
        return {}


def price_of(row: dict, pricing: dict) -> float | None:
    """What one call cost, or None when the provider reported it or no rate is configured.

    Cached reads and cache writes bill at their own rates, which is the whole reason the CLI's
    tenfold swing between a cold and a warm call exists. Reasoning tokens are already inside
    `output_tokens` and are billed at the output rate, so they are not added separately.
    """
    rates = (pricing.get("models") or {}).get(row["model"])
    if not rates:
        return None
    tier = ("long" if row.get("input_tokens", 0) + row.get("cache_read_tokens", 0)
            + row.get("cache_write_tokens", 0) > pricing.get("long_context_threshold", 128000)
            else "short")
    r = rates.get(tier) or {}
    return (row.get("input_tokens", 0) * r.get("input", 0)
            + row.get("cache_read_tokens", 0) * r.get("cached_input", 0)
            + row.get("cache_write_tokens", 0) * r.get("cache_write", 0)
            + row.get("output_tokens", 0) * r.get("output", 0)) / 1_000_000


def usage_report(label: str = "usage") -> str:
    """One line per model, plus a total. Empty when nothing was called."""
    if not USAGE:
        return ""
    pricing = _pricing()
    by: dict[str, dict] = {}
    for row in USAGE:
        acc = by.setdefault(row["model"], {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                                           "reasoning_tokens": 0, "cache_read_tokens": 0,
                                           "cache_write_tokens": 0, "cost_usd": 0.0})
        acc["calls"] += 1
        for k in ("input_tokens", "output_tokens", "reasoning_tokens", "cache_read_tokens",
                  "cache_write_tokens"):
            acc[k] += row.get(k, 0)
        # A provider-reported cost is authoritative; otherwise price it from the table.
        acc["cost_usd"] += row.get("cost_usd") or (price_of(row, pricing) or 0.0)
        acc["priced"] = acc.get("priced", True) and (
            bool(row.get("cost_usd")) or price_of(row, pricing) is not None)
    lines = [f"{label}:"]
    for model, a in sorted(by.items()):
        # The Claude CLI bills most of a first call's input as cache creation and reports
        # input_tokens as the remainder, so an input figure that omits the cache columns reads
        # as ~0 and hides where the money went. Reasoning tokens are a subset of output_tokens.
        billed_in = a["input_tokens"] + a["cache_write_tokens"] + a["cache_read_tokens"]
        lines.append(f"  {model}  {a['calls']} call(s)  in {billed_in:,} "
                     f"(fresh {a['input_tokens']:,} · cache write {a['cache_write_tokens']:,} "
                     f"· cache read {a['cache_read_tokens']:,})  "
                     f"out {a['output_tokens']:,} (of which reasoning "
                     f"{a['reasoning_tokens']:,})"
                     + (f"  ${a['cost_usd']:.4f}" if a.get("priced")
                        else "  cost not reported"))
    total = sum(a["cost_usd"] for a in by.values())
    if total and all(a.get("priced") for a in by.values()):
        lines.append(f"  total  ${total:.4f}")
    return "\n".join(lines)


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
              effort: str | None = None, max_tokens: int | None = None) -> dict:
    """A writer call that must come back as JSON matching `schema`."""
    kwargs = dict(model=model, instructions=system, input=prompt,
                  text={"format": {"type": "json_schema", "name": name,
                                   "schema": schema, "strict": True}},
                  max_output_tokens=max_tokens or MAX_OUTPUT_TOKENS)
    # The gpt-4 family has no reasoning parameter; sending one is an error, not a no-op.
    if effort and not re.match(r"^gpt-(4|3\.5)", model):
        kwargs["reasoning"] = {"effort": effort}
    response = _openai().responses.create(**kwargs)
    used = getattr(response, "usage", None)
    if used is not None:
        details = getattr(used, "output_tokens_details", None)
        with _cost_lock:
            USAGE.append({"model": model, "transport": "openai",
                          "input_tokens": getattr(used, "input_tokens", 0) or 0,
                          "output_tokens": getattr(used, "output_tokens", 0) or 0,
                          "reasoning_tokens": getattr(details, "reasoning_tokens", 0) or 0,
                          "cache_read_tokens": 0, "cache_write_tokens": 0, "cost_usd": 0.0})
    if response.status != "completed":
        raise RuntimeError(f"status={response.status} "
                           f"{getattr(response, 'incomplete_details', None)}")
    return json.loads(response.output_text)


def ask(judge: str, system: str, prompt: str, max_tokens: int = 1200) -> str:
    """One text judgement from one judge, at its default effort. Returns raw text."""
    model = JUDGES.get(judge, judge)
    if model.startswith("claude"):
        return ask_claude(model, system, prompt)
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
        if model.startswith("claude"):
            try:
                out = ask_claude(model, "Reply with one word.", "Say READY.")
                print(f"  {model:20} {role:10} {out[:40]!r}  (via CLI)")
            except Exception as exc:
                print(f"  {model:20} {role:10} FAILED {type(exc).__name__}: {exc}"[:150])
            continue
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
