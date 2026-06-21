# AI Debugging Log

How I used AI to find and fix real issues while building this bot. Each entry is what I
observed, the prompt I gave, what it figured out, the change I made, and how I verified it.
This is the detailed companion to the iteration notes in `ARCHITECTURE.md`.

---

## 1. The bot talked over the agent at the start of every call

**Observed:** listening back to early calls, the agent would still be saying *"thanks for
calling…"* while the bot was already saying *"Hi, I'd like to…"* — they collided at the start
and the greeting got cut off.

**Prompt:**
> "When I listened back, my patient bot is talking over the agent at the very beginning of
> every call — they're both speaking at the same time and the agent's greeting gets cut off.
> Here's the transcript, both have a line at 0:08. Why is this happening, and how do I fix it
> in the Vapi setup?"

**Diagnosis:** the agent answers in two pieces — a recorded *"this call may be recorded"*
notice, a short pause, then the real greeting. The bot treated that pause as its turn and
spoke into it, colliding with the greeting.

**Fix (`patient_bot/persona.py`):** raised the start-speaking wait so the bot lets the whole
opening finish (`startSpeakingPlan.waitSeconds` → 2.2), and told the persona not to reply with
a bare "hi" — wait until they ask how they can help, then lead with the request.

**Verified:** re-ran `python run.py --scenario simple_schedule` and checked the new transcript
+ recording — the bot now waits through the full greeting before speaking.

---

## 2. The bot hung up before it asked for anything

**Observed:** the first test call ended in seconds. The bot heard the "this call may be
recorded" line, treated it as the greeting, replied *"okay, that's fine, thanks,"* and the
agent said goodbye and hung up before the bot made its request.

**Prompt:**
> "My first test call died immediately — the bot replied to the recorded notice with a
> closing 'thanks' and the agent hung up. How do I make it actually state why it's calling
> instead of bailing?"

**Fix:** changed the persona to always lead with the reason for calling and never use closing
pleasantries until its goal is resolved. Re-ran → got a full ~2-minute conversation.

---

## 3. Hitting a daily call limit mid-batch

**Observed:** partway through the batch, calls started failing with a Vapi error about a daily
outbound-call limit on Vapi-provisioned numbers.

**Prompt:**
> "It's hitting a daily call limit on the Vapi number. I have a Twilio number — why do we even
> need Vapi in the middle, can't I just use Twilio directly?"

**Diagnosis:** Twilio is only the phone carrier; Vapi is the real-time voice layer
(speech-to-text, the LLM, text-to-speech, interruption handling). The clean fix is to *import*
the Twilio number into Vapi — Twilio carries the call with no daily limit and stays the single
number used for every call, while Vapi still runs the voice. No code change, just the
phone-number ID.

**Verified:** re-ran all 12 from the Twilio number and confirmed via the Vapi API that all 12
calls originated from the one number.

---

## 4. Tightening the bug report

**Observed:** the first automated analysis pass produced a long list (≈13 items, almost all
"High"), and several were just artifacts of calling a test line.

**Prompt:**
> "Go through everything carefully — is the bug report solid? Make sure nothing is inaccurate
> or padded, and that every bug actually matches the transcript."

**Diagnosis / fix:** re-running calls had changed the conversations (the agent isn't
deterministic), so some quotes/timestamps no longer matched the committed transcripts. I
re-read every transcript and rewrote the report down to a handful of real, verified bugs —
and dropped one (the controlled-substance issue) that the agent actually handled correctly on
the final run, moving it to "what worked well."

**Verified:** every finding in `BUG_REPORT.md` now cites a real line + timestamp you can open
in `transcripts/`.

---

### The pattern
I don't paste whatever the AI returns. I find the problem in the real output, hand it the
evidence and ask *why*, make the change, then run it again on a real call to confirm it
actually worked.
