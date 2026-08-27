# Hard task — 8-turn conversations, two vocalization events each

writer/verifier: gpt-5.6-terra · 14 item(s)

Each item was built backward: the ground truth below (target turn, sound, meaning,
evidence) was fixed before any dialogue existed, and the transcript was written to
realize it. The ground truth doubles as the evaluation rubric.

### gasp_laughter_001

Domain: Neighbours discussing repeated obstruction of the shared apartment fire stairwell and how to address it without escalating conflict in the building.  ·  contrast: gasp-laughter

1. **A:** The fire stairwell has been blocked twice this week, and the manager says it has to stay clear.
2. **B:** Then we should report whoever is doing it. Leaving things on an escape route is completely irresponsible.
3. **A:** I checked the security footage from Tuesday. It shows that distinctive blue folding handcart you use beside the stairwell at the relevant time.
4. **B:** [gasp]  ← target
5. **A:** Before we involve the manager, is there something you want to clarify? We can sort it out quietly if it was an accident.
6. **B:** I did leave it there while I carried boxes upstairs. I meant to come straight back for it, but I got distracted.
7. **A:** [laughter]  ← target
8. **B:** All right, I earned that. I will apologize to the manager and make sure it never happens again.

**event_1 — turn 4, B, [gasp]**

- Meaning: B reacts with alarm when A mentions security footage showing the distinctive folding handcart B used, because B realizes the evidence may expose that they were responsible for the obstruction they had just condemned.
- Evidence turns: [1, 2, 3]
- Evidence: A says the fire stairwell has repeatedly been blocked, B strongly urges reporting the responsible person, and A says security footage shows B's distinctive blue folding handcart by the stairwell at the relevant time.
- Planned before writing: Earlier context should establish that residents have repeatedly found the fire stairwell blocked, that B has strongly supported reporting the responsible neighbour, and that A has obtained or reviewed security footage which shows a distinctive folding handcart associated with B near the stairwell at the relevant time.

**event_2 — turn 7, A, [laughter]**

- Meaning: A playfully mocks B after B admits leaving the handcart in the stairwell, highlighting the irony that B had been the most vocal advocate for punishing whoever caused the problem.
- Evidence turns: [1, 2, 3, 6]
- Evidence: The residents are concerned about keeping the fire stairwell clear, B had forcefully called for reporting the offender, A connected the footage to B's handcart, and B admits leaving the cart there while carrying boxes upstairs.
- Planned before writing: Before this reaction, the conversation should establish the building's concern about keeping the shared fire stairwell clear, B's earlier forceful criticism of the unknown offender, A's indication that the footage points toward B's handcart, and B's eventual acknowledgement that they left it there while carrying items upstairs.

### sigh_gasp_001

Domain: Two friends are preparing a handmade tabletop escape-room puzzle as a side project for a library hobby fair.  ·  contrast: sigh-gasp

1. **A:** I finished a self-contained card-deck backup for the fair. It fits in a shoebox, even if it is plainer than your route-changing maze.
2. **B:** I spent three weekends on that maze. Its motor and external battery pack drive the hidden carriage, and the two-panel layout needs far more than a little table.
3. **A:** Mara just confirmed one 30-inch table per project, no outlets or batteries, and every piece has to stay on the tabletop.
4. **B:** [sigh]  ← target
5. **A:** That's all right; I'm genuinely happy with the deck. The book-clue cards are finished, and we can enter them as they are.
6. **B:** I was ready to submit the deck, but the route-changing trick can survive: a thumb wheel beneath a postcard-sized board can advance a hidden paper carriage one notch at a time. No power, no loose equipment, and it fits beside the cards.
7. **A:** [gasp]  ← target
8. **B:** The path can still change only after the right clue, but players will turn the wheel themselves.

**event_1 — turn 4, B, [sigh]**

- Meaning: B reluctantly concedes that the elaborate powered puzzle mechanism they have spent weeks designing cannot be used under the fair’s newly confirmed space and equipment restrictions, and that A’s plainer card-based backup is the only workable entry.
- Evidence turns: [1, 2, 3]
- Evidence: A has completed a compact card-deck backup, while B explains that the maze uses a motor, an external battery pack, and a wide two-panel layout. A then reports the confirmed single-table, no-power, tabletop-only rules.
- Planned before writing: Earlier context must establish that B is personally invested in an ambitious mechanism that needs more table space and external equipment than a simple puzzle would, that A has already prepared a less ambitious self-contained backup, and that the organizer’s confirmed rules rule out the requirements of B’s original design.

**event_2 — turn 7, A, [gasp]**

- Meaning: A is struck by admiration at B’s unexpectedly ingenious redesign: despite having just accepted the modest fallback, B has found a compact manual way to preserve the original puzzle’s central trick within the restrictions.
- Evidence turns: [1, 2, 3, 5, 6]
- Evidence: The earlier turns establish that the powered, wide maze violates the fair rules and that A is already content to enter the completed card deck. B then says B was ready to submit the deck but describes a postcard-sized thumb-wheel redesign that manually preserves the hidden route-changing carriage.
- Planned before writing: Before this event, the transcript must establish the limitations that made B’s original design seem unusable, B’s earlier reluctant acceptance of A’s basic backup, and B’s subsequent description of a genuinely compact, hand-operated redesign that keeps the distinctive mechanism A had understood to be impossible under the fair’s rules. It should also establish that A was already content with the backup, making A’s reaction chiefly appreciation of B’s ingenuity rather than concern about whether they will have an entry.

### sob_gasp_001

Domain: Two housemates sorting donations after a kitchen cleanup accidentally send an irreplaceable family recipe binder away.  ·  contrast: sob-gasp

1. **A:** Please keep the blue recipe binder on the counter; it has my late grandmother's original handwritten recipes, and it's the only copy.
2. **B:** While I was clearing the kitchen, I put everything from the counter into the charity-donation box.
3. **A:** I sealed that box and set it outside for the truck, which is due any minute. Was the binder there?
4. **B:** [gasp]  ← target
5. **A:** I ran outside, but the truck has already collected it. I called the service, and they said the boxes are unloaded together without individual labels.
6. **B:** They checked with the driver and depot, but they cannot identify or pull back one particular sealed box now.
7. **A:** [sob]  ← target
8. **B:** I am so sorry. I should never have put anything from that counter in the donation box.

**event_1 — turn 4, B, [gasp]**

- Meaning: B realizes with alarm that their attempt to clear the kitchen counter has put A's only binder of inherited handwritten recipes into a sealed donation box that is about to be collected.
- Evidence turns: [1, 2, 3]
- Evidence: A explains that the blue binder contains the only originals of their late grandmother's handwritten recipes; B says they put everything from the counter into a charity box; A says that sealed box is outside for an imminent collection and asks whether the binder was in it.
- Planned before writing: Earlier context should establish that the blue recipe binder contains A's late grandmother's original handwritten recipes and is uniquely important to A, that B moved items from the counter into a charity-donation box while tidying, and that A has placed the sealed box outside for an imminent collection.

**event_2 — turn 7, A, [sob]**

- Meaning: A is overwhelmed by the loss of the irreplaceable family binder after learning that the donation collection has already gone and the box cannot be traced or retrieved.
- Evidence turns: [1, 2, 3, 5, 6]
- Evidence: The binder is established as A's only copy of inherited handwritten recipes and as having been moved into the donation box. A then says the truck has already collected the box and the service cannot track individually labeled boxes, while B confirms neither the driver nor depot can identify or retrieve it.
- Planned before writing: Before this reaction, the conversation should establish that B's earlier mistake endangered the sentimental binder, that the charity truck has already collected the donation box, and that attempts to contact the collection service have confirmed there is no practical way to identify or recover that particular box.

### gasp_yawn_001

Domain: Two siblings are trying to secure a specialist assessment appointment before one sibling's referral expires, while evaluating the clinic's proposed paid fast-track program.  ·  contrast: gasp-yawn

1. **A:** I called the clinic about your specialist assessment. I know you have been waiting since November, and the referral expires on the 30th.
2. **B:** Did they find anything before then?
3. **A:** Their first ordinary assessment slot is July 8, nine days after the referral ends.
4. **B:** [gasp]  ← target
5. **A:** They offered a paid fast-track program instead, as though it might solve the timing problem.
6. **B:** I read the details: it is six weeks of generic wellness workshops and phone sessions, and it does not give me an earlier specialist assessment.
7. **A:** [yawn]  ← target
8. **B:** Then we should ask my doctor for a referral extension rather than pay for that.

**event_1 — turn 4, B, [gasp]**

- Meaning: B reacts with alarm when A reports that the clinic's first ordinary assessment slot is after B's referral will expire, threatening the appointment B has been waiting months to obtain.
- Evidence turns: [1, 3]
- Evidence: A says B has waited since November, that the referral expires on the 30th, and that A contacted the clinic; A then reports that the first ordinary slot is nine days after the referral ends.
- Planned before writing: Earlier context should establish that B has waited a long time for this specialist assessment, that the referral has a firm upcoming expiry date, and that A has contacted the clinic to check the available appointment options.

**event_2 — turn 7, A, [yawn]**

- Meaning: A pointedly conveys bored skepticism toward the clinic's paid fast-track orientation after B describes its long, generic wellness curriculum, since the program is being marketed as help with an urgent appointment problem without actually producing an earlier assessment slot.
- Evidence turns: [1, 3, 5, 6]
- Evidence: The referral has an upcoming expiry and no ordinary appointment is available in time. A says the clinic offered a paid fast-track program, while B explains that it consists of six weeks of generic sessions and does not provide an earlier specialist assessment.
- Planned before writing: Before this reaction, the conversation should establish the urgency created by B's expiring referral and lack of regular appointment availability, that the clinic has offered a paid fast-track program as an alternative, and that B has described the program as a lengthy set of generic sessions rather than a route to an earlier specialist assessment.

### laughter_grunt_001

Domain: Two friends trying to secure sold-out concert tickets for a weekend trip they have been planning together.  ·  contrast: laughter-grunt

1. **A:** Every resale listing for Saturday vanished, and this concert was the whole reason we planned the weekend.
2. **B:** I know. Your radio-station contest idea still sounds wildly optimistic; my closing shift Friday runs until midnight, so I cannot spend the night chasing tickets.
3. **A:** Mock my terrible rhyme all you want—the station just emailed: we won the pair.
4. **B:** [laughter]  ← target
5. **A:** There is one catch: the prize desk opens at 5:30 Saturday, and they release unclaimed tickets at six.
6. **B:** Since you championed the contest, please collect both; after that midnight closing shift, I cannot make a dawn trip across town.
7. **A:** [grunt]  ← target
8. **B:** Thanks. I will meet you at the station afterward, and breakfast is on me.

**event_1 — turn 4, B, [laughter]**

- Meaning: B responds with delighted, affectionate disbelief that A's supposedly far-fetched contest entry actually secured the tickets after B had doubted that A's improvised approach could work.
- Evidence turns: [1, 2, 3]
- Evidence: A says the sold-out concert is the reason for their weekend trip, B calls A's radio contest idea wildly optimistic, and A reveals that their rhyme entry won a pair of tickets.
- Planned before writing: Earlier context should establish that the concert is important to both friends, that ordinary ticket options have failed, that A chose an unconventional contest-based route despite B's doubts, and that A has already revealed that the entry succeeded.

**event_2 — turn 7, A, [grunt]**

- Meaning: A begrudgingly accepts B's fair insistence that A handle the unpleasant dawn ticket collection, since A pushed for the contest route and B had made clear that an early pickup would conflict with B's late work shift.
- Evidence turns: [2, 3, 5, 6]
- Evidence: B says a Friday closing shift lasts until midnight, A reveals that A's contest entry won, A explains the tickets must be collected at 5:30 Saturday, and B asks A to collect both tickets because A championed the contest.
- Planned before writing: Earlier context should establish that the prize tickets must be collected at an inconveniently early time, that B has a legitimate late work commitment the night before, that A initiated and defended the contest plan, and that B has asked A to take responsibility for collecting both tickets.

### grunt_sigh_001

Domain: Two co-parents are coordinating their child's last-minute promise to bring allergy-safe baked goods to a school potluck.  ·  contrast: grunt-sigh

1. **A:** I told Leo we'd bring three dozen homemade treats for his 8 a.m. class potluck tomorrow.
2. **B:** Leo's dairy and peanut allergy is serious, so ordinary mixes and icing are out, and I'm covering the evening shift.
3. **A:** It'll be easy—I'll grab a boxed mix and frosting on my way home and make all three dozen tonight.
4. **B:** [grunt]  ← target
5. **A:** I only promised homemade because Leo was so excited to contribute something himself.
6. **B:** The safe shop is sold out until Friday, every grocery mix nearby warns of peanut traces, and I won't be home before midnight.
7. **A:** [sigh]  ← target
8. **B:** I'll message the teacher that Leo can bring paper plates instead of food.

**event_1 — turn 4, B, [grunt]**

- Meaning: B signals skeptical disapproval of A's claim that the potluck contribution will be easy to manage, because A volunteered a large allergy-safe order despite knowing B is unavailable to help and has already warned that ordinary ingredients will not work.
- Evidence turns: [1, 2, 3]
- Evidence: A committed the family to three dozen treats, B stated Leo's serious dairy and peanut allergy and evening-shift unavailability, and A then proposed an overly simple boxed-mix plan.
- Planned before writing: Earlier context should establish that A committed the family to supplying a substantial number of treats, that the child attending has a serious ingredient restriction, and that B had previously made clear they would be working and could not take on last-minute baking. A should present an overly simple plan that overlooks those constraints before B reacts.

**event_2 — turn 7, A, [sigh]**

- Meaning: A reluctantly lets go of the hoped-for homemade contribution after the family’s timing, B's unavailability, and the allergy requirement have made the available shortcuts unsuitable.
- Evidence turns: [1, 2, 5, 6]
- Evidence: A had promised Leo homemade treats and wanted to preserve that promise, while B's work shift, Leo's allergy, sold-out safe shop, and unsafe grocery mixes made the available last-minute options unworkable.
- Planned before writing: Before this reaction, the conversation should establish A's desire to keep the promise made on the child's behalf, B's lack of time to assist, and the practical reasons that the suggested boxed, shop-bought, or hurried alternatives cannot safely meet the dietary requirement or be obtained in time.

### sob_grunt_001

Domain: Two former youth soccer teammates are organizing a retirement reception for their longtime coach.  ·  contrast: sob-grunt

1. **A:** Coach Ramirez's retirement reception is next month. The community room holds sixty, so we need to reserve places for her family and the current varsity squad before inviting alumni.
2. **B:** I still want the old roster included if we can manage it. I disappeared halfway through senior season, and I've always assumed Coach Ramirez saw that as betraying the team.
3. **A:** She didn't. When I said you might stay away, she pulled your captain's note from her desk and told me to make sure you knew she hopes you'll come.
4. **B:** [sob]  ← target
5. **A:** I want it to feel like a reunion too, but we can't use the family and current-team seats for alumni; the room really does stop at sixty.
6. **B:** I understand. I already sent invitations to every former player, though. I thought the more people who came, the better.
7. **A:** [grunt]  ← target
8. **B:** I'll send a follow-up tonight asking everyone to confirm, then we can prioritize the reserved seats.

**event_1 — turn 4, B, [sob]**

- Meaning: B is overcome with relieved gratitude when A reveals that the retiring coach kept B's old captain's note and specifically hopes B will attend, overturning B's fear that abruptly leaving the team years ago had permanently hurt the coach.
- Evidence turns: [1, 2, 3]
- Evidence: A identifies the event as Coach Ramirez's retirement reception; B says they left the team midway through senior season and feared Coach Ramirez felt betrayed; A says the coach kept B's captain's note and hopes B will attend.
- Planned before writing: Earlier context must establish that A and B are planning the coach's reception, that B left the team abruptly and has worried ever since that the coach felt betrayed, and that A has learned the coach preserved a personal note from B and asked that B be included in the event.

**event_2 — turn 7, A, [grunt]**

- Meaning: A conveys exasperated disapproval after B admits to inviting every former player despite A's earlier warning that the booked room has a strict capacity limit and that space must be protected for the coach's family and current team.
- Evidence turns: [1, 2, 5, 6]
- Evidence: A explains that the sixty-person room must preserve places for the coach's family and current squad, while B wants the former roster included. A repeats the restriction, and B then admits to having invited every former player.
- Planned before writing: Earlier context must establish the reception's limited venue capacity, A's explicit concern about reserving places for the coach's family and current players, B's wish to make the reunion feel inclusive, and B's subsequent disclosure that invitations have already been sent to the entire former roster.

### yawn_grunt_001

Domain: Two siblings are shopping for a replacement washing machine after their old one begins leaking, balancing an urgent delivery deadline against a tightly planned household budget.  ·  contrast: yawn-grunt

1. **A:** The washer is leaking across the laundry-room floor, so we need a replacement today, but I promised to keep the total under $700.
2. **B:** This store can deliver, install, and take away the old one tomorrow only if we order the in-stock model before four. Looking at more stores could cost us that window.
3. **A:** I know, but this coupon saves $20, my reward points cover another $15, and the card offer might beat both if I compare the three listings carefully.
4. **B:** [yawn]  ← target
5. **A:** The $620 online listings are tempting, though.
6. **B:** They add $120 for delivery, $90 for installation, and $50 to remove the old machine, and they cannot come until next week. The in-stock $760 package includes all of that tomorrow; should I place the order?
7. **A:** [grunt]  ← target
8. **B:** All right, I’ll submit it now so they can take the old washer away tomorrow.

**event_1 — turn 4, B, [yawn]**

- Meaning: B signals impatient boredom with A's drawn-out coupon and reward-point calculations, implicitly urging A to stop trying to optimize every small saving and make a choice before the needed delivery window closes.
- Evidence turns: [1, 2, 3]
- Evidence: A says the leaking washer requires a replacement today, B explains the before-four cutoff for next-day service, and A delays over several small coupons, points, and card offers.
- Planned before writing: Earlier context should establish that the old machine is unusable and that ordering by a particular cutoff is necessary for prompt delivery. It should also establish that A is determined not to overpay and has begun comparing several minor discounts or loyalty offers, while B has already emphasized that waiting or visiting more stores could sacrifice the practical delivery option.

**event_2 — turn 7, A, [grunt]**

- Meaning: A gives grudging assent to B's recommendation to buy the available machine at the higher displayed price, abandoning A's earlier spending cap because the apparently cheaper alternatives omit essential delivery, installation, or removal costs.
- Evidence turns: [1, 2, 5, 6]
- Evidence: A set a $700 total cap, B identified the immediate in-stock delivery option, and B explains that the cheaper $620 listings add delivery, installation, and removal fees and are delayed until next week, while the $760 package includes those services tomorrow.
- Planned before writing: Before this point, the transcript should establish A's original maximum budget and B's preference for an immediately available model. It should also reveal that the lower advertised options A favored would require extra charges or delays that make them unsuitable for the leaking-machine situation, and that B has presented the in-stock package as the more realistic choice.

### laughter_sigh_001

Domain: Two friends are navigating an unfamiliar coastal city on the final evening of a budget trip, trying to reach their airport before an early flight home.  ·  contrast: laughter-sigh

1. **A:** We have €55 left, so I am not spending €42 on the airport transfer. My ferry, tram, and shuttle combination is €13; I checked every departure, and it still gives us two hours before our early flight.
2. **B:** The direct transfer is simpler, and the stops here are confusing: Harbor Airport is not the airport stop, while Marina Harbor is the tourist waterfront. Are you sure your itinerary has the right one?
3. **A:** Wait—my booking says Marina Harbor, and those souvenir boats are definitely not an airport connection. I must have followed the wrong pin.
4. **B:** [laughter]  ← target
5. **A:** The next cheap shuttle from this harbor will not get us there until 6:15, and our flight boards at 6:40. I was counting on the two-hour buffer, and paying €42 now wrecks the budget.
6. **B:** The direct ride can leave now and should reach the terminal by 5:35. With the ferry and shuttle timing already gone, it is the only dependable option left.
7. **A:** [sigh]  ← target
8. **B:** I have ordered the direct ride. We can sort out the final €42 when we get home; for now, let us get to the terminal.

**event_1 — turn 4, B, [laughter]**

- Meaning: B playfully mocks A’s confidence in the elaborate money-saving route after A dismissed B’s simpler transfer suggestion and the carefully researched itinerary has led them to the tourist harbor rather than the airport connection.
- Evidence turns: [1, 2, 3]
- Evidence: A rejects the €42 direct transfer for a carefully checked €13 multi-service route, B warns that Marina Harbor and the airport stop are easy to confuse, and A then discovers the booking leads to the tourist harbor.
- Planned before writing: Earlier turns should establish that A insisted on combining several cheap local services instead of paying for the straightforward airport transfer, despite B’s warning that the similarly named harbor and airport stops are easy to confuse. They should also establish that A had presented the route as carefully checked and comfortably timed, before A realizes that the booking or map directions point them to the tourist harbor.

**event_2 — turn 7, A, [sigh]**

- Meaning: A reluctantly concedes that B’s costly direct ride is now the sensible choice, because A’s failed bargain route has removed the time buffer A had been relying on and made protecting their early flight more important than preserving the trip budget.
- Evidence turns: [1, 5, 6]
- Evidence: A says the remaining budget is only €55 and initially rejects the direct ride, then explains that the next cheap connection would arrive just before boarding; B states that the direct ride is now the only dependable way to reach the terminal in time.
- Planned before writing: Earlier turns should establish that A has been determined to stay within a tightly planned remaining budget and initially rejected the direct ride as wasteful. After the harbor mistake, the conversation should establish that the next cheap connection would leave too little margin for the early flight, while B explains that the direct ride is the only dependable option still available.

### laughter_sob_001

Domain: Workplace interactions: two coworkers are finalizing a high-stakes client renewal packet before a deadline.  ·  contrast: laughter-sob

1. **A:** The renewal packet is safe in my four-folder archive: drafts, redlines, approvals, and executed copies. With the client deadline at five, nothing can slip through.
2. **B:** I know you trust the color coding, but did we really need four folders for one renewal? I put a copy in the deal room too.
3. **A:** The archive has every draft except the signed version. I was the one who filed it, and if we miss that signature, we could lose the account.
4. **B:** [laughter]  ← target
5. **A:** I told everyone my system made this renewal foolproof; if I misplaced the executed packet, I may have cost the team our biggest client.
6. **B:** Check the deal room: I found a signed scan, and legal says it is the recoverable copy we need.
7. **A:** [sob]  ← target
8. **B:** I’ll upload it now and send the complete packet before five.

**event_1 — turn 4, B, [laughter]**

- Meaning: B playfully deflates A’s boast after A’s elaborate backup system proves to contain the wrong document versions.
- Evidence turns: [1, 2, 3]
- Evidence: A confidently describes a detailed four-folder filing system, B gently questions the need for it, and A then discovers that the archive lacks the signed version.
- Planned before writing: Earlier context should establish that A insisted their detailed filing system made the renewal packet safe, that B had gently questioned the need for it, and that A has just discovered the archive lacks the signed version.

**event_2 — turn 7, A, [sob]**

- Meaning: A is overwhelmed with relief after B confirms the signed renewal was recovered, ending A’s fear of costing the team the account.
- Evidence turns: [1, 3, 5, 6]
- Evidence: The packet has a five o’clock deadline, A says the missing signature could lose the account and fears having cost the team its biggest client, then B finds a signed scan that legal can use.
- Planned before writing: Earlier context should establish that the missing signed packet could jeopardize an important client renewal, that A feels personally responsible for its loss, and that B has confirmed a recoverable copy exists before A reacts.

### yawn_laughter_001

Domain: Two friends are baking a layered cake for a community bake-sale table, with limited time before they must deliver it.  ·  contrast: yawn-laughter

1. **A:** We have two hours before the bake-sale table needs this cake, and my aunt always said her vanilla layers were better after she chose the frosting color to match the napkins.
2. **B:** I volunteered to mix, bake, and wash up, so let's get the bowls moving before the delivery deadline catches us.
3. **A:** Right, but should the piped border be roses or little stars? At the last sale, Mrs. Chen told me a whole story about why roses made her buy an extra slice.
4. **B:** [yawn]  ← target
5. **A:** Fine, practical step first: once the batter is combined, it needs to rest for twenty minutes or the layers will turn rubbery.
6. **B:** Twenty minutes sounded expensive, so I put the bowl in the freezer while you measured. Now the batter is frozen solid around the whisk.
7. **A:** [laughter]  ← target
8. **B:** All right, chef, hand me a spoon and we'll rescue it before we miss the table.

**event_1 — turn 4, B, [yawn]**

- Meaning: B signals impatience with A’s extended stories about the recipe and decoration choices, indirectly pushing A to stop lingering over details and start the time-sensitive preparation.
- Evidence turns: [1, 2, 3]
- Evidence: A says the cake must reach the bake-sale table in two hours, B says they volunteered for practical kitchen work before the deadline, and A keeps discussing decoration details and a related story instead of beginning preparation.
- Planned before writing: Earlier context should establish that the cake must be finished and delivered within a limited window, that B volunteered expecting to help with practical kitchen tasks, and that A has repeatedly diverted from those tasks into lengthy anecdotes or minor design deliberations.

**event_2 — turn 7, A, [laughter]**

- Meaning: A playfully mocks B’s attempt to save time after B dismisses A’s warning about letting the batter rest and reveals that the improvised freezer shortcut has left it in an absurdly unusable state.
- Evidence turns: [5, 6]
- Evidence: A explains that the batter needs a twenty-minute rest to avoid rubbery layers, and B reveals that they ignored the wait by using the freezer, leaving the batter frozen around the whisk.
- Planned before writing: Earlier context should establish that A explained the resting step was necessary for the cake’s texture, that B was already impatient to move faster, and that B chose a shortcut instead of following that instruction before revealing the conspicuously bad result. The friends’ relationship should support gentle teasing rather than anger.

### sigh_sob_001

Domain: Two adult siblings are clearing their late father's workshop while moving their mother from the family house into a smaller apartment.  ·  contrast: sigh-sob

1. **A:** Since Dad died, we've been clearing this workshop, and Mom's move is Friday, so it has to be empty by Thursday night.
2. **B:** I know, but I still want his workbench to stay in the family. He built every cabinet in this house on it; maybe we can get it into Mom's apartment somehow.
3. **A:** I measured the apartment and checked with the superintendent: the elevator door and the hallway turn are too narrow, and there is nowhere to put it once it is inside.
4. **B:** [sigh]  ← target
5. **A:** I'll call the community woodshop, then. They can collect the bench tomorrow and keep it in use.
6. **B:** Wait—there's a false drawer here. It is full of your old cards and drawings, from kindergarten through college, each tucked into a dated envelope. Dad kept every one.
7. **A:** [sob]  ← target
8. **B:** He must have opened this drawer whenever he wanted to see what you were making.

**event_1 — turn 4, B, [sigh]**

- Meaning: B reluctantly accepts that their father's large workbench cannot accompany their mother, after having hoped it could remain in the family despite the apartment's space and access limits.
- Evidence turns: [1, 2, 3]
- Evidence: A sets a Thursday deadline for emptying the late father's workshop before their mother's Friday move. B says they want to keep their father's workbench in the family, while A reports that the apartment's elevator, hallway, and available space cannot accommodate it.
- Planned before writing: Earlier turns should establish that the move has a firm deadline, that B has been especially determined to keep the workbench because of its connection to their father, and that A has checked the new apartment and confirmed that the bench cannot fit through the access route or be accommodated there.

**event_2 — turn 7, A, [sob]**

- Meaning: A is overwhelmed by grief and tender recognition when B reveals that their father had carefully saved A's childhood cards and drawings in the workbench they are about to give away, showing an affection A had not known about.
- Evidence turns: [1, 5, 6]
- Evidence: The siblings are clearing their late father's workshop, and A arranges for the workbench to be collected by the community woodshop. Before it goes, B finds a false drawer containing A's cards and drawings from kindergarten through college, each preserved in a dated envelope.
- Planned before writing: Earlier turns should establish that the siblings are clearing their late father's belongings, that the workbench must be passed on despite B's attachment to it, and that A and B discover a hidden drawer containing A's old cards or drawings that their father preserved over many years.

### sigh_yawn_001

Domain: Two flatmates troubleshooting an aging home Wi-Fi router before one of them needs a stable connection for an important remote job interview.  ·  contrast: sigh-yawn

1. **A:** The connection has dropped on my laptop, both our phones, and the television today. This router is nine years old, and the manufacturer stopped updating it two years ago.
2. **B:** My remote interview is tomorrow morning, and the failures began after we connected the smart television. I think its streaming app is flooding the network.
3. **A:** The television was unplugged this morning, yet my laptop still lost connection twice. I checked the router's status page; it is struggling with every device, not just the TV.
4. **B:** Maybe the television changed a setting before we unplugged it, or it is still trying to reconnect in the background. We could switch channels and avoid buying anything new.
5. **A:** [yawn]  ← target
6. **B:** I still think a factory reset and putting the television on a guest network could carry us through tomorrow.
7. **A:** A reset cannot restore the updates this model no longer receives, and the status page shows repeated failures across devices. There is no dependable free fix before your interview; we need a replacement router.
8. **B:** [sigh]  ← target

**event_1 — turn 5, A, [yawn]**

- Meaning: A conspicuously dismisses B's latest elaborate theory blaming the smart television for the outages, signaling that B is chasing coincidences instead of addressing the ordinary router problem A has already identified.
- Evidence turns: [1, 2, 3, 4]
- Evidence: A establishes that the outages affect several devices and that the old router has not been updated, while B urgently needs internet for an interview and repeatedly attributes the problem to the smart television despite A's test with it unplugged.
- Planned before writing: Earlier context should establish that B urgently needs reliable internet for a remote interview, has repeatedly attributed the failures to a specific device or unusual pattern, and has resisted A's practical diagnosis. It should also establish that the connection drops across multiple devices and that the router is old or no longer properly supported.

**event_2 — turn 8, B, [sigh]**

- Meaning: B reluctantly acknowledges that keeping the router alive with free workarounds is no longer realistic, because the established cross-device failures and lack of support have made A's case for replacing it hard to avoid before the interview.
- Evidence turns: [1, 3, 4, 6, 7]
- Evidence: The connection fails across multiple devices, the router is old and unsupported, and B keeps proposing free settings changes or a reset. A explains that those steps cannot restore support or provide a dependable solution before the interview.
- Planned before writing: Earlier context should establish that B hoped to avoid buying new equipment and believed a simple tweak would carry them through the interview. It should also establish that A has checked the router's status, found evidence that the problem is not limited to the television, and explained that the device's age or support cutoff leaves no dependable repair option.

### sob_yawn_001

Domain: Two friends who volunteer with a local animal rescue are preparing an elderly dog for a meeting with the adult daughter of the dog's former guardian.  ·  contrast: sob-yawn

1. **A:** I've fostered Mabel for six weeks, ever since Mrs. Alvarez had to move into memory care. She has finally started sleeping through the night here, and I promised myself I would not rush her into another upheaval.
2. **B:** Dana is due in twenty minutes. We know Mabel needs slow walks, her arthritis pill in supper, and a quiet room at night, and Dana said her house can manage all of that.
3. **A:** But what if Dana's neighbors have noisy parties, or a delivery truck startles Mabel, or grandchildren visit unexpectedly, or the pill schedule changes when Dana travels? Maybe we should postpone until we can account for every possibility.
4. **B:** [yawn]  ← target
5. **A:** I know I am spiraling. Mabel kept waiting by the door for Mrs. Alvarez during her first weeks here, and I cannot bear the thought of handing her to someone who feels like a stranger.
6. **B:** Dana is not a stranger: she is Mrs. Alvarez's adult daughter. She brought the blue knitted blanket from her mother's armchair, and when she held it out, Mabel pressed her nose into it and started thumping her tail.
7. **A:** [sob]  ← target
8. **B:** Dana is waiting in the garden. Let's bring Mabel out to her slowly.

**event_1 — turn 4, B, [yawn]**

- Meaning: B signals that A's lengthy speculation about every possible adoption problem is becoming unhelpful, gently pushing A to stop rehearsing unlikely worries and focus on the imminent meeting and the dog's known needs.
- Evidence turns: [1, 2, 3]
- Evidence: A explains that Mabel is an elderly foster dog whose placement matters deeply, B says the meeting is imminent and lists Mabel's established needs, and A then raises a string of increasingly hypothetical concerns about Dana's home.
- Planned before writing: Earlier context should establish that A has been carefully fostering the elderly dog and feels responsible for choosing a safe home, that a meeting with a prospective adopter is about to happen, and that A has been repeatedly raising increasingly hypothetical concerns despite B having already summarized the dog's actual routines and needs.

**event_2 — turn 7, A, [sob]**

- Meaning: A is overwhelmed with relief and tenderness after learning that the visitor is the former guardian's daughter and that the dog immediately recognizes something familiar from its old home, making A feel the dog will not be leaving for an unknown future after all.
- Evidence turns: [1, 5, 6]
- Evidence: A says Mabel entered foster care after her longtime guardian moved into memory care, recalls Mabel waiting for that guardian, and worries about placing her with a stranger. B then reveals that Dana is the guardian's adult daughter and that Mabel responds warmly to a familiar blanket from her old home.
- Planned before writing: Earlier context should establish that the dog entered rescue after its longtime guardian could no longer care for it, that A has seen the dog struggle with the disruption and has worried about sending it to a stranger, and that B reveals before this reaction that the visitor is the guardian's daughter and has brought a familiar item or memory to which the dog responds.
