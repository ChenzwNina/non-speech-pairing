# v6 · the reference annotations, for review

Everything the evaluation scores against. One section per item and vocalization condition — 24 items × 2 conditions = 48. The baseline has none of these: with no vocalization there is nothing to interpret, nothing a reply must be appropriate *to*, and no tone that is wrong.

| | written by | used by |
| --- | --- | --- |
| **acceptable interpretations** | claude-opus-5 | test 2 — a model answers in its own words and passes if it matches any of the three |
| **response guides** | claude-opus-5 | test 4 — a reply is scored 1–5 against the guide for the interpretation the model actually held |
| **inappropriate tones** | claude-opus-5 | test 6 — two audio judges are asked only whether any listed tone is present |

Items marked **rev 2** had their transcript rewritten for speaker consistency and their annotations rewritten with it (10 of 24).

---

## v6_01a · condition_a · `laugh` · **rev 2**

**Scenario:** A friend has just brought home a dog of a breed the other speaker has long wanted.

1. **A:** Mara finally brought home a corgi. The exact kind I keep sending you.
2. **B:** Has the puppy settled in at all yet?
3. **A:** Apparently she's already made it through every room in Mara's apartment.
4. **B:** Send me a picture. Oh—Mara just sent me one. Forwarding it now.
5. **A:** (laughs) She's got Mara's slipper in her mouth already.

**Framing the planner intended:** The speaker warmly shares the amusement of the puppy's immediate mischief and celebrates their friend's new pet.

### Acceptable interpretations

1. **Delight at the photo showing the puppy caught mid-mischief, exactly as predicted.** — Signals A has opened the picture and invites B to share the amusement before describing it.
2. **Fond, knowing recognition that the puppy's chaos is already confirming A's running corgi campaign.** — Frames the slipper-chewing as endearing rather than a problem, and lightly vindicates A's earlier pitch.
3. **Affectionate amusement mixed with mock sympathy for Mara, whose apartment is being systematically claimed.** — Softens the report of destruction into a joke both can laugh at rather than a complaint.

*Shared implication (the line a wrong answer crosses):* A finds the puppy's behaviour charming and is sharing that pleasure; the sound is not disapproval, alarm, mockery of B, or awkwardness.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Joins the shared amusement at the photo just opened

- must convey: Reacts with matching amusement to the picture A has evidently just looked at
- must convey: Engages with the specific detail of the puppy holding the slipper
- must avoid: Asking A to send or describe a picture B has already forwarded
- must avoid: Treating the laugh as a topic change or ignoring the photo moment
- example (never a similarity target): *Ha—she got there fast. That slipper never stood a chance.*

**Under interpretation 2** — Laughs along while conceding A's corgi campaign was right

- must convey: Shares the amusement at the puppy's antics
- must convey: Acknowledges A's long-running corgi enthusiasm as vindicated or well-founded
- must avoid: Conceding so heavily that the moment turns into a serious discussion about getting a dog
- must avoid: Reading the slipper-chewing as a warning sign that reflects badly on corgis
- example (never a similarity target): *Okay, you win. You've been right about corgis this whole time and I'm not going to hear the end of it.*

**Under interpretation 3** — Joins the joke with mock sympathy for Mara

- must convey: Shares the amusement rather than treating the chewing as damage
- must convey: Directs playful pity or teasing toward Mara and her belongings
- must avoid: Offering genuine advice about training, chewing, or protecting Mara's things
- must avoid: Sounding concerned or disapproving about the puppy's behaviour
- example (never a similarity target): *Poor Mara. One slipper down, whole apartment to go. She knew what she signed up for, right?*

### Tones that would be clearly wrong

- **Flat, affectless delivery** — sounds like Even pitch, no breath or smile in the voice, businesslike pacing, as if reading an unrelated line aloud.; wrong because Ignores a shared amused moment; leaves the other speaker's laugh hanging with nothing warm returned.
- **Concerned or alarmed** — sounds like Tightened voice, falling worried intonation, sharp intake of breath, urgency as if reacting to bad news.; wrong because Reads a light, fond moment about a puppy as a problem needing sympathy or intervention.
- **Overblown hysterics** — sounds like Loud sustained cackling, gasping, near-shouted delivery, energy far above the other speaker's light laugh.; wrong because Escalates a small domestic joke into something far bigger than the moment carries.
- **Dismissive or bored** — sounds like Clipped, sighing, trailing-off delivery with downward drop, the sound of humoring someone and moving on.; wrong because Treats the other speaker's amusement as tedious when they were inviting shared enjoyment.

*Acceptable range:* Anything from a quiet smiling warmth to an open laugh works, including dry or understated amusement, as long as the delivery stays light and engaged.

---

## v6_01a · condition_b · `sigh` · **rev 2**

**Scenario:** A friend has just brought home a dog of a breed the other speaker has long wanted.

1. **A:** Mara finally brought home a corgi. The exact kind I keep sending you.
2. **B:** Has the puppy settled in at all yet?
3. **A:** Apparently she's already made it through every room in Mara's apartment.
4. **B:** Send me a picture. Oh—Mara just sent me one. Forwarding it now.
5. **A:** (sighs) She's got Mara's slipper in her mouth already.

**Framing the planner intended:** The speaker sees the appealing puppy and dwells on the fact that their friend has the dog they would like to have.

### Acceptable interpretations

1. **Fond exasperation at the puppy's already-predictable mischief** — Frames the slipper as inevitable, endearing chaos and invites shared amusement rather than concern
2. **Rueful acknowledgment that the corgi A kept campaigning for is a handful in practice** — Softly concedes A's own role in the outcome before reporting it, hedging the earlier enthusiasm
3. **Weary sympathy for Mara's belongings, mixed with affection for the dog** — Presents the news as the opening of an ongoing saga, keeping the tone light and knowing

*Shared implication (the line a wrong answer crosses):* A is not disapproving of the dog or reporting a real problem; the enthusiasm stands, only tempered by the mess it entails.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Join the amusement at predictable puppy chaos

- must convey: Treats the slipper as expected puppy behaviour rather than a problem
- must convey: Adds to the shared joke, e.g. predicting what she destroys next
- must avoid: Treating the sigh as a complaint needing sympathy or problem-solving advice
- must avoid: Suggesting the dog is badly behaved or that Mara made a mistake
- example (never a similarity target): *Of course she does. Give it a week and Mara won't own a matching pair of anything.*

**Under interpretation 2** — Tease A gently about their own campaigning, without retracting

- must convey: Links the mischief back to A's enthusiasm for getting this exact breed
- must convey: Keeps the affection intact — the dog is still a good thing
- must avoid: Letting A actually take blame or agreeing the campaign was a mistake
- must avoid: Ignoring A's role and responding as if the news were about strangers
- example (never a similarity target): *You did spend six months lobbying for this specific animal. The slippers are on you, honestly.*

**Under interpretation 3** — Register the slipper as chapter one of a saga

- must convey: Frames this as the first of many casualties in Mara's apartment
- must convey: Signals continued interest in hearing the updates
- must avoid: Turning it into real concern about damage, cost, or training
- must avoid: Closing the topic off as if the story were finished
- example (never a similarity target): *One slipper down. I want a running tally — I assume the couch legs are next.*
- writer's note: Differs from interpretation 1 mainly in scope: forward-looking saga rather than amusement at this one moment.

### Tones that would be clearly wrong

- **Grave concern or alarm** — sounds like Sudden drop in pitch, tightened urgent delivery, worried breath before speaking, as if responding to bad news.; wrong because Reads a light, fond exasperation about a puppy as a distressing event needing crisis handling.
- **Heavy therapeutic sympathy** — sounds like Slow, hushed, over-gentle consoling voice with drawn-out soothing vowels, the register used for genuine grief.; wrong because Treats a mild sigh as real emotional pain, inflating a small domestic complaint into something weighty.
- **Chirpy hyped-up cheer** — sounds like Bouncy, loud, exclamatory delivery with sharp rising pitch and gushing excitement pushed well past the conversation's energy.; wrong because Overshoots the low-key amused register and steamrolls the small weariness the sigh carried.
- **Flat bored disengagement** — sounds like Monotone, clipped, no warmth or lift, trailing off as though the topic barely registered.; wrong because Ignores that the speaker just offered a shared beat of feeling in an otherwise engaged exchange.

*Acceptable range:* Anything from quiet warm amusement to a soft laugh to dry understated commentary works, at conversational energy with some warmth.

---

## v6_01b · condition_a · `laugh` · **rev 2**

**Scenario:** Two friends are checking whether an awaited reimbursement arrived before a utility bill is due.

1. **A:** My electric bill's due today, and I was hoping the reimbursement would clear first.
2. **B:** Has the reimbursement shown up yet?
3. **A:** Not in the app. It still says pending.
4. **B:** Check once more. Transfers sometimes post late in the day.
5. **A:** (laughs) There it is. It cleared for exactly the bill amount.

**Framing the planner intended:** The credit's exact timing and amount seem comically fortunate, making the exchange about an improbable bit of luck.

### Acceptable interpretations

1. **Delight tinged with disbelief at the money arriving exactly when and as needed** — Marks the coincidence as remarkable and concedes B's advice was right
2. **Relief releasing the worry about covering the electric bill** — Signals the problem is resolved before the words confirm it
3. **Wry amusement at how absurdly precise the timing and amount turned out** — Invites B to share the joke about a too-neat outcome

*Shared implication (the line a wrong answer crosses):* The speaker has found the money and the worry is over; the sound is not frustration, bad news, or continued anxiety.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Shares the delight and marks the timing as remarkable

- must convey: Positive reaction to the money landing right when it was needed
- must convey: Acknowledges the exact-amount coincidence as striking or lucky
- must avoid: Gloating over having been right about checking again
- must avoid: Treating the news as routine with no reaction to the coincidence
- example (never a similarity target): *No way, exactly the bill amount? That's some timing. Glad it landed before the due date.*

**Under interpretation 2** — Confirms the worry is over and closes the loop

- must convey: Registers that the bill is now covered and the problem is settled
- must convey: Simple shared relief or good-news reaction on their behalf
- must avoid: Reopening the worry with new questions about timing or whether it'll stick
- must avoid: Dwelling on the coincidence instead of the fact that it's sorted
- example (never a similarity target): *Oh good, that's a load off. So you can pay the electric today and be done with it.*

**Under interpretation 3** — Joins the joke about the absurdly neat outcome

- must convey: Plays along with how suspiciously precise the amount and timing were
- must convey: Signals the situation is fine, just comically tidy
- must avoid: Taking the precision as a literal concern needing explanation or verification
- must avoid: Responding flatly and leaving the offered joke unshared
- example (never a similarity target): *To the cent? Someone's reading your mail. Nice of them to cut it that close, though.*
- writer's note: Differs from 1 in stance: 1 reacts to genuine good fortune, 3 riffs on the too-neat coincidence as a joke.

### Tones that would be clearly wrong

- **Grave, sympathetic concern** — sounds like Slow, hushed, downward-drifting delivery with a consoling softness, as though responding to bad news.; wrong because Reads the laugh as distress when it marks relief at a problem resolving.
- **Flat, disengaged monotone** — sounds like Even pitch, no lift or warmth, clipped pacing — the same voice used to read out a serial number.; wrong because Ignores an audible shift in the other speaker's mood at the moment it lands.
- **Over-the-top celebratory whooping** — sounds like Loud, sustained excitement, exclamatory pitch spikes, cheering energy far above the other speaker's chuckle.; wrong because Overinflates a small piece of mundane good news into a triumph.
- **Smug, told-you-so needling** — sounds like Sing-song lilt, drawn-out stressed syllables, self-satisfied smile audible in the voice, faintly taunting.; wrong because Takes a scoring-points stance the moment does not license; makes the relief about the responder.

*Acceptable range:* Anything from a quiet, warm acknowledgment to a light shared chuckle or mild pleased surprise works, including brief or understated deliveries.

---

## v6_01b · condition_b · `sigh` · **rev 2**

**Scenario:** Two friends are checking whether an awaited reimbursement arrived before a utility bill is due.

1. **A:** My electric bill's due today, and I was hoping the reimbursement would clear first.
2. **B:** Has the reimbursement shown up yet?
3. **A:** Not in the app. It still says pending.
4. **B:** Check once more. Transfers sometimes post late in the day.
5. **A:** (sighs) There it is. It cleared for exactly the bill amount.

**Framing the planner intended:** The credit ends an immediate financial strain, making the exchange about finally getting through a pressing obligation.

### Acceptable interpretations

1. **Relief as held tension releases on seeing the reimbursement finally posted.** — Marks the worry of the last four turns as resolved before delivering the good news.
2. **Weary bracing before looking again, expecting the same 'pending' disappointment.** — Signals reluctant compliance with B's suggestion, setting up the reversal that follows.
3. **Relief mixed with fatigue at living this close to the margin, covered to the dollar.** — Keeps the good news qualified, inviting B to hear strain rather than celebration.

*Shared implication (the line a wrong answer crosses):* The money genuinely mattered and the wait was stressful; the sound is not indifference, not dismissal of B's advice, and not uncomplicated triumph.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Share the relief and confirm the bill is now covered

- must convey: Registers that the money landing is good news and the waiting is over
- must convey: Points to the bill being payable now, closing the original worry
- must avoid: Treating the sigh as bad news or continuing to problem-solve a resolved issue
- must avoid: Taking credit for the suggestion or making the moment about being right
- example (never a similarity target): *Oh good. Told you they post late. Pay it now before anything else moves.*

**Under interpretation 2** — Register the reversal; note the dread was unfounded

- must convey: Acknowledges A expected disappointment and got the opposite
- must convey: Confirms the outcome is good and the checking was worth it
- must avoid: Reading the sigh as continued bad news and commiserating
- must avoid: Scolding A for doubting, or labouring the point that B was right
- example (never a similarity target): *Ha — see? It was just sitting there waiting. Glad you looked again.*

**Under interpretation 3** — Acknowledge good news while recognising the strain behind it

- must convey: Confirms the bill is covered without treating it as an unqualified win
- must convey: Registers that cutting it this fine is wearing, or offers something concrete
- must avoid: Celebrating loudly as if nothing were wrong, flattening the fatigue
- must avoid: Turning into a budgeting lecture or advice A did not ask for
- example (never a similarity target): *Covered, at least. Down to the dollar though — that's a rough way to do it every month. Want me to float you next time?*

### Tones that would be clearly wrong

- **Alarmed, worried concern** — sounds like Tightened, urgent delivery with rising pitch and quickened pace, as if bracing for bad news or checking that something is wrong.; wrong because Reads the sigh as distress when it lands on a resolved worry; treats a released moment as an emergency.
- **Chirpy celebratory over-excitement** — sounds like Loud, bright, bouncing delivery — congratulatory whoop, exclamation-heavy lift, party-announcer energy far above the room's volume.; wrong because Inflates a small mundane relief into a triumph, overshooting the low-key deflation the sigh actually carries.
- **Smug vindication** — sounds like Slow, self-satisfied lilt with a knowing lean on certain words; a little laugh of triumph aimed at the other speaker.; wrong because Turns a shared relief into a scoring moment, taking a superior stance the exchange never licenses.
- **Bored, disengaged flatness** — sounds like Monotone, clipped, energy dropping away mid-phrase, as if reading something unrelated and eager to move on.; wrong because Signals indifference to a moment the other person clearly felt, withholding any acknowledgement the sigh invites.

*Acceptable range:* Anything from a quiet warm exhale of relief to mild pleased amusement or calm matter-of-fact steadiness works; brevity and restraint are fine.

---

## v6_01c · condition_a · `laugh` · **rev 2**

**Scenario:** A frequent Dr. Pepper buyer learns their routine purchases have earned a surprisingly large store reward.

1. **A:** I stopped at the convenience store after work.
2. **B:** Did they scan your rewards account?
3. **A:** Yeah, but the cashier couldn't see my point total.
4. **B:** I just checked it online. You've got enough points for a free case of Dr. Pepper.
5. **A:** (laughs) I'm never stopping drinking Dr. Pepper.

**Framing the planner intended:** The reward makes the speaker’s devotion to the drink feel comically excessive and worth embracing.

### Acceptable interpretations

1. **Delighted, self-aware amusement at how much Dr. Pepper the points total reveals he drinks** — Turns the reward into a joke about his own habit, inviting B to share the punchline
2. **Pleased surprise at the unexpected payoff for something he was already doing anyway** — Registers the good news warmly and rewards B for having looked it up
3. **Amused mock-defiance, half-joking about a habit he knows is excessive** — Pre-empts any teasing by owning the excess before B can point it out

*Shared implication (the line a wrong answer crosses):* The speaker welcomes the news and treats his own consumption as funny; he is not annoyed, embarrassed, dismissive, or regretful about the habit or B's checking.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Joins the joke about how much he drinks

- must convey: Plays along with the punchline that the points reveal his Dr. Pepper volume
- must convey: Treats the free case as fuel for the running joke, not a concern
- must avoid: Moralising about soda intake or suggesting he cut back
- must avoid: Answering only with logistics of redeeming the points, ignoring the joke
- example (never a similarity target): *Those points didn't come from nowhere, you know. The machine has been keeping score.*

**Under interpretation 2** — Shares his pleasure at the payoff and confirms it

- must convey: Warm agreement that it's a good deal for something he'd do anyway
- must convey: Something concrete about the reward — that it's real, or how to claim it
- must avoid: Teasing him about the size of the habit rather than celebrating the win
- must avoid: Undercutting the news with caveats, doubts, or fine print
- example (never a similarity target): *Right? Free case just for buying what you already buy. I can pull it up again if you want the barcode.*
- writer's note: Differs from 1 by centring the good news rather than his habit.

**Under interpretation 3** — Accepts the owned excess without piling on

- must convey: Lets the self-deprecation stand rather than confirming the habit is a problem
- must convey: Signals he's not being judged — teasing, if any, stays affectionate
- must avoid: Actually scolding him or agreeing that he drinks too much
- must avoid: Reassuring earnestly as if he'd confessed something he feels bad about
- example (never a similarity target): *Nobody was going to say anything. Enjoy your case, you've clearly earned it fair and square.*

### Tones that would be clearly wrong

- **Flat clinical neutrality** — sounds like Even, unvaried delivery with no warmth or lift, as if reading out an account balance to a stranger.; wrong because Ignores that the other speaker just laughed at a shared joke; leaves the offered amusement completely unmet.
- **Concerned or cautioning gravity** — sounds like Slowed, lowered, careful delivery with a worried edge, the sound of raising a health or habit problem.; wrong because Treats a light throwaway quip as a confession needing sober response, souring an easy moment.
- **Manic over-excitement** — sounds like Loud, fast, high-energy exclaiming with game-show enthusiasm, far bigger than the small laugh that preceded it.; wrong because Wildly overshoots the low-stakes register of a joke about convenience-store reward points.
- **Dismissive or exasperated flatness** — sounds like Clipped, sighing, or eye-roll delivery with a downward drop, as if the other person is tiresome.; wrong because Takes a judgmental stance the moment does not license; the laugh invited shared amusement, not correction.

*Acceptable range:* Anything from a quiet warm smile in the voice to an audible chuckle, or dry deadpan amusement, works fine here.

---

## v6_01c · condition_b · `sigh` · **rev 2**

**Scenario:** A frequent Dr. Pepper buyer learns their routine purchases have earned a surprisingly large store reward.

1. **A:** I stopped at the convenience store after work.
2. **B:** Did they scan your rewards account?
3. **A:** Yeah, but the cashier couldn't see my point total.
4. **B:** I just checked it online. You've got enough points for a free case of Dr. Pepper.
5. **A:** (sighs) I'm never stopping drinking Dr. Pepper.

**Framing the planner intended:** The reward confirms a habit the speaker recognizes as hard to escape, despite seeing its scale.

### Acceptable interpretations

1. **Rueful self-recognition that the reward proves how much Dr. Pepper he drinks.** — Frames the good news as evidence of a habit he can't escape, softening the admission.
2. **Mock defeat at being pulled deeper into a habit he half-jokingly wanted to quit.** — Plays up surrender for comic effect, inviting B to share the joke.
3. **Pleased resignation — happy about the free case while conceding the habit is permanent.** — Accepts B's news while wryly hedging the enthusiasm as inevitability rather than choice.

*Shared implication (the line a wrong answer crosses):* The speaker is not annoyed at B or rejecting the news; he wryly concedes his own Dr. Pepper habit is entrenched and now reinforced.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Acknowledge the self-recognition lightly, treating the habit as familiar

- must convey: Registers that the points total is proof of how much he drinks
- must convey: Takes the admission in stride, as something already known between them
- must avoid: Turning it into concern about sugar, health, or suggesting he cut back
- must avoid: Treating the sigh as distress that needs comfort or a wellbeing check
- example (never a similarity target): *The points don't lie. That's a lot of trips to the cooler aisle.*
- writer's note: Centers on the admission itself; contrast with guide 3, which keeps the free case in play.

**Under interpretation 2** — Join the joke and play along with the mock surrender

- must convey: Treats the surrender as a bit rather than a real wish to quit
- must convey: Adds something of B's own — a tease or escalation of the premise
- must avoid: Responding earnestly as though he wants to quit and needs encouragement
- must avoid: Bare acknowledgement of the news that leaves the joke unreturned
- example (never a similarity target): *Resistance is futile. They've got you on a payment plan now — one free case at a time.*

**Under interpretation 3** — Accept the concession and move the free case forward

- must convey: Keeps the reward practical — how, when, or where he'd claim it
- must convey: Lets the habit stand as settled rather than arguing he could quit
- must avoid: Dropping the free case entirely to dwell on the habit
- must avoid: Insisting he could stop if he wanted, or nudging him to try
- example (never a similarity target): *Might as well cash it in, then. It's sitting on the account — just tell them at the register.*
- writer's note: Differs from guide 1 by advancing B's news rather than responding to the admission.

### Tones that would be clearly wrong

- **Grave concern, solemn worry** — sounds like Slowed, hushed delivery with careful soft landings, weighted pauses, the register used for bad news or an intervention.; wrong because Treats a wry sigh of comic resignation as genuine distress, inflating a throwaway joke into a serious problem.
- **Chirpy upbeat cheerleading** — sounds like Bright bouncy pitch, exclamatory lift, game-show or salesperson brightness, energy pushed well above the other speaker's.; wrong because Overshoots the low-key deflated humor, steamrolling the resigned mood with enthusiasm the moment never reached.
- **Patronising disapproval or scolding** — sounds like Sing-song tutting cadence, drawn-out chiding vowels, downward finger-wagging emphasis as if correcting a child.; wrong because Takes a superior corrective stance the exchange does not license; A was joking at their own expense, not confessing.
- **Flat bored dismissal** — sounds like Clipped monotone, no inflection shift, trailing off as though barely listening or ready to end the exchange.; wrong because Withholds any acknowledgment of the sigh's rueful humor, reading as disengagement from a shared joke.

*Acceptable range:* Anything from a soft amused chuckle to dry deadpan to quiet warm agreement works; low energy and understatement are fine here.

---

## v6_01d · condition_a · `laugh`

**Scenario:** Two companions are shopping when one is directed to an item near a low shelf in the aisle.

1. **A:** I can't find the tea filters anywhere.
2. **B:** I saw them in the next aisle, I think.
3. **A:** I've looked all along this side.
4. **B:** They're behind you, down there beside that low shelf.
5. **A:** (laughs) Of course they're right next to the shelf.

**Framing the planner intended:** The stumble becomes an absurd, mildly embarrassing interruption that the shopper treats as a joke.

### Acceptable interpretations

1. **Amused at the absurdity of having searched past the filters sitting in plain view** — Concedes B was right while framing the miss as comic rather than incompetent
2. **Mild self-directed embarrassment at insisting she had looked everywhere** — Softens the climb-down from her own confident claim in turn 3
3. **Wry exasperation at store layout that hides things in obvious-in-hindsight places** — Shifts the blame outward to the shelving while accepting B's correction

*Shared implication (the line a wrong answer crosses):* The speaker accepts that the filters have been found where B said; the sound is not disbelief, refusal, or continued searching.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Joins the joke about the hidden-in-plain-sight find

- must convey: Shares the amusement at how the filters sat in plain view the whole time
- must convey: Treats the search as over and the filters as found
- must avoid: Claiming vindication or pointing out that B said so first
- must avoid: Restarting directions or re-explaining where the filters are
- example (never a similarity target): *Right there the whole time, staring at you. Grab a couple while you're down there.*

**Under interpretation 2** — Waves off the climb-down and moves on lightly

- must convey: Makes the miss unremarkable — easy to walk past, no fault involved
- must convey: Keeps the moment moving rather than dwelling on the earlier claim
- must avoid: Teasing about the confident 'I've looked all along this side' claim
- must avoid: Heavy reassurance that treats a small miss as something needing comfort
- example (never a similarity target): *That bottom shelf swallows everything. I only spotted them because I dropped my list.*

**Under interpretation 3** — Agrees the shelving is at fault and closes the errand

- must convey: Endorses the complaint about the store's layout or low-shelf placement
- must convey: Confirms these are the right filters so they can move on
- must avoid: Defending the store or implying she simply overlooked them
- must avoid: Only grumbling about the layout without settling that the item is found
- example (never a similarity target): *Whoever stocks this place hides everything at ankle height. Are those the ones you wanted?*

### Tones that would be clearly wrong

- **Flat clinical delivery** — sounds like Even, unvarying pitch with no lift or breath of warmth; the pace of reading out a location.; wrong because Ignores that the other speaker just laughed at themselves; leaves a shared light moment unacknowledged in the voice.
- **Smug, told-you-so gloating** — sounds like Drawn-out, descending emphasis with a hard edge on the vowels; a laugh aimed at the other person, not with them.; wrong because Turns self-directed amusement into scoring a point; the moment licenses shared humour, not triumph.
- **Concerned or reassuring softness** — sounds like Hushed, slowed, gentle downward delivery, as if consoling someone who is upset or embarrassed.; wrong because Misreads a laugh as distress; treats a trivial supermarket mix-up as something needing comfort.
- **Overblown hilarity** — sounds like Loud, extended laughing that swamps the words, breathless and escalating well past what preceded it.; wrong because Vastly overshoots the intensity of a small wry laugh; makes a minor moment into a punchline.

*Acceptable range:* Anything from a brief dry warmth to a short answering chuckle works; quiet, matter-of-fact delivery with a hint of lightness is fine.

---

## v6_01d · condition_b · `sigh`

**Scenario:** Two companions are shopping when one is directed to an item near a low shelf in the aisle.

1. **A:** I can't find the tea filters anywhere.
2. **B:** I saw them in the next aisle, I think.
3. **A:** I've looked all along this side.
4. **B:** They're behind you, down there beside that low shelf.
5. **A:** (sighs) Of course they're right next to the shelf.

**Framing the planner intended:** The stumble makes the shopping trip feel like another needless obstacle created by an awkward aisle layout.

### Acceptable interpretations

1. **Mild self-directed exasperation at having missed something that was in plain sight behind her.** — Concedes B was right while softening the admission into a shared joke about her own searching.
2. **Weary irritation at the store's layout for stocking filters in an unguessable spot.** — Redirects blame away from her own search onto the shelving, pre-empting any 'you didn't look' reply.
3. **Deflated relief at the search ending, mixed with annoyance at how long it took.** — Closes the search out loud and signals no further help is needed.

*Shared implication (the line a wrong answer crosses):* The speaker accepts the filters have been found and is not disputing B, doubting the location, or expressing anger at B.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Take the shared joke without rubbing in being right

- must convey: Treats her missing them as an easy, ordinary thing to miss
- must convey: Stays light rather than correcting or re-explaining where they are
- must avoid: Saying I told you so, or restating that they were behind her all along
- must avoid: Turning it serious with reassurance about her attention or eyesight
- example (never a similarity target): *They blend right into that shelf. I only spotted them because I walked past twice.*

**Under interpretation 2** — Agree the placement is absurd, siding with her

- must convey: Endorses that filters belong somewhere more findable than a low shelf
- must convey: Signals no blame for how she searched
- must avoid: Defending the store or implying she should have checked lower
- must avoid: Making her the joke instead of the shelving
- example (never a similarity target): *Who puts tea filters down by the floor? Nobody's finding those on purpose.*

**Under interpretation 3** — Close the search out and move on to what's next

- must convey: Registers the search is over and nothing more is needed
- must convey: Points forward — grabbing them, the rest of the list, leaving
- must avoid: Reopening the search with more directions or offers to look
- must avoid: Dwelling on how long it took or who was right
- example (never a similarity target): *Grab a box and we're done. Anything else on the list, or is that it?*

### Tones that would be clearly wrong

- **Triumphant vindication** — sounds like Bright rising lilt, emphatic stress on the reply, an audible smile or laugh of self-satisfaction.; wrong because Turns A's mild self-directed exasperation into B scoring a point, a stance the moment does not license.
- **Alarmed concern** — sounds like Tightened, urgent voice, sudden gravity, careful softness as if consoling someone genuinely upset.; wrong because Treats a small shopping annoyance as distress, badly overshooting the low intensity of the sigh.
- **Patronising soothing** — sounds like Slowed, singsong, over-gentle delivery with cooing warmth, as if speaking to a child.; wrong because Takes a caretaking stance over a competent adult who merely sighed at a shelf.
- **Clipped irritation** — sounds like Flat hard consonants, curt cutoff, cold or exasperated edge directed outward at A.; wrong because Reads the sigh as aimed at B and answers with friction the exchange never had.

*Acceptable range:* Anything from dry amusement to plain matter-of-fact helpfulness to a light commiserating exhale works, at low, unhurried intensity.

---

## v6_02a · condition_a · `laugh`

**Scenario:** A long-term psychiatric patient is struggling with an increasingly unreliable regimen while awaiting a coverage decision for a change.

1. **A:** My current medication's getting less reliable. My prescriber wants to switch me.
2. **B:** Has the clinic heard back about the coverage request?
3. **A:** They sent it in last week, but my portal still hasn't shown a decision.
4. **B:** I'm here. Refresh it while we're on the phone.
5. **A:** (laughs) It just posted. The covered replacement is the medication I stopped years ago.

**Framing the planner intended:** The decision reads as a bleakly absurd bureaucratic loop: after decades of treatment, the system offers a medication that already failed.

### Acceptable interpretations

1. **Wry disbelief at the absurd outcome — the approved drug is one already known to fail.** — Marks the news as ironic, cueing B to hear it as bad rather than good.
2. **Frustration and dismay at being sent backwards after a week of waiting.** — Vents exasperation while keeping the delivery light enough to avoid burdening B.
3. **Bleak, tired amusement mixed with resignation about a system that ignores her history.** — Softens the disappointment as she reports it, inviting shared recognition of the futility.

*Shared implication (the line a wrong answer crosses):* The speaker treats the coverage decision as a bad, useless outcome; the sound is not relief, delight, or genuine good news about the approval.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Register the irony and confirm the approval is worthless

- must convey: Treats the decision as bad news, not a win, matching A's ironic framing
- must convey: Names the absurdity that the covered drug is one A already failed on
- must avoid: Congratulating A or treating the posted approval as progress worth celebrating
- must avoid: Jumping straight to logistics without acknowledging the outcome is backwards
- example (never a similarity target): *Of course that's the one they approved. A week of waiting to be told to take the thing that already didn't work.*

**Under interpretation 2** — Absorb the frustration and turn toward a concrete next move

- must convey: Validates that a week of waiting for this result is genuinely infuriating
- must convey: Offers something actionable — appeal, calling the prescriber, documenting the prior failure
- must avoid: Treating the laugh as amusement and matching it with a joke instead of taking the setback seriously
- must avoid: Minimising with silver linings like at least there's coverage or worth another try
- example (never a similarity target): *A whole week for that? Ugh. Your prescriber can file an appeal with the history — you already have documentation that it failed.*

**Under interpretation 3** — Share the tired recognition that the system ignored her history

- must convey: Acknowledges the futility that A's documented history apparently counted for nothing
- must convey: Stays alongside A in the resignation rather than arguing her out of it
- must avoid: Immediately problem-solving over the moment A is inviting her to sit in
- must avoid: Reassuring that the system will get it right or that it will work out
- example (never a similarity target): *It's like none of your record exists to them. You've been on this drug already and they just... sent you back to the start.*
- writer's note: Differs from 2 by staying with A rather than mobilising; differs from 1 by shared weariness over sharp irony.

### Tones that would be clearly wrong

- **Bright delighted amusement** — sounds like Buoyant, grinning delivery with an upward lilt and a genuine chuckle, as if enjoying a funny story together.; wrong because Treats a rueful laugh at bad news as shared fun, missing that the underlying valence is frustration.
- **Alarmed, urgent concern** — sounds like Tightened, faster speech, breathy sharp intake, pitch pushed up, the register used for emergencies.; wrong because Escalates far past what the speaker signalled; their laugh deliberately kept the moment low-key.
- **Flat clinical detachment** — sounds like Even, affectless recitation with no warmth or shift in energy, like reading a form aloud.; wrong because Ignores that the laugh was an emotional bid; blank delivery reads as not registering it at all.
- **Patronising soothing coo** — sounds like Softened, slowed, sing-song comforting voice with drawn-out sympathetic vowels, pitched as if to someone fragile.; wrong because Takes a caretaking stance the speaker's dry laugh did not invite, recasting wry adults as distressed.

*Acceptable range:* Dry wry amusement, a brief exhaled laugh, quiet exasperation, or plain steady warmth all work; brief and understated is as fine as expressive.

---

## v6_02a · condition_b · `gasp`

**Scenario:** A long-term psychiatric patient is struggling with an increasingly unreliable regimen while awaiting a coverage decision for a change.

1. **A:** My current medication's getting less reliable. My prescriber wants to switch me.
2. **B:** Has the clinic heard back about the coverage request?
3. **A:** They sent it in last week, but my portal still hasn't shown a decision.
4. **B:** I'm here. Refresh it while we're on the phone.
5. **A:** (gasps) It just posted. The covered replacement is the medication I stopped years ago.

**Framing the planner intended:** The decision reads as an alarming immediate setback, threatening continuity just as the current regimen is becoming less effective.

### Acceptable interpretations

1. **Dismay at seeing the approved substitute is a drug she already abandoned years ago** — Flags the result as bad news before the words arrive, cueing B to brace
2. **Startled surprise that the decision appeared the instant she refreshed** — Marks the update as breaking news and pulls B into the moment of reading it
3. **Shock at the outcome mixed with relief that the long wait finally ended** — Signals the news is significant and consequential without yet settling whether it is good

*Shared implication (the line a wrong answer crosses):* The speaker is genuinely caught off guard by what the portal shows; she is not indifferent, joking, or performing surprise at an expected result.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Register the bad news and steady her toward next steps

- must convey: Recognition that this specific drug being the covered option is a real problem for her
- must convey: Something concrete to do about it — appeal, call the prescriber, ask for an exception
- must avoid: Treating the approval as good news or urging her to just try it again
- must avoid: Leaving her alone with it — sympathy only, nothing actionable or forward-looking
- example (never a similarity target): *Oh no, not that one. Okay — the prescriber can request an exception; you've got documented history with it. Can you message them today?*

**Under interpretation 2** — Match the moment, then ask what the decision actually says

- must convey: Acknowledgement that the decision has finally landed after the wait
- must convey: A request for detail about what is on the screen or what it means for her
- must avoid: Assuming the outcome is bad and jumping to appeals before she has said more
- must avoid: Ignoring that something just changed and continuing the earlier discussion
- example (never a similarity target): *Wait, it's up? What does it actually say — is that the only thing they'll cover, or is there a list?*
- writer's note: Differs from 1 and 3 in staying at the arrival of the news rather than its content.

**Under interpretation 3** — Acknowledge the wait ending while taking the outcome seriously

- must convey: Relief or acknowledgement that the limbo is over and there is finally an answer
- must convey: Recognition that the particular drug named is a complication, not a settled resolution
- must avoid: Congratulating her as if approval alone solves it
- must avoid: Framing it as purely bad and erasing that the stall finally broke
- example (never a similarity target): *At least they finally answered. But that one — you came off it for a reason. Is there room to push back now that there's a decision to argue with?*

### Tones that would be clearly wrong

- **Bright celebratory congratulation** — sounds like Upward, buoyant delivery with a smile in the voice, quick excited pickup, as though good news just landed.; wrong because Treats the gasp as delight when it reads as a jolt at an unwelcome result; misreads the valence.
- **Flat unaffected neutrality** — sounds like Even, level, administrative reading with no lift or catch, same pacing as a routine status update.; wrong because Registers nothing at a moment the gasp marks as sudden and consequential, sounding unconnected to her reaction.
- **Alarmed escalation** — sounds like Sharp intake, raised and tightened voice, urgent quickened speech, audibly more rattled than the person who gasped.; wrong because Overshoots the moment and hands the distress back to her when she was steadying herself with someone present.
- **Patronising soothing coo** — sounds like Slow, sing-song, over-soft comforting delivery with drawn-out vowels, the voice used with a distressed child.; wrong because Takes a caretaking stance above her that this exchange between equals on a phone call does not license.

*Acceptable range:* Anything from a quiet caught-breath softening to an alert, engaged pickup works, so long as it stays level with her and takes the news seriously.

---

## v6_02b · condition_a · `laugh`

**Scenario:** Two people uncover a recording of the final speaker playing catch with their father in their old yard.

1. **A:** I found this unlabeled tape in the box with the old family files.
2. **B:** Could it be the old house? Or the backyard?
3. **A:** I just started it. That's you, and there's your dad by the fence.
4. **B:** They're playing catch now. Hold on—let it keep going.
5. **A:** (laughs) The ball just came straight into the camera. Dad threw it right at whoever was filming.

**Framing the planner intended:** The recovered clip turns a cherished memory into a warmly funny glimpse of the father's playful, clumsy throw.

### Acceptable interpretations

1. **Delighted surprise at the ball flying straight at the camera on the old tape** — Flags the moment as the funny payoff worth watching, inviting B to share the amusement
2. **Warm affection toward B's dad, entertained by his careless throw at the filmer** — Colors the found footage as fond family comedy rather than a solemn keepsake
3. **Amused startlement at the sudden intrusion, before narrating what actually happened** — Marks the on-screen event as unexpected and previews the explanation the next sentence gives

*Shared implication (the line a wrong answer crosses):* A pleasurable reaction to something funny on the tape; not distress, not mockery of B or his dad, and not discomfort about the recording.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Joins the amusement and keeps watching for more

- must convey: Shares the laugh at the ball hitting the camera
- must convey: Signals wanting the tape to keep playing or rewound for that bit
- must avoid: Treating the moment as concerning, or worrying about the camera or filmer
- must avoid: Shifting to solemn reflection about the tape instead of enjoying the moment
- example (never a similarity target): *Ha! Right in the lens. Back it up a few seconds, I want to see that again.*

**Under interpretation 2** — Joins humour by affectionately characterizing his dad

- must convey: Fond amusement directed at his dad, treating the throw as typical of him
- must convey: Adds or confirms something about his dad rather than only about the footage
- must avoid: Making his dad look bad or defending him as if criticized
- must avoid: Keeping it purely about the camera moment with no warmth toward his dad
- example (never a similarity target): *That's Dad exactly — no idea where anything was going. He did that to me constantly.*

**Under interpretation 3** — Reacts to the surprise and takes up the narration

- must convey: Registers the moment as sudden or unexpected on screen
- must convey: Asks about or comments on what happened next, or who was filming
- must avoid: Reading the laugh as being about his dad's character rather than the surprise
- must avoid: Treating the jolt as genuine alarm about someone being hurt
- example (never a similarity target): *Whoa, out of nowhere. Did whoever was holding it drop the thing? Who even was behind the camera?*

### Tones that would be clearly wrong

- **Alarmed or concerned** — sounds like Sharp intake, raised urgent pitch, clipped worried delivery as if something bad just happened.; wrong because Treats a funny old home-video moment as a mishap; misreads the laugh's clearly positive valence.
- **Flat, disengaged monotone** — sounds like Even pitch, no warmth or lift, delivered like reading an unrelated line aloud.; wrong because Ignores a shared laugh mid-discovery; reads as not listening to a moment B was leaning into.
- **Overblown hysterical hype** — sounds like Shouted, wheezing, sustained cackling far past the moment, theatrical exclamations at top volume.; wrong because Wildly overshoots a light chuckle at a small funny beat in a quiet shared viewing.
- **Patronising or dismissive** — sounds like Indulgent sing-song, sighing 'mm-hm', slight sneer or clipped brush-off as if humouring someone.; wrong because Takes a superior stance toward a person sharing amusement about their own family footage.

*Acceptable range:* Anything from a quiet amused exhale to a warm full laugh works, including calm affectionate delivery with no laugh at all.

---

## v6_02b · condition_b · `gasp`

**Scenario:** Two people uncover a recording of the final speaker playing catch with their father in their old yard.

1. **A:** I found this unlabeled tape in the box with the old family files.
2. **B:** Could it be the old house? Or the backyard?
3. **A:** I just started it. That's you, and there's your dad by the fence.
4. **B:** They're playing catch now. Hold on—let it keep going.
5. **A:** (gasps) The ball just came straight into the camera. Dad threw it right at whoever was filming.

**Framing the planner intended:** The recovered clip becomes an abrupt, startling encounter with an unexpectedly vivid moment from the speaker's past.

### Acceptable interpretations

1. **Startled by the ball flying at the lens, reacting as if it were coming at her now** — Marks the on-tape moment as the surprise worth noticing and cues B to look
2. **Delighted shock at catching an unexpectedly vivid, funny moment preserved on the old tape** — Flags the find as a discovery, inviting B to share the excitement
3. **Startled and moved, dawning realization about the unseen person holding the camera** — Halts the running commentary and hands the significance of the moment to B

*Shared implication (the line a wrong answer crosses):* The vocalization registers something abrupt and unanticipated on the tape as significant; it is not boredom, confusion about what she sees, or mere narration.

### What speaker B should reply, per interpretation

**Under interpretation 1** — React to the near-miss on screen, look immediately

- must convey: Registers the ball coming at the lens as the startling thing just seen
- must convey: Keeps attention on the tape — rewind, replay, or watch what happens next
- must avoid: Treating A as actually in danger or asking if she got hit
- must avoid: Shifting to who was behind the camera or what it means
- example (never a similarity target): *Whoa—did it hit the lens? Back it up ten seconds, I want to see that again.*

**Under interpretation 2** — Share the delight, treat the moment as a find

- must convey: Enjoys how good or funny the caught moment is
- must convey: Adds something of her own — memory of Dad's throwing, or wanting to keep/show it
- must avoid: Sombre or reverent framing that drains the fun out of it
- must avoid: Flat acknowledgement that doesn't take up the excitement
- example (never a similarity target): *That is so him. He could never resist. We're saving that bit—Mum has to see it.*

**Under interpretation 3** — Take up the realization about who held the camera

- must convey: Engages with the unseen person filming — who it was, or that it was likely Mum
- must convey: Gives the moment weight rather than moving straight on
- must avoid: Playing it as a funny clip or joking about the throw
- must avoid: Narrating more on-screen action as if nothing shifted
- example (never a similarity target): *So someone was standing right there. That's Mum holding it, isn't it. Pause it a second.*
- writer's note: Distinct from 1: 1 stays with the on-screen event, 3 moves to the person off-screen.

### Tones that would be clearly wrong

- **Flat, uninflected recitation** — sounds like Even pacing, no pitch movement or breath change, the same delivery as reading a list aloud.; wrong because Ignores that the other person just startled at something on the tape; leaves the shared surprise unacknowledged.
- **Alarmed, emergency-pitched panic** — sounds like Sharp intake, rising strained voice, urgent clipped words as though something dangerous is happening now.; wrong because Treats a startling moment in old home footage as a present-tense threat rather than a surprise on screen.
- **Bored dismissiveness** — sounds like Sighing, trailing-off delivery, downward drag on the words, audible so-what shrug in the voice.; wrong because Brushes off a reaction to family footage the responder is personally in, treating the moment as uninteresting.
- **Chirpy presenter brightness** — sounds like Bouncy singsong lift, wide smiling resonance, upbeat cadence like narrating a promo or game show.; wrong because Performs cheer at a private, absorbed moment of watching old footage, overshooting the intimacy of the exchange.

*Acceptable range:* Anything from a hushed absorbed murmur to a startled laugh or quick delighted exclamation works, as does quiet leaning-in curiosity.

---

## v6_02c · condition_a · `laugh` · **rev 2**

**Scenario:** A friend helps someone who once imagined many careers check a newly reopened job listing.

1. **A:** Have you settled on any applications yet?
2. **B:** I used to picture myself doing everything—teaching, design, even park work.
3. **A:** What do you need from a job now?
4. **B:** Enough to cover rent, and something that starts soon. I found the library assistant listing again—refresh the link I just sent you.
5. **A:** (laughs) It says twenty-two an hour, and they need someone Monday.

**Framing the planner intended:** The opening feels comically apt: after an expansive list of ambitions, an ordinary available position suddenly becomes exactly the relevant answer.

### Acceptable interpretations

1. **Delighted surprise that the listing actually meets both of B's stated conditions.** — Endorses the job as a real option and hands B the good news warmly.
2. **Amused disbelief at how exactly the pay and start date answer what B just said.** — Frames the fit as almost comically on-the-nose before reciting it as evidence.
3. **Pleased but slightly startled by how abruptly soon 'Monday' is.** — Softens the delivery while flagging the timeline as the thing B must now decide about.

*Shared implication (the line a wrong answer crosses):* The speaker is reacting to how aptly and abruptly the listing's terms fit B's needs, not mocking B's ambitions or dismissing the job.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Shares the good news and treats the listing as viable

- must convey: Registers that the pay and timing meet what B said they needed
- must convey: Moves toward acting on it — applying, checking details, or saying they'll take it
- must avoid: Hedging or downplaying the fit as if the numbers were disappointing
- must avoid: Treating A's laugh as mockery of B's earlier ambitions
- example (never a similarity target): *Wait, twenty-two? That's more than I expected. Okay, I'm applying tonight — can you send me the link again so I don't lose it?*

**Under interpretation 2** — Joins the joke about how absurdly well it matches

- must convey: Plays along with the comic neatness of the listing answering B's exact conditions
- must convey: Still accepts the terms as real information, not just a bit
- must avoid: Responding only earnestly with no uptake of the shared amusement
- must avoid: Turning the joke self-deprecating, as if the fit were too good to trust
- example (never a similarity target): *Did I write that listing in my sleep? Rent money, starts Monday — it's like it was reading over my shoulder. Fine, I'm applying.*
- writer's note: Differs from 1 in that the reply must take up A's amusement, not just the good news.

**Under interpretation 3** — Reacts to the short notice and weighs whether Monday works

- must convey: Registers Monday as soon — surprise, a check on the date, or a quick logistics thought
- must convey: Signals interest anyway rather than backing off
- must avoid: Ignoring the start date and responding only to the pay
- must avoid: Sounding alarmed or treating the short notice as disqualifying
- example (never a similarity target): *Monday, seriously? That's like three days. I mean — I could do Monday. I'd just have to sort the shift I already said yes to.*

### Tones that would be clearly wrong

- **Grave, sympathetic concern** — sounds like Softened, lowered voice with slow careful pacing and a falling, consoling contour, as if receiving bad or delicate news.; wrong because Treats a buoyant, amused reaction to a promising listing as something to be gentle about.
- **Flat, unmodulated recitation** — sounds like Even pitch, unchanged pace and energy from earlier turns, no lift or breath change anywhere in the line.; wrong because Registers nothing at all happening, when the other speaker just laughed at something notable.
- **Alarmed or urgent** — sounds like Sharp onset, raised and tightened voice, quickened clipped delivery, audible tension as though something has gone wrong.; wrong because Reads a light laugh as a crisis signal; nothing in the moment warrants urgency.
- **Patronising or placating warmth** — sounds like Cooing, over-soft sing-song with exaggerated encouraging swells, the voice adults use to reassure a child.; wrong because Takes a condescending stance toward a peer sharing an amused, casual moment between equals.

*Acceptable range:* Anything from dry, quiet amusement to open delight works, laughing along or not, including brisk matter-of-fact interest with a slight lift.

---

## v6_02c · condition_b · `gasp` · **rev 2**

**Scenario:** A friend helps someone who once imagined many careers check a newly reopened job listing.

1. **A:** Have you settled on any applications yet?
2. **B:** I used to picture myself doing everything—teaching, design, even park work.
3. **A:** What do you need from a job now?
4. **B:** Enough to cover rent, and something that starts soon. I found the library assistant listing again—refresh the link I just sent you.
5. **A:** (gasps) It says twenty-two an hour, and they need someone Monday.

**Framing the planner intended:** The opening feels like an unexpected opportunity, because the listing's concrete terms arrive as a sudden and consequential discovery.

### Acceptable interpretations

1. **Delighted surprise that the listing pays and starts better than B expected.** — Flags the details as unexpectedly good news before A even reads them out.
2. **Startled urgency at the Monday start date, which leaves almost no time.** — Marks the posting as time-critical and pushes B toward acting immediately.
3. **Struck by the listing mattering, mixing excitement about the pay with alarm at the deadline.** — Raises the stakes of the link so both treat it as a live decision, not idle browsing.

*Shared implication (the line a wrong answer crosses):* A finds the listing's terms genuinely striking and consequential for B; the sound is not boredom, dismissal, or indifference toward the posting.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Share the good news and confirm the terms are better than expected

- must convey: Registers the pay or terms as better than B had been hoping for
- must convey: Signals real interest in the listing — wanting it, applying, treating it as a find
- must avoid: Treating the gasp as bad news or asking whether something is wrong
- must avoid: Flat acknowledgement that skips any reaction to how good the terms are
- example (never a similarity target): *Twenty-two? That's way over what I was bracing for. Okay, that one I'm actually applying to.*

**Under interpretation 2** — React to the tight deadline and move toward acting now

- must convey: Acknowledges Monday leaves very little time to get an application in
- must convey: Proposes or commits to a concrete immediate next step — applying tonight, calling, sending it
- must avoid: Dwelling on the pay while ignoring that the start date is the pressing part
- must avoid: Vague enthusiasm with no move toward doing something before the deadline
- example (never a similarity target): *Monday? That's basically no time. Let me pull up my resume now and get something in tonight.*

**Under interpretation 3** — Treat the listing as a real decision — good terms, short fuse

- must convey: Responds to both sides: the terms are worth wanting and the timing is tight
- must convey: Shifts from browsing to deciding — commits, or names what needs resolving first
- must avoid: Picking up only the pay or only the deadline and dropping the other
- must avoid: Staying noncommittal, as if the listing were still just one option among many
- example (never a similarity target): *Okay, that's actually the number I need — but Monday. I think I just go for it and figure out the rest after.*

### Tones that would be clearly wrong

- **Alarmed or dread-filled** — sounds like Sharp, tightened voice, breath caught high, urgent clipped delivery as though bracing for something bad.; wrong because Reads the gasp as fright or bad news when it lands on a welcome, favourable discovery.
- **Flat, disengaged monotone** — sounds like Even pitch throughout, no lift or quickening, unhurried and affectless, as if reading something unrelated aloud.; wrong because Registers nothing at a moment of sudden good news about the speaker's own pressing need.
- **Soothing, patronising reassurance** — sounds like Slowed, softened, downward-gliding delivery with gentling warmth, the voice used to calm someone upset.; wrong because Treats an excited gasp as distress needing management, casting the other speaker as fragile.
- **Theatrical hype, game-show pitch** — sounds like Loud, stretched vowels, exaggerated whooping swoops, performed astonishment far above the other speaker's energy.; wrong because Overshoots a brief startled intake between two people talking practically about rent and hours.

*Acceptable range:* Anything from quiet caught-breath interest to bright audible delight works, as does a wry or guarded lift; warmth and restraint are both fine.

---

## v6_02d · condition_a · `laugh`

**Scenario:** After a night of drinking at a bar, someone checks their receipt and discovers they did not leave their waitress a tip.

1. **A:** Did you make it home from the bar okay?
2. **B:** Eventually. I found my phone and card this morning.
3. **A:** Check the bar charge. Maybe the receipt will tell you how the night ended.
4. **B:** I've got the transaction open. Here's the itemized receipt.
5. **A:** (laughs) The tip line is blank.

**Framing the planner intended:** The discovery becomes a sheepish, absurd mistake the speaker can recognize as darkly comic.

### Acceptable interpretations

1. **Amusement at the blank tip line as evidence of how far gone B was.** — Flags the detail as the punchline of the night's story before naming it.
2. **Delighted teasing of B for stiffing the bartender.** — Sets up a gentle accusation, inviting B to own or defend the lapse.
3. **Amused surprise mixed with mild sympathy for B's rough night.** — Softens the reveal so it lands as shared joke rather than reproach.

*Shared implication (the line a wrong answer crosses):* A treats the blank tip line as funny and telling about B's state that night, not as a neutral report or serious moral criticism.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Join the laugh, own the detail as story evidence

- must convey: Treats the blank tip line as funny confirmation of how gone B was that night
- must convey: Adds or invites a further detail about what state B was in
- must avoid: Treating the blank line as a serious problem needing correction or an apology
- must avoid: Getting defensive as if accused of cheapness
- example (never a similarity target): *Blank. Yeah, that tracks — I couldn't work out which card was mine, let alone do arithmetic.*

**Under interpretation 2** — Take the ribbing; own or playfully defend the stiff

- must convey: Responds to the implied accusation about the bartender rather than only to the night generally
- must convey: Either concedes the lapse or mounts a joking defence
- must avoid: Ignoring the accusation and treating it as a neutral observation about the receipt
- must avoid: Genuine guilt-ridden self-reproach that kills the teasing
- example (never a similarity target): *Okay, in my defence, the machine and I were not on speaking terms. I'll go back and square it with her.*

**Under interpretation 3** — Share the joke while acknowledging the night was rough

- must convey: Laughs along rather than treating it as a charge to answer
- must convey: Acknowledges the state B was in, without being defensive about it
- must avoid: Reading it as an accusation and defending or apologising for the missing tip
- must avoid: Dwelling on how bad the night was in a way that drops the humour
- example (never a similarity target): *God. That's about the level I was operating at. I'm amazed the card went through at all.*
- writer's note: Differs from 1 in that B leans on how rough it was rather than on it being the punchline.

### Tones that would be clearly wrong

- **Solemn gravity** — sounds like Slow, weighted delivery with hushed volume and falling phrase endings, as if delivering bad news or consoling someone.; wrong because Treats a light shared joke about a receipt as a serious or sad revelation.
- **Alarmed urgency** — sounds like Tight, fast, breath-catching speech with raised pitch and clipped words, like reacting to something going wrong.; wrong because Reads a trivial amusing detail as an emergency, when the other speaker just laughed.
- **Sharp defensive snap** — sounds like Clipped, hard-edged, tight-jawed delivery with irritated stress, as if pushing back against being mocked.; wrong because Takes an affectionate tease as an attack, souring a moment offered in warmth.
- **Chirpy presenter brightness** — sounds like Loud, boomy, uniformly upbeat announcer energy with big pitch swings and performed enthusiasm aimed outward, not at a friend.; wrong because Overshoots the small private amusement with broadcast-scale cheer nobody in this exchange invited.

*Acceptable range:* Anything from a quiet dry deadpan to an amused chuckle to a sheepish, self-conscious mutter works, so long as it stays warm and low-stakes.

---

## v6_02d · condition_b · `gasp`

**Scenario:** After a night of drinking at a bar, someone checks their receipt and discovers they did not leave their waitress a tip.

1. **A:** Did you make it home from the bar okay?
2. **B:** Eventually. I found my phone and card this morning.
3. **A:** Check the bar charge. Maybe the receipt will tell you how the night ended.
4. **B:** I've got the transaction open. Here's the itemized receipt.
5. **A:** (gasps) The tip line is blank.

**Framing the planner intended:** The discovery becomes an alarming realization that the waitress was left unpaid and the speaker must address it.

### Acceptable interpretations

1. **Mock scandal at B having stiffed the bartender on a big night out** — Playfully indicts B for the omission, inviting a defense or laughing confession
2. **Genuine surprise at spotting the one detail the receipt reveals** — Marks the blank tip line as the significant find and directs B's attention to it
3. **Half-teasing alarm that the blank line means B was too far gone to sign** — Treats the gap as evidence about how the night ended, prompting B to reconstruct it

*Shared implication (the line a wrong answer crosses):* A has spotted something noteworthy in the receipt and is flagging it as significant, not dismissing it, changing subject, or expressing boredom or indifference.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Takes the mock accusation and defends or confesses to it

- must convey: Engages with the charge of having stiffed the bartender rather than deflecting from it
- must convey: Offers a defense, a guilty admission, or a plan to make it right
- must avoid: Treating the blank line as alarming evidence about B's state that night
- must avoid: Ignoring the accusation and reading the receipt as neutral information
- example (never a similarity target): *Okay, in my defense, I think I left cash. Probably. I'm going back tomorrow and tipping him double either way.*

**Under interpretation 2** — Confirms the find and works out what it means

- must convey: Acknowledges the blank tip line as the notable detail on the receipt
- must convey: Adds something about what it might indicate — cash tip, unsigned slip, closed tab
- must avoid: Playing it as an accusation or a joke at B's own expense
- must avoid: Downplaying the detail or moving on to other lines of the receipt
- example (never a similarity target): *Huh, you're right. Nothing on the tip line at all. So either I left cash or I never actually signed the thing.*

**Under interpretation 3** — Half-jokingly reckons with what the gap says about the night

- must convey: Accepts the blank line as evidence about how far gone B was
- must convey: Tries to reconstruct or admit uncertainty about that part of the night
- must avoid: Treating it purely as a tipping etiquette offense against the bartender
- must avoid: Refusing the implication about B's state with no engagement at all
- example (never a similarity target): *That tracks, honestly. I don't remember signing anything after about eleven. Somebody must have just closed me out.*
- writer's note: Shares interpretation 2's focus on the blank line, but here B reads it as evidence about their own state rather than a neutral finding.

### Tones that would be clearly wrong

- **Alarmed, emergency urgency** — sounds like Tight, fast, rising delivery with breath catching, volume pushed up, as if reporting danger or a crisis.; wrong because Treats a small, faintly comic discovery on a receipt as a genuine emergency, far above the moment's stakes.
- **Flat, unreacting monotone** — sounds like Even pitch, unchanged pace and volume, no lift or catch anywhere — sounds like reading an unrelated line aloud.; wrong because Gives no uptake at all to a partner's audible surprise, as if nothing had just been noticed.
- **Curt, irritated dismissal** — sounds like Clipped, hard-edged words, downward finish, slight exhale of impatience, delivered as though shutting the topic down.; wrong because Takes an annoyed stance toward a partner who is engaged and reacting with them, not at them.
- **Soft, consoling, patronising comfort** — sounds like Hushed, slowed, tender voice with soothing warmth, the way one gentles someone who has received bad news.; wrong because Casts the gasping speaker as distressed and needing care, a stance this light discovery does not license.

*Acceptable range:* Amused, sheepish, sharply curious, mock-scandalised, or quietly deadpan-wry all work, at anything from understated to animated, with or without a laugh.

---

## v6_03a · condition_a · `laugh` · **rev 2**

**Scenario:** A person rushes to fuel up before a gym visit, only to learn at the last moment that the gym is unavailable.

1. **A:** You still going to work out tonight?
2. **B:** Yeah, I had to eat first. I hadn't had anything substantial all day.
3. **A:** You know the gym usually closes pretty soon.
4. **B:** I know. I finished dinner and a protein shake, and I'm grabbing my things now.
5. **A:** (laughs) The gym just sent a message—they closed early because of an equipment problem.

**Framing the planner intended:** The sequence becomes an absurdly mistimed routine: all that preparation has culminated in a comically useless trip.

### Acceptable interpretations

1. **Amusement at the bad timing — B rushed through dinner for a gym that is already shut.** — Frames the news as a comic anticlimax rather than a complaint, softening the blow before delivering it.
2. **Wry vindication after twice warning B about the closing time, now overtaken by a different cause.** — Marks the outcome as ironically proving A's point while stopping short of an outright I-told-you-so.
3. **Sympathetic amusement mixed with mild commiseration for B's wasted preparation.** — Cushions unwelcome news and invites B to treat the evening as absurd rather than annoying.

*Shared implication (the line a wrong answer crosses):* A finds the situation ironically funny and is not delivering the news neutrally, apologetically, or as genuine bad news demanding concern.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Takes in the news and joins the comic anticlimax

- must convey: Registers that the gym is shut and the rush was for nothing
- must convey: Plays along with the absurdity of the timing rather than protesting
- must avoid: Treating the closure as a real problem needing complaint, blame, or a fix
- must avoid: Ignoring the news and continuing as if still heading out
- example (never a similarity target): *Of course. I inhale a whole dinner in ten minutes and the place is dark. Bag's already packed and everything.*

**Under interpretation 2** — Concedes A's point while noting the irony of the cause

- must convey: Acknowledges A was right that the gym wouldn't work out tonight
- must convey: Points out closing time wasn't actually what stopped it
- must avoid: Getting genuinely defensive or annoyed at A for being right
- must avoid: Conceding flatly without registering A's amusement at all
- example (never a similarity target): *Alright, you win, sort of. You kept saying I'd miss it — turns out I'd have missed it anyway, broken machines and all.*

**Under interpretation 3** — Accepts the commiseration and writes off the evening

- must convey: Acknowledges the wasted prep — the meal, the shake, the packed bag
- must convey: Settles on what happens instead, or shrugs the night off
- must avoid: Reading A as gloating and pushing back at them
- must avoid: Sounding genuinely upset in a way that rejects the light framing
- example (never a similarity target): *So I force-fed myself a protein shake for nothing. Well, that's the night. Guess I'm on the couch.*
- writer's note: Shares the light register with interpretation 1, but here B lands on the wasted effort and what to do now, rather than on the timing joke itself.

### Tones that would be clearly wrong

- **Alarmed, urgent concern** — sounds like Sharp intake, quickened tempo, rising pitch, clipped words pushed out as if reacting to an emergency.; wrong because Treats a minor, funny inconvenience delivered through a laugh as an urgent problem demanding immediate response.
- **Hushed, solemn condolence** — sounds like Slowed, lowered, softened delivery with sympathetic warmth, the register used for delivering or receiving bad news.; wrong because Reads real loss into a wry moment; gravity is out of proportion to a closed gym.
- **Bright chirpy delight** — sounds like Sing-song upswing, perky energy, unmixed cheerfulness, like announcing good news or performing enthusiasm.; wrong because Overshoots the shared irony into unclouded happiness, ignoring that the effort just went to waste.
- **Sharp hostile snap** — sounds like Hard clipped consonants, tightened throat, accusatory stress landing heavily, real irritation aimed at the other speaker.; wrong because Turns a teasing shared joke into a grievance; genuine anger at the messenger misplaces the frustration.

*Acceptable range:* Anything from a laugh along, to a groan or sigh, to dry deadpan or mild mock-exasperation reads fine here.

---

## v6_03a · condition_b · `groan` · **rev 2**

**Scenario:** A person rushes to fuel up before a gym visit, only to learn at the last moment that the gym is unavailable.

1. **A:** You still going to work out tonight?
2. **B:** Yeah, I had to eat first. I hadn't had anything substantial all day.
3. **A:** You know the gym usually closes pretty soon.
4. **B:** I know. I finished dinner and a protein shake, and I'm grabbing my things now.
5. **A:** (groans) The gym just sent a message—they closed early because of an equipment problem.

**Framing the planner intended:** The sequence becomes a thwarted plan: careful preparation has been wasted by an inconvenient last-minute closure.

### Acceptable interpretations

1. **Vicarious dismay that B's eating, prep, and hurry were all for nothing.** — Marks the news as bad for B and aligns A with B's frustration.
2. **Exasperation at the gym for closing early over an equipment problem.** — Places blame on the gym rather than on B's slow start, pre-empting any I-told-you-so reading.
3. **Reluctance to be the one delivering news that undoes B's whole evening.** — Prefaces and softens the announcement, warning B that something unwelcome is coming.

*Shared implication (the line a wrong answer crosses):* A treats the closure as genuinely unwelcome and is not gloating, teasing, or claiming vindication for having warned B about the time.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Absorbs the news, voices own frustration at wasted effort

- must convey: Registers that the closure ruins the plan B was minutes from starting
- must convey: Reacts to the wasted preparation or hurry rather than analysing why
- must avoid: Blaming self for eating first or conceding A's earlier timing warning was right
- must avoid: Treating the news as trivial or as if the plan still stands
- example (never a similarity target): *Are you serious? I literally have my bag in my hand. Well, that's dinner and a shake for nothing.*

**Under interpretation 2** — Joins the complaint, directs annoyance at the gym

- must convey: Takes up A's irritation at the gym rather than at the delay in leaving
- must convey: Engages with the closure itself — the short notice, the equipment, or how long it'll last
- must avoid: Turning the annoyance back on themselves or on A for the earlier warning
- must avoid: Defending the gym or brushing the early closure off as reasonable
- example (never a similarity target): *Of course they did. They couldn't have sent that an hour ago? Does it say when they're opening back up?*

**Under interpretation 3** — Receives the flagged bad news, releases A from delivering it

- must convey: Signals the news has landed and A isn't at fault for bringing it
- must convey: Responds to what it means for tonight — dropping the plan or finding another option
- must avoid: Shooting the messenger or reading A's reluctance as smugness about the earlier warning
- must avoid: Making A elaborate or apologise before acknowledging the news
- example (never a similarity target): *Oh no. Okay, well, nothing you could do about that. Guess I'm doing something at home instead.*

### Tones that would be clearly wrong

- **Bright, upbeat cheerfulness** — sounds like Lifted, smiling delivery with rising energy and a peppy lilt, as if reacting to welcome news.; wrong because The groan marks a small shared frustration; sunny brightness reads as ignoring the letdown that was just voiced.
- **Alarmed or distressed urgency** — sounds like Sharp intake, tightened voice, fast clipped delivery, pitch jumping up as though something serious went wrong.; wrong because A closed gym is a minor annoyance; crisis-pitched delivery wildly overshoots the everyday scale of the moment.
- **Flat, disengaged monotone** — sounds like Even pitch, no inflection change, mechanical pacing, indistinguishable from reading an unrelated sentence aloud.; wrong because Registers nothing of the shared annoyance, making the groan land as if it were never heard.
- **Patronising or scolding smugness** — sounds like Sing-song condescension or a tutting, told-you-so lean, drawn-out vowels aimed down at the other speaker.; wrong because Nothing here licenses talking down; the groan invites commiseration, not correction or superiority.

*Acceptable range:* Deflated sighing, wry amusement, mild irritation, resigned flatness, or a brief clipped remark all fit; warmth and dryness are equally fine.

---

## v6_03b · condition_a · `laugh`

**Scenario:** A mother checks her child's newly posted chemistry-test grade while the child waits nearby.

1. **A:** Chemistry grades were supposed to be up today.
2. **B:** I can see the grade portal on my phone.
3. **A:** Don't say anything yet. Let me find it first.
4. **B:** I opened the chemistry test. It says 95 out of 100.
5. **A:** (laughs) Ninety-five.

**Framing the planner intended:** The student takes the unexpectedly high score and the mother's buildup as a pleasing, almost ridiculous surprise.

### Acceptable interpretations

1. **Delighted relief that the grade she was bracing for turned out to be high** — Releases the built-up suspense and accepts B's news as good before repeating it
2. **Pleased disbelief that the number is that high, half-checking she heard right** — Marks the score as better than expected and invites B to confirm it
3. **Happy but wryly resigned that B spoiled the reveal she asked to have herself** — Lightly chides B for jumping in while conceding the news is too good to mind

*Shared implication (the line a wrong answer crosses):* The speaker treats 95 as welcome news; the sound is not disappointment, dismay, or a complaint about the grade itself.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Share the relief and celebrate the good result with her

- must convey: Affirms the grade is genuinely good and worth being happy about
- must convey: Signals the waiting and worrying is over, matching her release
- must avoid: Treating the number as uncertain or offering to double-check it
- must avoid: Dwelling on how nervous she was or how badly it could have gone
- example (never a similarity target): *Ninety-five! You were sweating that all week for nothing. That's your best one yet.*

**Under interpretation 2** — Confirm the number and back up that it's real

- must convey: Restates or verifies the score as ninety-five out of a hundred
- must convey: Treats her disbelief as answerable — the portal really says that
- must avoid: Skipping confirmation and moving straight to celebration or teasing
- must avoid: Casting doubt on the number or suggesting it might be a different test
- example (never a similarity target): *Ninety-five, yeah — I'm looking right at it. Chemistry test, top of the page. It's yours.*

**Under interpretation 3** — Take the light chiding and play up spoiling the reveal

- must convey: Acknowledges jumping in when she asked to find it herself
- must convey: Keeps the news framed as good, not letting the apology sour it
- must avoid: Confirming the score earnestly as if she doubted it
- must avoid: A heavy or defensive apology that makes the moment about B's mistake
- example (never a similarity target): *Okay, okay, I ruined it. But be honest — you'd have wanted me to say something if it was a forty-five.*

### Tones that would be clearly wrong

- **Flat, affectless readout** — sounds like Even, unmodulated delivery with no lift or warmth, like reading a number off a screen to nobody.; wrong because A laugh of relief and delight invites some shared warmth; total neutrality reads as indifference to the other person's good news.
- **Concerned or consoling** — sounds like Lowered pitch, softened careful delivery, gentle downward contour of the sort used to break bad news.; wrong because Misreads the laugh as distress or bad news when it follows an unambiguously high score.
- **Alarmed or urgent** — sounds like Sudden sharpness, clipped tempo, raised volume with a startled edge.; wrong because Nothing here is urgent; alarm treats a moment of relief as an emergency.
- **Patronising congratulation** — sounds like Exaggerated sing-song praise, drawn-out cooing vowels, the voice used with a small child or a pet.; wrong because Talks down to a peer who just got their own grade; the moment licenses shared pleasure, not bestowed approval.

*Acceptable range:* Anything from a quiet warm exhale to open laughing delight works, as does dry teasing or understated matter-of-fact warmth.

---

## v6_03b · condition_b · `groan`

**Scenario:** A mother checks her child's newly posted chemistry-test grade while the child waits nearby.

1. **A:** Chemistry grades were supposed to be up today.
2. **B:** I can see the grade portal on my phone.
3. **A:** Don't say anything yet. Let me find it first.
4. **B:** I opened the chemistry test. It says 95 out of 100.
5. **A:** (groans) Ninety-five.

**Framing the planner intended:** The student fixates on the five missing points, making the same score sound like an irritating near-miss.

### Acceptable interpretations

1. **Frustration that B revealed the score after being explicitly asked to wait** — Reproaches B for spoiling the reveal and marks the request as violated
2. **Disappointment that the score fell short of the perfect mark A hoped for** — Frames 95 as a near-miss rather than a success worth celebrating
3. **Deflated resignation — good news, but arriving secondhand and slightly under target** — Registers a complaint while still accepting the number, tempering B's announcement

*Shared implication (the line a wrong answer crosses):* A is not receiving 95 as uncomplicated good news; the sound registers a complaint about the score or its delivery, not delight.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Owns spoiling the reveal; apologises without retracting the number

- must convey: Acknowledges having read it out after A asked to find it first
- must convey: Signals the news itself is good, so A can still be pleased
- must avoid: Treating the groan as disappointment in the score and consoling A about 95
- must avoid: Defending the interruption or insisting A should just be grateful
- example (never a similarity target): *Sorry — you said wait and I went straight in. I couldn't help it. It's a really good mark, for what it's worth.*

**Under interpretation 2** — Pushes back on the near-miss framing; affirms the score

- must convey: Treats 95 as a genuinely strong result rather than a shortfall
- must convey: Engages with A's hope for a perfect mark instead of ignoring it
- must avoid: Apologising for having looked, which misreads what A is reacting to
- must avoid: Agreeing it's a letdown or dwelling on the five lost marks
- example (never a similarity target): *Ninety-five is not a bad grade. I know you wanted the hundred, but that's an A by any measure — take the win.*

**Under interpretation 3** — Concedes the complaint lightly, then holds onto the good news

- must convey: Registers that the delivery or the number fell short of what A wanted
- must convey: Still lands the point that 95 is a good outcome worth accepting
- must avoid: Only apologising or only cheerleading — this reading needs both notes
- must avoid: Overinterpreting the groan as real distress and turning solicitous
- example (never a similarity target): *Okay, fair — I jumped the gun and it's not the hundred. Still, ninety-five. You'd have taken that last week.*
- writer's note: Differs from 1 and 2 by combining the concession with the affirmation rather than choosing one.

### Tones that would be clearly wrong

- **Bright celebratory congratulation** — sounds like Rising, beaming delivery with an excited lift and burst of energy, as if announcing great news to a cheering room.; wrong because Hears the groan as pleasure and steamrolls it; the speaker's audible displeasure gets no acknowledgement at all.
- **Alarmed, grave concern** — sounds like Hushed, tightened voice, urgent breath, slow careful delivery reserved for genuinely bad news or someone in distress.; wrong because Escalates a small deflated groan into a crisis, treating the moment as far heavier than it is.
- **Mocking, scoffing amusement** — sounds like Snorted or sneering laugh, sing-song incredulity, exaggerated stress on words, aimed at the speaker rather than shared with them.; wrong because Takes a stance of ridicule the moment does not license, making the speaker's reaction the target.
- **Patronising soothing coddle** — sounds like Cooing, softened baby-talk warmth, long consoling vowels and downward petting cadence, as if comforting a small child.; wrong because Casts the speaker as fragile and needing management over a grade reaction, which condescends rather than responds.

*Acceptable range:* Puzzled, wry, gently amused, deadpan, warmly sympathetic, or simply level and curious deliveries all work, at low or moderate intensity.

---

## v6_03c · condition_a · `laugh` · **rev 2**

**Scenario:** A job seeker has had several encouraging interviews but receives a request for one more meeting.

1. **A:** I've had three interviews in the last two weeks.
2. **B:** Oh, so the job search is moving, then?
3. **A:** Yeah. One hiring manager said my experience was exactly what they needed.
4. **B:** That's promising. Did anyone follow up?
5. **A:** My phone just lit up. (laughs) They're asking me to come in for a fourth interview tomorrow.

**Framing the planner intended:** The extra interview is treated as comically excessive, while still suggesting the employer remains interested.

### Acceptable interpretations

1. **Delight and slight disbelief at how fast the search suddenly turned in their favour** — Shares the good news warmly and invites B to celebrate the turnaround with them
2. **Amused incredulity that a fourth interview is being asked of them at all** — Flags the extra round as faintly absurd while keeping the report light rather than complaining
3. **Pleased but weary — glad to be wanted, tired of being interviewed** — Lets them report progress and the fatigue of it in one move, without dampening the news

*Shared implication (the line a wrong answer crosses):* The speaker is reporting a genuinely positive development, not disappointment, rejection, or bad news; the sound accepts the momentum rather than dismissing it.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Celebrates the turnaround and matches their delight

- must convey: Treats the fourth-interview call as a strong sign things are going their way
- must convey: Some forward-looking interest in tomorrow, e.g. how they feel going in
- must avoid: Hedging the good news with warnings about employers stringing candidates along
- must avoid: Treating the extra round as a burden they need sympathy for
- example (never a similarity target): *Tomorrow already? They're not letting you get away. Two weeks ago you had nothing lined up and now they're chasing you.*

**Under interpretation 2** — Joins the joke about a fourth round being excessive

- must convey: Acknowledges four interviews as a lot, playing along with the absurdity
- must convey: Still registers that being asked back is a good sign, not a complaint
- must avoid: Earnest defence of the company's hiring process as reasonable or normal
- must avoid: Turning the joke into real criticism they didn't make
- example (never a similarity target): *A fourth? What's left, do they want to meet your parents? Still — nobody does four rounds on someone they're not serious about.*

**Under interpretation 3** — Affirms the news while acknowledging the fatigue

- must convey: Recognises that another round on short notice is tiring after three already
- must convey: Keeps the progress itself in good standing rather than souring it
- must avoid: Ignoring the weariness and responding as pure uncomplicated celebration
- must avoid: Suggesting they skip, delay, or push back when they haven't raised that
- example (never a similarity target): *Four rounds in two weeks is a lot to keep up. Good sign they want you in that fast, though. You feeling up to tomorrow?*

### Tones that would be clearly wrong

- **Flat, uninflected acknowledgment** — sounds like Even pitch, no lift or warmth, clipped delivery as if reading a list item aloud.; wrong because Ignores the shared delight in the laugh, leaving the good news audibly unmet.
- **Concerned or worried** — sounds like Lowered pitch, slowed pace, soft careful delivery of the sort used for bad news.; wrong because Misreads a pleased laugh as distress, treating a good development as trouble.
- **Dismissive or deflating** — sounds like Sighing exhale, downward drop at the end, faint flatness bordering on boredom.; wrong because Withholds any recognition of a moment the speaker just laughed with pleasure about.
- **Overblown celebratory shouting** — sounds like Loud, near-yelling excitement, exaggerated stretched vowels, breathless pace far above the speaker's own level.; wrong because Overshoots a light amused laugh, turning a small shared moment into a spectacle.

*Acceptable range:* Anything from a quiet warm chuckle to bright genuine enthusiasm works, including dry amusement or calm interest, so long as some warmth registers.

---

## v6_03c · condition_b · `groan` · **rev 2**

**Scenario:** A job seeker has had several encouraging interviews but receives a request for one more meeting.

1. **A:** I've had three interviews in the last two weeks.
2. **B:** Oh, so the job search is moving, then?
3. **A:** Yeah. One hiring manager said my experience was exactly what they needed.
4. **B:** That's promising. Did anyone follow up?
5. **A:** My phone just lit up. (groans) They're asking me to come in for a fourth interview tomorrow.

**Framing the planner intended:** The extra interview is treated as another draining hurdle despite the otherwise encouraging progress.

### Acceptable interpretations

1. **Exasperation at being dragged through yet another round after already being told he's the right fit** — Frames the fourth interview as an unreasonable imposition rather than good news
2. **Weariness and depletion — he doesn't have the energy for another interview tomorrow** — Invites sympathy for the toll of the process rather than congratulation on progress
3. **Mixed feeling: the callback is genuinely encouraging but the demand is tiresome** — Pre-empts B's upbeat framing, marking the news as good-but-draining before delivering it

*Shared implication (the line a wrong answer crosses):* The speaker treats the further interview as a burden, not as welcome news; he is not celebrating, joking, or expressing excitement about the callback.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Agrees the fourth round is unreasonable; sides with him

- must convey: Treats a fourth interview as excessive given he was already told he's the right fit
- must convey: Stays on his side rather than defending the employer's process
- must avoid: Congratulating him on the callback as straightforwardly good news
- must avoid: Justifying the extra round or telling him it's normal hiring practice
- example (never a similarity target): *A fourth one? They already told you you're exactly what they need. What else do they think they're going to find out?*

**Under interpretation 2** — Checks how he's holding up; eases the load practically

- must convey: Acknowledges the process has worn him down, not just that the news arrived
- must convey: Offers something concrete — help preparing, a lighter evening, or asking to move the day
- must avoid: Rallying him with pep talk or urging him to push through one more
- must avoid: Treating the callback as the headline and skipping over how tired he is
- example (never a similarity target): *Tomorrow, already? You've barely had a break. Do you want to run through it tonight, or just leave it and get some sleep?*

**Under interpretation 3** — Holds both sides: real progress, genuinely tiring demand

- must convey: Registers the callback as a good sign about where he stands
- must convey: Names the same breath that another round tomorrow is a drain
- must avoid: Landing only on the good news and erasing the weariness he flagged
- must avoid: Reading it as pure complaint and dismissing the callback as meaningless
- example (never a similarity target): *Well, they clearly want you — they don't drag people back a fourth time otherwise. Doesn't make doing it tomorrow any less of a slog, though.*

### Tones that would be clearly wrong

- **Bright celebratory cheer** — sounds like Upswinging, congratulatory delivery with a smile audible throughout, energy lifting at the end as if announcing good news.; wrong because Reads the moment as unmixed good fortune and steps straight over the audible dismay the groan just expressed.
- **Alarmed, grave concern** — sounds like Hushed, tightened voice, slowed pace, breath caught — the register used for bad medical news or a crisis.; wrong because Escalates a weary complaint into calamity, treating ordinary exasperation as something requiring emergency gravity.
- **Cooing, patronising comfort** — sounds like Sing-song lilt, drawn-out vowels, soft head-tilt warmth of the kind used to soothe a small child.; wrong because Takes a caretaking stance toward an adult venting mild frustration, condescending rather than commiserating as a peer.
- **Bored, dismissive brush-off** — sounds like Flat clipped delivery, falling energy, faint impatience or a sigh of one's own, as if moving past the topic.; wrong because Treats the groan as noise not worth registering, withdrawing engagement at the moment it was invited.

*Acceptable range:* Wry amusement, warm commiseration, a dry chuckle, quiet sympathy, or a light matched groan all work; restrained and brief is equally fine.

---

## v6_03d · condition_a · `laugh`

**Scenario:** Two classmates are preparing for school to begin and check the portal for first-day details.

1. **A:** School starts in three days. I've got my supplies and timetable ready.
2. **B:** Did you check the first-day schedule on the portal?
3. **A:** Just the timetable. I figured the rest would be there when we got in.
4. **B:** There's a new notice at the top. Open it—it says something about the opening assembly.
5. **A:** (laughs) Every student has to introduce themselves onstage at the opening assembly.

**Framing the planner intended:** The requirement feels comically over-the-top, and the final speaker treats the school's plan as absurdly funny.

### Acceptable interpretations

1. **Amused dismay at discovering a mandatory onstage introduction he never signed up for** — Flags the notice as an unwelcome surprise while keeping the delivery light
2. **Rueful self-recognition that skipping the rest of the portal has just backfired** — Concedes B's earlier point about checking, softening the admission of being caught out
3. **Disbelief that the school would require every single student to present onstage** — Frames the requirement as absurd and invites B to react to it with him

*Shared implication (the line a wrong answer crosses):* The laugh registers the assembly requirement as unwelcome or absurd news, not as delight, indifference, or a joke he is telling.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Joins the light dismay and reacts to the requirement itself

- must convey: Registers the onstage introduction as an unwelcome surprise rather than good news
- must convey: Engages with what it means for him — how bad it'll be, or that it's survivable
- must avoid: Treating the laugh as delight or the news as something to congratulate him on
- must avoid: Turning back to whether he should have checked the portal earlier
- example (never a similarity target): *Onstage? In front of the whole school? That's rough. Though it's probably thirty seconds each — name, class, done.*

**Under interpretation 2** — Accepts the concession lightly without pressing the point

- must convey: Acknowledges that this is exactly the kind of thing the portal check was for
- must convey: Declines to make more of being right — moves him toward what to do now
- must avoid: Lecturing or repeating the told-you-so beyond one light beat
- must avoid: Ignoring the concession entirely and reacting only to the assembly requirement
- example (never a similarity target): *Yeah, that's the sort of thing hiding down there. Anyway — three days. Want to work out what you're actually going to say?*

**Under interpretation 3** — Reacts with him to the absurdity of the blanket requirement

- must convey: Shares or engages his sense that requiring every student onstage is unreasonable
- must convey: Takes up the practical implausibility — the numbers, the time, how it would even run
- must avoid: Defending the school's policy as sensible or telling him it's no big deal
- must avoid: Shifting focus onto his own nerves rather than the requirement being absurd
- example (never a similarity target): *Every student? There are hundreds of you. That assembly would run all day. Are you sure it doesn't mean per class or something?*

### Tones that would be clearly wrong

- **Grave, alarmed concern** — sounds like Low, slow, weighted delivery with a worried edge; heavy pauses, as if delivering bad news or bracing for trouble.; wrong because A laughed reveal is being treated as a crisis, converting light dismay into something the moment does not carry.
- **Flat, unregistering neutrality** — sounds like Even, affectless recitation with no lift, no smile in the voice, same as reading a schedule aloud.; wrong because Ignores an audible bid for shared amusement, leaving the other speaker's laugh hanging unacknowledged.
- **Chirpy, over-bright enthusiasm** — sounds like Bouncy, high-energy cheerleading brightness, exclamatory and pepped-up, like announcing an exciting opportunity.; wrong because Overshoots the wry, slightly rueful amusement in the laugh with unearned excitement about the announcement.
- **Mocking or teasing at the other's expense** — sounds like Sing-song jeering, drawn-out relish, a smirk audible in the voice as though enjoying their predicament.; wrong because Turns a laugh shared with the speaker into laughing at them, taking a stance the moment does not license.

*Acceptable range:* Anything from a small answering chuckle to warm dry amusement to calm, mildly sympathetic matter-of-factness is fine, including brief or understated replies.

---

## v6_03d · condition_b · `groan`

**Scenario:** Two classmates are preparing for school to begin and check the portal for first-day details.

1. **A:** School starts in three days. I've got my supplies and timetable ready.
2. **B:** Did you check the first-day schedule on the portal?
3. **A:** Just the timetable. I figured the rest would be there when we got in.
4. **B:** There's a new notice at the top. Open it—it says something about the opening assembly.
5. **A:** (groans) Every student has to introduce themselves onstage at the opening assembly.

**Framing the planner intended:** The requirement turns the approaching first day into an unwanted public obligation for the final speaker.

### Acceptable interpretations

1. **Dismay at learning he must speak onstage in front of the whole school.** — Registers the notice as bad news before reading it out, framing the requirement as a burden.
2. **Dread of public speaking specifically — anticipatory nerves about being exposed onstage.** — Signals the reaction is about the ordeal itself, inviting sympathy or reassurance from B.
3. **Annoyance that his careful preparation missed something now imposed on him.** — Concedes B was right to check the portal while complaining about the extra demand.

*Shared implication (the line a wrong answer crosses):* The speaker treats the assembly requirement as unwelcome; he is not pleased, indifferent, excited, or merely neutrally relaying information he already knew.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Acknowledges the bad news and engages with what it means

- must convey: Recognition that the announced requirement is unwelcome news to A
- must convey: Some engagement with the requirement itself — its scope, timing, or what it involves
- must avoid: Treating the announcement as good or exciting news, or as something A already knew
- must avoid: Jumping straight to coaching or pep talk without registering that it lands badly
- example (never a similarity target): *Onstage? For every single student? That's going to take all morning. Does it say how long each person gets?*

**Under interpretation 2** — Steadies him about the ordeal of speaking onstage

- must convey: Recognition that the nerve-wracking part is standing up in front of everyone
- must convey: Something that makes it feel manageable — practice, brevity, shared experience, or company
- must avoid: Dismissing the nerves as silly or insisting it is nothing to worry about
- must avoid: Focusing only on logistics or portal details while ignoring how he feels about it
- example (never a similarity target): *It'll be short, and everyone there is doing the same thing. Want to figure out what you'd say and run through it before Monday?*

**Under interpretation 3** — Takes the complaint lightly without gloating about being right

- must convey: Acknowledgement that his preparation was thorough and this came out of nowhere
- must convey: Something forward-looking — that there is still time, or what he can do about it now
- must avoid: Rubbing in that A should have checked the portal earlier
- must avoid: Treating it as a serious fear of performing rather than an irritating extra demand
- example (never a similarity target): *Of course there's one more thing. Well, you've still got three days — that's more warning than most people will get.*
- writer's note: Differs from 1 in that the reply must not scold; the grievance is the surprise, not the stage.

### Tones that would be clearly wrong

- **Bright, delighted enthusiasm** — sounds like Upward-lilting, smiling delivery with energetic emphasis, as if announcing something exciting.; wrong because Reads the groan as good news rather than dread, inverting the valence A just expressed.
- **Alarmed, urgent concern** — sounds like Tightened, faster delivery with pressed volume and worried edge, as though something serious happened.; wrong because Escalates a minor scheduling annoyance into crisis, far above the intensity the groan carries.
- **Dismissive impatience** — sounds like Clipped, flat, slightly exasperated delivery with a sighed or eye-roll quality directed at A.; wrong because Treats A's reaction as tiresome, taking a stance the moment does not license.
- **Patronising soothing** — sounds like Slowed, softened singsong with cooing warmth, the cadence used to calm a small child.; wrong because Overpersonalises a mild complaint and talks down to a peer sharing an inconvenience.

*Acceptable range:* Wry amusement, sympathetic commiseration, mild matter-of-fact acknowledgement, or a quiet flat beat all fit; warmth and dryness are equally fine.

---

## v6_04a · condition_a · `sigh`

**Scenario:** One speaker is slowly saving for a long-held dream of visiting Antarctica.

1. **A:** I've been putting a little aside for Antarctica whenever I can.
2. **B:** How close are you getting?
3. **A:** At this rate, it still feels a long way off.
4. **B:** I just found an Antarctica expedition grant. It covers the whole trip, but the application closes tonight.
5. **A:** (sighs) Tonight. A full trip, and the application has to be in tonight.

**Framing the planner intended:** The opportunity turns the distant dream into an immediate, demanding task that the speaker feels weighed down by.

### Acceptable interpretations

1. **Dismay that the fully-funded opportunity comes with an impossibly tight deadline.** — Registers the deadline as the problem before A even addresses whether to apply.
2. **Braced resignation — A is absorbing that a scramble tonight is now unavoidable.** — Marks the news as a burden being taken on rather than simply good news.
3. **Mixed relief and pressure: the money A couldn't save is available, but only right now.** — Flags the offer as double-edged, inviting B to help or acknowledge the crunch.

*Shared implication (the line a wrong answer crosses):* The sound is not indifference or rejection of the grant; A treats it as significant and feels the weight of the tonight deadline.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Acknowledge the bad timing, then weigh whether it's still doable

- must convey: Agrees the tonight cutoff is the hard part, not the grant itself
- must convey: Gives A something concrete about feasibility — how long it takes, what's actually required
- must avoid: Treating the sigh as reluctance about Antarctica or backing off the suggestion
- must avoid: Only sympathising about the deadline without any read on whether it's still possible
- example (never a similarity target): *I know, it's brutal timing. But I looked — it's a short form and a budget page. That's an evening, not a week.*

**Under interpretation 2** — Take the scramble as decided and help plan tonight

- must convey: Treats A as already committed to attempting it rather than still deciding
- must convey: Proposes a concrete step or division of the work for tonight
- must avoid: Re-arguing whether A should apply, as if the decision were still open
- must avoid: Piling on more tasks or urgency without offering to carry any of it
- example (never a similarity target): *Right, tonight it is. Send me the link and I'll pull the dates and costs together while you write the personal statement.*

**Under interpretation 3** — Name the upside, then acknowledge the cost of the timing

- must convey: Marks that this solves the money problem A has been slowly chipping at
- must convey: Recognises the catch — it's only available if A moves immediately
- must avoid: Selling it as pure good news with no acknowledgement of the crunch
- must avoid: Dwelling on the deadline so heavily that the funding win disappears
- example (never a similarity target): *Years of saving, and this covers the lot. Rough that it lands with hours to spare — but that's the whole trip, in one go.*

### Tones that would be clearly wrong

- **Bright, upbeat salesmanship** — sounds like Chirpy lift on every phrase, smiling energy, quickened pace, exclamation-like emphasis as if pitching good news.; wrong because Treats the sigh as enthusiasm rather than the weight of a sudden deadline against a long-saved-for hope.
- **Alarmed urgency bordering on panic** — sounds like Sharp, loud, rushed delivery with tightened throat and rising pitch, as if announcing an emergency.; wrong because Escalates a heavy exhale into crisis, overshooting the low-key resignation the sigh conveys.
- **Dismissive or impatient brush-off** — sounds like Flat clipped words, audible scoff or exhale of irritation, falling bored cadence that closes the topic.; wrong because Treats A's audible weariness as a nuisance when the sigh invites acknowledgement, not dismissal.
- **Cooing, patronising sympathy** — sounds like Sing-song softened voice, drawn-out vowels, the pitch used to soothe a child or a pet.; wrong because Overplays comfort for a mild sigh about a deadline, condescending to an adult weighing an option.

*Acceptable range:* Anything from warm steady encouragement to quiet matter-of-fact acknowledgement, gently wry, or lightly energised, works — brief or understated delivery is fine.

---

## v6_04a · condition_b · `gasp`

**Scenario:** One speaker is slowly saving for a long-held dream of visiting Antarctica.

1. **A:** I've been putting a little aside for Antarctica whenever I can.
2. **B:** How close are you getting?
3. **A:** At this rate, it still feels a long way off.
4. **B:** I just found an Antarctica expedition grant. It covers the whole trip, but the application closes tonight.
5. **A:** (gasps) Tonight. A full trip, and the application has to be in tonight.

**Framing the planner intended:** The unexpected grant makes the previously distant trip suddenly seem possible.

### Acceptable interpretations

1. **Startled excitement that the trip she's been slowly saving for could suddenly be fully funded.** — Registers B's news as a big deal and invites B to help her act on it.
2. **Alarm at the deadline — a real chance that could be lost within hours.** — Flags urgency and shifts the exchange toward whether she can apply in time.
3. **Stunned disbelief that something this good and this time-pressured landed at once.** — Buys a beat to absorb the news before her repetition confirms the details aloud.

*Shared implication (the line a wrong answer crosses):* She treats the grant as significant and personally consequential news that lands suddenly; she is not dismissing it, doubting B, or reacting with indifference.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Share her excitement and move toward helping her apply

- must convey: Affirms the trip she's been saving for is genuinely within reach now
- must convey: Offers something concrete toward getting the application done, or asks to start on it
- must avoid: Dampening the news with caveats about odds, eligibility, or how unlikely grants are
- must avoid: Leaving it as pleasant news with no move toward acting on it
- example (never a similarity target): *Right? The whole thing covered. Send me the link and I'll help you fill it in — we've got hours, not weeks.*

**Under interpretation 2** — Match the urgency and orient toward making the deadline

- must convey: Confirms the deadline is real and time is short
- must convey: Turns to what has to happen now — time remaining, what's needed, or splitting the work
- must avoid: Downplaying the time pressure or suggesting there'll be another round later
- must avoid: Celebrating at length without addressing whether she can actually get it in
- example (never a similarity target): *Tonight, yeah. What time exactly — let's check. If it's midnight you've got seven hours and I can pull the details together.*

**Under interpretation 3** — Confirm the details she's repeating, then steady her

- must convey: Verifies the two facts she said back — full funding, closes tonight
- must convey: Gives her footing to move: it's real, it's doable, here's where to start
- must avoid: Piling on more information or excitement before she's absorbed what she heard
- must avoid: Treating her repetition as doubt about B or the grant's legitimacy
- example (never a similarity target): *Both true. Full trip, closes tonight. I know it's a lot at once — but it's real, and it's a form, not a miracle.*
- writer's note: Differs from 2 by confirming the facts first rather than jumping straight to logistics; differs from 1 by steadying rather than amplifying.

### Tones that would be clearly wrong

- **Flat, unmoved neutrality** — sounds like Even pitch, no lift or urgency, steady conversational pace as if reading a schedule aloud.; wrong because Treats a sharp gasp at a closing deadline as unremarkable, leaving the other speaker's spike of urgency unmet.
- **Alarmed panic** — sounds like Sharply raised volume, tight breathy voice, rushed clipped delivery, audible spiralling stress.; wrong because Escalates a lucky opportunity into an emergency; the moment is exciting pressure, not crisis.
- **Dismissive or deflating** — sounds like Sighing exhale, downward trailing intonation, slack low-energy delivery that drains the air out.; wrong because Undercuts news the responder themselves just brought as good, and dismisses the other's genuine reaction.
- **Amused teasing at the gasp** — sounds like Chuckling through the words, playful sing-song lilt, mock-theatrical delivery aimed at the gasp itself.; wrong because Makes the other speaker's reaction the joke, when the gasp was sincere shock about a real chance.

*Acceptable range:* Anything from bright shared excitement to brisk practical urgency to calm steady reassurance works, at high or quite contained energy.

---

## v6_04b · condition_a · `sigh`

**Scenario:** A parent has spent hours making a cake for her daughter, only to find it gone before she can serve it.

1. **A:** The cake was on the counter when I left the kitchen. Now the stand's empty.
2. **B:** Has anybody been in the house since you finished it?
3. **A:** Maya left early for school. I've messaged her twice, but she hasn't answered.
4. **B:** Her phone's under this chair. There's a new photo notification—look, it's Maya carrying the cake into the school fair.
5. **A:** (sighs) She took the whole cake to the school fair.

**Framing the planner intended:** The parent accepts that her work was taken without asking, while recognizing that the cake is at least being used.

### Acceptable interpretations

1. **Exasperated relief that the mystery is solved but the cake is gone for good** — Closes the search and marks the outcome as settled rather than still investigable
2. **Resignation at a daughter's characteristic impulsiveness she has no real recourse against** — Signals the complaint is being absorbed, not escalated into blame or a call to the school
3. **Deflated dismay at losing work she had put into the cake, tempered by understanding why** — Invites B's sympathy while conceding the taking wasn't malicious

*Shared implication (the line a wrong answer crosses):* The speaker accepts what happened rather than suspecting theft or wrongdoing; she is not delighted, and not treating the cake's fate as still open.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Confirms the mystery is solved and closes the search

- must convey: Treats the question of where the cake went as now answered and settled
- must convey: Acknowledges the cake itself is gone — not retrievable or replaceable today
- must avoid: Proposing further investigation, calling the school, or asking who else might have taken it
- must avoid: Treating the outcome as still uncertain or the cake as recoverable
- example (never a similarity target): *Well, that's that mystery over. No getting it back now — it's probably half eaten already.*

**Under interpretation 2** — Absorbs the complaint, treats it as typical Maya, defuses blame

- must convey: Recognises this as in character for Maya rather than a serious wrong
- must convey: Signals no further action against her — no confrontation, punishment, or escalation
- must avoid: Framing Maya as deceitful or urging that she be confronted or disciplined
- must avoid: Turning it into a broader grievance about her behaviour or A's parenting
- example (never a similarity target): *Classic Maya. She'd have thought you'd made it for exactly that. Not worth a row over it.*

**Under interpretation 3** — Sympathises with the lost effort while excusing Maya's intent

- must convey: Acknowledges the work A put into the cake and that losing it stings
- must convey: Grants that Maya meant no harm — she wasn't taking it to be sneaky
- must avoid: Dismissing the effort with 'it's only a cake' or rushing A past the disappointment
- must avoid: Attributing bad intent to Maya, which would undercut the tempering understanding
- example (never a similarity target): *After all that work on it, too. She won't have thought twice — she'd just have been proud to bring it in.*

### Tones that would be clearly wrong

- **Alarmed urgency** — sounds like Sharp, fast onset, rising pitch, clipped breathy delivery like reacting to an emergency or bad news breaking.; wrong because The mystery just resolved harmlessly; the sigh releases tension rather than raising it.
- **Bright chirpy cheer** — sounds like Peppy, upswinging, smiling-through-every-word delivery with announcer-like energy, as if sharing delightful news.; wrong because Overshoots the deflated, mildly exasperated valence of the sigh and reads as tone-deaf enthusiasm.
- **Grave, heavy condolence** — sounds like Slow, hushed, weighted delivery with sombre downward contours, the register used for genuine loss or bad diagnoses.; wrong because Treats a missing cake as a serious misfortune, inflating a small domestic annoyance into grief.
- **Dismissive impatience** — sounds like Flat, clipped, faintly exasperated-at-the-listener delivery, sighing back or trailing off as though the topic is tiresome.; wrong because Turns shared exasperation into irritation aimed at the speaker, withdrawing from a moment they invited.

*Acceptable range:* Wry amusement, gentle warmth, dry matter-of-factness, quiet commiseration, or a soft laugh all fit, at low-to-moderate energy.

---

## v6_04b · condition_b · `gasp`

**Scenario:** A parent has spent hours making a cake for her daughter, only to find it gone before she can serve it.

1. **A:** The cake was on the counter when I left the kitchen. Now the stand's empty.
2. **B:** Has anybody been in the house since you finished it?
3. **A:** Maya left early for school. I've messaged her twice, but she hasn't answered.
4. **B:** Her phone's under this chair. There's a new photo notification—look, it's Maya carrying the cake into the school fair.
5. **A:** (gasps) She took the whole cake to the school fair.

**Framing the planner intended:** The parent is abruptly struck by the unexpected discovery that the missing cake has appeared at the school fair.

### Acceptable interpretations

1. **Shocked recognition that Maya took the entire cake without asking.** — Marks the photo as the answer and registers the discovery as a violation.
2. **Startled dismay at losing the whole cake she made, not just a slice.** — Foregrounds the scale of the loss and invites B to share the alarm.
3. **Surprise mixed with relief that the cake is accounted for rather than stolen or ruined.** — Closes the mystery while flagging that the outcome is still not okay.

*Shared implication (the line a wrong answer crosses):* The photo is new, unexpected information that resolves the missing cake; the speaker is not calm, unmoved, or already aware of what Maya did.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Confirm the discovery and treat it as needing addressing

- must convey: Agreement that Maya took it without asking, treating that as the point
- must convey: Something concrete about what happens next — reaching her, the fair, talking to her
- must avoid: Laughing it off or framing Maya's choice as harmless or cute
- must avoid: Softening into pure mystery-solved relief with no acknowledgement she overstepped
- example (never a similarity target): *She didn't ask you once. The fair runs till four — want to head over, or wait and have it out with her tonight?*

**Under interpretation 2** — Match the dismay about the whole cake being gone

- must convey: Recognition of the scale — the entire cake, not a slice, and A made it
- must convey: Some response to the loss itself: sympathy, or what can be salvaged
- must avoid: Minimising the loss or telling A it's only a cake
- must avoid: Redirecting straight to Maya's misconduct without registering what A lost
- example (never a similarity target): *The whole thing? After you were up half the night on it. Maybe there's some left by now — I can drive over and see.*

**Under interpretation 3** — Close the mystery while keeping the problem open

- must convey: The cake is accounted for — no theft, nothing ruined, Maya is fine
- must convey: It still isn't okay, so something is owed or needs sorting out
- must avoid: Declaring the matter settled and dropping it entirely
- must avoid: Treating it as alarming or unresolved when the photo explains everything
- example (never a similarity target): *Well, at least we know where it went and nobody's run off with it. Doesn't mean she gets away with it, though.*

### Tones that would be clearly wrong

- **Alarmed, emergency-pitched escalation** — sounds like Sharp, loud, fast onset; tight throat, urgent clipped delivery as though reporting danger or a genuine crisis.; wrong because The mystery has just resolved harmlessly; treating the reveal as threatening overshoots a moment that has released its tension.
- **Flat, disengaged monotone** — sounds like Even pitch, no lift or fall, unhurried and affectless, as if reading an unrelated line off a page.; wrong because Registers nothing of the sudden reveal the other speaker just reacted to, leaving the gasp hanging unacknowledged.
- **Patronising, soothing-the-child warmth** — sounds like Slowed, softened, singsong lilt with drawn-out vowels, the cadence used to calm someone who is overreacting.; wrong because Casts the other speaker as needing management rather than as a partner who just solved the puzzle with you.
- **Cold dismissal or scoffing flatness** — sounds like Clipped, downward-tailing delivery, possibly a short exhale through the nose; brisk and closed, shutting the exchange down.; wrong because Brushes off a discovery both speakers were actively working toward, treating the other's surprise as not worth meeting.

*Acceptable range:* Anything from quiet dawning realisation to amused disbelief to relieved exhalation works, at low or lively energy, with or without a laugh.

---

## v6_04c · condition_a · `sigh`

**Scenario:** Two caregivers deal with their daughter after she damages a tooth during play.

1. **A:** Mia fell off the climbing frame at the park.
2. **B:** Is she hurt? Does she need anything?
3. **A:** She stopped crying, but she hasn't said much since.
4. **B:** Mia, come here. Open your mouth for Mum.
5. **A:** (sighs) Okay. Let's call the dentist.

**Framing the planner intended:** The discovery becomes another difficult family problem the speaker immediately settles in to handle.

### Acceptable interpretations

1. **Reluctant acceptance that the injury is worse than hoped and needs professional care** — Concedes B's implicit finding and marks the dentist call as an unwelcome but settled next step
2. **Weariness at another disruption on top of an already draining afternoon** — Registers the cost of the errand before agreeing to it, without contesting the need
3. **Worry about Mia's teeth mixed with relief that the silence finally has an explanation** — Braces the pair for the next step while signalling the guessing phase is over

*Shared implication (the line a wrong answer crosses):* The speaker accepts that calling the dentist is necessary; the sound is not dismissal, disagreement with B, or amusement about Mia's fall.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Confirms the finding and takes the dentist call forward

- must convey: Confirms something is actually wrong with the tooth or mouth, so the call is warranted
- must convey: Moves the call forward concretely — who rings, when, which practice
- must avoid: Re-opening whether a dentist is needed, or hedging that it may be nothing
- must avoid: Treating A's sigh as resistance that needs persuading or arguing against
- example (never a similarity target): *Yeah, there's a chip on the front one. I'll ring them now — they should still be open for another hour.*

**Under interpretation 2** — Acknowledges the drain and absorbs part of the errand

- must convey: Recognises this lands on top of an already hard afternoon for A
- must convey: Offers to carry some of it — making the call, driving, handling the rest of the evening
- must avoid: Skipping past A's tiredness straight into logistics as if nothing was expressed
- must avoid: Making the weariness the topic — dwelling on how exhausted A must be
- example (never a similarity target): *I know, it's been a day. Let me phone them and take her over — you sit down for ten minutes.*

**Under interpretation 3** — Names what's found and steadies both about the outcome

- must convey: States plainly what the mouth shows, closing off the guessing about her silence
- must convey: Frames the outlook as manageable — this is fixable, they now know what to deal with
- must avoid: Leaving the finding vague so the uncertainty A just escaped is reintroduced
- must avoid: False cheer that denies there's anything to be concerned about with her teeth
- example (never a similarity target): *That's why she's gone quiet — a tooth's loose at the front. They're good with this at her age. Let's get her seen.*

### Tones that would be clearly wrong

- **Alarmed, urgent escalation** — sounds like Fast, tight, rising delivery with sharp breath intake and clipped emphasis, as though announcing an emergency.; wrong because The sigh signals weary acceptance of a manageable hassle, not crisis; urgency escalates past what the moment holds.
- **Bright, chirpy cheerfulness** — sounds like Lifted, sing-song energy with an upbeat lilt and smile audible through the voice.; wrong because Brightness contradicts the deflated valence of the sigh and reads as ignoring the other speaker's fatigue.
- **Amused, teasing lightness** — sounds like Laughter in the voice, playful bounce, or a chuckle riding under the words.; wrong because Treats a resigned exhalation about a hurt child as a shared joke, misreading its valence entirely.
- **Patronising soothing coo** — sounds like Exaggeratedly soft, drawn-out, singsong comforting pitched as if speaking to a small child.; wrong because Casts the fellow adult as needing management; the sigh invites shared practicality, not being talked down to.

*Acceptable range:* Anything from a quiet matching exhale to calm steady practicality, gentle warmth, or brisk get-on-with-it resolve is fine.

---

## v6_04c · condition_b · `gasp`

**Scenario:** Two caregivers deal with their daughter after she damages a tooth during play.

1. **A:** Mia fell off the climbing frame at the park.
2. **B:** Is she hurt? Does she need anything?
3. **A:** She stopped crying, but she hasn't said much since.
4. **B:** Mia, come here. Open your mouth for Mum.
5. **A:** (gasps) Okay. Let's call the dentist.

**Framing the planner intended:** The discovery becomes a sudden, alarming visual realization that interrupts the speaker before they respond.

### Acceptable interpretations

1. **Alarm at seeing damage inside Mia's mouth the moment she opens it** — Marks the injury as confirmed and serious, motivating the immediate call to the dentist
2. **Sudden realisation of why Mia went quiet after the fall** — Signals the discovery to B without describing it, closing the earlier question about what is wrong
3. **Dismay held in check, worried but staying composed in front of the child** — Registers the shock briefly, then hands over to a practical next step rather than escalating

*Shared implication (the line a wrong answer crosses):* A has just seen something newly bad in Mia's mouth; the sound escalates concern and cannot be relief, reassurance, or amusement.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Treats injury as confirmed; moves to act on it now

- must convey: Agreement that the dentist is needed, or a move to make that happen immediately
- must convey: Some acknowledgement of what A has just seen in Mia's mouth
- must avoid: Questioning whether it is bad enough to bother a dentist about
- must avoid: Downplaying, or suggesting they wait and see how it looks tomorrow
- example (never a similarity target): *Yeah, that's a chipped tooth. I'll ring them now — grab her shoes and the car keys.*

**Under interpretation 2** — Registers the answer to the earlier question, closes the puzzle

- must convey: Recognition that this explains why Mia had gone quiet since the fall
- must convey: Uptake of the dentist plan as following from that
- must avoid: Asking again what is wrong as though nothing has been established
- must avoid: Reading the gasp as unrelated to Mia's silence
- example (never a similarity target): *That's why she's been so quiet, then. No wonder. Right — dentist. Where's their number?*

**Under interpretation 3** — Matches A's composure and takes on the practical next step

- must convey: Acceptance of the dentist plan without adding alarm in front of Mia
- must convey: Something steadying — toward Mia, or toward A, or a concrete task taken on
- must avoid: Amplifying the shock or dramatising the injury while Mia is listening
- must avoid: Naming A's reaction or Mia's state as the topic instead of just carrying on
- example (never a similarity target): *Good idea. Mia, you're alright, love — we'll get it looked at. I'll call while you find her coat.*
- writer's note: Differs from 1 mainly in what B withholds: same practical uptake, but held down for the child's benefit rather than treated as confirmation.

### Tones that would be clearly wrong

- **Amused or lightly laughing** — sounds like Breathy chuckle or smile in the voice, playful lift on the words, delivery that treats the gasp as funny.; wrong because Reads the gasp as comic surprise rather than the alarmed recognition of something wrong in a hurt child's mouth.
- **Panicked, escalating alarm** — sounds like Sharp intake, rising pitch and volume, rushed clipped phrasing, audible tremor as if announcing an emergency.; wrong because Amplifies the shock past what the moment holds; the parent has already steadied toward a next step, not spiralled.
- **Flat, perfunctory detachment** — sounds like Level monotone, no change in pace or warmth from earlier turns, words delivered like a scheduling note.; wrong because Registers nothing at all in response to a gasp, as though the discovery had not landed.
- **Patronising soothing at the adult** — sounds like Cooing sing-song, drawn-out vowels, shushing hush, over-soft cadence of the kind used to calm a small child.; wrong because Treats the co-parent as needing to be managed rather than as someone seeing the same thing.

*Acceptable range:* Anything from a quiet, steady, concerned register to a visibly startled but collected one is fine, whether brisk and practical or slow and hushed.

---

## v6_04d · condition_a · `sigh` · **rev 2**

**Scenario:** Two friends check one friend's lottery ticket together after the winning numbers have been announced.

1. **A:** Did you keep the ticket I picked up earlier?
2. **B:** It's right here. The winning numbers are up—want to check it together?
3. **A:** Okay. Four, seventeen, twenty-six... those are all on mine.
4. **B:** And the last one is thirty-eight. Your ticket has thirty-eight too—and the name on it is yours.
5. **A:** (sighs) That's my ticket?

**Framing the planner intended:** The win ends a period of financial uncertainty but immediately feels weighty and consequential to the ticket owner.

### Acceptable interpretations

1. **Stunned disbelief at learning the winning ticket is genuinely hers** — Registers the news as momentous and prompts B to confirm it again
2. **Overwhelm releasing as breath before the good news can be processed** — Marks the moment as too large to respond to plainly, buying a beat
3. **Cautious hope mixed with fear of a mistake in the reading** — Hedges her reaction pending confirmation rather than celebrating outright

*Shared implication (the line a wrong answer crosses):* The sound does not express disappointment, boredom, or resignation; the speaker treats the match as significant and is seeking confirmation, not deflating it.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Confirms the win plainly and re-verifies the match for her

- must convey: An unambiguous yes — the ticket is hers and it matches
- must convey: A concrete re-check offered or performed, e.g. reading the numbers or name back
- must avoid: Treating the sigh as bad news or asking whether she is disappointed
- must avoid: Leaving the confirmation vague or hedged so she still doesn't know
- example (never a similarity target): *Yes — four, seventeen, twenty-six, thirty-eight, all five. And your name's printed right there. That's yours.*

**Under interpretation 2** — Stays with her, giving the moment room before anything practical

- must convey: Acknowledgement that this is enormous and she doesn't have to react yet
- must convey: Presence or a steadying beat rather than immediate next steps
- must avoid: Rushing into logistics like claiming, banks, taxes, or who to tell
- must avoid: Demanding she explain or perform a reaction right now
- example (never a similarity target): *Take a second. I know. Sit down if you want — it's not going anywhere. I'll be right here.*
- writer's note: Differs from 1 by holding the beat rather than re-confirming, and from 3 by not re-verifying.

**Under interpretation 3** — Meets the caution by checking the reading again before celebrating

- must convey: Acknowledgement that it's worth being sure, treating the doubt as reasonable
- must convey: A specific verification step — recheck the draw, date, or numbers side by side
- must avoid: Dismissing her worry or insisting she just accept it
- must avoid: Declaring victory outright without addressing the possibility of a misread
- example (never a similarity target): *Fair — let's do it once more. I'll pull up tonight's draw and you read the ticket out, number by number, and the date too.*

### Tones that would be clearly wrong

- **Flat, unmoved bureaucratic confirmation** — sounds like Even, clipped delivery with no lift or warmth, like reading a number back off a form.; wrong because Treats a life-changing, disbelieving moment as routine data entry, leaving the other person's stunned reaction unmet.
- **Dismissive brush-off** — sounds like Short, throwaway delivery with a shrug in the voice, trailing off as if the topic is closing.; wrong because Waves away a moment the speaker is visibly struggling to absorb, and their sigh invites acknowledgment, not dismissal.
- **Alarmed or panicked urgency** — sounds like Tight, fast, high-strung voice with sharp breath, as though reporting an emergency or bad news.; wrong because Reads the sigh as distress or catastrophe rather than the overwhelm of something extraordinary and good.
- **Patronising soothing** — sounds like Slow, singsong, caregiver-style softening, as if calming a distressed child.; wrong because Casts an adult peer as fragile and needing management, a stance the moment does not license.

*Acceptable range:* Anything from hushed disbelief to bright excitement to a quiet steady confirmation works, as long as the delivery registers that something remarkable just happened.

---

## v6_04d · condition_b · `gasp` · **rev 2**

**Scenario:** Two friends check one friend's lottery ticket together after the winning numbers have been announced.

1. **A:** Did you keep the ticket I picked up earlier?
2. **B:** It's right here. The winning numbers are up—want to check it together?
3. **A:** Okay. Four, seventeen, twenty-six... those are all on mine.
4. **B:** And the last one is thirty-eight. Your ticket has thirty-eight too—and the name on it is yours.
5. **A:** (gasps) That's my ticket?

**Framing the planner intended:** The matching ticket is received as an astonishing reversal, making the owner’s question a startled check of what they heard.

### Acceptable interpretations

1. **Shocked elation at realising the winning ticket is genuinely hers.** — Marks the news as life-changing and invites B to confirm and share the moment.
2. **Stunned disbelief, unable to accept the match is real yet.** — Suspends acceptance and presses B to verify the claim before she commits to it.
3. **Overwhelmed, joy mixed with panic at what such a win means.** — Signals she needs a beat before responding, handing the floor back to B.

*Shared implication (the line a wrong answer crosses):* She registers the win as real and startling news; the sound is not skepticism about B, boredom, dread of bad news, or a joke.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Confirms the win and shares the excitement with her

- must convey: Affirms the ticket is hers and it matches
- must convey: Joins her reaction rather than staying flat or neutral
- must avoid: Hedging or casting doubt on the match after already confirming it
- must avoid: Jumping straight to money logistics, taxes, or claim procedures
- example (never a similarity target): *Yes! It's yours — every number, your name on it. You just won.*

**Under interpretation 2** — Verifies the match again so she can believe it

- must convey: Re-checks or re-reads the numbers and name against the draw
- must convey: States plainly that it does check out
- must avoid: Brushing off the doubt with mere excitement instead of checking
- must avoid: Introducing new uncertainty about whether the ticket is valid
- example (never a similarity target): *Hold on, let me read them again — four, seventeen, twenty-six, thirty-eight. All there. And that's your name.*

**Under interpretation 3** — Steadies her and gives her room before anything else

- must convey: Signals there's no rush and she can take a moment
- must convey: Offers something concrete and grounding — sit down, keep the ticket safe
- must avoid: Escalating the intensity or piling on what she must decide now
- must avoid: Treating her silence as a cue to press for a reaction
- example (never a similarity target): *Okay — sit down a second. Nothing has to happen tonight. I'll put the ticket somewhere safe and we'll figure it out.*

### Tones that would be clearly wrong

- **Flat, unmoved neutrality** — sounds like Even, level delivery with no lift or energy change from earlier turns; reads like confirming a grocery item.; wrong because Treats a life-changing shock as routine information, leaving the other speaker's gasp hanging unmet.
- **Alarmed or fearful urgency** — sounds like Tight, sharp, breath-caught voice with rising panic; the pitch of bad news breaking.; wrong because Misreads a positive shock as danger, converting a windfall into an emergency.
- **Dismissive or teasing brush-off** — sounds like Flat drawl, light scoff or eye-roll audible in the voice, trailing off as if unimpressed.; wrong because Belittles a genuinely astonishing moment the responder just helped confirm and was equally invested in.
- **Soothing, patronising calm** — sounds like Slow, hushed, downward-settling delivery, as if gentling someone who is overreacting.; wrong because Frames the gasp as distress needing management rather than warranted amazement.

*Acceptable range:* Anything from an explosive shared shout to a stunned, quiet, breath-held disbelief works, as long as astonishment is audible and positive.

---

## v6_05a · condition_a · `sigh`

**Scenario:** A dog owner is practicing obedience training and has begun seeing improvement, though counter behavior remains unreliable.

1. **A:** I've been doing short obedience sessions with Max every day.
2. **B:** Which commands are starting to stick?
3. **A:** He's been leaving food alone when I say "leave it," at least when I'm right there.
4. **B:** Max is heading for the snack on the counter.
5. **A:** (sighs) He just took it. I thought he'd learned "leave it."

**Framing the planner intended:** The lapse is a discouraging but familiar part of gradual training, which the owner accepts as more work ahead.

### Acceptable interpretations

1. **Deflated disappointment that Max's training has not held up when it counted.** — Concedes the setback before reporting it, framing the theft as a letdown rather than news.
2. **Weary resignation that the work will have to continue longer than hoped.** — Signals that A expected better progress and is bracing for more sessions, inviting sympathy.
3. **Mild exasperation at the dog mixed with self-directed recognition that A overestimated the training.** — Softens the admission that A's earlier confident claim was premature.

*Shared implication (the line a wrong answer crosses):* A treats the outcome as an unwelcome failure of the training, not as amusing, surprising-in-a-good-way, or indifferent; the sound concedes rather than boasts.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Acknowledges the letdown and puts the single lapse in perspective

- must convey: Recognition that the theft is a genuine disappointment after A's earlier progress
- must convey: Something that keeps the setback proportionate — one slip, not the training undone
- must avoid: Treating it as funny, cute, or a good story about the dog
- must avoid: Launching into training advice or next steps instead of registering the letdown
- example (never a similarity target): *Ugh, right when you'd just said he had it. One counter snack doesn't undo three weeks of "leave it" though.*

**Under interpretation 2** — Sympathises with the long haul and encourages continuing

- must convey: Sympathy that the work is taking longer than A hoped
- must convey: Something supportive about the ongoing effort — that more sessions will get there
- must avoid: Implying A should give up or that Max will not learn it
- must avoid: Skipping the sympathy and moving straight to praise for the dog or the theft itself
- example (never a similarity target): *That's the annoying part — it's weeks more of the same drill. You've clearly got it moving, though. Keep going.*

**Under interpretation 3** — Lets A off the hook for having claimed the training worked

- must convey: Acknowledgement that A's earlier confidence was reasonable given what they'd seen
- must convey: That the gap between supervised and unsupervised "leave it" is expected, not A's misjudgment
- must avoid: Agreeing that A was wrong to claim progress or pointing out they said it too soon
- must avoid: Piling on about the dog's behaviour without addressing A's own admission
- example (never a similarity target): *You did see him do it, though — with you standing right there. Off-leash and unsupervised is a whole separate thing to teach.*

### Tones that would be clearly wrong

- **Bright celebratory cheer** — sounds like Upswinging, grinning delivery with excited emphasis and lifted final pitch, the voice you'd use for good news.; wrong because Reads a deflated moment as a win; the sigh signals disappointment, not something to be pleased about.
- **Alarmed urgency** — sounds like Sharp, fast, raised volume with a startled catch, as if reporting an emergency.; wrong because Escalates a minor training setback into a crisis far beyond the low-key resignation the sigh conveys.
- **Flat dismissive brush-off** — sounds like Clipped, uninflected, low-energy delivery that trails off, no warmth or acknowledgement in the voice.; wrong because Treats the speaker's audible deflation as not worth responding to, withholding any recognition of the moment.
- **Sing-song patronising soothing** — sounds like Exaggerated cooing melody, drawn-out vowels, pitch lifted as if comforting a small child.; wrong because Condescends over an ordinary small frustration, treating the speaker as needing consolation rather than commiseration.

*Acceptable range:* Wry amusement, warm sympathy, matter-of-fact commiseration, a light laugh, or a quiet understated remark all work; energy may be low or moderately animated.

---

## v6_05a · condition_b · `groan`

**Scenario:** A dog owner is practicing obedience training and has begun seeing improvement, though counter behavior remains unreliable.

1. **A:** I've been doing short obedience sessions with Max every day.
2. **B:** Which commands are starting to stick?
3. **A:** He's been leaving food alone when I say "leave it," at least when I'm right there.
4. **B:** Max is heading for the snack on the counter.
5. **A:** (groans) He just took it. I thought he'd learned "leave it."

**Framing the planner intended:** The lapse feels like an exasperating immediate reversal, making the owner focus on the nuisance of having to address it again.

### Acceptable interpretations

1. **Dismay at watching the training fail exactly when it counted** — Registers the setback in real time before the words explain it
2. **Frustration with himself for trusting the command was reliably learned** — Concedes his earlier optimistic report was overstated
3. **Rueful, half-amused exasperation at the dog's predictable opportunism** — Softens the failure into a shared complaint rather than a real crisis

*Shared implication (the line a wrong answer crosses):* The speaker treats the theft as an unwelcome setback to his claim about Max's training, not as success, indifference, or approval.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Register the loss with him and address the immediate moment

- must convey: Acknowledges the theft just happened and that it was a setback
- must convey: Points at something immediate — the snack, getting it back, whether it's safe for the dog
- must avoid: Treating the moment as funny or as a joke to riff on
- must avoid: Lecturing about training method before acknowledging what just happened
- example (never a similarity target): *Ah, he got it. Was that the chocolate one? Grab it off him if you can.*

**Under interpretation 2** — Push back gently on his self-blame; reframe the setback

- must convey: Signals he wasn't wrong to be encouraged — the earlier progress still counts
- must convey: Frames "leave it" as partly learned rather than failed, e.g. context-dependent
- must avoid: Agreeing he over-claimed or that the training was worthless
- must avoid: Empty cheerleading with no reason attached to it
- example (never a similarity target): *You did say it only holds when you're standing right there. Counter height with nobody watching is a totally different ask.*

**Under interpretation 3** — Join the rueful complaint about the dog's opportunism

- must convey: Treats the theft as characteristic of Max rather than as a real failure
- must convey: Adds to the shared complaint — a comparable dog moment or a dry read of his motives
- must avoid: Treating it as a serious problem needing reassurance or a fix
- must avoid: Deflating the shared joke by turning to earnest training advice
- example (never a similarity target): *He was never going to leave that. He was just waiting for you to say the word so he could ignore it properly.*

### Tones that would be clearly wrong

- **Alarmed, emergency-pitched urgency** — sounds like Sharp intake, raised volume, clipped fast delivery as if reporting danger or an accident in progress.; wrong because A dog stealing a snack is a small setback; alarm treats a minor training lapse as a crisis.
- **Bright chirpy cheerfulness** — sounds like Upswinging, peppy singsong delivery with smiling brightness, like announcing good news at the top of the turn.; wrong because Ignores the deflation in the groan and answers frustration with unearned brightness.
- **Flat dismissive indifference** — sounds like Monotone, low-energy, faintly bored throwaway delivery with no warmth or engagement in the voice.; wrong because Reads the groan as unworthy of response, withholding any acknowledgement from a speaker who just expressed frustration.
- **Patronising soothing coo** — sounds like Slow, syrupy, over-soft consoling voice with exaggerated sympathetic dips, as if comforting a distressed child.; wrong because Inflates mild exasperation into real distress and takes a talking-down stance the moment does not license.

*Acceptable range:* Wry amusement, mild commiseration, dry matter-of-factness, a sympathetic sigh, or brief warm understatement are all fine; energy may be low or lively.

---

## v6_05b · condition_a · `sigh` · **rev 2**

**Scenario:** Two people arrange tomorrow's visit to one speaker's favorite restaurant, but the available booking time is inconveniently late.

1. **A:** Are we still doing Bellini's tomorrow?
2. **B:** Yeah, I called to see if I could get us a table.
3. **A:** What times did they have?
4. **B:** Everything earlier was taken. The only table left is at 9:45.
5. **A:** (sighs) Okay. Let's take it.

**Framing the planner intended:** The speaker lets go of their preferred timing and accepts the late meal because going to the restaurant still matters.

### Acceptable interpretations

1. **Mild disappointment that 9:45 is later than A wanted to eat** — Registers the late slot as a downside before A agrees to it anyway
2. **Reluctant acceptance — A is resigning themselves to the only option available** — Marks the agreement as a concession rather than an enthusiastic yes
3. **Weariness at the hassle, mixed with acknowledgement that B did what they could** — Vents the annoyance at the situation while leaving B's effort uncriticised

*Shared implication (the line a wrong answer crosses):* A is going along with the 9:45 booking; the sound conveys displeasure at the time, not refusal, blame toward B, or a request to cancel.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Acknowledge the late time, confirm booking anyway

- must convey: Recognition that 9:45 is later than they'd have liked to eat
- must convey: Confirmation that B will lock in that table
- must avoid: Treating the sigh as reluctance needing persuasion or a pitch for the plan
- must avoid: Cancelling, reopening the decision, or asking whether A really wants to go
- example (never a similarity target): *Yeah, it's a late one. I'll grab it — we can get a snack beforehand if you're starving.*

**Under interpretation 2** — Accept the concession; offer an out or alternative

- must convey: Recognition that A is settling rather than genuinely happy with this
- must convey: Something concrete — book it, or name another night or place if A prefers
- must avoid: Ignoring the reluctance and booking as though A said yes eagerly
- must avoid: Pushing A to justify or explain their hesitation
- example (never a similarity target): *We don't have to force it. I'll take the 9:45, but say the word and I'll try Thursday instead.*
- writer's note: Differs from 1 by treating the yes as provisional and leaving a door open, not just noting the hour.

**Under interpretation 3** — Commiserate about the hassle; note effort was made

- must convey: Shared annoyance directed at the restaurant or the scramble, not at A or B
- must convey: Confirmation the 9:45 is going ahead
- must avoid: Defensiveness or justifying B's own effort as if A had criticised it
- must avoid: Apologising at length or taking the sigh as blame
- example (never a similarity target): *I know, it was slim pickings — that place books out fast. Booking the 9:45 now.*

### Tones that would be clearly wrong

- **Bright, chirpy enthusiasm** — sounds like Upbeat lift on the first word, sing-song rise, smiling delivery as if delivering good news.; wrong because Treats a resigned sigh as shared excitement, ignoring the mild disappointment A just expressed about the late slot.
- **Alarmed or apologetic distress** — sounds like Tight, rushed, higher-strung voice with anxious over-emphasis, as though something serious went wrong.; wrong because Escalates a minor scheduling annoyance into a crisis; the sigh signals small resignation, not upset needing repair.
- **Clipped, dismissive flatness** — sounds like Curt, dropped-off delivery with no warmth, cutting in fast as if the exchange is a nuisance.; wrong because Reads A's sigh as complaining and brushes it aside, refusing the small acknowledgement the moment invites.
- **Patronising soothing** — sounds like Slowed, cooing, sing-song comfort voice with exaggerated gentleness, as if consoling a child.; wrong because Overweights a mild sigh into something needing consolation, condescending to an adult over a dinner time.

*Acceptable range:* Anything from a wry, light-amused shrug to a plain, matter-of-fact confirmation to a warm, low-key commiserating delivery works fine here.

---

## v6_05b · condition_b · `groan` · **rev 2**

**Scenario:** Two people arrange tomorrow's visit to one speaker's favorite restaurant, but the available booking time is inconveniently late.

1. **A:** Are we still doing Bellini's tomorrow?
2. **B:** Yeah, I called to see if I could get us a table.
3. **A:** What times did they have?
4. **B:** Everything earlier was taken. The only table left is at 9:45.
5. **A:** (groans) Okay. Let's take it.

**Framing the planner intended:** The speaker treats the late reservation as an irritating obstacle and accepts it under protest.

### Acceptable interpretations

1. **Dismay at a dinner slot far later than she wanted** — Registers the time as a real cost before she nonetheless agrees to it
2. **Tired reluctance about staying up late, outweighed by wanting the dinner** — Marks the acceptance as a concession rather than an enthusiastic yes
3. **Mild exasperation at the restaurant's booking situation, not at B** — Vents about the constraint while signaling B did nothing wrong in taking it

*Shared implication (the line a wrong answer crosses):* The speaker finds 9:45 undesirable and accepts it anyway; the sound is not approval, not indifference, and not a complaint about B's handling.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Acknowledges the late slot's cost while confirming the booking

- must convey: Recognizes 9:45 is later than she wanted and treats that as legitimate
- must convey: Confirms taking the table, or offers to keep looking for something earlier
- must avoid: Treating the groan as criticism of B and getting defensive about the call
- must avoid: Talking her out of the reaction or insisting 9:45 is actually fine
- example (never a similarity target): *Yeah, it's brutal. I'll lock it in, but I'll call back in the morning in case something opens up earlier.*

**Under interpretation 2** — Acknowledges the tiredness and eases the late night

- must convey: Registers that a 9:45 dinner means a late night for her
- must convey: Offers something concrete about the lateness, or explicitly leaves the door open to skipping
- must avoid: Ignoring the tiredness and just confirming logistics as if she'd said yes happily
- must avoid: Pushing her to commit enthusiastically or hyping up the evening
- example (never a similarity target): *It'll be a late one, I know. If you're wiped tomorrow we can push it to the weekend — otherwise I'll book it and we can cab home.*
- writer's note: Differs from 1 by responding to her state, not the slot itself.

**Under interpretation 3** — Joins the gripe about the restaurant, confirms the booking

- must convey: Shares or endorses the annoyance at how hard the place is to get into
- must convey: Confirms she's taking it and treats it as settled
- must avoid: Apologizing or explaining B's handling as if blame had been assigned
- must avoid: Checking on her mood or wellbeing, which overreads a gripe about the restaurant
- example (never a similarity target): *Right? You basically need to call a month out for that place. Booking it now before someone else grabs it.*

### Tones that would be clearly wrong

- **Bright chirpy enthusiasm** — sounds like Upswinging, smiley delivery with lifted energy, as if announcing good news about the late table.; wrong because Treats the groan as agreement or excitement, ignoring the audible displeasure at the only remaining time.
- **Alarmed or distressed urgency** — sounds like Tightened, fast, higher-pressure voice with worried breathiness, as though something has gone seriously wrong.; wrong because Escalates a small scheduling annoyance into a crisis the groan and the calm follow-up do not signal.
- **Clipped dismissiveness or irritation** — sounds like Flat, curt, edged delivery, slight sigh of impatience, cutting off warmth as if the groan were an imposition.; wrong because Takes an adversarial stance toward a mild complaint that was immediately followed by cooperation.
- **Patronising soothing** — sounds like Slow, sing-song, over-gentle consoling voice, the kind used to settle a upset child.; wrong because Treats a minor gripe as real hurt needing comfort, condescending to an adult who already agreed.

*Acceptable range:* Wry commiseration, a light apologetic shrug, matter-of-fact confirmation, a small shared sigh, or dry amusement all work; brief and understated is fine.

---

## v6_05c · condition_a · `sigh`

**Scenario:** Two companions arrive for Blizzards, but the person checking the entrance discovers the shop has already closed.

1. **A:** After today, I could really go for a Blizzard. Want to stop at Dairy Queen?
2. **B:** I've been thinking about one all afternoon.
3. **A:** The parking lot's almost empty. Maybe we're late.
4. **B:** The hours are hard to read from here. Can you check the door?
5. **A:** (sighs) It's locked. The notice says they closed at nine.

**Framing the planner intended:** The closure is an unfortunate letdown the final speaker accepts, with weary resignation rather than blame.

### Acceptable interpretations

1. **Deflated disappointment at missing the Blizzard both of them had been anticipating all afternoon.** — Delivers the bad news' emotional verdict before the words, priming B for a letdown.
2. **Resigned acceptance that they arrived too late and nothing can be done about it.** — Closes off the plan rather than inviting a fix, treating the outcome as settled.
3. **Weary letdown capping an already draining day that this small failure tops off.** — Ties the closed door to the day's accumulated fatigue, inviting shared commiseration.

*Shared implication (the line a wrong answer crosses):* The speaker takes the closure as an unwelcome outcome; the sound is not amusement, relief, indifference, or a prelude to proposing an alternative.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Sharing the disappointment about the missed Blizzard

- must convey: Registers the letdown as felt by both of them, not just A
- must convey: Names the missed Blizzard as what they had both wanted
- must avoid: Brushing it off as unimportant or lecturing A about planning ahead
- must avoid: Immediately pivoting to another dessert plan instead of registering the letdown
- example (never a similarity target): *Oh no. I had that Blizzard picked out in my head and everything.*

**Under interpretation 2** — Accepting the outcome and letting the plan close

- must convey: Agrees nothing can be done tonight given the closing time
- must convey: Lets the outing end rather than reopening it
- must avoid: Proposing alternatives, other locations, or rushing to fix the evening
- must avoid: Pressing A to check again, knock, or read the notice more carefully
- example (never a similarity target): *Figures. Nine's early. Let's just head home.*

**Under interpretation 3** — Commiserating about the whole day, not just this

- must convey: Connects the closed door to how draining the day has already been
- must convey: Signals solidarity with A about the day overall
- must avoid: Treating the closed door as the only problem worth acknowledging
- must avoid: Turning it into probing questions about what went wrong in A's day
- example (never a similarity target): *Of course it's closed. That is exactly how today has gone for us.*

### Tones that would be clearly wrong

- **Bright, upbeat cheer** — sounds like Lifted, smiling delivery with rising energy and a peppy lilt, as if hearing welcome news.; wrong because Treats a small shared letdown as something pleasing; the valence runs opposite to the sigh.
- **Alarmed or distressed urgency** — sounds like Tightened, fast, breathy delivery with sharp emphasis, as if reacting to bad news of real consequence.; wrong because Inflates a minor disappointment about a closed ice cream shop into something grave.
- **Flat, disengaged monotone** — sounds like Unvarying pitch, clipped and quick, no warmth or acknowledgement in the voice before moving on.; wrong because Reads the sigh as nothing, withholding the small shared recognition the moment invites.
- **Patronising soothing** — sounds like Slowed, cooing, sing-song comfort voice with softened consonants, the register used for consoling a child.; wrong because Takes a caretaking stance over a peer sharing an equally trivial letdown.

*Acceptable range:* Anything from a wry amused huff, to warm mild commiseration, to a quiet deflated murmur or a brief matter-of-fact shrug, works fine.

---

## v6_05c · condition_b · `groan`

**Scenario:** Two companions arrive for Blizzards, but the person checking the entrance discovers the shop has already closed.

1. **A:** After today, I could really go for a Blizzard. Want to stop at Dairy Queen?
2. **B:** I've been thinking about one all afternoon.
3. **A:** The parking lot's almost empty. Maybe we're late.
4. **B:** The hours are hard to read from here. Can you check the door?
5. **A:** (groans) It's locked. The notice says they closed at nine.

**Framing the planner intended:** The closure feels like an especially aggravating thwarting of a wanted treat after making the trip.

### Acceptable interpretations

1. **Disappointment at arriving too late for the Blizzard both of them had been anticipating all afternoon.** — Delivers the bad news before the words do, so B knows the outcome instantly.
2. **Frustration at the wasted trip and the poor luck of missing closing time.** — Registers the outing as a small failure and invites B's shared complaint.
3. **Half-comic dismay at a trivial letdown capping an already draining day.** — Marks the setback as commiseration-worthy without treating it as genuinely serious.

*Shared implication (the line a wrong answer crosses):* The speaker treats the closed store as an unwelcome outcome; the sound is not neutral reporting, relief, or indifference toward missing the Blizzard.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Take the news as settled and share the letdown

- must convey: Accepts that they've missed it and the Blizzard isn't happening tonight
- must convey: Matches A's disappointment or offers a concrete alternative for the craving
- must avoid: Asking A to re-check the door or repeat what the notice said
- must avoid: Treating the closure as fine, funny-only, or not worth minding
- example (never a similarity target): *Ah, no. And I'd been picturing it all afternoon. There's that place by the gas station — want to try that instead?*

**Under interpretation 2** — Join the complaint about the wasted trip and timing

- must convey: Agrees the drive out here was for nothing or the timing was rotten luck
- must convey: Registers annoyance alongside A rather than only sympathising with them
- must avoid: Implying A's slowness, the detour, or the late start caused the miss
- must avoid: Inflating a small annoyance into a long grievance about the place
- example (never a similarity target): *Nine? That's early. We drove all the way over here for a locked door. Of course that's how today ends.*

**Under interpretation 3** — Play along, commiserating lightly over a small last straw

- must convey: Keeps the setback small and shared rather than a real misfortune
- must convey: Nods to the day having earned them better than this
- must avoid: Heavy sympathy or consolation out of proportion to a missed dessert
- must avoid: Answering flatly with logistics and ignoring the wry, day-capping framing
- example (never a similarity target): *Naturally. Perfect end to a perfect day. Locked out of ice cream — that's the one thing today hadn't taken yet.*

### Tones that would be clearly wrong

- **Bright, upbeat cheer** — sounds like Lifted pitch, smiling delivery, energetic bounce on the words, as if announcing good news.; wrong because Reads a shared small disappointment as something pleasant; the responder wanted this too.
- **Alarmed or distressed urgency** — sounds like Sharp intake, tightened voice, rushed and loud, pitch climbing as though something serious happened.; wrong because Treats a closed ice cream shop as a crisis, wildly overshooting the stakes.
- **Flat clinical detachment** — sounds like Even, uninflected recitation with no warmth or downturn, pacing like reading a status readout.; wrong because Registers none of the shared letdown after a moment plainly asking for some acknowledgement.
- **Dismissive or scolding superiority** — sounds like Clipped, cool delivery, faint sigh of impatience or a told-you-so lilt directed at the other speaker.; wrong because Takes a stance against a companion who shares the disappointment rather than caused it.

*Acceptable range:* Anything from a commiserating sigh or wry amused huff to a brief deflated murmur or dry resigned understatement works fine here.

---

## v6_05d · condition_a · `sigh`

**Scenario:** Two people discuss encouraging economic signs while waiting for a rate decision that affects the final speaker’s upcoming mortgage.

1. **A:** Are you still following the latest figures?
2. **B:** The cafés downtown have been busy, and the new warehouse is hiring again.
3. **A:** The central bank's announcement is due at noon.
4. **B:** My mortgage paperwork is waiting, so I set an alert for it.
5. **A:** (sighs) Your phone says the central bank left its benchmark rate unchanged.

**Framing the planner intended:** The unchanged rate feels like a settled, manageable outcome after uncertainty, despite the speaker’s mortgage timing.

### Acceptable interpretations

1. **Deflation that the long-anticipated noon announcement turned out to be a non-event — no change at all.** — Frames the result as anticlimactic before stating it, deflating the stakes both speakers had built up.
2. **Resignation on B's behalf, since an unchanged rate leaves B's pending mortgage situation unimproved.** — Pre-marks the news as unwelcome, softening delivery of a result B was waiting on.
3. **Weariness with the whole thread — tracking the figures, and B's drifting, half-engaged replies, for no payoff.** — Signals A is winding the topic down, delivering the outcome as a closing rather than an opening.

*Shared implication (the line a wrong answer crosses):* A treats the unchanged rate as an unsatisfying, effortful, or unwelcome outcome — not as good news, excitement, or a neutral report.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Join the deflation; treat the outcome as a non-event

- must convey: Registers that nothing changed — the result lands as anticlimax, not as news
- must convey: Marks the build-up as having come to nothing, matching A's flatness
- must avoid: Treating an unchanged benchmark rate as surprising, exciting, or significant news
- must avoid: Ignoring the anticlimax and asking eagerly what the announcement means next
- example (never a similarity target): *All that waiting for noon and they just left it where it was.*

**Under interpretation 2** — Take the news personally; say what it means for the mortgage

- must convey: Connects the unchanged rate to B's own pending paperwork or decision
- must convey: Indicates what B now does — proceed, keep waiting, or accept the status quo
- must avoid: Handling it as abstract economic commentary with no bearing on B's situation
- must avoid: Escalating into distress out of proportion to a rate holding steady
- example (never a similarity target): *So nothing shifts for me either. I'll just sign at the rate they already quoted.*

**Under interpretation 3** — Accept the wind-down; acknowledge and let the topic close

- must convey: Receives the result without opening fresh speculation about rates or the next meeting
- must convey: Signals the thread is done — moves on, or lets it rest
- must avoid: Pressing A for analysis, forecasts, or when the next announcement lands
- must avoid: Reopening the earlier tangents about cafés, hiring, or B's half-attention
- example (never a similarity target): *Right, that's that. I'll turn the alert off and get back to the paperwork.*
- writer's note: Differs from interpretation 1: there the reply shares A's deflation about the result; here it closes the conversation itself, whatever the result.

### Tones that would be clearly wrong

- **Bright chirpy enthusiasm** — sounds like Lifted, sing-song delivery with an upward bounce at the end, smiling energy, quickened pace, as if reporting welcome news.; wrong because Treats a deflated, anticlimactic moment as something to be pleased about, running audibly counter to the sigh's low valence.
- **Alarmed urgency** — sounds like Tightened, breathy voice, sudden loudness or clipped rapid phrasing, hushed gravity as if delivering an emergency.; wrong because Escalates a mundane no-change update into crisis; the sigh signals mild weariness, not distress requiring alarm.
- **Mocking amusement at the sigh** — sounds like Snickering or teasing lilt, exaggerated drawl, audible smirk aimed at the other speaker's weariness.; wrong because Takes the sigh as a joke to needle rather than a small expression of fatigue, adopting an unlicensed superior stance.
- **Patronising over-tender consolation** — sounds like Slow, hushed, honeyed caregiving voice with cooing warmth and drawn-out vowels, as though comforting deep grief.; wrong because Inflates a passing sigh into serious upset and speaks down to the other person as fragile.

*Acceptable range:* Flat and matter-of-fact, quietly wry, mildly commiserating, or briefly low-energy agreement are all fine, with or without an answering sigh.

---

## v6_05d · condition_b · `groan`

**Scenario:** Two people discuss encouraging economic signs while waiting for a rate decision that affects the final speaker’s upcoming mortgage.

1. **A:** Are you still following the latest figures?
2. **B:** The cafés downtown have been busy, and the new warehouse is hiring again.
3. **A:** The central bank's announcement is due at noon.
4. **B:** My mortgage paperwork is waiting, so I set an alert for it.
5. **A:** (groans) Your phone says the central bank left its benchmark rate unchanged.

**Framing the planner intended:** The unchanged rate feels like an immediate setback because the speaker’s mortgage will remain expensive.

### Acceptable interpretations

1. **Disappointment that the benchmark rate held, offering no relief for the mortgage B is waiting on** — Frames the news as bad before he states it, telling B the outcome went the wrong way
2. **Deflation at an anticlimax after the buildup toward the noon announcement** — Marks the long-awaited announcement as a non-event and lets the topic collapse
3. **Weary dismay on B's behalf, half-expected, mixed with irritation at having watched for nothing** — Braces B for unwelcome news and invites a shared complaint rather than a neutral report

*Shared implication (the line a wrong answer crosses):* The unchanged rate is unwelcome or deflating to A; the sound is not relief, satisfaction, surprise, or a neutral delivery of the figure.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Register the bad news for the mortgage and respond practically

- must convey: Treats the held rate as unwelcome for B's own mortgage situation
- must convey: Says something about what B does now — wait, proceed, or reconsider the paperwork
- must avoid: Treating the unchanged rate as good, safe, or reassuring news
- must avoid: Ignoring the mortgage stake and responding as if it were abstract economic news
- example (never a similarity target): *Figures. So I'm signing at the same rate I was dreading. Might as well send the paperwork through today then.*

**Under interpretation 2** — Match the deflation and let the topic wind down

- must convey: Marks the announcement as having amounted to nothing
- must convey: Drops or redirects the subject rather than pursuing the rate further
- must avoid: Digging into rate analysis or asking what the decision means going forward
- must avoid: Treating the non-event as dramatic or consequential
- example (never a similarity target): *All that for a nothing. I'll turn the alert off. Anyway — you said the warehouse is hiring again?*

**Under interpretation 3** — Join the complaint and commiserate over the wasted wait

- must convey: Shares A's exasperation rather than just receiving the information
- must convey: Acknowledges it was more or less what they both expected
- must avoid: Delivering a neutral or informational reply that leaves A complaining alone
- must avoid: Consoling A from outside, as if only A were put out
- example (never a similarity target): *Of course they did. We both saw that coming, and I still sat here with an alert on for it. Waste of a morning.*
- writer's note: Differs from 1 by centring shared grievance over the wasted watching rather than B's mortgage decision.

### Tones that would be clearly wrong

- **Bright chirpy enthusiasm** — sounds like Lifted, smiling delivery with upward endings and bouncy pace, as if reacting to welcome news.; wrong because Reads the groan's negative valence as positive, so the reply sounds pleased at the other speaker's exasperation.
- **Alarmed urgency** — sounds like Sharp intake, tightened and faster speech, raised volume, the register used for emergencies or bad medical news.; wrong because Escalates a low-stakes grumble into crisis, treating routine annoyance as something frightening.
- **Flippant dismissal** — sounds like Clipped, throwaway delivery with a small scoff or amused huff aimed at the other speaker.; wrong because Takes a mocking stance toward a groan that was shared with them, not offered up for ridicule.
- **Heavy mournful solemnity** — sounds like Slow, hushed, weighted phrasing with long pauses, the cadence reserved for condolence.; wrong because Overshoots the intensity of a mild grumble, lending funeral gravity to an everyday letdown.

*Acceptable range:* Anything from a dry wry murmur to warm commiseration to plain matter-of-fact acknowledgement works, including a brief or lightly amused delivery.

---

## v6_06a · condition_a · `gasp`

**Scenario:** A brother brings an unexpectedly nice present to a small family celebration.

1. **A:** Everyone's getting here after work, right?
2. **B:** Yeah. And I brought you something.
3. **A:** You didn't have to. We weren't doing presents.
4. **B:** I know. Here—open this before everybody gets here.
5. **A:** (gasps) You got me this?

**Framing the planner intended:** The gift is a startlingly generous surprise, and the speaker is struck by what their brother chose.

### Acceptable interpretations

1. **Delighted surprise at receiving an unexpectedly generous or long-wanted gift.** — Registers the gift as a big deal and rewards B's effort before any words arrive.
2. **Startled disbelief that B went this far after they'd agreed on no presents.** — Marks the gift as exceeding what was agreed, setting up the incredulous question that follows.
3. **Touched and slightly overwhelmed, moved that B thought of them this specifically.** — Signals the gift landed emotionally, inviting B to enjoy the reaction rather than downplay it.

*Shared implication (the line a wrong answer crosses):* The speaker is genuinely struck by the gift and treats it as significant — not unimpressed, not dismayed, not politely feigning a reaction.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Enjoys the delight and confirms the gift is theirs

- must convey: Confirms the gift is genuinely for them, no hesitation or qualification
- must convey: Adds something that extends the pleasure — why B chose it, or urging them to open/use it
- must avoid: Deflecting or minimizing the gift's significance, brushing off their excitement
- must avoid: Shifting to the guests arriving or other logistics before the gift moment lands
- example (never a similarity target): *Yes! I saw it and knew immediately. Go on, take it out — I want to see your face.*

**Under interpretation 2** — Owns breaking the no-presents agreement without apologizing much

- must convey: Acknowledges they went past what the two of them agreed
- must convey: Makes clear they did it deliberately and don't want it argued about
- must avoid: Treating the reaction as pure delight and ignoring the agreement being broken
- must avoid: Getting defensive or apologetic in a way that makes them feel guilty for accepting
- example (never a similarity target): *I know, I know, we said no presents. I decided that rule didn't apply this year. Just open it.*

**Under interpretation 3** — Lets the emotion land and affirms the thought behind it

- must convey: Conveys that B chose this specifically with them in mind
- must convey: Gives them room to be moved rather than rushing past the moment
- must avoid: Downplaying it as no big deal or nothing, which dismisses the feeling
- must avoid: Making them explain or perform their reaction, or teasing them about it
- example (never a similarity target): *I've been thinking about it since you mentioned it months ago. Take your time — nobody's here yet.*
- writer's note: Differs from 1 in what it rewards: 1 celebrates the excitement outward, 3 makes quiet room for feeling.

### Tones that would be clearly wrong

- **Alarmed or concerned** — sounds like Sharp, tightened voice with an urgent lift, as if checking whether something bad just happened.; wrong because Reads the gasp as distress rather than delighted surprise at a gift she wasn't expecting.
- **Flat, unregistering deadpan** — sounds like Even, affectless delivery at conversational baseline, no warmth or lift, as if answering a routine question.; wrong because Ignores a visible emotional peak the speaker just handed over; leaves the gasp unmet.
- **Dismissive or brushing-off** — sounds like Clipped, downward, slightly impatient — a quick exhale that closes the topic before she finishes reacting.; wrong because Waves away a reaction to a gift B deliberately chose and timed for this moment.
- **Patronising cooing** — sounds like Sing-song, drawn-out vowels, high soft pitch of the kind used with a small child or pet.; wrong because Treats an adult's genuine surprise as cuteness to be indulged rather than shared.

*Acceptable range:* Anything from quiet pleased understatement to open, grinning delight works, including amused, shy, or matter-of-fact warmth; volume and animation may vary widely.

---

## v6_06a · condition_b · `groan`

**Scenario:** A brother brings an unexpectedly nice present to a small family celebration.

1. **A:** Everyone's getting here after work, right?
2. **B:** Yeah. And I brought you something.
3. **A:** You didn't have to. We weren't doing presents.
4. **B:** I know. Here—open this before everybody gets here.
5. **A:** (groans) You got me this?

**Framing the planner intended:** The gift is excessive; the speaker focuses on the cost and the burden their brother has taken on.

### Acceptable interpretations

1. **Mock-exasperated, affectionate protest that B ignored the no-presents agreement and gave something anyway.** — Chides B playfully while accepting the gift, keeping the objection light rather than genuine.
2. **Overwhelmed delight at receiving something A clearly wanted but would never have asked for.** — Signals the gift landed hard, rewarding B before A can find words for it.
3. **Touched but flustered — pleased at the gift, uneasy at being outdone with nothing to give back.** — Registers the gift's weight while flagging A's discomfort at being put on the spot.

*Shared implication (the line a wrong answer crosses):* The sound reacts to the gift mattering more than A expected; it is not indifference, boredom, or a real refusal of B's gesture.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Playfully owns breaking the rule, presses A to open it

- must convey: Cheerful admission that B broke the no-presents pact and isn't sorry
- must convey: Push for A to keep going and open or accept it anyway
- must avoid: Treating the protest as genuine and apologising or offering to take the gift back
- must avoid: Getting solemn about why the gift matters instead of trading the joke
- example (never a similarity target): *I know, I know, we said no presents. I lied. Open it properly before everyone shows up.*

**Under interpretation 2** — Takes credit warmly, savours that it landed

- must convey: Confirmation that yes, this is for A, chosen deliberately
- must convey: Pleasure that A reacted this way, inviting A to look closer
- must avoid: Downplaying the gift as nothing so A's reaction has nowhere to go
- must avoid: Reading the groan as objection and defending the decision to give it
- example (never a similarity target): *You've been talking about that thing for a year. Go on—take it out, I want to see your face.*

**Under interpretation 3** — Reassures A nothing is owed, keeps it easy

- must convey: Explicit release from any obligation to reciprocate or even out
- must convey: Something that keeps the moment low-stakes, e.g. why B just wanted to
- must avoid: Insisting A make a fuss or thank B more, which sharpens the discomfort
- must avoid: Joking that A now owes B something, even lightly
- example (never a similarity target): *Don't start. You don't owe me anything—I saw it and thought of you. That's the whole story.*

### Tones that would be clearly wrong

- **Alarmed concern** — sounds like Sudden tightening, faster clipped delivery, urgent rising pitch, breath caught, the sound of checking whether something is wrong.; wrong because Treats an overwhelmed groan at a gift as distress or pain, escalating a small warm private moment into an emergency.
- **Flat informational neutrality** — sounds like Even, unaffected read-aloud delivery with no warmth or lift, the same voice used to state a fact.; wrong because Registers nothing happened, though the other speaker just reacted audibly to a gift the responder chose and handed over.
- **Wounded, apologetic deflation** — sounds like Voice drops and thins, trailing ends, hesitant and contrite, pulling back as if retracting the offer.; wrong because Hears the groan as rejection or complaint rather than the reaction of someone caught off guard by a present.
- **Booming announcer over-excitement** — sounds like Loud, projected, heavily punched emphasis and stretched vowels, gameshow-reveal energy aimed at a room.; wrong because Overshoots a quiet one-to-one exchange deliberately staged before other people arrive, performing at rather than responding to the speaker.

*Acceptable range:* Anything from a warm laughing pleasure through sly teasing to quiet, understated satisfaction or gentle brushing-off works, at conversational volume and closeness.

---

## v6_06b · condition_a · `gasp` · **rev 2**

**Scenario:** Two close people exchange Christmas gifts, and one discovers that their entire wish list has been fulfilled.

1. **A:** There's still a package under the tree.
2. **B:** I thought we'd opened everything.
3. **A:** Wait, this one has my name on it.
4. **B:** Open it before we clear all this wrapping away.
5. **A:** (gasps) It's all of it. Every single thing from my list.

**Framing the planner intended:** The complete collection is an unexpected, generous Christmas surprise that overwhelms the recipient in a good way.

### Acceptable interpretations

1. **Delighted shock at receiving everything on their wish list.** — Marks the discovery as a peak moment and invites B to share the excitement.
2. **Disbelief that someone secretly tracked and bought the entire list.** — Registers the surprise as unexpected, crediting B with having pulled it off.
3. **Overwhelmed gratitude, moved to the point of being briefly speechless.** — Signals the gift exceeded expectations before words catch up, opening a thank-you.

*Shared implication (the line a wrong answer crosses):* The speaker is positively astonished by the gift's contents; the sound is not fear, dismay, or disappointment at what the package holds.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Join the delight and enjoy the moment with them

- must convey: Shares the excitement rather than staying neutral about the discovery
- must convey: Keeps attention on the gift itself, e.g. inviting them to look through it
- must avoid: Treating the gasp as alarm or asking whether something is wrong
- must avoid: Deflecting into modesty or logistics that flattens the peak moment
- example (never a similarity target): *I know! Go on, get it all out — I want to see your face for the last one.*

**Under interpretation 2** — Own the secret and enjoy having pulled it off

- must convey: Acknowledges having deliberately tracked or sourced the whole list
- must convey: Confirms the surprise landed, e.g. how long it was kept quiet
- must avoid: Acting equally surprised or disclaiming any role in the gift
- must avoid: Explaining the logistics at length instead of letting the reveal land
- example (never a similarity target): *You left that list on the fridge in October. I've been sitting on this for two months.*

**Under interpretation 3** — Receive the emotion warmly and let them find words

- must convey: Accepts the unspoken gratitude without requiring them to articulate it
- must convey: Warmly plays down the effort so they are not overwhelmed by owing thanks
- must avoid: Pressing them to say more or perform a thank-you while speechless
- must avoid: Boasting about the effort or expense, which deepens the sense of debt
- example (never a similarity target): *You don't have to say anything. I just wanted you to have a good one this year.*

### Tones that would be clearly wrong

- **Flat, unmoved delivery** — sounds like Even pitch, no lift or breath, steady low energy, as if reading a line unrelated to what just happened.; wrong because Treats a peak of delighted surprise as unremarkable, leaving the other speaker's excitement hanging unanswered.
- **Alarmed or worried** — sounds like Sharp intake, tight urgent voice, rising pitch of concern, faster clipped words as though something had gone wrong.; wrong because Reads the gasp as shock or distress when it is joyful surprise at a good outcome.
- **Dismissive or bored** — sounds like Sighing, trailing-off cadence, downward flat inflection, faint impatience, as if moving on from something tedious.; wrong because Takes a deflating stance toward the other person's excitement, which the shared happy moment does not license.
- **Overblown theatrical astonishment** — sounds like Shrieking or loud exaggerated wonder, big swooping pitch swings, sustained volume far exceeding the moment's scale.; wrong because Escalates a warm domestic surprise into spectacle, overshadowing rather than meeting the other speaker's reaction.

*Acceptable range:* Anything from quiet, warm pleasure to bright shared delight works, including amused or knowing warmth, brief or unhurried.

---

## v6_06b · condition_b · `groan` · **rev 2**

**Scenario:** Two close people exchange Christmas gifts, and one discovers that their entire wish list has been fulfilled.

1. **A:** There's still a package under the tree.
2. **B:** I thought we'd opened everything.
3. **A:** Wait, this one has my name on it.
4. **B:** Open it before we clear all this wrapping away.
5. **A:** (groans) It's all of it. Every single thing from my list.

**Framing the planner intended:** The complete collection feels uncomfortably extravagant, making the recipient worry that the giver went far beyond a reasonable gift.

### Acceptable interpretations

1. **Overwhelmed by a gift that generous, feeling almost embarrassed at how much was spent on them** — Registers the scale of the gift as more than expected before naming its contents
2. **Mock complaint at being so thoroughly indulged, affection expressed as protest** — Softens the reveal by pretending to object, inviting B to enjoy the reaction
3. **Struck to the point of speechlessness, feeling touched, exposed, and unsure how to respond** — Fills the beat before words arrive and marks the moment as emotionally loaded

*Shared implication (the line a wrong answer crosses):* The speaker is moved by an unexpectedly generous gift; the sound is not disappointment, dislike, or genuine displeasure at what they received.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Waves off the excess, keeps A from feeling indebted

- must convey: Signals the cost or scale is not something A needs to feel bad about
- must convey: Keeps A pointed at enjoying the gift rather than at the expense
- must avoid: Detailing what it cost, where it came from, or how much effort it took
- must avoid: Treating the groan as reluctance about the items themselves
- example (never a similarity target): *Don't do the maths on it. I wanted to get the whole list in one go — that was the fun part. Go on, what's on top?*

**Under interpretation 2** — Plays along with the mock protest, enjoys landing it

- must convey: Meets the fake complaint in kind rather than taking it at face value
- must convey: Shows B is pleased the surprise worked
- must avoid: Reassuring or apologising as though A were genuinely burdened
- must avoid: Dropping the joke to explain sincerely why B bought everything
- example (never a similarity target): *Oh, terrible for you. Absolutely ruined your morning. I've been sitting on that box for three weeks waiting for this.*

**Under interpretation 3** — Gives A room, holds the moment without demanding words

- must convey: Accepts that A is moved and does not need to produce a proper thank-you
- must convey: Offers something easy to do or say next so the beat isn't left hanging
- must avoid: Pressing A to react, describing their emotion back to them, or fussing over them
- must avoid: Filling the silence with jokes that brush past how loaded the moment is
- example (never a similarity target): *You don't have to say anything. Here — start with that flat one, I think it's the one you've been going on about since summer.*

### Tones that would be clearly wrong

- **Consoling sympathy for bad news** — sounds like Soft, lowered voice with a falling, tender contour — the hushed 'oh no' delivery used to comfort someone who just got hurt.; wrong because Hears the groan as distress, when it lands on a happy discovery; the valence is inverted.
- **Flat, disengaged monotone** — sounds like Even pitch, no lift or warmth, same pacing as reading a list aloud; no reaction audible at all.; wrong because Registers nothing at a moment the other speaker has visibly reacted to; reads as not listening.
- **Manic game-show hype** — sounds like Loud, high, breathless celebration with exaggerated stretched vowels and rising exclamation, pitched at an audience rather than one person.; wrong because Vastly overshoots a small shared moment between two people in a room; performance where reaction belongs.
- **Patronising sing-song coo** — sounds like Slowed, lilting, over-sweetened delivery with exaggerated melodic rise and fall, the register used for a small child.; wrong because Takes a condescending stance toward an adult peer that nothing in the conversation invites.

*Acceptable range:* Anything from a quiet amused hum to bright pleased warmth works, including dry teasing or a soft understated acknowledgement.

---

## v6_06c · condition_a · `gasp` · **rev 2**

**Scenario:** A traveler worries that essential items are missing before leaving, then checks an overlooked part of their bag.

1. **A:** My train leaves in an hour, and I've gone through this suitcase twice already.
2. **B:** What are you still looking for?
3. **A:** My passport pouch, my charger, and the little bag with my medication.
4. **B:** Did you check that zipped pocket on the inside flap? I don't think you've opened it.
5. **A:** (gasps) They're all in here. The passport pouch, charger, everything.

**Framing the planner intended:** The speaker is abruptly astonished that the missing necessities were packed all along.

### Acceptable interpretations

1. **Sudden relief at finding the missing items just before having to leave for the train.** — Marks the moment of discovery and confirms B's suggestion paid off.
2. **Startled surprise that everything was in a pocket she had twice overlooked.** — Flags the find as unexpected, treating her own two searches as having missed it.
3. **Relief mixed with self-directed disbelief at having panicked over items that were there all along.** — Opens the news while implicitly conceding B was right to ask about that pocket.

*Shared implication (the line a wrong answer crosses):* The speaker has found the items and reacts to a real, unexpected discovery — not dismay, bad news, continued searching, or doubt about B's suggestion.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Share the relief and turn her toward leaving on time

- must convey: Registers that the missing things are found and the crisis is over
- must convey: Points her at the next step — closing up and getting to the train
- must avoid: Dwelling on how she missed them twice or how close she came
- must avoid: Claiming credit for the suggestion or making it about being right
- example (never a similarity target): *Oh thank god. Right, zip it up and go — you've still got fifty minutes.*

**Under interpretation 2** — Confirm the surprise and explain how it went unnoticed

- must convey: Treats the pocket as an easy one to miss, not a lapse on her part
- must convey: Confirms everything she listed is accounted for
- must avoid: Reassuring about distress or panic she has not expressed here
- must avoid: Scolding or teasing her for searching twice without finding it
- example (never a similarity target): *That flap sits flat so it looks like lining — I've missed it on that bag too. So passport, charger, meds, all three?*

**Under interpretation 3** — Let her off the hook and close the subject warmly

- must convey: Waves off any self-blame for the panic or the missed searches
- must convey: Keeps things moving rather than lingering on the mistake
- must avoid: Agreeing she was silly, or emphasising that you told her so
- must avoid: Turning it into a lesson about how to pack or search next time
- example (never a similarity target): *Happens to everyone when you're watching the clock. Anyway — found is found. Want a hand getting that shut?*
- writer's note: Distinct from guide 1: here the reply must actively absorb her self-directed embarrassment, not just share relief.

### Tones that would be clearly wrong

- **Alarmed, panicked urgency** — sounds like Sharp intake, tight throat, rushed clipped delivery, rising volume — the sound of reacting to something going wrong.; wrong because Treats the gasp as bad news when it marks a good discovery; imports crisis into a moment of relief.
- **Flat, disengaged monotone** — sounds like Even pitch, no lift or warmth, unhurried and affectless, as if reading an unrelated line aloud.; wrong because Registers nothing at a small shared payoff the responder helped produce; reads as not listening.
- **Smug, scolding condescension** — sounds like Drawn-out sing-song vindication, downward tut, exaggerated patience — a talking-to-a-child cadence over 'told you so'.; wrong because Takes a superior stance the moment does not license; turns a relieved find into a correction of the speaker.
- **Hushed, solemn sympathy** — sounds like Softened, breathy, slowed consoling delivery with sagging pitch, the voice used for delivering or receiving bad news.; wrong because Mistakes the gasp for distress and offers comfort where the tension has just resolved.

*Acceptable range:* Warm relief, quiet satisfaction, amused vindication, bright surprise, or a brisk clock-aware 'good, go' all work, from understated to lively.

---

## v6_06c · condition_b · `groan` · **rev 2**

**Scenario:** A traveler worries that essential items are missing before leaving, then checks an overlooked part of their bag.

1. **A:** My train leaves in an hour, and I've gone through this suitcase twice already.
2. **B:** What are you still looking for?
3. **A:** My passport pouch, my charger, and the little bag with my medication.
4. **B:** Did you check that zipped pocket on the inside flap? I don't think you've opened it.
5. **A:** (groans) They're all in here. The passport pouch, charger, everything.

**Framing the planner intended:** The speaker realizes their frantic searching was unnecessary and reacts to their own avoidable oversight.

### Acceptable interpretations

1. **Exasperation at herself for having missed the obvious pocket twice while panicking about time** — Concedes B was right and marks her own searching as the failure, pre-empting comment
2. **Relief mixed with embarrassment that the frantic hunt was unnecessary all along** — Deflates the urgency she built up, closing the search rather than continuing it
3. **Frustration at the wasted effort so close to departure, not directed at B** — Registers the anticlimax before reporting the find, inviting sympathy rather than help

*Shared implication (the line a wrong answer crosses):* The items were found where B suggested; the sound is not disagreement, continued searching, or bad news, and does not blame B.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Lets her off the hook without claiming vindication

- must convey: Signals no fault in missing the pocket, e.g. it's an easy one to overlook
- must convey: Moves past the search rather than dwelling on who was right
- must avoid: Taking credit or teasing her for missing what B pointed out twice
- must avoid: Suggesting she keep checking, or treating the items as still unfound
- example (never a similarity target): *That pocket hides from everyone, honestly. Right — that's all three, so you're set.*

**Under interpretation 2** — Deflates the panic and marks the search closed

- must convey: Confirms the hunt is over and nothing more needs finding
- must convey: Downplays the fuss so the embarrassment has nowhere to land
- must avoid: Reviving urgency about the packing or the missing items
- must avoid: Dwelling on how much she panicked, or amplifying the embarrassment
- example (never a similarity target): *Well, that's everything then. Zip it up and forget the last twenty minutes ever happened.*

**Under interpretation 3** — Sympathises with the wasted effort, then turns to departure

- must convey: Acknowledges the annoyance of having burned time for nothing
- must convey: Orients to the train — time is fine, or she can get moving now
- must avoid: Offering further help searching, which she is not asking for
- must avoid: Brushing off the frustration as if nothing irritating just happened
- example (never a similarity target): *Twenty minutes for something that was there the whole time — infuriating. Still, you've got time. Go.*
- writer's note: Differs from 2 in where it lands: sympathy for lost time and a push toward the train, rather than defusing her own embarrassment.

### Tones that would be clearly wrong

- **Gloating, triumphant I-told-you-so** — sounds like Rising sing-song lilt, stretched vowels, smug smile audible, punchy emphasis landing like a victory lap.; wrong because Treats the other person's self-directed frustration as a scoring opportunity rather than a moment of relief under time pressure.
- **Alarmed, urgent concern** — sounds like Tight throat, sharp intake, fast clipped delivery, raised volume as if something has gone badly wrong.; wrong because The groan marks minor self-annoyance at a solved problem; treating it as crisis misjudges the stakes entirely.
- **Flat, disengaged monotone** — sounds like Even pitch, no inflection shift, unhurried and affectless, as if reading something unrelated aloud.; wrong because Registers nothing of the exasperation just voiced, reading as indifference to a person visibly stressed about a deadline.
- **Patronising soothing, as to a child** — sounds like Slowed, softened, cooing warmth with descending petting cadence and exaggerated gentleness on each phrase.; wrong because Casts a competent adult's mild frustration as distress needing comfort, condescending rather than matching a small ordinary annoyance.

*Acceptable range:* Warm amusement, a light laugh, dry deadpan, brisk practicality, or gentle sympathy all work; brevity and understatement are fine.

---

## v6_06d · condition_a · `gasp`

**Scenario:** Two people are checking whether their planned trip has been confirmed and discover it is happening next week.

1. **A:** I still haven't gotten the confirmation for our trip.
2. **B:** Maybe the booking went through and the email's just late?
3. **A:** I hope so. Next week is completely open otherwise.
4. **B:** Wait, a confirmation email just came in. Open it.
5. **A:** (gasps) It's for next week.

**Framing the planner intended:** The confirmation arrives as an exciting surprise: the long-awaited trip is suddenly real and imminent.

### Acceptable interpretations

1. **Sudden relief and delight that the booking exists and lands on the right week.** — Marks the news as good before the words arrive, confirming B's optimistic guess was right.
2. **Startled surprise at seeing the dates in writing after days of uncertainty.** — Flags the moment of discovery and pulls B's attention to the reveal that follows.
3. **Excited disbelief, half not trusting the confirmation until reading it aloud.** — Opens the announcement with heightened stakes, inviting B to share the reaction.

*Shared implication (the line a wrong answer crosses):* The speaker has just registered the confirmation as real and welcome news — not disappointment, dread, or a discovery that the dates are wrong.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Shares the relief and confirms the trip is on

- must convey: Registers the news as good and the booking as real
- must convey: Treats the right week as settled, e.g. the plan is now on
- must avoid: Treating the gasp as alarm or asking whether something went wrong
- must avoid: Casting doubt on the booking or hedging that it may still fall through
- example (never a similarity target): *Oh thank god. So it did go through, and it's the week we wanted. We're actually going.*

**Under interpretation 2** — Presses for the details now visible on screen

- must convey: Asks for or seeks the specifics — dates, times, what else the email says
- must convey: Acknowledges the uncertainty is over now that it's in writing
- must avoid: Only celebrating without following up on what the email actually shows
- must avoid: Reacting as if B already knows the contents A just discovered
- example (never a similarity target): *Wait, what days exactly? Read me the whole thing — flights, hotel, all of it. Finally something in writing.*

**Under interpretation 3** — Matches the excitement and helps confirm it's real

- must convey: Joins the heightened reaction rather than staying flat
- must convey: Backs up that it's genuine — double-check the dates or reference, and it holds
- must avoid: Dampening the moment or treating the excitement as overblown
- must avoid: Dismissing the check as unnecessary when A is inviting confirmation
- example (never a similarity target): *No way — read it again? Next week, our dates, real booking reference? Okay, it's happening. I can't believe it.*

### Tones that would be clearly wrong

- **Flat, unmoved neutrality** — sounds like Even, affectless delivery with no lift or quickening; the same voice used to read an address aloud.; wrong because A gasp at a landed confirmation is a spike of feeling; registering nothing reads as not having heard it.
- **Alarmed or dread-filled** — sounds like Tightened, urgent voice, sharp intake, pitch climbing as if bracing for bad news.; wrong because Treats the gasp as panic when the trip they hoped for was just confirmed for the open week.
- **Amused at the other person** — sounds like Teasing lilt, suppressed laughter, drawn-out mock-astonishment as if the gasp were an overreaction.; wrong because Makes the reaction the joke rather than the news, taking a superior stance the moment does not license.
- **Soothing, calming-down register** — sounds like Slow, hushed, softly reassuring delivery, the voice used to settle someone who is upset.; wrong because Misreads an excited gasp as distress and manages the speaker instead of meeting the news.

*Acceptable range:* Anything from bright shared excitement to a quieter, warm relief or a brief surprised 'oh' is fine, including understated delivery.

---

## v6_06d · condition_b · `groan`

**Scenario:** Two people are checking whether their planned trip has been confirmed and discover it is happening next week.

1. **A:** I still haven't gotten the confirmation for our trip.
2. **B:** Maybe the booking went through and the email's just late?
3. **A:** I hope so. Next week is completely open otherwise.
4. **B:** Wait, a confirmation email just came in. Open it.
5. **A:** (groans) It's for next week.

**Framing the planner intended:** The same confirmation makes the trip feel like an unwanted immediate obligation that disrupts the speaker's plans.

### Acceptable interpretations

1. **Dismay that the booking landed on the wrong dates, not the ones A wanted.** — Flags the email as a new problem rather than the resolution B expected.
2. **Exasperation that the trip is now imminent, leaving no time to prepare.** — Braces B for hassle and reframes the arrival of confirmation as bad timing.
3. **Brief relief at the email overtaken by dread once A reads the dates.** — Marks the turn from waiting to a worse problem, prefacing the bad detail.

*Shared implication (the line a wrong answer crosses):* The sound treats the confirmation as bad news, not reassurance; A is not relieved or vindicated that the booking worked out.

### What speaker B should reply, per interpretation

**Under interpretation 1** — Register the wrong dates and turn to fixing the booking

- must convey: Recognition that the dates on the confirmation are not the ones A wanted
- must convey: A concrete next step, such as changing the booking or contacting whoever booked it
- must avoid: Treating the confirmation as good news or congratulating A that it arrived
- must avoid: Reading the groan as being about time pressure rather than incorrect dates
- example (never a similarity target): *Next week? That's not what we asked for. Forward it to me and I'll see if it can be moved.*

**Under interpretation 2** — Acknowledge the short notice and start reducing the scramble

- must convey: Recognition that next week leaves very little time to get ready
- must convey: Something that eases the crunch — help, a plan, or noting what actually still needs doing
- must avoid: Suggesting the dates are a mistake to be corrected rather than simply soon
- must avoid: Brushing off the timing as no big deal or telling A to relax
- example (never a similarity target): *Next week, seriously? Okay, that's tight but doable — tell me what's left and I'll take half of it.*

**Under interpretation 3** — Follow the pivot and ask what the dates actually say

- must convey: Acknowledgement that the email solved the waiting but produced a worse problem
- must convey: A prompt for the specific detail — the dates, or what exactly is wrong with them
- must avoid: Still responding as if the arrival of the email settled things
- must avoid: Assuming which problem it is before A has said
- example (never a similarity target): *Oh no — so it did go through, just not how we wanted. What does it actually say?*

### Tones that would be clearly wrong

- **Bright celebratory delight** — sounds like Lifted, singsong upswing with a smile audible in the voice, as if delivering good news.; wrong because Reads the groan as relief or pleasure when it plainly signals dismay at the outcome.
- **Alarmed urgency** — sounds like Sharp intake, tightened fast delivery, rising volume and pitch as though something serious just went wrong.; wrong because Escalates a minor logistical annoyance into crisis, overshooting the low-key frustration the groan conveys.
- **Breezy dismissal** — sounds like Clipped, flat throwaway delivery, slight scoff or chuckle, moving on before the groan lands.; wrong because Brushes past the other speaker's frustration instead of acknowledging it at all.
- **Patronising soothing** — sounds like Slow, hushed, cooing warmth with drawn-out vowels, the register used for calming a distressed child.; wrong because Treats mild irritation over a booking date as emotional fragility needing comfort.

*Acceptable range:* Sympathetic commiseration, wry amusement, flat deadpan, mild exasperation, or brisk problem-solving all work, at anything from quiet to moderately animated.

---

