#!/usr/bin/env python3
"""Find MELD lines where the *delivery* is positive but the *words* are negative.

The shape we want:

    A: <ridiculous but earnest plan>
    B: [happy laughter] You are crazy.

MELD transcripts carry no vocalization tags, so the positive delivery has to be
read off the annotation instead: MELD raters labelled from video, so Emotion=joy
on a line whose words are hostile means the *sound* carried the positivity while
the words carried the attack. Every hit still has to be confirmed against the
clip audio (MELD.Raw -> dia{Dialogue_ID}_utt{Utterance_ID}.mp4).

    python3 find_valence_mismatch.py [--data DIR] [--out DIR] [--include-surprise]
"""
import argparse, csv, json, os, re, sys
from collections import defaultdict

POSITIVE_EMOTIONS = {"joy"}
NEG_COMPOUND = -0.35          # VADER on the words alone, for lines with no cue hit

# --- hostile-content lexicon -------------------------------------------------
# Words and phrases that make a transcript line read as an attack, an insult, a
# taunt, or a flat refusal. Delivered with a laugh, most of these flip to warmth.
HOSTILE = {
    "insult": r"""crazy | insane | nuts | psycho | lunatic | delusional |
        out\ of\ your\ mind | idiot | idiotic | moron | moronic | stupid |
        stupidest | dumb | dumbest | dummy | jerk | loser | freak | weirdo |
        creep | creepy | pathetic | ridiculous | absurd | lame | bitch | bastard |
        jackass | dork | slob | monster | evil | cruel | awful | horrible |
        terrible | worst | disgusting | gross | revolting | nasty | selfish |
        liar | coward | witch |
        (?:so|such\ a|really|being)\ mean | mean\ to\ me | you'?re\ mean""",
    "hate": r"""i\ hate\ (?:you|this|that|it|him|her|them) |
        can'?t\ stand\ (?:you|this|it) | you\ disgust\ me""",
    "threat": r"""(?:gonna|going\ to|will|i'?ll)\ (?:kill|strangle|murder|hurt|destroy)\ (?:you|him|her) |
        you'?re\ (?:so\ )?dead | you'?re\ dead\ meat | i'?ll\ get\ you |
        you'?re\ gonna\ (?:die|pay)""",
    "dismiss": r"""shut\ up | bite\ me | screw\ you | damn\ you | go\ to\ hell |
        get\ out | go\ away | drop\ dead | yeah\ right | as\ if |
        give\ me\ a\ break | oh\ please""",
    "refusal": r"""no\ way | forget\ it | not\ a\ chance | over\ my\ dead\ body |
        absolutely\ not | in\ your\ dreams | not\ happening""",
    "disbelief": r"""are\ you\ (?:kidding|serious|insane|crazy|nuts) |
        you'?ve\ got\ to\ be\ kidding | you\ cannot\ be\ serious |
        i\ don'?t\ believe\ you""",
    "doom": r"""you'?re\ (?:so\ )?screwed | we'?re\ (?:so\ )?screwed | doomed |
        disaster | catastrophe | nightmare | it'?ll\ never\ work |
        that'?ll\ never\ work | this\ is\ a\ mistake""",
}
CUES = [(re.compile(r"\b(?:%s)\b" % v, re.I | re.X), k) for k, v in HOSTILE.items()]
SECOND_PERSON = re.compile(r"\b(you|your|you're|ya)\b", re.I)


def load(data_dir):
    rows = []
    for split in ("train", "dev", "test"):
        path = os.path.join(data_dir, f"{split}_sent_emo.csv")
        if not os.path.exists(path):
            sys.exit(f"missing {path} — get it from declare-lab/MELD, data/MELD/")
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                r["split"] = split
                r["Utterance_ID"] = int(r["Utterance_ID"])
                r["Dialogue_ID"] = int(r["Dialogue_ID"])
                rows.append(r)
    return rows


def norm(t):
    return (t.replace("’", "'").replace("“", '"').replace("”", '"')
             .replace("\x92", "'").replace("\x85", "...").strip())


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--data", default=here)
    ap.add_argument("--out", default=here)
    ap.add_argument("--include-surprise", action="store_true",
                    help="also take surprise/positive lines, not just joy")
    ap.add_argument("--context", type=int, default=2, help="prior turns to keep")
    args = ap.parse_args()

    import nltk
    try:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        SentimentIntensityAnalyzer()
    except LookupError:
        nltk.download("vader_lexicon", quiet=True)
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
    sia = SentimentIntensityAnalyzer()

    rows = load(args.data)
    dias = defaultdict(list)
    for r in rows:
        dias[(r["split"], r["Dialogue_ID"])].append(r)
    for k in dias:
        dias[k].sort(key=lambda r: r["Utterance_ID"])

    hits = []
    for turns in dias.values():
        for i, u in enumerate(turns):
            pos_delivery = u["Emotion"] in POSITIVE_EMOTIONS or (
                args.include_surprise and u["Emotion"] == "surprise"
                and u["Sentiment"] == "positive")
            if not pos_delivery or i == 0:
                continue                       # need a trigger line to react to
            prev = turns[i - 1]
            if prev["Speaker"].strip().lower() == u["Speaker"].strip().lower():
                continue                       # want A -> B, not B continuing

            text = norm(u["Utterance"])
            comp = sia.polarity_scores(text)["compound"]
            cues = sorted({tag for rx, tag in CUES if rx.search(text)})
            if not cues and comp > NEG_COMPOUND:
                continue

            directed = bool(SECOND_PERSON.search(text))
            trigger_is_question = norm(prev["Utterance"]).endswith("?")
            score = (2.0 * len(cues) + (1.0 if directed else 0.0)
                     + (0.0 if comp > 0 else -comp)
                     - (0.5 if trigger_is_question else 0.0)
                     - (0.5 if len(text.split()) > 25 else 0.0))

            hits.append({
                "id": f"{u['split']}_dia{u['Dialogue_ID']}_utt{u['Utterance_ID']}",
                "split": u["split"],
                "dialogue_id": u["Dialogue_ID"], "utterance_id": u["Utterance_ID"],
                "clip": f"dia{u['Dialogue_ID']}_utt{u['Utterance_ID']}.mp4",
                "season": u["Season"], "episode": u["Episode"],
                "start": u["StartTime"], "end": u["EndTime"],
                "emotion": u["Emotion"], "sentiment": u["Sentiment"],
                "text_compound": round(comp, 3),
                "cues": cues, "directed_at_addressee": directed,
                "trigger_is_question": trigger_is_question,
                "score": round(score, 3),
                "context": [{"speaker": t["Speaker"], "text": norm(t["Utterance"]),
                             "emotion": t["Emotion"], "utterance_id": t["Utterance_ID"]}
                            for t in turns[max(0, i - args.context):i]],
                "speaker": u["Speaker"], "utterance": text,
                "next": ({"speaker": turns[i + 1]["Speaker"],
                          "text": norm(turns[i + 1]["Utterance"]),
                          "emotion": turns[i + 1]["Emotion"]}
                         if i + 1 < len(turns) else None),
            })

    hits.sort(key=lambda h: -h["score"])
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "valence_mismatch.json"), "w", encoding="utf-8") as f:
        json.dump({"n_utterances": len(rows), "n_hits": len(hits),
                   "n_cue_hits": sum(1 for h in hits if h["cues"]), "hits": hits},
                  f, indent=2, ensure_ascii=False)

    with open(os.path.join(args.out, "valence_mismatch.md"), "w", encoding="utf-8") as f:
        f.write("# MELD: positive delivery, negative words\n\n")
        f.write(f"{len(hits)} candidates out of {len(rows)} utterances "
                f"({sum(1 for h in hits if h['cues'])} matched a hostile-content cue). "
                "The emotion label describes the delivery; VADER scores the words alone. "
                "Confirm the actual laugh in `dia{D}_utt{U}.mp4` before using a line.\n\n")
        for h in hits:
            f.write(f"## {h['id']} — S{h['season']}E{h['episode']}, `{h['clip']}`\n\n")
            f.write(f"cues: {', '.join(h['cues']) or '—'} · words VADER {h['text_compound']}"
                    f" · at-addressee: {'yes' if h['directed_at_addressee'] else 'no'}"
                    f" · score {h['score']}\n\n")
            for c in h["context"]:
                f.write(f"- {c['speaker']}: {c['text']}  _({c['emotion']})_\n")
            f.write(f"- **{h['speaker']}: {h['utterance']}**  _({h['emotion']})_\n")
            if h["next"]:
                f.write(f"- {h['next']['speaker']}: {h['next']['text']}  _({h['next']['emotion']})_\n")
            f.write("\n")

    print(f"{len(hits)} hits ({sum(1 for h in hits if h['cues'])} cue-matched) "
          f"-> {os.path.join(args.out, 'valence_mismatch.{json,md}')}")


if __name__ == "__main__":
    main()
