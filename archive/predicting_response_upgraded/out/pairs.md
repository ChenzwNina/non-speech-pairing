# Predicting response — upgraded (2-turn, 3-question benchmark)

writer: gpt-5.6-terra · 12 pair(s)

Turn 1 (A) is identical across both versions. Turn 2 is B's vocalization only —
that is all the benchmark audio contains. The verbal continuation is a text-only
gold answer for Q3, never synthesized. Q2 and Q3 are a forced choice between the
two versions' own gold answers — no distractors. Option lettering below is for
reading only; the real eval shuffles each question's options independently.

### Pair gasp_grunt_001

Contrast: gasp-grunt

**Shared Turn 1** — A: The last train leaves in twenty minutes, but the encore starts in five.

**Version 1** — [gasp] (B suddenly realizes that staying for the encore could leave them stranded and urgently wants to leave.)
  B continues: Wait, the last train? We have to go now.

**Version 2** — [grunt] (B reluctantly agrees to stay for the encore but makes A responsible for the consequences of missing the train.)
  B continues: Fine, one more song—but you're putting me up if we miss it.

**Q1 options:** Gasp / Grunt / Laughter / Sigh / Sob / Yawn

**Q2 interpretation options (for reading; real eval shuffles):**
  A. B suddenly realizes that staying for the encore could leave them stranded and urgently wants to leave.
  B. B reluctantly agrees to stay for the encore but makes A responsible for the consequences of missing the train.

**Q3 continuation options (for reading; real eval shuffles):**
  A. Wait, the last train? We have to go now.
  B. Fine, one more song—but you're putting me up if we miss it.

**Contrastive rationale:**
The first reaction communicates an alarmed realization and prompts an urgent departure, while the second conveys grudging consent to remain with a practical condition. Agreeing to stay would clash with the first reaction's urgency, and the abrupt alarm about leaving would not fit the second reaction's reluctant concession.

### Pair gasp_sigh_001

Contrast: gasp-sigh

**Shared Turn 1** — A: I tried to fix the pipe under the kitchen sink, and now water is spraying everywhere.

**Version 1** — [gasp] (B is alarmed that the leak could quickly damage the kitchen and urgently tells A to stop the water.)
  B continues: Turn off the main valve before the whole kitchen floods!

**Version 2** — [sigh] (B is fed up with A's failed home repairs and draws a firm line against letting A attempt another one.)
  B continues: I'm calling a plumber; you're not touching another pipe.

**Q1 options:** Gasp / Grunt / Laughter / Sigh / Sob / Yawn

**Q2 interpretation options (for reading; real eval shuffles):**
  A. B is alarmed that the leak could quickly damage the kitchen and urgently tells A to stop the water.
  B. B is fed up with A's failed home repairs and draws a firm line against letting A attempt another one.

**Q3 continuation options (for reading; real eval shuffles):**
  A. Turn off the main valve before the whole kitchen floods!
  B. I'm calling a plumber; you're not touching another pipe.

**Contrastive rationale:**
The first reaction communicates immediate alarm and calls for emergency action, whereas the second communicates frustrated finality and a decision to stop A's DIY repairs. Calling a plumber instead of stopping the water would be an inappropriately delayed response to the alarmed reaction, while the urgent command does not express the fed-up boundary conveyed by the other reaction.

### Pair gasp_sob_001

Contrast: gasp-sob

**Shared Turn 1** — A: The principal just announced that the school is closing the music program after this semester.

**Version 1** — [gasp] (B is stunned by the abrupt decision and immediately challenges the school's authority to eliminate the program without proper process.)
  B continues: What? They can't just shut it down without even holding a public meeting.

**Version 2** — [sob] (B is emotionally devastated because the program was a deeply important refuge and source of belonging for them.)
  B continues: That program is the only reason I ever felt like I belonged here.

**Q1 options:** Gasp / Grunt / Laughter / Sigh / Sob / Yawn

**Q2 interpretation options (for reading; real eval shuffles):**
  A. B is stunned by the abrupt decision and immediately challenges the school's authority to eliminate the program without proper process.
  B. B is emotionally devastated because the program was a deeply important refuge and source of belonging for them.

**Q3 continuation options (for reading; real eval shuffles):**
  A. What? They can't just shut it down without even holding a public meeting.
  B. That program is the only reason I ever felt like I belonged here.

**Contrastive rationale:**
The first reaction turns the announcement into an urgent procedural challenge, while the second reveals a personal sense of loss. A demand for a public meeting is strongly dispreferred after the intimate, tearful disclosure, and the personal confession is dispreferred after the startled challenge.

### Pair gasp_yawn_001

Contrast: gasp-yawn

**Shared Turn 1** — A: I made a two-hour podcast explaining how I accidentally deleted the company's only customer database.

**Version 1** — [gasp] (B is alarmed by the potentially disastrous loss of company data and urges A to seek immediate technical help rather than explain it.)
  B continues: Forget the podcast—call IT right now!

**Version 2** — [yawn] (B is disengaged by A's excessively long format and refuses to devote two hours to hearing the story.)
  B continues: I can't sit through a two-hour podcast; send me the short version.

**Q1 options:** Gasp / Grunt / Laughter / Sigh / Sob / Yawn

**Q2 interpretation options (for reading; real eval shuffles):**
  A. B is alarmed by the potentially disastrous loss of company data and urges A to seek immediate technical help rather than explain it.
  B. B is disengaged by A's excessively long format and refuses to devote two hours to hearing the story.

**Q3 continuation options (for reading; real eval shuffles):**
  A. Forget the podcast—call IT right now!
  B. I can't sit through a two-hour podcast; send me the short version.

**Contrastive rationale:**
The gasp conveys alarm and prioritizes an emergency response to the deleted database, whereas the yawn rejects A's drawn-out delivery. Asking for a summary after alarm would trivialize the apparent crisis, while urgently calling IT after signaling disengagement from the presentation is strongly dispreferred.

### Pair grunt_laughter_001

Contrast: grunt-laughter

**Shared Turn 1** — A: I told the city festival organizer our little garage band could replace the headliner if they cancel.

**Version 1** — [grunt] (B is dismissing A's unrealistic promise and urging them to prevent the band from being booked for a performance they cannot handle.)
  B continues: Call her back—we are not ready for that stage.

**Version 2** — [laughter] (B finds the unlikely prospect of headlining amusing and enthusiastically treats it as a chance for the band to have fun with the fantasy.)
  B continues: This is our big break—I'm finally buying those silver boots.

**Q1 options:** Gasp / Grunt / Laughter / Sigh / Sob / Yawn

**Q2 interpretation options (for reading; real eval shuffles):**
  A. B is dismissing A's unrealistic promise and urging them to prevent the band from being booked for a performance they cannot handle.
  B. B finds the unlikely prospect of headlining amusing and enthusiastically treats it as a chance for the band to have fun with the fantasy.

**Q3 continuation options (for reading; real eval shuffles):**
  A. Call her back—we are not ready for that stage.
  B. This is our big break—I'm finally buying those silver boots.

**Contrastive rationale:**
The first reaction rejects the proposal and calls for immediate damage control, while the second playfully celebrates the improbable opportunity. A demand to call the organizer back would clash with the celebratory reaction, and excitedly planning stage clothes would strongly conflict with the dismissive one.

### Pair grunt_sob_001

Contrast: grunt-sob

**Shared Turn 1** — A: The shelter just called: your childhood dog is alive, but he needs someone to take him home by tonight.

**Version 1** — [grunt] (B is reluctantly agreeing to take on an unexpected responsibility while making A accountable for the practical costs.)
  B continues: Fine, bring him here, but you’re covering the vet bills.

**Version 2** — [sob] (B is overwhelmed with relief and joy at learning that the dog they believed lost is still alive.)
  B continues: Bring him home—I thought I’d lost him forever.

**Q1 options:** Gasp / Grunt / Laughter / Sigh / Sob / Yawn

**Q2 interpretation options (for reading; real eval shuffles):**
  A. B is reluctantly agreeing to take on an unexpected responsibility while making A accountable for the practical costs.
  B. B is overwhelmed with relief and joy at learning that the dog they believed lost is still alive.

**Q3 continuation options (for reading; real eval shuffles):**
  A. Fine, bring him here, but you’re covering the vet bills.
  B. Bring him home—I thought I’d lost him forever.

**Contrastive rationale:**
The first reaction conveys begrudging acceptance focused on the burden of caring for the dog, whereas the second conveys an emotional reunion with someone B believed was gone. A practical demand about expenses is strongly dispreferred after the emotionally overwhelmed reaction, while the reunion-focused response does not fit the reluctant, irritated reaction.

### Pair grunt_yawn_001

Contrast: grunt-yawn

**Shared Turn 1** — A: I have another hour of edits on this documentary, and I want your opinion on every single cut.

**Version 1** — [grunt] (B is begrudgingly willing to help but pushes back against A's overly demanding review process by setting a limit.)
  B continues: Fine, but give me the rough cut, not a stop-and-start commentary.

**Version 2** — [yawn] (B is too mentally drained to give useful feedback now and asks to postpone the review until they can concentrate.)
  B continues: I can't keep my eyes open—send it tomorrow and I'll watch it fresh.

**Q1 options:** Gasp / Grunt / Laughter / Sigh / Sob / Yawn

**Q2 interpretation options (for reading; real eval shuffles):**
  A. B is begrudgingly willing to help but pushes back against A's overly demanding review process by setting a limit.
  B. B is too mentally drained to give useful feedback now and asks to postpone the review until they can concentrate.

**Q3 continuation options (for reading; real eval shuffles):**
  A. Fine, but give me the rough cut, not a stop-and-start commentary.
  B. I can't keep my eyes open—send it tomorrow and I'll watch it fresh.

**Contrastive rationale:**
The grunt conveys reluctant cooperation with a boundary on the task, whereas the yawn conveys fatigue and a request to defer it. Agreeing to review the cut immediately is disfavored after the yawn, while claiming exhaustion does not naturally follow the begrudging, task-focused acceptance.

### Pair laughter_sigh_001

Contrast: laughter-sigh

**Shared Turn 1** — A: I just submitted an application for us to appear on a reality show that films couples living in a tiny house.

**Version 1** — [laughter] (B treats A's impulsive application as a ridiculous but enjoyable prospect and playfully imagines participating.)
  B continues: Perfect—our arguments about dishes finally have an audience.

**Version 2** — [sigh] (B is dismayed that A volunteered their private life without asking and insists that the application be withdrawn.)
  B continues: Withdraw it; I won't turn our relationship into a spectacle.

**Q1 options:** Gasp / Grunt / Laughter / Sigh / Sob / Yawn

**Q2 interpretation options (for reading; real eval shuffles):**
  A. B treats A's impulsive application as a ridiculous but enjoyable prospect and playfully imagines participating.
  B. B is dismayed that A volunteered their private life without asking and insists that the application be withdrawn.

**Q3 continuation options (for reading; real eval shuffles):**
  A. Perfect—our arguments about dishes finally have an audience.
  B. Withdraw it; I won't turn our relationship into a spectacle.

**Contrastive rationale:**
The first reaction embraces the absurd premise as a shared joke, while the second objects to the unwanted exposure and demands a reversal. Imagining an audience conflicts with the resigned refusal to be publicly displayed, so swapping the continuations would strongly undercut each stance.

### Pair laughter_sob_001

Contrast: laughter-sob

**Shared Turn 1** — A: I posted the video of you slipping during the award ceremony, and it already has thousands of views.

**Version 1** — [laughter] (B treats the embarrassing mishap as shared humor and wants to amplify the joke rather than be embarrassed by it.)
  B continues: Send me the link—I need to put it in the group chat.

**Version 2** — [sob] (B feels hurt and betrayed because A publicly shared a humiliating moment without permission.)
  B continues: Please take it down—I trusted you with that.

**Q1 options:** Gasp / Grunt / Laughter / Sigh / Sob / Yawn

**Q2 interpretation options (for reading; real eval shuffles):**
  A. B treats the embarrassing mishap as shared humor and wants to amplify the joke rather than be embarrassed by it.
  B. B feels hurt and betrayed because A publicly shared a humiliating moment without permission.

**Q3 continuation options (for reading; real eval shuffles):**
  A. Send me the link—I need to put it in the group chat.
  B. Please take it down—I trusted you with that.

**Contrastive rationale:**
The laughter supports self-deprecating shared humor and eager sharing, whereas the sob conveys personal hurt and a demand to remove the video. Asking for the link after being upset would be strongly mismatched, while requesting removal after treating the clip as a joke is dispreferred.

### Pair laughter_yawn_001

Contrast: laughter-yawn

**Shared Turn 1** — A: I found a twelve-minute voicemail from my uncle trying to explain how he accidentally entered a goat in a dog show.

**Version 1** — [laughter] (B finds the absurd mix-up genuinely funny and eagerly wants to hear the full story.)
  B continues: Play it—I need to hear how a goat ended up at a dog show.

**Version 2** — [yawn] (B is impatient with the prospect of a long, irrelevant anecdote and wants to move on to another topic.)
  B continues: I don't have twelve minutes for that; let's talk about something else.

**Q1 options:** Gasp / Grunt / Laughter / Sigh / Sob / Yawn

**Q2 interpretation options (for reading; real eval shuffles):**
  A. B finds the absurd mix-up genuinely funny and eagerly wants to hear the full story.
  B. B is impatient with the prospect of a long, irrelevant anecdote and wants to move on to another topic.

**Q3 continuation options (for reading; real eval shuffles):**
  A. Play it—I need to hear how a goat ended up at a dog show.
  B. I don't have twelve minutes for that; let's talk about something else.

**Contrastive rationale:**
The laughter conveys eager amusement at the ridiculous premise, while the yawn conveys disengagement from the lengthy voicemail. Asking to play the recording conflicts with the disengaged reaction, and refusing to hear it conflicts with the eager amusement.

### Pair sigh_yawn_001

Contrast: sigh-yawn

**Shared Turn 1** — A: The clinic can see us only at eight tomorrow, but that overlaps your dentist appointment; should I take it?

**Version 1** — [sigh] (B reluctantly agrees to disrupt their own plans because getting the clinic appointment seems important enough to take.)
  B continues: Go ahead and book it. I’ll move my dentist appointment again.

**Version 2** — [yawn] (B has lost track of the scheduling details and needs A to repeat the key information before deciding.)
  B continues: Sorry, I drifted off—what time did they offer?

**Q1 options:** Gasp / Grunt / Laughter / Sigh / Sob / Yawn

**Q2 interpretation options (for reading; real eval shuffles):**
  A. B reluctantly agrees to disrupt their own plans because getting the clinic appointment seems important enough to take.
  B. B has lost track of the scheduling details and needs A to repeat the key information before deciding.

**Q3 continuation options (for reading; real eval shuffles):**
  A. Go ahead and book it. I’ll move my dentist appointment again.
  B. Sorry, I drifted off—what time did they offer?

**Contrastive rationale:**
The first reaction communicates reluctant acceptance of an inconvenient tradeoff, while the second communicates loss of attention and a need for clarification. Agreeing to reschedule immediately after admitting they missed the offered time is contradictory, and asking for the time after committing to move the dentist appointment is strongly dispreferred.

### Pair sob_yawn_001

Contrast: sob-yawn

**Shared Turn 1** — A: I found all the cassette recordings Grandma made for us, and I turned them into a forty-five-minute slideshow for the reunion.

**Version 1** — [sob] (B is deeply moved by the chance to hear their grandmother again and wants the tribute shown in full.)
  B continues: Please play the whole thing—I miss hearing her voice.

**Version 2** — [yawn] (B is impatient with the prospect of making everyone sit through a long presentation and wants a shorter alternative.)
  B continues: Forty-five minutes? Just put out a photo album instead.

**Q1 options:** Gasp / Grunt / Laughter / Sigh / Sob / Yawn

**Q2 interpretation options (for reading; real eval shuffles):**
  A. B is deeply moved by the chance to hear their grandmother again and wants the tribute shown in full.
  B. B is impatient with the prospect of making everyone sit through a long presentation and wants a shorter alternative.

**Q3 continuation options (for reading; real eval shuffles):**
  A. Please play the whole thing—I miss hearing her voice.
  B. Forty-five minutes? Just put out a photo album instead.

**Contrastive rationale:**
The sob communicates heartfelt attachment to the recordings and support for the full slideshow, while the yawn communicates impatience with its length and a request to replace it. Asking to play the whole tribute conflicts with the disengaged reaction, whereas dismissing it in favor of a photo album conflicts with the emotional overwhelm.
