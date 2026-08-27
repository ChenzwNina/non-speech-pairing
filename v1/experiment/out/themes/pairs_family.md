# Predicting response

writer: gpt-4o · 15 pair(s) · 6 turns per version · cast A and B

Turns 1–4 are identical across both versions, and turn 4 is the trigger. Turn 5 is B's first contribution, a vocalization only. Turn 6 is the reply the vocalization should select.

### Pair family_gasp_grunt_001

Contrast: gasp-grunt · Scenario: A parent informs their teenager about an upcoming family reunion plan.
Trigger: The family reunion is scheduled for a weekend trip next month.

**Shared context**

1. A: Hey, I've got some news about the family.
2. A: Your Aunt Sarah is organizing a reunion.
3. A: She wants to have everyone together for a weekend trip.
4. A: It's scheduled for next month.  ← trigger

**Version 1** — [gasp] as surprise

5. B: [gasp]
6. A: It's exciting, right? Everyone's going to be there.

**Version 2** — [grunt] as strong unwillingness

5. B: [grunt]
6. A: We can talk about whether you need to go, but it means a lot to her.

**Why the vocalization changes the response:**
With a gasp, A assumes surprise and excitement, reinforcing the positive aspect of the gathering. With a grunt, A recognizes reluctance and offers to discuss participation, acknowledging the possible unwillingness.

### Pair family_gasp_laughter_001

Contrast: gasp-laughter · Scenario: Sibling discovery of their childhood drawings while sorting old family boxes.
Trigger: A finds and shows an old drawing of a dinosaur wearing a superhero cape.

**Shared context**

1. A: Hey, while I was going through these boxes, I found something you'd love.
2. A: Remember all those drawings we made as kids?
3. A: Check this out—it's a dinosaur wearing a superhero cape.
4. A: We must have thought it was the coolest thing ever.  ← trigger

**Version 1** — [gasp] as surprise

5. B: [gasp]
6. A: Right? I completely forgot how imaginative we were as kids.

**Version 2** — [laughter] as amusement

5. B: [laughter]
6. A: I know, right? We were such little artists back then.

**Why the vocalization changes the response:**
After the gasp, A acknowledges the surprise and reflects on their forgotten creativity, highlighting the unexpectedness. The laughter response takes a playful approach, sharing amusement over their youthful imagination, maintaining a lighthearted tone.

### Pair family_gasp_sigh_001

Contrast: gasp-sigh · Scenario: A parent informs their child about discovering a rare family heirloom that needs restoring.
Trigger: A revealed finding an old, damaged quilt with embroidered family stories.

**Shared context**

1. A: I was in the attic today, sorting through some of the old boxes.
2. A: You'll never believe what I found—it was your great-grandmother's quilt.
3. A: It's got all these intricate family stories embroidered on it.
4. A: But it's pretty damaged after all these years.  ← trigger

**Version 1** — [gasp] as surprise

5. B: [gasp]
6. A: I know, right? We should definitely get it restored soon.

**Version 2** — [sigh] as feeling burdened

5. B: [sigh]
6. A: It's a lot of work, but we can restore it gradually.

**Why the vocalization changes the response:**
With the gasp, A shares B's surprise and immediately suggests restoration, highlighting excitement. The sigh signals a sense of burden, so A responds by acknowledging the work involved and suggests a gradual approach, indicating understanding and pacing.

### Pair family_gasp_sob_001

Contrast: gasp-sob · Scenario: A tells B about discovering their grandfather's hidden journals with complicated family history.
Trigger: A reveals they found their grandfather's journals with detailed family history, offering surprising and emotional insights.

**Shared context**

1. A: I was cleaning out the attic yesterday and found a dusty old box.
2. A: Inside were a bunch of Grandpa's old journals, ones no one knew about.
3. A: I've only read a little, but they have some surprising family stories.
4. A: Apparently, he wrote about a side of our family that moved to France during the war.  ← trigger

**Version 1** — [gasp] as surprise, admiration

5. B: [gasp]
6. A: Right? I can barely believe it myself! Seems like there's a lot we didn't know.

**Version 2** — [sob] as being emotionally overwhelmed

5. B: [sob]
6. A: Hey, it's a lot to take in, I know. Let's sit down and go through them together when you're ready.

**Why the vocalization changes the response:**
The [gasp] indicates surprise or admiration, leading A to share in the unexpected discovery enthusiastically. The [sob] signals emotional overwhelm, prompting A to offer comfort and suggest going through the journals gently together, adapting to B's emotional state.

### Pair family_gasp_yawn_001

Contrast: gasp-yawn · Scenario: A parent discusses a surprise family trip they've planned for the kids.
Trigger: A reveals they've planned a surprise weekend trip to a historic locale.

**Shared context**

1. A: Guess what? I've been planning something special for the whole family.
2. A: I've secretly arranged for us to go on a weekend trip.
3. A: It's somewhere we haven't been before, and I think it'll be really fun.
4. A: We're going to that historic town by the coast this weekend!  ← trigger

**Version 1** — [gasp] as surprise

5. B: [gasp]
6. A: Right? The kids are going to love exploring all the old buildings!

**Version 2** — [yawn] as tiredness

5. B: [yawn]
6. A: Let's make sure we get plenty of rest before we head out.

**Why the vocalization changes the response:**
In version 1, B's gasp indicates surprise or excitement, prompting A to share in the enthusiasm and highlight the fun aspect of the trip. In version 2, B's yawn signals low energy or tiredness, leading A to suggest rest to prepare for the trip, adapting to a more practical concern.

### Pair family_grunt_laughter_001

Contrast: grunt-laughter · Scenario: A parent tells their child about needing to sort through the attic to make space for visiting family.
Trigger: A says the attic needs to be fully cleared for the family visit.

**Shared context**

1. A: Hey, remember that we're hosting the family reunion next month?
2. A: I've been thinking we should clear out the attic to make some room.
3. A: There's a ton of old stuff up there that we never use.
4. A: So we'll need to clear it all out before they arrive.  ← trigger

**Version 1** — [grunt] as strong unwillingness

5. B: [grunt]
6. A: Okay, we can just focus on the left side this weekend and tackle the rest later.

**Version 2** — [laughter] as amusement

5. B: [laughter]
6. A: Right? It's going to be like a treasure hunt up there. Let's find some interesting stuff.

**Why the vocalization changes the response:**
The grunt indicates reluctance or resistance, leading A to soften the task by suggesting a phased approach. The laughter suggests B finds the idea amusing or exciting, prompting A to frame the task as a fun discovery activity.

### Pair family_grunt_sigh_001

Contrast: grunt-sigh · Scenario: Two siblings are sorting through old family photo albums for an upcoming anniversary party.
Trigger: A reveals how many albums are left to sort.

**Shared context**

1. A: We really need to get these albums sorted for Grandma and Grandpa's anniversary party.
2. A: I started with the ones from the 1970s, but it's taking longer than I thought.
3. A: It's kind of fun, though—look at how everyone dressed back then.
4. A: But we still have ten more albums to go through by tomorrow.  ← trigger

**Version 1** — [grunt] as impatience

5. B: [grunt]
6. A: I know it's a lot, but maybe we can skip some years if they're too similar.

**Version 2** — [sigh] as feeling burdened

5. B: [sigh]
6. A: Let's leave half for later; we don't have to finish all tonight.

**Why the vocalization changes the response:**
The grunt indicates impatience, prompting A to negotiate by suggesting a way to speed up the process, while the sigh reflects feeling burdened, leading A to propose dividing the task to make it more manageable.

### Pair family_grunt_sob_001

Contrast: grunt-sob · Scenario: Two siblings are packing up their late grandmother's belongings.
Trigger: A shares that they need to sort through Grandma's personal letters tonight.

**Shared context**

1. A: I sorted through all of Grandma's clothes this morning. It was harder than I thought.
2. A: I found some old trinkets we might want to keep, too.
3. A: But there’s still a lot left to do. The hardest part is going through her personal letters.
4. A: We should try to get through those tonight.  ← trigger

**Version 1** — [grunt] as strong unwillingness

5. B: [grunt]
6. A: What if we just start with a few? We can finish the rest over the weekend.

**Version 2** — [sob] as deep sadness

5. B: [sob]
6. A: Hey, it's okay. We can take it slow and stop whenever you need.

**Why the vocalization changes the response:**
The grunt signals reluctance, prompting A to suggest breaking up the task into smaller, manageable parts. The sob indicates emotional overwhelm, leading A to offer reassurance and the option to pause.

### Pair family_grunt_yawn_001

Contrast: grunt-yawn · Scenario: Parent and teenager discussing a weekend plan to reorganize the basement.
Trigger: Speaker A reveals the plan to spend the weekend clearing out the basement.

**Shared context**

1. A: Hey, so this weekend I've planned for us to finally tackle the basement.
2. A: We've been putting it off for months now, and it really needs to be done.
3. A: I thought we could both spend Saturday sorting through everything.
4. A: It's a big job, but it’ll be great to have it organized.  ← trigger

**Version 1** — [grunt] as strong unwillingness

5. B: [grunt]
6. A: Okay, okay—how about we do just half this weekend and finish the rest next time?

**Version 2** — [yawn] as tiredness

5. B: [yawn]
6. A: We can start later in the morning so you can sleep in a bit. Does that help?

**Why the vocalization changes the response:**
The grunt signals strong unwillingness, prompting A to offer a compromise to reduce the workload. The yawn indicates tiredness, leading A to adjust the timing to accommodate B's energy levels. Each response adapts differently based on B's vocalization, addressing either workload or rest.

### Pair family_laughter_sigh_001

Contrast: laughter-sigh · Scenario: Two siblings discuss their childhood toys while clearing out the attic.
Trigger: A found an old handmade puppet from their childhood.

**Shared context**

1. A: Remember when we used to play in the attic for hours, pretending it was our secret castle?
2. A: We had that whole collection of toys and made up the craziest stories.
3. A: Oh wow, look what I found!
4. A: It's our old handmade puppet! I can't believe it survived all these years.  ← trigger

**Version 1** — [laughter] as amusement

5. B: [laughter]
6. A: Right? We should keep it; it's a piece of our crazy stories.

**Version 2** — [sigh] as tiredness

5. B: [sigh]
6. A: Let's just decide later; maybe we can sort through the rest of the toys another day.

**Why the vocalization changes the response:**
With laughter, A joins the humor of finding an unlikely survivor, celebrating their playful past. With a sigh, A senses B's weariness and shifts to postponing the decision, acknowledging the burden of sorting.

### Pair family_laughter_sob_001

Contrast: laughter-sob · Scenario: A parent and their adult child are reflecting on old family videos.
Trigger: Revealing a hilarious or deeply moving moment in an old family video.

**Shared context**

1. A: I was going through the old family videos last night.
2. A: Do you remember that trip to the beach when you were five?
3. A: You were trying to build a sandcastle but kept getting distracted by seagulls.
4. A: And then you started performing your own little dance, completely unprompted.  ← trigger

**Version 1** — [laughter] as amusement

5. B: [laughter]
6. A: I know, right? You always knew how to entertain a crowd!

**Version 2** — [sob] as being emotionally overwhelmed

5. B: [sob]
6. A: Oh, those memories really get to you, don't they? They’re so precious.

**Why the vocalization changes the response:**
Laughter from B prompts A to join in the amusement and lighten the moment with a playful comment about entertaining a crowd. The sob suggests B is overwhelmed with emotion, prompting A to acknowledge the depth of feeling and value of the memories. The two responses show different engagement based on B's emotional reaction.

### Pair family_laughter_yawn_001

Contrast: laughter-yawn · Scenario: Two siblings talking about preparing a short, funny speech for their parent's birthday.
Trigger: A shares the final line planned for the speech, aiming for humor.

**Shared context**

1. A: I've been working on the speech for mom's birthday.
2. A: I want to make it fun and lighthearted.
3. A: I've added a story about the time she accidentally ordered forty pizzas for a school event.
4. A: I'm ending with: 'So here's to mom, the only person who can feed an entire town by mistake!'  ← trigger

**Version 1** — [laughter] as amusement

5. B: [laughter]
6. A: Glad you liked that bit! I think she'll get a kick out of it too.

**Version 2** — [yawn] as tiredness

5. B: [yawn]
6. A: Alright, maybe we won't rehearse any more. Let's finish it tomorrow.

**Why the vocalization changes the response:**
The laughter signals amusement and encourages A to continue with the humorous tone, reinforcing the idea that the speech is engaging. The yawn, suggesting tiredness, prompts A to recognize B's low energy and propose stopping the rehearsal, prioritizing rest over rehearsal.

### Pair family_sigh_sob_001

Contrast: sigh-sob · Scenario: A parent tells their child about needing to get rid of their late relative's belongings.
Trigger: A informs B about needing to sort through and donate their grandmother's possessions.

**Shared context**

1. A: We really need to start sorting through Grandma's things soon.
2. A: I know it’s going to be tough, but we can donate a lot of it to charity.
3. A: There are so many memories attached to each item.
4. A: But leaving it untouched isn't going to get any easier.  ← trigger

**Version 1** — [sigh] as feeling burdened

5. B: [sigh]
6. A: Let's just tackle one box today and see how we feel after that, okay?

**Version 2** — [sob] as deep sadness

5. B: [sob]
6. A: Hey, we don’t have to do it all now. We can keep her favorite things for as long as we need.

**Why the vocalization changes the response:**
In version 1, A acknowledges B's feeling of being burdened and suggests breaking the task into smaller, more manageable parts to alleviate the sense of overwhelm. In version 2, A perceives B's deep sadness and offers reassurance by suggesting they keep meaningful items, reducing emotional pressure and focusing on gentler emotional support.

### Pair family_sigh_yawn_001

Contrast: sigh-yawn · Scenario: Two siblings discussing a weekend meal prep plan for a large family gathering.
Trigger: A reveals that they need to make five different dishes for the meal prep.

**Shared context**

1. A: So, this weekend we're tackling the meal prep for the family gathering.
2. A: I was thinking we'll need to make enough for everyone, maybe plan a few different dishes.
3. A: I know it's going to be a bit of work, but it should be fun to do it together.
4. A: We have to make five different dishes for Saturday.  ← trigger

**Version 1** — [sigh] as tiredness

5. B: [sigh]
6. A: Let's just pick a few favorites and keep it simple.

**Version 2** — [yawn] as low energy

5. B: [yawn]
6. A: How about we skip a couple of those and just do the essentials?

**Why the vocalization changes the response:**
The sigh indicates B is feeling weary, so A suggests simplifying the plan by choosing a few favorite dishes. The yawn signals low energy, prompting A to consider prioritizing only the essential dishes. Each response adjusts the workload differently based on B's reaction.

### Pair family_sob_yawn_001

Contrast: sob-yawn · Scenario: A parent discusses the future of the family home they currently live in.
Trigger: A asks B to consider the prospect of moving out of their childhood home.

**Shared context**

1. A: You know how much this house means to all of us.
2. A: But maintaining it is getting harder every year.
3. A: We’ve talked about downsizing a bit.
4. A: I think it's really time to consider moving out soon.  ← trigger

**Version 1** — [sob] as being emotionally overwhelmed

5. B: [sob]
6. A: It's okay, we don't have to decide anything today. Let's just keep talking about it.

**Version 2** — [yawn] as tiredness

5. B: [yawn]
6. A: Why don't we discuss this tomorrow after we've both rested?

**Why the vocalization changes the response:**
The sob indicates that B is emotionally overwhelmed by the thought of leaving the family home, so A offers reassurance and patience to handle the emotional weight. The yawn suggests fatigue or low engagement with the ongoing discussion, prompting A to suggest postponing the conversation until they are both more refreshed.
