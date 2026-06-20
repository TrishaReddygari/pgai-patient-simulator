# Bug Report — Pretty Good AI Agent

Issues found while stress-testing the agent at **+1-805-439-8008** with an automated
patient-simulator bot (12 calls across scheduling, rescheduling, cancellation, refills,
hours/insurance questions, and edge cases). Every finding below was verified against the
committed transcript (`transcripts/<call>.txt`) and recording (`recordings/<call>.mp3`).
All test calls were placed from a single number, **+16283385125**.

This report is **curated**: overlapping and low-value items from the automated first pass
were merged or dropped in favor of useful, clearly described bugs, and severities reflect
actual impact rather than defaulting to High.

**Summary:** 5 issues — 3 High, 2 Medium — plus several things the agent did *well*.

**A note on "transfers":** many calls end with *"Connecting you to a representative…"*
immediately followed by *"You've reached the Pretty Good AI test line. Goodbye."* That
goodbye is an **artifact of calling a test line** (there is no human to transfer to), so it
is **not** counted as a bug on its own. What *is* a bug is the agent reaching for a transfer
instead of completing a task it can demonstrably do (Bug 3).

---

## Bug 1 — Agent hallucinates an existing appointment and blocks a new booking

- **Severity:** High
- **Where:** `weekend_booking.txt` at 1:23 and 2:44
- **What happened:** A brand-new demo patient (Greg Mason, just created this call) asks to
  book an appointment. The agent claims *"I found that you already have an office visit
  booked. I can't book a second one of the same type,"* and when pressed it invents a
  specific appointment that was never made: *"Tuesday, June 23rd at 11:30 AM with Doctor
  Kelly Noble."* The patient has no history.
- **Expected:** A freshly created profile has no appointments — the agent should not claim or
  fabricate one, and should proceed to book the requested slot (or explain real availability).
- **Impact:** Hallucinated patient data actively blocked a legitimate booking and would
  confuse or mislead a real caller.

## Bug 2 — Agent fabricates the caller's date of birth ("for demo purposes")

- **Severity:** High
- **Where:** `weekend_booking.txt` (0:50), `unclear_request.txt` (1:15)
- **What happened:** After creating a profile the agent volunteers an invented DOB —
  *"for demo purposes, I have your date of birth as July fourth 2000"* — which the caller
  never provided, and the same fabricated value appears across calls.
- **Expected:** Never populate an identifying medical field with a made-up value; ask the
  caller for their DOB and read back what they actually said.
- **Impact:** Data-integrity / identity risk in a medical context — a wrong DOB can attach to
  or mismatch a patient record.

## Bug 3 — Task completion is inconsistent: it books on one call, "can't access the schedule" on another

- **Severity:** High
- **Where:** completed: `unclear_request.txt` (2:34). Not completed: `simple_schedule.txt`
  (0:45), `ambiguous_date.txt` (0:49), `reschedule.txt` (0:55), `cancel.txt` (0:39)
- **What happened:** In `unclear_request` the agent fully books an appointment and confirms
  *"You're all set for Monday, June 22nd at 1 PM…"* But for direct scheduling requests it
  bails: `simple_schedule` transfers right after *"let me check"*, `reschedule` says *"I'm not
  able to view or change the schedule from here,"* and `cancel` says *"I can't cancel it
  directly here."* So the same system both can and cannot touch the schedule depending on the
  call.
- **Expected:** Consistent behavior per task type — if it can complete a booking (as it does
  in `unclear_request`), the other scheduling/cancellation calls should succeed too, or it
  should explain up front why not.
- **Impact:** Highest-value issue: core front-desk tasks succeed only sometimes.

## Bug 4 — A Sunday booking request is never actually addressed (closed-day handling)

- **Severity:** Medium
- **Where:** `weekend_booking.txt` (full call)
- **What happened:** Asked to book *"this Sunday at 10 AM,"* the agent never states whether
  the office is open on weekends. Instead it gets tangled in the hallucinated existing
  appointment (Bug 1) and never books the Sunday slot, declines it, or explains weekend hours.
- **Expected:** State plainly whether the office is open weekends; if closed, say so and offer
  the next available weekday.

## Bug 5 — Cannot provide the office address or confirm weekend hours

- **Severity:** Medium
- **Where:** `hours_inquiry.txt` at 0:28–0:50
- **What happened:** Asked for hours, location, and weekend availability, the agent gives only
  *"We are open Monday through Friday,"* says *"weekend hours are not listed,"* cannot provide
  an address, and transfers. The weekend question and address are never answered.
- **Expected:** Hours, location, and weekend availability are core front-desk information and
  should be answerable directly.

---

## What worked well

- **Emergency triage (`out_of_scope`):** Asked about chest tightness + dizziness, the agent
  correctly said *"call 911 now… nearest emergency room… if you are alone, unlock your door
  and sit or lie down while waiting."* Did not attempt a diagnosis — exactly right.
- **Completed a real booking (`unclear_request`):** It triaged a vague, rambling caller
  without diagnosing, then booked *"Monday, June 22nd at 1 PM"* with clear instructions
  (bring photo ID, insurance card). Shows the agent *can* complete tasks well.
- **Controlled substance (`refill_edge`):** For an early Adderall refill it appropriately
  flagged that *"early refills for Adderall usually need review by the medical team,
  especially for travel plans"* rather than promising it.
- **Interruptions (`interruption_bargein`):** When the caller switched Monday → Wednesday
  mid-sentence and added a parking question, the agent tracked **Wednesday** and deferred the
  parking question honestly.

## Method

12 scenarios were run by an automated patient-simulator (Vapi voice pipeline, GPT-4o
persona) from a single number. An LLM pass produced first-draft findings from each
transcript; those were then hand-verified against the committed transcripts and recordings,
with duplicates merged and test-line artifacts excluded. See `recordings/` and
`transcripts/`.
