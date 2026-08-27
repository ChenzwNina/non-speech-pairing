"""Build a local HTML viewer for predicting_content clips and eval results.

Usage:
    python predicting_content/make_viewer.py
    python predicting_content/make_viewer.py --serve
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ITEMS = HERE / "out" / "items.json"
DEFAULT_EVAL = HERE / "out" / "eval_realtime.json"
DEFAULT_OUT = HERE / "out" / "viewer.html"

VOC_ORDER = [
    "sigh",
    "groan",
    "laugh",
    "hmm",
    "mmhm",
    "scoff",
    "throat_clear",
    "exhale",
    "yawn",
    "shaky_breath",
]

VOC_LABEL = {
    "sigh": "Sigh",
    "groan": "Groan",
    "laugh": "Laugh",
    "hmm": "Hmm",
    "mmhm": "Mm-hm",
    "scoff": "Scoff",
    "throat_clear": "Throat clear",
    "exhale": "Exhale",
    "yawn": "Yawn",
    "shaky_breath": "Shaky breath",
}


def acc_block(rows: list[dict]) -> dict:
    n = len(rows)
    correct = sum(1 for row in rows if row.get("correct"))
    return {"n": n, "correct": correct, "accuracy": (correct / n) if n else None}


def group_acc(rows: list[dict], key: str) -> dict:
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return {name: acc_block(subset) for name, subset in groups.items()}


def merge(items: dict, evaluation: dict) -> dict:
    source = {row["item_id"]: row for row in items["results"] if row.get("gold")}
    trials = []
    for row in evaluation["results"]:
        item = source[row["item_id"]]
        t1, t2, _t3 = item["transcript"]
        trials.append(
            {
                "item_id": row["item_id"],
                "vocalization_id": row["vocalization_id"],
                "vocalization": VOC_LABEL.get(row["vocalization_id"], row["vocalization_id"]),
                "formula": item.get("formula"),
                "domain": row["domain"],
                "content_type": item.get("content_type"),
                "audio": f"audio_sewn/{row['item_id']}.mp3",
                "turn_1": t1["text"],
                "turn_2": t2["text"],
                "options": row["options"],
                "correct_key": row["correct_key"],
                "predicted_key": row.get("predicted_key"),
                "gold_text": row.get("gold_text"),
                "alt_text": row.get("alt_text"),
                "correct": bool(row.get("correct")),
            }
        )
    trials.sort(key=lambda trial: (VOC_ORDER.index(trial["vocalization_id"]) if trial["vocalization_id"] in VOC_ORDER else 99, trial["domain"]))
    return {
        "model": evaluation.get("model"),
        "seed": evaluation.get("seed"),
        "generated_at": evaluation.get("generated_at"),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "n": len(trials),
        "voc_order": VOC_ORDER,
        "voc_label": VOC_LABEL,
        "summary": {
            "overall": acc_block(trials),
            "by_vocalization": group_acc(trials, "vocalization_id"),
            "by_domain": group_acc(trials, "domain"),
        },
        "trials": trials,
    }


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Predicting content · gpt-realtime-2.1</title>
  <style>
    :root {
      --paper: #f3efe6;
      --ink: #1c1712;
      --mute: #6d6458;
      --line: #d8cfc0;
      --card: #fbf8f2;
      --ok: #215c40;
      --ok-bg: #dcecde;
      --miss: #9a3124;
      --miss-bg: #f4ddd6;
      --gold: #8a5a12;
      --gold-bg: #f3e6c8;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; background: var(--paper); color: var(--ink); }
    body {
      font: 15px/1.45 "Avenir Next", "Segoe UI", sans-serif;
      padding: 28px 20px 80px;
    }
    h1, h2, h3, .serif { font-family: "Iowan Old Style", Palatino, "Palatino Linotype", Georgia, serif; }
    .wrap { max-width: 1120px; margin: 0 auto; }
    header.top { display: grid; grid-template-columns: 1fr auto; gap: 18px; align-items: end; padding-bottom: 22px; border-bottom: 1px solid var(--line); }
    header.top p.kicker { margin: 0 0 6px; color: var(--mute); letter-spacing: 0.08em; text-transform: uppercase; font-size: 11px; }
    h1 { margin: 0; font-size: 32px; font-weight: 600; letter-spacing: -0.03em; }
    .lede { margin: 8px 0 0; color: var(--mute); max-width: 44em; }
    .score { text-align: right; }
    .score .num { font-size: 42px; line-height: 1; font-weight: 600; letter-spacing: -0.04em; }
    .score .sub { color: var(--mute); margin-top: 4px; }
    section { margin-top: 28px; }
    h2 { font-size: 18px; margin: 0 0 12px; font-weight: 600; }
    .bars { display: grid; grid-template-columns: 1.4fr 1fr; gap: 28px; }
    .bar-row { display: grid; grid-template-columns: 120px 1fr 54px; gap: 10px; align-items: center; margin: 7px 0; font-size: 13px; }
    .bar-row .label { color: var(--mute); }
    .track { height: 8px; background: #e6dfd2; }
    .fill { height: 8px; background: var(--ink); }
    .fill.low { background: var(--miss); }
    .count { text-align: right; font-variant-numeric: tabular-nums; }
    .controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    select, input[type="search"] {
      font: inherit; background: var(--card); color: var(--ink);
      border: 1px solid var(--line); padding: 7px 10px;
    }
    input[type="search"] { min-width: 220px; }
    .meta { color: var(--mute); font-size: 13px; margin-top: 10px; }
    .card {
      background: var(--card); border: 1px solid var(--line); padding: 18px 18px 14px; margin: 14px 0;
    }
    .card-head { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; margin-bottom: 8px; }
    .card-head h3 { margin: 0; font-size: 18px; }
    .badge { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--mute); }
    .badge.ok { color: var(--ok); }
    .badge.miss { color: var(--miss); }
    .shared { color: var(--mute); font-size: 14px; margin: 0 0 10px; }
    .shared b { color: var(--ink); font-weight: 600; }
    .voc { font-size: 13px; color: var(--mute); margin-bottom: 6px; }
    audio { width: 100%; height: 32px; margin: 4px 0 10px; }
    ul.opts { list-style: none; margin: 0; padding: 0; }
    ul.opts li {
      display: grid; grid-template-columns: 22px 1fr auto; gap: 8px; align-items: start;
      padding: 7px 8px; margin: 4px 0; font-size: 13px; border: 1px solid transparent;
    }
    ul.opts li.gold { background: var(--gold-bg); border-color: #e2c98a; }
    ul.opts li.pred { outline: 1px solid var(--miss); }
    ul.opts li.gold.pred { outline-color: var(--ok); background: var(--ok-bg); border-color: #b7d0bb; }
    .tag { font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--mute); padding-top: 2px; }
    .empty { color: var(--mute); padding: 24px 0; }
    @media (max-width: 820px) {
      header.top, .bars { grid-template-columns: 1fr; }
      .score { text-align: left; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <header class="top">
      <div>
        <p class="kicker">Predicting content eval</p>
        <h1>Speaker A’s next line</h1>
        <p class="lede" id="lede"></p>
      </div>
      <div class="score serif">
        <div class="num" id="score-num"></div>
        <div class="sub" id="score-sub"></div>
      </div>
    </header>

    <section class="bars">
      <div>
        <h2>Accuracy by vocalization</h2>
        <div id="bars-voc"></div>
      </div>
      <div>
        <h2>Accuracy by domain</h2>
        <div id="bars-domain"></div>
      </div>
    </section>

    <section>
      <h2>Clips</h2>
      <div class="controls">
        <select id="f-voc"></select>
        <select id="f-domain"></select>
        <select id="f-outcome">
          <option value="all">All outcomes</option>
          <option value="correct">Correct only</option>
          <option value="wrong">Incorrect only</option>
        </select>
        <input id="f-search" type="search" placeholder="Search id, domain, transcript" />
      </div>
      <p class="meta" id="clip-meta"></p>
      <div id="list"></div>
    </section>
  </div>
  <script id="payload" type="application/json">__DATA__</script>
  <script>
    const DATA = JSON.parse(document.getElementById("payload").textContent);
    const $ = (id) => document.getElementById(id);
    const state = { voc: "all", domain: "all", outcome: "all", q: "" };

    function pct(block) {
      if (!block || block.accuracy == null) return "n/a";
      return (100 * block.accuracy).toFixed(1) + "%";
    }
    function esc(s) {
      return String(s ?? "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[c]));
    }
    function barHtml(name, block) {
      const acc = block.accuracy || 0;
      const cls = acc < 0.4 ? "fill low" : "fill";
      return `<div class="bar-row"><span class="label">${esc(name)}</span>
        <div class="track"><div class="${cls}" style="width:${(100*acc).toFixed(1)}%"></div></div>
        <span class="count">${block.correct}/${block.n}</span></div>`;
    }

    function renderHead() {
      const o = DATA.summary.overall;
      $("lede").textContent = `${DATA.model} two-choice on 30 sewn clips (Turn 1 + Turn 2 + clipped Turn 3 vocalization). Chance is 50%. Seed ${DATA.seed}.`;
      $("score-num").textContent = pct(o);
      $("score-sub").textContent = `${o.correct} / ${o.n} correct`;
      $("bars-voc").innerHTML = DATA.voc_order.map((id) =>
        barHtml(DATA.voc_label[id] || id, DATA.summary.by_vocalization[id] || {n:0,correct:0,accuracy:0})
      ).join("");
      const domains = ["school", "work", "family"];
      $("bars-domain").innerHTML = domains.map((d) =>
        barHtml(d, DATA.summary.by_domain[d] || {n:0,correct:0,accuracy:0})
      ).join("");
      $("f-voc").innerHTML = `<option value="all">All vocalizations</option>` +
        DATA.voc_order.map((id) => `<option value="${id}">${esc(DATA.voc_label[id] || id)}</option>`).join("");
      $("f-domain").innerHTML = `<option value="all">All domains</option>` +
        domains.map((d) => `<option value="${d}">${d}</option>`).join("");
    }

    function optionList(trial) {
      return `<ul class="opts">` + trial.options.map((opt) => {
        const gold = opt.key === trial.correct_key;
        const pred = opt.key === trial.predicted_key;
        const cls = [gold ? "gold" : "", pred ? "pred" : ""].join(" ").trim();
        const tag = gold && pred ? "gold · model" : gold ? "gold" : pred ? "model" : "alternative";
        return `<li class="${cls}"><span>${esc(opt.key)}</span><span>${esc(opt.text)}</span><span class="tag">${tag}</span></li>`;
      }).join("") + `</ul>`;
    }

    function visible(trial) {
      if (state.voc !== "all" && trial.vocalization_id !== state.voc) return false;
      if (state.domain !== "all" && trial.domain !== state.domain) return false;
      if (state.outcome === "correct" && !trial.correct) return false;
      if (state.outcome === "wrong" && trial.correct) return false;
      if (state.q) {
        const blob = [trial.item_id, trial.domain, trial.vocalization, trial.turn_1, trial.turn_2, trial.gold_text, trial.alt_text].join(" ").toLowerCase();
        if (!blob.includes(state.q)) return false;
      }
      return true;
    }

    function renderList() {
      const trials = DATA.trials.filter(visible);
      $("clip-meta").textContent = `${trials.length} clip(s)`;
      if (!trials.length) {
        $("list").innerHTML = `<p class="empty">No clips match these filters.</p>`;
        return;
      }
      $("list").innerHTML = trials.map((trial) => `<article class="card">
        <div class="card-head">
          <h3>${esc(trial.item_id)}</h3>
          <span class="badge ${trial.correct ? "ok" : "miss"}">${esc(trial.vocalization)} · ${esc(trial.domain)} · ${trial.correct ? "correct" : "incorrect"}</span>
        </div>
        <p class="shared"><b>A</b> ${esc(trial.turn_1)}<br /><b>B</b> ${esc(trial.turn_2)}</p>
        <div class="voc">Turn 3 starts with ${esc(trial.formula)}</div>
        <audio controls preload="none" src="${esc(trial.audio)}"></audio>
        ${optionList(trial)}
      </article>`).join("");
    }

    $("f-voc").addEventListener("change", (e) => { state.voc = e.target.value; renderList(); });
    $("f-domain").addEventListener("change", (e) => { state.domain = e.target.value; renderList(); });
    $("f-outcome").addEventListener("change", (e) => { state.outcome = e.target.value; renderList(); });
    $("f-search").addEventListener("input", (e) => { state.q = e.target.value.trim().toLowerCase(); renderList(); });

    renderHead();
    renderList();
  </script>
</body>
</html>
"""


def write_viewer(payload: dict, path: Path) -> None:
    data = json.dumps(payload, ensure_ascii=True).replace("<", "\\u003c")
    path.write_text(TEMPLATE.replace("__DATA__", data), encoding="utf-8")


def serve(directory: Path, port: int) -> None:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"serving {directory} at http://127.0.0.1:{port}/viewer.html")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=Path, default=DEFAULT_ITEMS)
    parser.add_argument("--eval", type=Path, default=DEFAULT_EVAL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    payload = merge(json.loads(args.items.read_text()), json.loads(args.eval.read_text()))
    write_viewer(payload, args.out)
    print(f"wrote {args.out}  ({payload['summary']['overall']['correct']}/{payload['n']})")
    if args.serve:
        serve(args.out.parent, args.port)


if __name__ == "__main__":
    main()
