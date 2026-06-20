# Architecture

**How it works.** The bot is a *caller simulator*: for each scenario it builds a
Vapi "transient assistant" — a system prompt that makes the model behave like a
real human patient with a specific goal, the facts it knows about itself, and the
edge case it should push on (`patient_bot/persona.py` + `scenarios.py`). It then
places an outbound call through Vapi to the Pretty Good AI agent
(`POST /call` with that assistant, our Vapi phone number, and the target number),
and Vapi runs the realtime loop — Deepgram speech-to-text → GPT-4o → TTS, with
barge-in and call recording. We poll `GET /call/{id}` until the call ends, then
pull the recording URL, transcript, and turn-by-turn messages from the call
artifact (`patient_bot/vapi_client.py`), download the audio as mp3, and write a
readable Patient/Agent transcript (`patient_bot/collector.py`). Finally an
offline GPT pass reviews each transcript against the scenario's "what a correct
agent should do" criteria and aggregates real, useful bugs — severity-ranked —
into `BUG_REPORT.md` (`patient_bot/analyzer.py`). `run.py` is the single
orchestrator (`--all`, `--scenario`, `--analyze-only`).

**Key design choices.** (1) *Vapi for the audio pipeline* — the challenge's #1
criterion is lucid, natural voice, and it explicitly doesn't reward
reinventing telephony/infra, so the engineering effort goes into persona design,
scenario coverage, and analysis rather than a hand-rolled media pipeline.
(2) *Personas, not scripts* — the patient is goal-driven and improvises, so it
behaves like a real user (the rubric warns against scripted benchmark runners)
and actively steers the call. (3) *Edge cases chosen to expose specific failure
modes* — e.g. insisting on a Sunday appointment to test closed-day handling, and
an early controlled-substance refill to test over-promising. (4) *Grounded bug
analysis* — each scenario ships with explicit success criteria so the analyzer
flags meaningful deviations instead of nitpicks. (5) *Tunable voice knobs* — the
voice, transcriber, and start/stop speaking plans sit at the top of `persona.py`
so the natural-conversation quality can be iterated quickly.

**Iteration loop.** Run a 2–3 call smoke batch (`python run.py --scenario ...`),
listen to the recordings, adjust the voice and the `startSpeakingPlan` /
`stopSpeakingPlan` timing for natural turn-taking, then run the full batch with
`python run.py --all`.

Iteration log:
- **v1 → v2 (opening derail):** the first smoke call failed — the bot treated the
  "this call may be recorded" disclaimer as the greeting and replied "okay, that's
  fine, thanks", which made the agent say goodbye and hang up before the patient
  stated its goal. Fix: persona now leads with the reason for calling and avoids
  closing pleasantries until the goal is resolved, and `startSpeakingPlan.waitSeconds`
  was raised 0.6 → 1.4 so the bot doesn't jump in on the recorded notice. The
  re-run produced a full ~2-minute natural conversation.
- **Telephony (daily limit):** a free Vapi-provisioned number caps outbound calls
  per day, which blocked the batch partway. Fixed by importing a Twilio number into
  Vapi (carrier = Twilio, no cap; voice brain = Vapi) and using it for all 12 calls,
  so every recording shares one number (required by the submission form).
- **Robustness (flaky network):** a long batch hit transient `Connection reset by
  peer` errors on `POST /call`. Added bounded retries with backoff to
  `VapiClient.create_call` (4xx still fails fast; only network errors retry), then
  re-ran the affected scenarios.
- **Analyzer (inflated findings):** the first automated pass over-reported (13 bugs,
  mostly "High", several just test-line transfer artifacts). Tightened the analyzer
  prompt to ignore the test-line goodbye, de-duplicate systemic issues, and reserve
  "High" for real failures — then hand-curated the final report.
