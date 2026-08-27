"""Build a local HTML viewer for sewn clips and gpt-realtime results.

Usage:
    python pairing_type/make_viewer.py
    python pairing_type/make_viewer.py --serve
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_MCQ = HERE / "out" / "mcq.json"
DEFAULT_EVAL = HERE / "out" / "eval_realtime.json"
DEFAULT_OUT = HERE / "out" / "viewer.html"

CONTRAST_SHORT = {
    "C1": "Enjoyment vs impatience",
    "C2": "Enjoyment vs exhaustion",
    "C3": "Impatience vs relief",
    "C4": "Engagement vs impatience",
}

LABEL_ORDER = [
    "Enjoyment / amusement",
    "Impatience",
    "Exhaustion",
    "Relief",
    "Engagement / attention",
]


def acc_block(rows: list[dict]) -> dict:
    n = len(rows)
    correct = sum(1 for row in rows if row.get("correct"))
    return {
        "n": n,
        "correct": correct,
        "accuracy": (correct / n) if n else None,
    }


def group_acc(rows: list[dict], key: str) -> dict:
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return {name: acc_block(subset) for name, subset in groups.items()}


def merge(mcq: dict, evaluation: dict) -> dict:
    questions = {item["question_id"]: item for item in mcq["results"]}
    trials = []
    for row in evaluation["results"]:
        question = questions[row["question_id"]]
        pred_key = row.get("predicted_key")
        pred_opt = next((opt for opt in question["options"] if opt["key"] == pred_key), None)
        gold_opt = next((opt for opt in question["options"] if opt["key"] == question["correct_key"]), None)
        trials.append(
            {
                "question_id": row["question_id"],
                "item_id": row["item_id"],
                "comparison_id": row["comparison_id"],
                "contrast": question.get("contrast"),
                "contrast_short": CONTRAST_SHORT.get(row["comparison_id"], row["comparison_id"]),
                "domain": row["domain"],
                "version": row["version"],
                "vocalization": question.get("vocalization"),
                "audio": f"audio_sewn/{row['question_id']}.mp3",
                "turn_1": question["turn_1"],
                "turn_2_lexical": question["turn_2_lexical"],
                "turn_2": question["turn_2"],
                "options": question["options"],
                "correct_key": question["correct_key"],
                "correct_id": question["correct_id"],
                "correct_label": gold_opt["label"] if gold_opt else row.get("correct_label"),
                "predicted_key": pred_key,
                "predicted_label": pred_opt["label"] if pred_opt else None,
                "correct": bool(row.get("correct")),
                "raw_text": row.get("raw_text"),
            }
        )

    pairs = []
    by_item = defaultdict(dict)
    for trial in trials:
        by_item[trial["item_id"]][trial["version"]] = trial
    for item_id, versions in by_item.items():
        a = versions.get("a")
        b = versions.get("b")
        sample = a or b
        both = [item for item in (a, b) if item]
        pairs.append(
            {
                "item_id": item_id,
                "comparison_id": sample["comparison_id"],
                "contrast_short": sample["contrast_short"],
                "domain": sample["domain"],
                "turn_1": sample["turn_1"],
                "turn_2_lexical": sample["turn_2_lexical"],
                "a": a,
                "b": b,
                "pair_correct": sum(1 for item in both if item["correct"]),
                "pair_n": len(both),
            }
        )
    pairs.sort(key=lambda item: (item["comparison_id"], item["domain"], item["item_id"]))

    confusion = {gold: {pred: 0 for pred in LABEL_ORDER} for gold in LABEL_ORDER}
    for trial in trials:
        gold = trial["correct_label"]
        pred = trial["predicted_label"]
        if gold in confusion and pred in confusion[gold]:
            confusion[gold][pred] += 1

    return {
        "model": evaluation.get("model"),
        "seed": evaluation.get("seed"),
        "generated_at": evaluation.get("generated_at"),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "question": mcq.get("question") or "What is Speaker B's current status?",
        "n": len(trials),
        "summary": {
            "overall": acc_block(trials),
            "by_contrast": group_acc(trials, "comparison_id"),
            "by_domain": group_acc(trials, "domain"),
            "by_version": group_acc(trials, "version"),
            "by_correct_label": group_acc(trials, "correct_label"),
        },
        "labels": LABEL_ORDER,
        "confusion": confusion,
        "trials": trials,
        "pairs": pairs,
    }


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Pairing type · gpt-realtime</title>
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
    a { color: inherit; }
    .wrap { max-width: 1120px; margin: 0 auto; }
    header.top { display: grid; grid-template-columns: 1fr auto; gap: 18px; align-items: end; padding-bottom: 22px; border-bottom: 1px solid var(--line); }
    header.top p.kicker { margin: 0 0 6px; color: var(--mute); letter-spacing: 0.08em; text-transform: uppercase; font-size: 11px; }
    h1 { margin: 0; font-size: 32px; font-weight: 600; letter-spacing: -0.03em; }
    .lede { margin: 8px 0 0; color: var(--mute); max-width: 42em; }
    .score { text-align: right; }
    .score .num { font-size: 42px; line-height: 1; font-weight: 600; letter-spacing: -0.04em; }
    .score .sub { color: var(--mute); margin-top: 4px; }
    section { margin-top: 28px; }
    h2 { font-size: 18px; margin: 0 0 12px; font-weight: 600; }
    .bars { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; }
    .bar-row { display: grid; grid-template-columns: 148px 1fr 64px; gap: 10px; align-items: center; margin: 7px 0; font-size: 13px; }
    .bar-row .label { color: var(--mute); }
    .track { height: 8px; background: #e6dfd2; }
    .fill { height: 8px; background: var(--ink); }
    .fill.low { background: var(--miss); }
    .count { text-align: right; font-variant-numeric: tabular-nums; }
    table.confusion { border-collapse: collapse; font-size: 12px; width: 100%; }
    table.confusion th, table.confusion td { border: 1px solid var(--line); padding: 6px 8px; text-align: center; }
    table.confusion th { font-weight: 500; color: var(--mute); }
    table.confusion td.diag { background: var(--ok-bg); font-weight: 600; }
    table.confusion td.hit { background: var(--miss-bg); }
    table.confusion .corner { text-align: left; color: var(--ink); }
    .controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    select, input[type="search"] {
      font: inherit; background: var(--card); color: var(--ink);
      border: 1px solid var(--line); padding: 7px 10px;
    }
    input[type="search"] { min-width: 220px; }
    .toggles { margin-left: auto; display: flex; gap: 0; border: 1px solid var(--line); }
    .toggles button {
      font: inherit; background: transparent; border: 0; padding: 7px 12px; cursor: pointer; color: var(--mute);
    }
    .toggles button.on { background: var(--ink); color: var(--paper); }
    .meta { color: var(--mute); font-size: 13px; margin-top: 10px; }
    .pair {
      background: var(--card); border: 1px solid var(--line); padding: 18px 18px 14px; margin: 14px 0;
    }
    .pair-head { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; margin-bottom: 8px; }
    .pair-head h3 { margin: 0; font-size: 18px; }
    .badge { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--mute); }
    .badge.ok { color: var(--ok); }
    .badge.miss { color: var(--miss); }
    .shared { color: var(--mute); font-size: 14px; margin: 0 0 14px; }
    .shared b { color: var(--ink); font-weight: 600; }
    .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .trial { border-top: 1px solid var(--line); padding-top: 12px; }
    .trial-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 8px; }
    .voc { font-size: 13px; color: var(--mute); }
    audio { width: 100%; height: 32px; margin: 6px 0 10px; }
    ul.opts { list-style: none; margin: 0; padding: 0; }
    ul.opts li {
      display: grid; grid-template-columns: 22px 1fr auto; gap: 8px; align-items: center;
      padding: 5px 8px; margin: 3px 0; font-size: 13px; border: 1px solid transparent;
    }
    ul.opts li.gold { background: var(--gold-bg); border-color: #e2c98a; }
    ul.opts li.pred { outline: 1px solid var(--miss); }
    ul.opts li.gold.pred { outline-color: var(--ok); background: var(--ok-bg); border-color: #b7d0bb; }
    .tag { font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--mute); }
    .empty { color: var(--mute); padding: 24px 0; }
    @media (max-width: 820px) {
      header.top, .bars, .cols { grid-template-columns: 1fr; }
      .score { text-align: left; }
      .toggles { margin-left: 0; }
      .bar-row { grid-template-columns: 120px 1fr 54px; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <header class="top">
      <div>
        <p class="kicker">Pairing type eval</p>
        <h1>Speaker B status</h1>
        <p class="lede" id="lede"></p>
      </div>
      <div class="score serif">
        <div class="num" id="score-num"></div>
        <div class="sub" id="score-sub"></div>
      </div>
    </header>

    <section class="bars">
      <div>
        <h2>Accuracy by contrast</h2>
        <div id="bars-contrast"></div>
      </div>
      <div>
        <h2>Accuracy by gold attitude</h2>
        <div id="bars-label"></div>
      </div>
    </section>

    <section>
      <h2>Predicted vs gold</h2>
      <table class="confusion" id="confusion"></table>
    </section>

    <section>
      <h2>Clips</h2>
      <div class="controls">
        <select id="f-contrast"></select>
        <select id="f-domain"></select>
        <select id="f-outcome">
          <option value="all">All outcomes</option>
          <option value="correct">Correct only</option>
          <option value="wrong">Incorrect only</option>
          <option value="split">Split pairs</option>
        </select>
        <input id="f-search" type="search" placeholder="Search id, domain, transcript" />
        <div class="toggles">
          <button type="button" id="view-pairs" class="on">Pairs</button>
          <button type="button" id="view-trials">Trials</button>
        </div>
      </div>
      <p class="meta" id="clip-meta"></p>
      <div id="list"></div>
    </section>
  </div>
  <script id="payload" type="application/json">__DATA__</script>
  <script>
    const DATA = JSON.parse(document.getElementById("payload").textContent);
    const $ = (id) => document.getElementById(id);
    const state = { view: "pairs", contrast: "all", domain: "all", outcome: "all", q: "" };

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
      const cls = acc < 0.3 ? "fill low" : "fill";
      return `<div class="bar-row"><span class="label">${esc(name)}</span>
        <div class="track"><div class="${cls}" style="width:${(100*acc).toFixed(1)}%"></div></div>
        <span class="count">${block.correct}/${block.n}</span></div>`;
    }

    function renderHead() {
      const o = DATA.summary.overall;
      $("lede").textContent = `${DATA.model} forced-choice on 48 sewn clips (Turn 1 + vocalization + Turn 2). Chance is 25%. Seed ${DATA.seed}.`;
      $("score-num").textContent = pct(o);
      $("score-sub").textContent = `${o.correct} / ${o.n} correct`;
      const contrastOrder = ["C1","C2","C3","C4"];
      $("bars-contrast").innerHTML = contrastOrder.map((id) => {
        const short = {C1:"C1 enjoyment vs impatience",C2:"C2 enjoyment vs exhaustion",C3:"C3 impatience vs relief",C4:"C4 engagement vs impatience"}[id];
        return barHtml(short, DATA.summary.by_contrast[id]);
      }).join("");
      $("bars-label").innerHTML = DATA.labels.map((lab) => barHtml(lab, DATA.summary.by_correct_label[lab] || {n:0,correct:0,accuracy:0})).join("");

      const labels = DATA.labels;
      let html = "<thead><tr><th class='corner'>gold \\ pred</th>" + labels.map(l => `<th>${esc(l)}</th>`).join("") + "</tr></thead><tbody>";
      for (const gold of labels) {
        html += `<tr><th class="corner">${esc(gold)}</th>`;
        for (const pred of labels) {
          const n = DATA.confusion[gold][pred] || 0;
          const cls = n && gold === pred ? "diag" : (n ? "hit" : "");
          html += `<td class="${cls}">${n || ""}</td>`;
        }
        html += "</tr>";
      }
      $("confusion").innerHTML = html + "</tbody>";

      const contrasts = [...new Set(DATA.pairs.map(p => p.comparison_id))].sort();
      const domains = [...new Set(DATA.pairs.map(p => p.domain))].sort();
      $("f-contrast").innerHTML = `<option value="all">All contrasts</option>` + contrasts.map(id => `<option value="${id}">${id} · ${esc(DATA.pairs.find(p=>p.comparison_id===id).contrast_short)}</option>`).join("");
      $("f-domain").innerHTML = `<option value="all">All domains</option>` + domains.map(d => `<option value="${d}">${d}</option>`).join("");
    }

    function optionList(trial) {
      return `<ul class="opts">` + trial.options.map((opt) => {
        const gold = opt.key === trial.correct_key;
        const pred = opt.key === trial.predicted_key;
        const cls = [gold ? "gold" : "", pred ? "pred" : ""].join(" ").trim();
        const tag = gold && pred ? "gold · model" : gold ? "gold" : pred ? "model" : "";
        return `<li class="${cls}"><span>${esc(opt.key)}</span><span>${esc(opt.label)}</span><span class="tag">${tag}</span></li>`;
      }).join("") + `</ul>`;
    }

    function trialCard(trial) {
      const ok = trial.correct;
      return `<div class="trial">
        <div class="trial-head">
          <strong>Version ${esc(trial.version)}</strong>
          <span class="badge ${ok ? "ok" : "miss"}">${ok ? "correct" : "incorrect"}</span>
        </div>
        <div class="voc">${esc(trial.vocalization)}</div>
        <audio controls preload="none" src="${esc(trial.audio)}"></audio>
        ${optionList(trial)}
      </div>`;
    }

    function matchText(trial, q) {
      const blob = [trial.question_id, trial.item_id, trial.domain, trial.turn_1, trial.turn_2_lexical, trial.vocalization, trial.correct_label, trial.predicted_label].join(" ").toLowerCase();
      return blob.includes(q);
    }

    function pairVisible(pair) {
      if (state.contrast !== "all" && pair.comparison_id !== state.contrast) return false;
      if (state.domain !== "all" && pair.domain !== state.domain) return false;
      const trials = [pair.a, pair.b].filter(Boolean);
      if (state.outcome === "correct" && !trials.every(t => t.correct)) return false;
      if (state.outcome === "wrong" && !trials.every(t => !t.correct)) return false;
      if (state.outcome === "split" && !(pair.pair_n === 2 && pair.pair_correct === 1)) return false;
      if (state.q && !trials.some(t => matchText(t, state.q))) return false;
      return true;
    }

    function trialVisible(trial) {
      if (state.contrast !== "all" && trial.comparison_id !== state.contrast) return false;
      if (state.domain !== "all" && trial.domain !== state.domain) return false;
      if (state.outcome === "correct" && !trial.correct) return false;
      if (state.outcome === "wrong" && trial.correct) return false;
      if (state.outcome === "split") return false;
      if (state.q && !matchText(trial, state.q)) return false;
      return true;
    }

    function renderList() {
      const list = $("list");
      if (state.view === "pairs") {
        const pairs = DATA.pairs.filter(pairVisible);
        $("clip-meta").textContent = `${pairs.length} pair(s) · ${pairs.reduce((n,p)=>n+p.pair_n,0)} clip(s)`;
        if (!pairs.length) { list.innerHTML = `<p class="empty">No pairs match these filters.</p>`; return; }
        list.innerHTML = pairs.map((pair) => {
          const mark = pair.pair_correct === pair.pair_n ? "ok" : (pair.pair_correct === 0 ? "miss" : "");
          const label = `${pair.pair_correct}/${pair.pair_n} correct`;
          return `<article class="pair">
            <div class="pair-head">
              <h3>${esc(pair.item_id)}</h3>
              <span class="badge ${mark}">${esc(pair.comparison_id)} · ${esc(pair.domain)} · ${label}</span>
            </div>
            <p class="shared"><b>A</b> ${esc(pair.turn_1)}<br /><b>B words</b> ${esc(pair.turn_2_lexical)}</p>
            <div class="cols">${pair.a ? trialCard(pair.a) : ""}${pair.b ? trialCard(pair.b) : ""}</div>
          </article>`;
        }).join("");
      } else {
        const trials = DATA.trials.filter(trialVisible);
        $("clip-meta").textContent = `${trials.length} trial(s)`;
        if (!trials.length) { list.innerHTML = `<p class="empty">No trials match these filters.</p>`; return; }
        list.innerHTML = trials.map((trial) => `<article class="pair">
          <div class="pair-head">
            <h3>${esc(trial.question_id)}</h3>
            <span class="badge ${trial.correct ? "ok" : "miss"}">${esc(trial.comparison_id)} · ${esc(trial.domain)}</span>
          </div>
          <p class="shared"><b>A</b> ${esc(trial.turn_1)}<br /><b>B words</b> ${esc(trial.turn_2_lexical)}</p>
          ${trialCard(trial)}
        </article>`).join("");
      }
    }

    $("f-contrast").addEventListener("change", (e) => { state.contrast = e.target.value; renderList(); });
    $("f-domain").addEventListener("change", (e) => { state.domain = e.target.value; renderList(); });
    $("f-outcome").addEventListener("change", (e) => { state.outcome = e.target.value; renderList(); });
    $("f-search").addEventListener("input", (e) => { state.q = e.target.value.trim().toLowerCase(); renderList(); });
    $("view-pairs").addEventListener("click", () => {
      state.view = "pairs"; $("view-pairs").classList.add("on"); $("view-trials").classList.remove("on"); renderList();
    });
    $("view-trials").addEventListener("click", () => {
      state.view = "trials"; $("view-trials").classList.add("on"); $("view-pairs").classList.remove("on"); renderList();
    });

    renderHead();
    renderList();
  </script>
</body>
</html>
"""


def write_viewer(payload: dict, path: Path) -> None:
    data = json.dumps(payload, ensure_ascii=True)
    data = data.replace("<", "\\u003c")
    html = TEMPLATE.replace("__DATA__", data)
    path.write_text(html, encoding="utf-8")


def serve(directory: Path, port: int) -> None:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"serving {directory} at http://127.0.0.1:{port}/viewer.html")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcq", type=Path, default=DEFAULT_MCQ)
    parser.add_argument("--eval", type=Path, default=DEFAULT_EVAL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    payload = merge(json.loads(args.mcq.read_text()), json.loads(args.eval.read_text()))
    write_viewer(payload, args.out)
    print(f"wrote {args.out}  ({payload['summary']['overall']['correct']}/{payload['n']})")
    if args.serve:
        serve(args.out.parent, args.port)


if __name__ == "__main__":
    main()
