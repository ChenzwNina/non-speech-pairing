# Predicting response

writer: gpt-4o · 15 pair(s) · 6 turns per version · cast A and B

Turns 1–4 are identical across both versions, and turn 4 is the trigger. Turn 5 is B's first contribution, a vocalization only. Turn 6 is the reply the vocalization should select.

### Pair school_gasp_grunt_001

Contrast: gasp-grunt · Scenario: Students discussing a last-minute assignment in the library.
Trigger: A reveals the entire project is due tomorrow.

**Shared context**

1. A: We really have to pull through with this project if we want to pass history.
2. A: I went ahead and compiled the research sources last night.
3. A: We can use some charts and graphs to make the presentation stronger.
4. A: Oh, and by the way, the entire project is due tomorrow.  ← trigger

**Version 1** — [gasp] as surprise

5. B: [gasp]
6. A: I know—it's a lot, but we can split up the sections to get it done.

**Version 2** — [grunt] as strong unwillingness

5. B: [grunt]
6. A: Okay, let's just focus on the most important parts to save time.

**Why the vocalization changes the response:**
The gasp indicates surprise, prompting A to reassure and offer a plan to manage the shock. The grunt suggests reluctance, leading A to simplify the workload to accommodate B's resistance.

### Pair school_gasp_laughter_001

Contrast: gasp-laughter · Scenario: Students are discussing their team project after a class presentation.
Trigger: A reveals the professor's unexpected praise for their project.

**Shared context**

1. A: I can't believe we finally finished our presentation this morning.
2. A: I was so nervous in front of the class.
3. A: But we pulled it off without any major issues, right?
4. A: And guess what? Professor Lee said it was one of the best he's seen all semester!  ← trigger

**Version 1** — [gasp] as surprise

5. B: [gasp]
6. A: Yeah, I was shocked too! I think he'll mention it in the newsletter.

**Version 2** — [laughter] as amusement

5. B: [laughter]
6. A: Right? That’s hilarious! I thought he’d mention the time we almost tripped over the cables!

**Why the vocalization changes the response:**
With the gasp, A assumes B is surprised and shares their own shock, offering more serious acknowledgment of the praise. With laughter, A treats the reaction as humor, joining in on the amusement and making a playful comment about the presentation.

### Pair school_gasp_sigh_001

Contrast: gasp-sigh · Scenario: Students discussing a group project deadline extension after class.
Trigger: A reveals that the project deadline has been extended by another week.

**Shared context**

1. A: Hey, did you hear about the group project? I just talked to Mr. Davis.
2. A: He realized that everyone's struggling to keep up with the original timeline.
3. A: So, he decided to give us some extra time to finish it.
4. A: The deadline is now extended by another week.  ← trigger

**Version 1** — [gasp] as pleasant surprise

5. B: [gasp]
6. A: Right? It’s a huge relief! Now we can actually polish our presentation.

**Version 2** — [sigh] as resignation

5. B: [sigh]
6. A: I know, it's been a lot to juggle. We can pace ourselves better now.

**Why the vocalization changes the response:**
The gasp shows pleasant surprise, prompting A to share in the excitement and relief about having more time. The sigh indicates feeling burdened, leading A to acknowledge the workload and offer a plan to manage the time more effectively.

### Pair school_gasp_sob_001

Contrast: gasp-sob · Scenario: Two classmates discuss a scholarship opportunity in the school common room.
Trigger: A reveals that B has received the full scholarship for their top-choice university.

**Shared context**

1. A: Hey, you remember that scholarship you applied for?
2. A: The one for the university you really wanted to attend?
3. A: I just saw the list of recipients in the office.
4. A: You're on it! You got the full scholarship!  ← trigger

**Version 1** — [gasp] as surprise

5. B: [gasp]
6. A: Amazing, right? I knew you could do it!

**Version 2** — [sob] as being emotionally overwhelmed

5. B: [sob]
6. A: Hey, take your time. You totally deserve this.

**Why the vocalization changes the response:**
The gasp suggests surprise, leading A to share excitement and affirmation. The sob indicates B is overwhelmed, so A offers gentle support and acknowledgment, allowing B to process their emotions.

### Pair school_gasp_yawn_001

Contrast: gasp-yawn · Scenario: Two classmates discuss their upcoming school trip's itinerary.
Trigger: A mentions adding a surprise visit to a famous art gallery to the school trip's itinerary.

**Shared context**

1. A: So, I talked to Mr. Edwards about the trip.
2. A: He said we could fit a little more into the schedule.
3. A: Since we'll be near downtown anyway, I suggested a surprise visit to the famous art gallery.
4. A: He thought it was a great idea and added it without telling everyone.  ← trigger

**Version 1** — [gasp] as surprise

5. B: [gasp]
6. A: I know, right? It's going to be amazing seeing all that art.

**Version 2** — [yawn] as low energy

5. B: [yawn]
6. A: Feeling tired? We can always skip it if it's too much.

**Why the vocalization changes the response:**
With the gasp, A acknowledges B's surprise and shares excitement about the gallery visit. With the yawn, A senses B's low energy and offers reassurance that the gallery visit is optional if B feels overwhelmed.

### Pair school_grunt_laughter_001

Contrast: grunt-laughter · Scenario: Two classmates are discussing decorating their classroom for spirit week.
Trigger: A reveals the teacher wants them to decorate the entire room by tomorrow.

**Shared context**

1. A: So, I talked to Mr. Johnson about spirit week decorations.
2. A: He said we can use anything we find in the art supplies closet.
3. A: But the catch is, we have to set up everything tonight after school.
4. A: And he wants the entire room done by tomorrow morning.  ← trigger

**Version 1** — [grunt] as strong unwillingness

5. B: [grunt]
6. A: Okay, okay—we can just focus on the front wall and leave the rest.

**Version 2** — [laughter] as amusement

5. B: [laughter]
6. A: Right? Guess we'll be making some quick art decisions tonight!

**Why the vocalization changes the response:**
The grunt indicates B's reluctance, prompting A to suggest narrowing the task to make it manageable. The laughter suggests B finds the situation amusing, leading A to play along with the absurdity and enthusiasm for a creative challenge.

### Pair school_grunt_sigh_001

Contrast: grunt-sigh · Scenario: Two classmates are planning a study schedule for finals week.
Trigger: A reveals the extra credit opportunity that requires extra study on a weekend.

**Shared context**

1. A: Alright, we need to come up with a study schedule for finals week.
2. A: I was thinking we could start with math since it's the toughest.
3. A: And then maybe history, since there's so much to memorize.
4. A: Plus, there's an extra credit project due on Saturday if we can put in some weekend hours.  ← trigger

**Version 1** — [grunt] as strong unwillingness

5. B: [grunt]
6. A: Okay, okay—we can skip it if you’d rather not. Let’s just focus on the essentials.

**Version 2** — [sigh] as feeling burdened

5. B: [sigh]
6. A: We don't have to do the extra credit this week; let's prioritize what’s most important.

**Why the vocalization changes the response:**
With the grunt, A responds to what sounds like a firm unwillingness to add more work, suggesting dropping the extra credit entirely. In contrast, the sigh indicates being overwhelmed, so A proposes not prioritizing the extra credit but leaves it as an optional task, reflecting a more supportive adaptation rather than immediate dismissal.

### Pair school_grunt_sob_001

Contrast: grunt-sob · Scenario: Two students in the art room discuss the immense workload for the upcoming art exhibition.
Trigger: A reveals they have to set up all exhibits by Friday.

**Shared context**

1. A: You know the art exhibition is just around the corner, right?
2. A: We got confirmation from Mr. Davis today about the final list.
3. A: It's more than we expected, with a lot of pieces coming in from other classes.
4. A: We have to set up all the exhibits by Friday afternoon.  ← trigger

**Version 1** — [grunt] as strong unwillingness

5. B: [grunt]
6. A: I get it, it's a lot. Maybe we can split the setup over a couple of days.

**Version 2** — [sob] as being emotionally overwhelmed

5. B: [sob]
6. A: Hey, it's okay. We can take it one step at a time. How about we start with just one section?

**Why the vocalization changes the response:**
The grunt suggests a strong unwillingness, prompting A to offer a practical compromise to reduce the burden. The sob indicates being overwhelmed, leading A to offer emotional support and a suggestion to take things slowly. Each response addresses B's distinct emotional signal differently.

### Pair school_grunt_yawn_001

Contrast: grunt-yawn · Scenario: Two classmates discuss organizing the school's talent show after classes.
Trigger: A suggests they need to stay late all week for rehearsal setup.

**Shared context**

1. A: So, the talent show schedule is finalized, and we've got everyone assigned their rehearsal slots.
2. A: But we still need more volunteers to manage the backstage setup.
3. A: It's going to be a lot of work, especially checking all the lighting and sound equipment by Friday.
4. A: I think we'll have to stay late after school every day this week to get it all ready.  ← trigger

**Version 1** — [grunt] as strong unwillingness

5. B: [grunt]
6. A: Alright, how about I handle the equipment checks, and you oversee scheduling the volunteers?

**Version 2** — [yawn] as tiredness

5. B: [yawn]
6. A: We can take it easy and see how much we finish today before worrying about tomorrow.

**Why the vocalization changes the response:**
The grunt indicates an unwillingness or resistance to staying late, so A responds by proposing a division of labor to make it more manageable. The yawn suggests tiredness or low energy, leading A to suggest pacing themselves and focusing only on today's tasks for now. Each response adapts the workload based on B's reaction.

### Pair school_laughter_sigh_001

Contrast: laughter-sigh · Scenario: Two classmates discuss their science club's experiment results.
Trigger: A reveals that their experiment was completely off the mark.

**Shared context**

1. A: I stayed late in the lab last night to analyze our data.
2. A: I thought we'd nailed the experiment this time.
3. A: But instead of getting the reaction we expected, the whole thing turned purple.
4. A: Turns out we mixed up the reagents.  ← trigger

**Version 1** — [laughter] as amusement

5. B: [laughter]
6. A: Right? It was like a chemistry comic sketch gone wrong.

**Version 2** — [sigh] as feeling burdened

5. B: [sigh]
6. A: Let's take a break and recollect tomorrow; it’s been a long week.

**Why the vocalization changes the response:**
In the laughter version, A embraces the humor of the mistake, treating B's reaction as a cue to share in the amusement. In the sigh version, A acknowledges the exhaustion, offering a pause before continuing.

### Pair school_laughter_sob_001

Contrast: laughter-sob · Scenario: Two classmates talk about their roles in the upcoming school play.
Trigger: A admits they accidentally swapped the main characters' costumes.

**Shared context**

1. A: I’ve been organizing the costumes for the school play all week.
2. A: It's taken a ton of coordination to make sure everyone looks the part.
3. A: You know how detailed these characters can be, every accessory matters.
4. A: Well, here's the thing—I accidentally swapped the main characters' costumes.  ← trigger

**Version 1** — [laughter] as amusement

5. B: [laughter]
6. A: I know, it sounds ridiculous! Luckily, we have time to switch them back.

**Version 2** — [sob] as being emotionally overwhelmed

5. B: [sob]
6. A: Hey, it's okay. We'll sort it out in time for the dress rehearsal.

**Why the vocalization changes the response:**
The laughter suggests B finds the mix-up funny, prompting A to join in on the humor and reassure B that it's manageable. The sob indicates B is overwhelmed by the mistake, leading A to offer comfort and assure them it can be resolved.

### Pair school_laughter_yawn_001

Contrast: laughter-yawn · Scenario: Two classmates discussing their new history assignment in the classroom.
Trigger: A reveals they found a drawing from last year's class hidden in a school desk.

**Shared context**

1. A: Guess what I found in the desk when I was reaching for my notes.
2. A: It’s a drawing that someone from last year's class left behind.
3. A: It’s a cartoon of Mr. Thompson dressed as a knight!
4. A: He’s holding a ruler like a sword, and there’s a dragon labeled 'Homework.'  ← trigger

**Version 1** — [laughter] as amusement

5. B: [laughter]
6. A: Right? I think it deserves a spot on the classroom wall again.

**Version 2** — [yawn] as tiredness

5. B: [yawn]
6. A: Feeling sleepy? We can always check it out tomorrow after class.

**Why the vocalization changes the response:**
With [laughter], A joins in the amusement and suggests displaying the drawing, creating a shared humorous moment. With [yawn], A notices B's low energy and offers to defer examining the drawing, acknowledging fatigue.

### Pair school_sigh_sob_001

Contrast: sigh-sob · Scenario: Two classmates discuss feedback received on their history projects from their teacher.
Trigger: The teacher's feedback indicated that they both need to redo a major part of their projects.

**Shared context**

1. A: We finally got the feedback on our history projects.
2. A: I thought I did pretty well, but I guess not.
3. A: Mrs. Daniels said our main arguments need to be reworked entirely.
4. A: Looks like we'll have to redo a major part of our projects.  ← trigger

**Version 1** — [sigh] as tiredness

5. B: [sigh]
6. A: Alright, let's break it down into smaller tasks so it feels less overwhelming.

**Version 2** — [sob] as being emotionally overwhelmed

5. B: [sob]
6. A: Hey, it's tough, but we can take it one step at a time together.

**Why the vocalization changes the response:**
The sigh indicates weariness, so A offers a practical way to reduce the burden. In contrast, the sob shows emotional overwhelm, leading A to provide emotional support and reassurance.

### Pair school_sigh_yawn_001

Contrast: sigh-yawn · Scenario: Two classmates plan a weekend study session for an upcoming exam.
Trigger: A suggests starting the study session early in the morning.

**Shared context**

1. A: We really need to prepare for the biology exam next week.
2. A: I was thinking we could meet up this Saturday to go over the chapters.
3. A: There's a lot to cover, so it'd be good to start early in the morning.
4. A: I think starting at 8 AM would be ideal to get a head start.  ← trigger

**Version 1** — [sigh] as tiredness

5. B: [sigh]
6. A: Okay, we can start at 9 AM instead if that's more manageable.

**Version 2** — [yawn] as low energy

5. B: [yawn]
6. A: Alright, I’ll narrow it down to the key topics so it won’t take as long.

**Why the vocalization changes the response:**
In version 1, A perceives B's sigh as exhaustion, leading A to adjust the schedule for a later start. In version 2, A interprets B's yawn as low energy, prompting A to simplify the study plan to maintain engagement.

### Pair school_sob_yawn_001

Contrast: sob-yawn · Scenario: Two classmates discuss class elections and a speech that must be given.
Trigger: A reveals they will have to speak in front of the entire school by Friday.

**Shared context**

1. A: I just found out about the class elections schedule.
2. A: They moved everything one day earlier than planned.
3. A: So instead of next week, all speeches are due by Friday.
4. A: We’ll have to speak in front of the entire school by then.  ← trigger

**Version 1** — [sob] as being emotionally overwhelmed

5. B: [sob]
6. A: Hey, it's okay. We can work on the speech together—I'll help you with it.

**Version 2** — [yawn] as tiredness

5. B: [yawn]
6. A: Alright, let's just get through the draft tonight and polish it later.

**Why the vocalization changes the response:**
After [sob], A responds with emotional support and a team-oriented offer, sensing that B is overwhelmed by the pressure. After [yawn], A shifts to a more practical approach, recognizing B's fatigue and suggesting they tackle the immediate task with less intensity.
