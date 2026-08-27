# Laughter taxonomy — Mazzocconi, Tian & Ginzburg

Summary of *"What's Your Laughter Doing There? A Taxonomy of the Pragmatic Functions of
Laughter"* (Chiara Mazzocconi, Ye Tian, Jonathan Ginzburg — IEEE Transactions on Affective
Computing, 2020/2022), plus the companion papers that use the same annotation scheme.

> **Provenance note.** The IEEE version is paywalled and its open-access mirror on HAL sits
> behind a proof-of-work bot check that this harness does not bypass. The definitions below are
> taken from the authors' own open-access papers that apply the *same* annotation scheme —
> primarily Mazzocconi (DiSS 2023), which restates the four-branch scheme with definitions, and
> Mazzocconi, Tian & Ginzburg (SemDial 2016), the direct precursor, which gives the function
> inventory and corpus distributions. Cross-checked against published descriptions of the 2020
> paper. Sources listed at the bottom.

---

## 1. The core claim (why this benchmark exists)

Laughter is **not** a homogeneous signal, and its acoustic form does **not** determine what it is
doing. The paper treats laughter as an **event anaphor** carrying propositional content: a laugh
points at a **laughable** in the context and predicates something about it. Two basic meaning
dimensions are posited:

1. the laugher **enjoys** the laughable;
2. the laugher perceives the laughable as **incongruous**.

Those two dimensions, combined with contextual/pragmatic reasoning over the social, situational
and linguistic context, derive an open-ended set of **functions**. The paper's explicit
methodological consequence:

> laughters with similar acoustic features can have different functions in different contexts.

That is exactly the property this benchmark probes. A model that classifies "laugh type" from
audio texture alone cannot recover function; it has to read the **framing** of the conversation
the laugh sits in.

The paper also separates layers that earlier taxonomies conflated — **form**, **laughable /
trigger**, **meaning**, and **function**. Most prior taxonomies mix "types of function" with
"types of trigger"; the annotation scheme keeps them on separate tiers.

## 2. Annotation tiers

| Tier | Values |
| --- | --- |
| **Arousal (form)** | low / medium / high. Correlates with duration: mean ≈ 1.11 s (low), 2.55 s (mid), 4.6 s (high). Most conversational laughter is **low** arousal; high arousal is rare. |
| **Speech-laughter** | laughter overlapping speech vs. stand-alone laughter (~40% speech-laughter in DUEL — higher than earlier reports). |
| **Mimicking / antiphonal** | laugh that starts within ~1 s of (or overlapping) the partner's laugh vs. non-mimicking. |
| **Laughable origin** | self-produced vs. partner-produced. Speakers laugh at their own laughables more than audiences do. |
| **Laughable type** | described event (most common) / exophoric (something in the shared situation) / linguistic (rare). |
| **Laughter position** | after / during / before the laughable. **Refutes** the common assumption that laughter directly follows its laughable (DUEL: ~74% after, ~24% during, ~2% before). |
| **Incongruity branch** | the four categories in §3 — the first split of the decision tree. |
| **Function** | terminal node, §4. |

## 3. The four branches (type of laughable)

The decision tree first asks whether the laughable contains an incongruity and, if so, which kind.

1. **Pleasant incongruity** — a clash between the laughable and background information that is
   perceived as witty, rewarding and/or somehow pleasant. Jokes, puns, goofy behaviour,
   conversational humour.
2. **Social incongruity** — a clash between social norms and/or comfort and the laughable.
   Includes social discomfort (embarrassment, awkwardness), violation of social norms (invading
   someone's space, asking a favour), or an utterance that clashes with the interlocutor's
   expectations about one's behaviour (e.g. criticism).
3. **Pragmatic incongruity** — a clash between what is said and what is intended: irony,
   scare-quoting, hyperbole. Here the laugh is the speaker's own signal that the hearer should
   opt for a *less probable* interpretation of the speaker's utterance.
4. **Pleasantness** (no incongruity) — no incongruity is identifiable; what is associated with
   the laughable is a sense of **closeness** felt or displayed toward the interlocutor, e.g. while
   thanking, or on receiving a pat on the shoulder.

## 4. Functions (terminal nodes)

Function = *the effect the laugher intends the laugh to have on the current dialogue.* The
efficient top-level partition is **cooperative** (promotes continuation of the interaction) vs.
**non-cooperative** (damages the flow).

**Cooperative**

- **Show enjoyment** — enjoy the (typically pleasant) incongruity. *Most frequent function.*
- **Mark funniness / mark incongruity** — flag that something is absurd/ridiculous when that is
  not otherwise salient to the others; does not require enjoyment.
- **Smoothing / softening** — reduce intrusion or defuse a face threat; **negative politeness**.
  Second most frequent cluster.
- **Benevolence induction** — induce agreement/goodwill; **positive politeness**. (Clusters with
  smoothing; the difference is inducing agreement vs. reducing intrusion.)
- **Show agreement** — affiliative uptake; typically **antiphonal**, laughable from partner.
- **Show sympathy** — align with the interlocutor's trouble.
- **Self-mocking** — laughable from self, softening one's own face threat.
- **Apology**.
- **Show appreciation / thanking** — typically the *pleasantness* branch, no incongruity.
- **Social bonding / show closeness** — pleasantness branch; e.g. laughter accompanying a
  compliment.

**Non-cooperative**

- **Mocking** — at the partner or their laughable.
- **Show disagreement**.

## 5. Distributional findings that matter for item design

- ~**85%** of laughs were perceived as communicating an appraisal of **incongruity** (both French
  and Chinese). Non-incongruity laughs were perceived as communicating **ingroupness**.
- **Pleasant incongruity dominates**: showing enjoyment of, or marking, pleasant incongruity
  accounts for 74% (DUEL French), 67% (DUEL Chinese), 75% (BNC).
- Function frequency order: *show enjoyment* > *smoothing/softening* ≈ *benevolence induction* >
  *show agreement* > *mark funniness*. Rarer: self-mocking, apology, show sympathy, thanking.
- Function is characterised by a **cluster** of tiers, not any single one. Which cue carries
  function is **language-dependent**: in Chinese arousal does not explain variance in function; in
  French speech-laughter does not. Task register matters too — the serious "border control" task
  produced ~100% low-arousal laughter in French.
- Laughter can be **positive-shift-marking** without the speaker being in a positive state: a very
  sad or angry baseline plus recognition of incongruity still yields a (possibly tiny) positive
  shift.

## 6. Design implications for contrastive audio items

Direct consequences used by `harness/` when it builds pairs:

1. **Hold the words constant, vary the framing.** Function is derived from laughable + context, so
   two versions with identical lexical content and different prosody must legitimately carry
   different functions. Any lexical difference is a confound.
2. **Cross branches, not just functions.** A pair drawn from two different branches of §3 (e.g.
   *pleasant incongruity → show enjoyment* vs. *social incongruity → smoothing*) gives a genuine
   semantic contrast rather than an intensity difference.
3. **Encode the form tier in the audio tags.** Arousal (low/mid/high), speech-laughter vs.
   stand-alone, and antiphonal placement are the levers that realise the intended function — so
   the tag set per function varies arousal and laughter type, not just the adjective.
4. **Don't leak framing into the text.** The tag-free transcript must avoid emotive punctuation
   (`!`, `…`), interjection choices and lexical valence that pre-decide the reading.
5. **Placement is a variable, not a constant.** Since laughter does not always follow its
   laughable, versions may place the laugh *during* the laughable (speech-laughter) or before it.

---

### Sources

- [What's Your Laughter Doing There? A Taxonomy of the Pragmatic Functions of Laughter — IEEE Xplore](https://ieeexplore.ieee.org/document/9093177/) (target paper; paywalled)
- [How do you laugh in an fMRI scanner? — Mazzocconi et al., DiSS 2023](https://www.isca-archive.org/diss_2023/mazzocconi23_diss.pdf) (restates the four-branch scheme with definitions)
- [Multi-layered analysis of laughter — Mazzocconi, Tian & Ginzburg, SemDial 2016](https://www.semdial.org/anthology/Z16-Mazzocconi_semdial_0014.pdf) (function inventory, distributions)
- [Laughter as language — Ginzburg, Mazzocconi & Tian, Glossa 2020](https://doi.org/10.5334/gjgl.1152) (formal semantics companion)
- [Linguistic patterning of laughter in human-socialbot interactions — Perkins Booker et al., Frontiers 2024](https://doi.org/10.3389/fcomm.2024.1346738) (independent application of the scheme)
- [Why Do We Laugh? Annotation and Taxonomy Generation for Laughable Contexts — Inoue et al., IWSDS 2025](https://aclanthology.org/2025.iwsds-1.34.pdf) (contrasting LLM-generated taxonomy; GPT-4o F1 43.1% on laughable-context recognition)
