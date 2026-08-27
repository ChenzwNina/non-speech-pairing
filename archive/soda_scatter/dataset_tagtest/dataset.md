# SODA-seeded vocalization dataset

1 conversations of 12 turns each. Vocalization placement was fixed before the dialogue was written; the labels below are only those a majority of verifier runs could actually hear in the rendered audio.

**4 of 12 planned vocalizations survived verification (33%).**

| sound | planned | verified | survival |
| --- | --- | --- | --- |
| laughter | 3 | 0 | 0% |
| yawn | 4 | 1 | 25% |
| sob | 1 | 0 | 0% |
| sigh | 4 | 3 | 75% |

---

## soda_4845347

*SODA #4845347* — Jazlynn hit Sandra with a bat because Jazlynn wanted to teach Sandra a lesson about picking fights with people. Jazlynn thought that if she hit Sandra hard enough, Sandra would never pick another fight again.

**Audio** `soda_scatter/dataset_tagtest/audio/soda_4845347.mp3` · 92.4s · Jazlynn / Sandra

4 verified of 12 planned

1. **Jazlynn:** [bitter laugh] You kept provoking people and acting untouchable. I thought one hard hit would make you stop.
2. **Sandra:** [long yawn] My head is pounding and I can't focus. Put the bat away and call emergency services.
3. **Jazlynn:** [sleepy yawn] I've been up all night, but that doesn't excuse what I did. The bat is on the ground; I'm calling now. ←
4. **Sandra:** [voice breaking, crying] I picked fights, but I didn't deserve to be hit. Tell them exactly what happened.
5. **Jazlynn:** [embarrassed laugh] I called it teaching you a lesson because I didn't want to admit I lost control. I won't lie to them.
6. **Sandra:** [resigned sigh] Fine. Then say you swung it, and say I need help before we argue about anything else. ←
7. **Jazlynn:** [long sigh] You're right. The dispatcher says to keep you still, and I'm staying here until the ambulance arrives. ←
8. **Sandra:** [disbelieving laugh] Staying here doesn't undo it. After the doctor checks me, I want the police to hear my side.
9. **Jazlynn:** [exhausted yawn] They will. I'll give a statement and accept whatever comes from it.
10. **Sandra:** [sigh of relief] The paramedic says nothing looks broken, but they're taking me in for scans. Don't follow me into the exam room. ←
11. **Jazlynn:** [remorseful sigh] I understand. I'm sorry I hurt you, and I'll wait where the officers tell me to.
12. **Sandra:** [weary yawn] Good. I need sleep and treatment, not another confrontation. Let them handle the rest.

| turn | at | sound | tag | target | intention after |
| --- | --- | --- | --- | --- | --- |
| 3 | 0:16.56 | yawn | `[sleepy yawn]` | her sleeplessness and guilt | Reject exhaustion as an excuse and call for help. |
| 6 | 0:43.24 | sigh | `[resigned sigh]` | Jazlynn's claimed honesty | Set the facts straight and prioritize treatment. |
| 7 | 0:48.96 | sigh | `[long sigh]` | the emergency instructions | Accept Sandra's demand and focus on safety. |
| 10 | 1:09.80 | sigh | `[sigh of relief]` | the paramedic's initial assessment | Set limits while agreeing to further care. |

*Dropped as inaudible: t1=laughter, t2=yawn, t4=sob, t5=laughter, t8=laughter, t9=yawn, t11=sigh, t12=yawn*
