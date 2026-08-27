# Hard task — 8-turn conversations, two vocalization events each

writer/verifier: gpt-5.6-terra · 6 item(s)

Each item was built backward: the ground truth below (target turn, sound, meaning,
evidence) was fixed before any dialogue existed, and the transcript was written to
realize it. The ground truth doubles as the evaluation rubric.

### gasp_grunt_001

Domain: School and student life: two students on the school newspaper navigate fallout from an anonymous satirical cafeteria comic.  ·  contrast: gasp-grunt

1. **A:** I just came from Ms. Rivera: the principal spotted the little details in the anonymous cafeteria comic and asked her to name its creator. You sent it without your name so the menu criticism would not come back on you.
2. **B:** [gasp]  ← target
3. **A:** Ms. Rivera wants to speak with you before dismissal today while she decides how to answer him.
4. **B:** That overlaps my peer-tutoring shift in the library; Jordan is counting on me to help with algebra.
5. **A:** And that is the only library period I set aside to study for tomorrow's chemistry test. I really need the review.
6. **B:** Could you take my tutoring shift just this once so I can meet Ms. Rivera?
7. **A:** [grunt]  ← target
8. **B:** Thank you. I will let Jordan know you are covering and head to her office.

**event_1 — turn 2, B, [gasp]**

- Meaning: B reacts with alarm because A's news suggests the principal may expose B as the creator of the anonymous comic, defeating B's attempt to criticize the cafeteria without being personally singled out.
- Evidence turns: [1]
- Evidence: A says that B submitted the cafeteria comic anonymously to avoid repercussions, and that the principal noticed identifying details and asked the adviser to identify the creator.
- Planned before writing: Before this reaction, establish that B submitted a satirical cafeteria comic anonymously to the student newspaper and that A has learned the principal noticed identifying details and has asked the newspaper adviser to identify its creator. Make clear that B chose anonymity to avoid personal repercussions for the criticism.

**event_2 — turn 7, A, [grunt]**

- Meaning: A gives reluctant assent to cover B's peer-tutoring shift so B can meet the adviser about the comic, despite A having planned to use that same library period to prepare for an important test.
- Evidence turns: [3, 4, 5, 6]
- Evidence: A says the adviser needs to meet B before dismissal; B explains that this conflicts with a peer-tutoring shift, while A says the same library period is needed for chemistry-test study. B then asks A to cover the shift.
- Planned before writing: Before this reaction, establish that the adviser needs to meet B promptly about the principal's inquiry, that the meeting conflicts with B's committed peer-tutoring shift, and that B asks A to cover it. Also establish that A had already said the library period was needed for studying for a major test, making the help a genuine concession.

### gasp_laughter_001

Domain: Neighbours preparing an apartment building’s shared courtyard for a residents’ potluck, including setting up borrowed string lights near a temperamental communal outlet.  ·  contrast: gasp-laughter

1. **A:** I volunteered to hang the borrowed string lights; I’m the practical neighbour around here, so I can get the courtyard ready before anyone brings food.
2. **B:** Please leave the communal outlet controls alone. That outlet has been unreliable, and sprinklers can leave the paving wet around plugged-in equipment.
3. **A:** I’ll only run a quick test from the panel, then route the cords up the posts and keep them off the ground.
4. **B:** The potluck starts soon, so call me before changing anything in that cabinet.
5. **A:** I did a test with the lights plugged in, and the sprinklers came on instead; water is spraying across the courtyard.
6. **B:** [gasp]  ← target
7. **A:** I pressed the irrigation control, not the lighting switch. The safety breaker cut power before the lights were harmed, and nobody has arrived; apparently my practical method was to water the empty courtyard first.
8. **B:** [laughter]  ← target

**event_1 — turn 6, B, [gasp]**

- Meaning: B reacts with alarm to A admitting that their lighting test activated the courtyard sprinklers while the string lights were connected, because B had warned that the shared outlet was unreliable and the wet setup could become dangerous before the potluck.
- Evidence turns: [1, 2, 3, 5]
- Evidence: A presents themself as capable of handling the borrowed lights, B warns that the unreliable communal outlet and wet sprinkler area are unsafe around plugged-in equipment, and A then says the sprinklers came on while the lights were plugged in.
- Planned before writing: Earlier context should establish that A volunteered for the courtyard lighting and confidently presented themselves as capable of handling it, that B warned them not to tamper with the unreliable communal controls, and that the potluck setup involves electrical equipment in an area that can be wet. Before this reaction, A must reveal that their attempted test activated the sprinklers while the lights were plugged in.

**event_2 — turn 8, B, [laughter]**

- Meaning: B playfully teases A’s claim to be the practical neighbour after learning that A mistook the irrigation control for the lighting switch, especially once it is clear that the breaker protected the equipment and no guests had arrived yet.
- Evidence turns: [1, 2, 5, 7]
- Evidence: A had claimed to be the practical neighbour, B had warned about the controls, and A later reveals they pressed the irrigation control, while the safety breaker protected the lights and the courtyard was still empty.
- Planned before writing: The prior context should retain A’s earlier confidence and B’s warning about the courtyard controls, along with the apparent mishap that prompted B’s concern. Before this reaction, A must clarify that they pressed the wrong control, that the safety breaker cut power before the lights were damaged, and that the courtyard was still empty, making A’s supposedly expert setup attempt safely ridiculous rather than a disaster.

### gasp_sigh_001

Domain: Two friends developing a small cooperative video game as a side project and unexpectedly being offered a slot on an online indie-game livestream.  ·  contrast: gasp-sigh

1. **A:** I still think of this as our weekend experiment; we were going to keep testing it with friends until it felt less rough.
2. **B:** Right, and my revive animation is still half done, while your new cave level has placeholder lighting everywhere.
3. **A:** The Indie Relay organizers just emailed: they picked our current build for their livestream on Friday, in front of their whole audience.
4. **B:** [gasp]  ← target
5. **A:** Friday is far too soon for the matchmaking fixes and the final boss pass I wanted before anyone outside our little group saw it.
6. **B:** But a slot like this could bring feedback from real co-op players. Please do not pull us; we can tell viewers the build is still in progress and learn what needs attention.
7. **A:** [sigh]  ← target
8. **B:** Okay, I will confirm that we are in and put together a feedback form for the stream.

**event_1 — turn 4, B, [gasp]**

- Meaning: B reacts with startled excitement to A's revelation that their modest, unfinished hobby game has been selected for an imminent public livestream, turning what B expected to be a private experiment into an unexpectedly visible opportunity.
- Evidence turns: [1, 2, 3]
- Evidence: A and B describe the game as a casual private experiment with unfinished animation, lighting, and other rough work, then A reports that the current build was selected for a Friday Indie Relay livestream before its whole audience.
- Planned before writing: Earlier context should establish that A and B have been making the game casually, expected to refine it privately before anyone notable saw it, and have different unfinished contributions still in progress. It should also establish that A has just learned of an unexpected near-term invitation or selection that would put the current build before a much larger audience than either expected.

**event_2 — turn 7, A, [sigh]**

- Meaning: A gives reluctant agreement to B's wish to keep the game on the livestream schedule, despite A's concern that the incomplete build will make a poor first impression after the project suddenly became public.
- Evidence turns: [2, 3, 5, 6]
- Evidence: The build still has incomplete components, the livestream is scheduled for Friday, A says the planned matchmaking and boss polish cannot be finished before public exposure, and B urges keeping the slot for player feedback rather than withdrawing.
- Planned before writing: Before this reaction, the transcript should establish that the livestream is too soon for A's planned polish and that A had wanted to delay public exposure until key parts worked properly. It should also establish that B sees the invitation as a rare chance for useful player feedback and has urged A not to withdraw the game, making A's concession meaningful rather than enthusiastic.

### sob_gasp_001

Domain: A kitchen plumbing leak threatens a box of irreplaceable family papers stored beneath the sink.  ·  contrast: sob-gasp

1. **A:** That drip under the kitchen sink never stopped. I put Grandma's handwritten recipes in that box in the cabinet because I thought it was protected; they're the family's only originals, and no one can recreate them.
2. **B:** I found the leak at the supply valve, but water has spread across the cabinet floor and soaked the bottom of your box.
3. **A:** [sob]  ← target
4. **B:** If the water got into it, those pages are probably ruined.
5. **A:** Wait—the outer box is drenched, but the recipes were inside this sealed metal tin. The lid held, and the papers are dry.
6. **B:** [gasp]  ← target
7. **A:** Every card is still here, even the one with Grandma's notes in the margins.
8. **B:** Let's move the tin somewhere safe while I shut off the water and call a plumber.

**event_1 — turn 3, A, [sob]**

- Meaning: A is devastated on finding the leak has reached the box containing their late grandmother's handwritten recipes, which A had been carefully keeping as the family's only originals.
- Evidence turns: [1, 2]
- Evidence: A says the persistent sink leak threatens a cabinet box containing their late grandmother's handwritten recipes, which are the family's only originals and cannot be recreated; B then says water has soaked the bottom of that box.
- Planned before writing: Earlier context should establish that A and B are tracing a persistent leak beneath the kitchen sink, that A stored a box of family papers in that cabinet because it seemed protected, and that the handwritten recipes are uniquely important to A because they cannot be replaced or recreated.

**event_2 — turn 6, B, [gasp]**

- Meaning: B reacts with stunned relief when A reveals that the recipes were inside a sealed inner tin, overturning B's assumption that the leak had destroyed the irreplaceable papers.
- Evidence turns: [1, 2, 4, 5]
- Evidence: The earlier turns establish the leak and the irreplaceable original recipes, B says the wet box probably means the pages are ruined, and A then finds that a sealed metal tin inside the soaked box kept the recipes dry.
- Planned before writing: Before this reaction, the transcript should establish the leak, A's distress after seeing the wet outer box, B's belief that the recipes have probably been ruined, and A's subsequent discovery that the soaked box contained a sealed inner container holding the papers.

### gasp_yawn_001

Domain: A couple discussing whether A should keep an inconvenient sleep-medicine appointment after a home monitoring test.  ·  contrast: gasp-yawn

1. **A:** I mailed back that home monitor, but I still think this consultation can wait. Tuesday cuts into the project launch, and the daytime slump is just work stress.
2. **B:** You fell asleep during the playoff game and again while we were talking after dinner, which is not like you. Your primary-care clinician arranged this because it has been happening repeatedly.
3. **A:** [yawn]  ← target
4. **B:** The clinic called this morning after reviewing the monitor. A clinician wants to go over the result this week, so they moved your appointment into an earlier slot.
5. **A:** [gasp]  ← target
6. **B:** I know the launch is important, but they would not have rearranged the schedule if they thought it could simply sit for another month.
7. **A:** All right. I will tell my team I need an hour away and keep the appointment.
8. **B:** Good. We can sort out the work coverage tonight.

**event_1 — turn 3, A, [yawn]**

- Meaning: A inadvertently undercuts their earlier claim that the daytime drowsiness is merely a temporary work-stress problem, signaling reluctant recognition that B's concern about keeping the sleep appointment may be justified.
- Evidence turns: [1, 2]
- Evidence: A says the returned home-monitor follow-up can wait because the daytime slump is only work stress, while B describes A falling asleep during normally engaging activities and says the primary-care clinician arranged the consultation because the pattern is recurring.
- Planned before writing: Earlier context should establish that A wants to postpone or cancel the appointment because it conflicts with work and has minimized the problem as ordinary stress. B should describe a recent pattern of A becoming drowsy during activities where A would normally be alert and engaged, and connect that pattern to why A's primary-care clinician arranged the consultation.

**event_2 — turn 5, A, [gasp]**

- Meaning: A is alarmed when B reveals that the clinic accelerated the appointment after reviewing A's home-monitoring result, overturning A's assumption that the consultation was routine and could safely wait.
- Evidence turns: [1, 4]
- Evidence: A says the home-monitor consultation can wait, but B later reports that the clinic reviewed the monitor, moved the appointment earlier, and wants a clinician to discuss the result that week.
- Planned before writing: Before this reaction, the transcript should establish that A completed and returned a home sleep-monitoring test and initially treated the follow-up as nonurgent. B should then relay that the clinic contacted them with an earlier slot because a clinician wants to review the result promptly, making the changed urgency clear before A reacts.

### grunt_laughter_001

Domain: Two close friends are discussing A's request to postpone helping B assemble a long-delayed bookcase so A can attend a pottery class with someone A has a crush on.  ·  contrast: grunt-laughter

1. **A:** I know I promised tonight after putting you off twice, but Maya invited me to pottery; can we move your bookcase again? I do not want to seem too eager.
2. **B:** [grunt]  ← target
3. **A:** I will stop by the greenhouse next door for a giant monstera, then casually end up in the class.
4. **B:** [laughter]  ← target
5. **A:** All right, it sounds less casual out loud. I will assemble the bookcase Saturday.
6. **B:** Saturday at six. Bring the drill and the missing shelf pins.
7. **A:** Deal. And I may still get the monstera, because it is a good plant.
8. **B:** Of course it is. Just do not make Maya carry it home for you.

**event_1 — turn 2, B, [grunt]**

- Meaning: B signals reluctant irritation at being asked to sacrifice a third planned evening for assembling the bookcase because A wants to chase an unexpected invitation from their crush.
- Evidence turns: [1]
- Evidence: A says B has been put off twice after a promise to help with the bookcase, and asks to postpone again because Maya invited A to pottery.
- Planned before writing: Before this turn, the transcript must establish that B has been waiting for A's promised help with the bookcase, that the task has already been postponed more than once, and that A is now asking to delay it again for the pottery-class invitation.

**event_2 — turn 4, B, [laughter]**

- Meaning: B playfully teases A for insisting that an elaborate plant-shopping cover story will make the pottery-class appearance seem casual, when it instead makes A's effort to impress the crush conspicuously obvious.
- Evidence turns: [1, 3]
- Evidence: A says they do not want to seem too eager about Maya, then proposes buying a giant monstera as a cover for casually ending up at the pottery class.
- Planned before writing: Before this turn, the transcript must establish A's desire to appear casually interested rather than eager around the crush, along with A's overly elaborate plan to arrive at the class under the pretense of shopping for a conspicuous houseplant. The earlier discussion should also make clear that B has heard A worry about seeming too obvious.
