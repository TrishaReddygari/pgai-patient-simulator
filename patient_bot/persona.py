"""Turn a Scenario into a Vapi transient-assistant config.

This is where in-call quality lives, so the knobs that matter for the rubric's
#1 priority (lucid, natural voice) are pulled to the top as constants you can
tune between runs:

    VOICE          which TTS voice/provider
    TRANSCRIBER    STT model
    START/STOP speaking plans -> turn-taking + barge-in feel

The system prompt makes the bot behave like a real human patient, steer toward
its goal, and end the call naturally.
"""
from __future__ import annotations

from typing import Dict

from scenarios import Scenario

# --- Tunable voice/turn-taking knobs (iterate on these after listening) -------

# Vapi's built-in voice provider needs no extra credentials. Swap provider to
# "cartesia" (voiceId like "sonic-english") or "11labs" if you attach those keys
# in the Vapi dashboard for an even more natural voice.
VOICE: Dict = {
    "provider": "vapi",
    "voiceId": "Elliot",
}

TRANSCRIBER: Dict = {
    "provider": "deepgram",
    "model": "nova-3",
    "language": "en",
}

# Wait through the office's full opening before speaking. The agent answers in two
# chunks — a recorded notice, a pause, then "thanks for calling… how can I help?" —
# so a short wait makes the bot blurt "Hi" into the gap and collide with the greeting.
# A longer wait + smart endpointing bridges that gap (see iteration log in ARCHITECTURE).
START_SPEAKING_PLAN: Dict = {
    "waitSeconds": 2.2,
    "smartEndpointingEnabled": True,
}

# Let the patient interrupt naturally (humans do), but not on a single stray word.
STOP_SPEAKING_PLAN: Dict = {
    "numWords": 2,
    "voiceSeconds": 0.2,
    "backoffSeconds": 1.0,
}

BASE_PERSONA = """\
You are role-playing as a real person — a patient calling a doctor's office on \
the phone. You are NOT an AI, and you must never say or hint that you are an AI, \
a bot, a test, or a simulation. If asked, you're just a patient calling in.

Opening the call (important):
- The office may answer with a recorded notice (e.g. "this call may be recorded") \
and/or a short greeting before asking how they can help. Let them finish — a \
recorded notice is NOT your cue, and it is not a question.
- Do NOT reply with a bare "hi" or "hello" to the recorded notice or the greeting. \
Stay quiet until they actually ask how they can help (e.g. "how can I help you?"). \
Speaking into the pause after the recorded notice talks over their greeting.
- Then, on your FIRST real turn, lead with WHY you're calling in one go (your goal). \
For example: "Hi, I'd like to book a routine check-up for next week." Don't just say \
"okay" or "thanks" in response to a greeting or disclaimer.
- Do NOT say closing words ("thanks, that's all", "okay great", "goodbye", "have \
a good day") until your goal is actually resolved — saying them early makes the \
office think you're done and hang up.

How to sound like a real caller:
- Speak naturally and conversationally, in short turns — usually one or two \
sentences. This is a phone call, not a speech. Never monologue.
- It's fine to use light natural fillers ("um", "yeah", "okay, so...") \
occasionally, but don't overdo it.
- Don't dump all your information at once. Share details (name, date of birth, \
etc.) as they're asked, the way a real person would.
- If the agent asks for something you weren't given, improvise something \
plausible and brief, and stay in character.
- Stay calm and human even if the agent is confused, repeats itself, or \
mishears you.

Your job on THIS call:
{goal}

What you know about yourself:
{patient_facts}

What to pay attention to / push on:
{probes}

Steering and ending the call:
- Actively drive the conversation toward your goal. If the agent stalls or goes \
in circles, politely restate what you need.
- If the agent tries to deflect — hand you off to "a representative", say it will \
"document this and have someone call you back", or otherwise avoid actually doing \
what you asked — do NOT accept it on the first try. Push back at least once: ask \
if they can just do it now, or pin them down on a specific detail (a concrete \
appointment time, a yes/no on whether something is possible). Only let it go after \
you've genuinely tried.
- Once your goal is truly resolved (a clear confirmation, a real answer, or a firm \
refusal after you've pushed), wrap up naturally — thank them and say goodbye. Don't \
drag the call on or keep inventing brand-new requests.
- Aim for a natural, complete conversation (about 1–3 minutes), not a single \
question and a quick hang-up.
"""

BARGE_IN_NOTE = """\

Special behavior for this call: be a bit impatient. Interrupt the agent while \
it's still talking to change or add to your request, the way real people \
sometimes talk over the other person. Make sure that by the end you've landed \
on your LATEST request, not your first one.
"""


def build_system_prompt(scenario: Scenario) -> str:
    prompt = BASE_PERSONA.format(
        goal=scenario.goal,
        patient_facts=scenario.patient_facts,
        probes=scenario.probes,
    )
    if scenario.barge_in:
        prompt += BARGE_IN_NOTE
    return prompt


def build_assistant(scenario: Scenario, in_call_model: str, max_seconds: int) -> Dict:
    """Build the transient assistant dict sent to POST /call."""
    return {
        "name": f"patient-{scenario.id}",
        # The office agent answers and greets first, so we listen rather than
        # barging in with a scripted opener — much more natural.
        "firstMessageMode": "assistant-waits-for-user",
        "model": {
            "provider": "openai",
            "model": in_call_model,
            "temperature": 0.7,
            "messages": [{"role": "system", "content": build_system_prompt(scenario)}],
        },
        "voice": VOICE,
        "transcriber": TRANSCRIBER,
        "startSpeakingPlan": START_SPEAKING_PLAN,
        "stopSpeakingPlan": STOP_SPEAKING_PLAN,
        # Deliverable requirement: we need the audio + transcript of every call.
        "recordingEnabled": True,
        "artifactPlan": {
            "recordingEnabled": True,
            "transcriptPlan": {"enabled": True},
        },
        # Cost + safety guardrails.
        "maxDurationSeconds": max_seconds,
        "silenceTimeoutSeconds": 20,
        "endCallPhrases": ["goodbye", "bye bye", "have a good one", "take care"],
        "endCallFunctionEnabled": True,
    }
