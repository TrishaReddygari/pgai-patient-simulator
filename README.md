# PGAI Patient-Simulator Voice Bot

A Python bot that **calls the Pretty Good AI test agent** (`+1-805-439-8008`),
role-plays realistic **patients** (scheduling, reschedules, cancellations,
refills, hours/insurance questions, and edge cases), **records + transcribes**
both sides of each call, and produces a **bug report** on the agent's behavior.

The realtime voice (STT → LLM → TTS, barge-in, telephony, recording) is handled
by [Vapi](https://vapi.ai); this code defines the patient personas/scenarios,
orchestrates the calls, collects the artifacts, and runs an LLM bug-analysis pass.

## Setup

1. **Python deps** (Python 3.10+)
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Accounts / keys** — copy the env template and fill it in:
   ```bash
   cp .env.example .env
   ```
   - **Vapi** (`VAPI_API_KEY`, `VAPI_PHONE_NUMBER_ID`): make a free account at
     [dashboard.vapi.ai](https://dashboard.vapi.ai), grab your private API key,
     and create/buy a phone number (Dashboard → Phone Numbers) — copy its ID.
     Note: free Vapi-provisioned numbers have a **daily outbound-call limit**. To
     run all scenarios in one sitting, **import your own Twilio number** into Vapi
     (Phone Numbers → Import → Twilio) and use that number's ID — no daily cap, and
     it keeps every call on a single number (which the submission form requires).
   - **OpenAI** (`OPENAI_API_KEY`): used for the transcript bug-analysis pass.
   - `TARGET_NUMBER` is already set to the assessment number — leave it.

3. *(Optional)* install `ffmpeg` so non-mp3 recordings auto-convert to mp3.

## Run

One command runs the whole thing — place every call, then analyze:

```bash
python run.py --all
```

Other modes:

```bash
python run.py --list                       # list scenarios
python run.py --scenario weekend_booking   # run a single scenario (smoke test)
python run.py --scenario simple_schedule refill_basic   # run a few
python run.py --analyze-only               # re-run bug analysis over saved transcripts
python run.py --all --no-analyze           # calls only, skip analysis
```

## Output

- `recordings/<scenario>.mp3` — audio of each call
- `transcripts/<scenario>.txt` — readable Patient/Agent transcript (+ `.json` raw)
- `results/<scenario>.json` — raw Vapi call artifacts
- `BUG_REPORT.md` — aggregated, severity-sorted findings

## Scenarios

12 scenarios spanning every required category, including deliberate edge cases:
a **Sunday-booking** probe (closed-day bug), an **early controlled-substance
refill** (over-promising), **barge-in/interruptions**, an **ambiguous relative
date**, a **rambling unclear** caller, and an **out-of-scope medical-advice**
request. See `scenarios.py`.

## Cost

Sequential short calls (~2 min, `MAX_CALL_SECONDS=180`) keep total spend well
under the challenge's ~$20 budget — expect roughly $5–10 across Vapi + OpenAI.

## Notes

- The bot stays in character as a human patient and never reveals it's automated.
- It waits for the office agent to greet first (`assistant-waits-for-user`) for a
  natural call open.
- Tune voice/turn-taking knobs at the top of `patient_bot/persona.py` between
  runs (this is the main iteration lever for voice quality).
