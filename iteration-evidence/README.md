# Iteration evidence — turn-taking fix (before/after)

These are **not** part of the 12 test calls in `recordings/`. They're kept as evidence of one
iteration: early on, the bot spoke into the pause after the agent's recorded notice and talked
**over** the agent's greeting at the start of every call. See `AI_DEBUG_LOG.md` (entry 1) for
how it was diagnosed and fixed (`patient_bot/persona.py` — longer start-speaking wait + a
"don't reply with a bare hi" instruction).

| Before (the overlap bug — listen at the start) | After (fixed) |
|---|---|
| `before_simple_schedule.mp3` — bot says "Hi" over the agent's "Thank you for call…" (~0:08) | `../recordings/simple_schedule.mp3` (bot waits for the full greeting) |
| `before_hours_inquiry.mp3` — overlaps twice (~0:08 and ~0:12) | `../recordings/hours_inquiry.mp3` |
| `before_reschedule.mp3` — "Thanks for calling… Hi" collision (~0:08) | `../recordings/reschedule.mp3` |
| `before_out_of_scope.mp3` — "Thanks for calling Hi there" collision (~0:08) | `../recordings/out_of_scope.mp3` |
