"""Thin wrapper around the headless Claude CLI (`claude -p --output-format json`).

Every model call in the harness goes through here so that model choice, retries and JSON
extraction live in one place. Stdlib only.
"""

import json
import os
import re
import shutil
import subprocess


class ClaudeError(RuntimeError):
    pass


def cli_path():
    """Locate the Claude CLI binary."""
    candidate = os.environ.get("CLAUDE_CODE_EXECPATH")
    if candidate and os.path.exists(candidate):
        return candidate
    found = shutil.which("claude")
    if found:
        return found
    raise ClaudeError(
        "Claude CLI not found. Set CLAUDE_CODE_EXECPATH or put `claude` on PATH."
    )


def ask(prompt, system=None, model="sonnet", timeout=900):
    """One-shot text call. Returns (text, cost_usd)."""
    cmd = [
        cli_path(),
        "-p",
        prompt,
        "--output-format",
        "json",
        "--model",
        model,
        "--no-session-persistence",
        "--disable-slash-commands",
        "--strict-mcp-config",
    ]
    if system:
        cmd += ["--system-prompt", system]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise ClaudeError(
            "claude exited %d: %s" % (proc.returncode, (proc.stderr or "")[-2000:])
        )

    payload = _last_json_object(proc.stdout)
    if payload is None:
        raise ClaudeError("could not parse CLI output: %r" % proc.stdout[-500:])
    if payload.get("is_error"):
        raise ClaudeError("claude reported an error: %r" % payload.get("result"))
    return payload.get("result", ""), float(payload.get("total_cost_usd") or 0.0)


def ask_json(prompt, system=None, model="sonnet", timeout=900, attempts=3):
    """Same as `ask`, but insists on a JSON object. Returns (obj, cost_usd)."""
    total = 0.0
    current = prompt
    last_err = None
    for i in range(attempts):
        text, cost = ask(current, system=system, model=model, timeout=timeout)
        total += cost
        obj = extract_json(text)
        if obj is not None:
            return obj, total
        last_err = text
        current = (
            prompt
            + "\n\nYour previous reply was not valid JSON. Reply with the JSON object "
            "only — no prose, no code fence."
        )
    raise ClaudeError("no JSON object after %d attempts. Last reply: %r" % (attempts, (last_err or "")[:500]))


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text):
    """Pull the first JSON object out of a model reply (fenced or bare). None on failure."""
    if not text:
        return None
    for candidate in [m.group(1) for m in _FENCE.finditer(text)] + [text]:
        obj = _scan_object(candidate)
        if obj is not None:
            return obj
    return None


def _scan_object(text):
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch not in "{[":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
        except ValueError:
            continue
        if isinstance(obj, (dict, list)):
            return obj
    return None


def _last_json_object(stdout):
    obj = _scan_object(stdout)
    if isinstance(obj, dict):
        return obj
    for line in reversed(stdout.strip().splitlines()):
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
