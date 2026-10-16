# The Air Gap

### What it is

A word gets partially registered. The profanity detector fires on a fragment, not
on the complete word. The speaker intended nothing. The platform heard something.

It happens on every live broadcast that carries a scrubbed speech track, and it
happens constantly — several times an evening on a normal stream. The person
speaking usually doesn't notice. **The system notices, and the system reacts.**

---

### The mechanic

The trigger is a censor that fires on **partial or homophone-adjacent matches**
in the audio, rather than on the transcript.

| The speaker says | The detector reads | Result |
|---|---|---|
| a clean word containing a profanity fragment | the fragment | flag |
| a homophone of a slur ("fixin'" near a vowel-collapsed track) | the slur | flag |
| a censored word, spoken | the consonants | flag |
| a bystander repeating the flagged word | the same fragment | **second flag, same word, different person** |

Three properties make this worse than it looks:

**1. The speaker is not the offender.** The flag attaches to whoever's audio
triggered it. A bystander echoing a word is not making a point; they are being
punctuation. Both get logged identically in any system that keys on audio alone.

**2. Repetition makes it worse.** The natural reaction to a flag is to say the
word again — to explain it, to apologise, to clarify. That is three more
activations of the same detector, from the same mouth, within four seconds.
**The corrective behaviour is the amplifier.**

**3. It compounds on the viewer's side.** One flagged fragment gets repeated in
the chat as a guess. The guess is not what was said. The guess is now a second
instance of the word, unattributed, and it will get flagged again if anyone
types it into a matching surface.

---

### What it looks like from the inside

- Account warnings with **no recognisable offending word in the log**
- Two people flagged in the same ten seconds **for the same word, one of whom
  was quoting**
- A room that goes quiet for a beat that nobody in it can explain
- **The speaker apologising for something they did not say**, which is the
  clearest tell and the most corrosive, because it teaches the speaker that
  their own mouth is not reliable to them

That last one is the real damage. The system corrupts the speaker's trust in
their own record.

---

### Why it reads as an attack

To the person being flagged, the effect is **indistinguishable from being
targeted**. That is not a perception error on their part — it is a faithful
reading of an event with no visible cause. The response is rational and the
system treats it as a behavioural problem.

This is the loop:

```
fragment matches
   → flag lands on a bystander
      → bystander apologises (3 more matches)
         → account warning with no identifiable word
            → "this is being done to me on purpose"
               → behaviour that reads as hostile
                  → harder flag
```

**Every step of that is the platform working as designed.** There is no actor
and no conspiracy in it. It produces the *appearance* of targeted attack
without requiring one, which makes it a very effective way to manufacture
enemies without doing anything.

---

### Handling it on a stream

- **Never repeat the flagged word.** Not to apologise, not to clarify, not to
  explain what it was. Every repetition re-triggers the detector and deepens
  the flag.
- **Bystander flags are the priority.** A repeat is not participation. Key the
  log on *near-duplicate audio*, not on identity, and discount a flag that
  arrives within seconds of an identical one.
- **Apologising counts as the offending word.** This is the least intuitive
  consequence and it catches experienced hosts hardest — the apology is a full
  clean pronunciation, which is a *stronger* signal than the original fragment.
- **Vary the delivery.** The detector keys on the waveform. A word said
  differently is a different signal to it, and this is not evasion — the
  meaning is unchanged, the trigger surface is not.
- **Log the actual audio, not just the transcript.** If the log says a word was
  said and the audio does not contain it, that gap is the bug, and it is the
  only evidence that survives.

---

### The general shape

Any system that classifies on a lossy signal and attaches the result to a person
will produce this: **false positives that are indistinguishable from targeted
harassment, and a corrective behaviour that increases the score.**

The detector is not wrong about much. It is wrong about the *wrong things*, and
the person carrying the consequence cannot tell which category theirs is in.
That gap — between what actually happened and what can be established — is the
whole effect, and it is where the harm lives.