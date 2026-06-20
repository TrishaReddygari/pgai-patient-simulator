"""GPT-powered bug analysis over call transcripts.

For each call we ask the model to act as a QA reviewer: given the scenario's
intended outcome and the transcript, surface *useful* bugs (not punctuation
nitpicks) in the Pretty Good AI agent's behavior, grounded in a rubric.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

from openai import OpenAI

SYSTEM = """\
You are a meticulous QA engineer reviewing a voice AI that works the front desk \
of a medical practice (scheduling, reschedules, cancellations, refills, and \
answering questions about hours/location/insurance).

You are given (a) what the test caller was trying to do and what a CORRECT agent \
should have done, and (b) the call transcript. Your job is to find real, useful \
bugs and quality issues in the AGENT's responses (the "AGENT (Pretty Good AI)" \
turns), not in the patient's.

Focus on things that matter:
- Booking on closed days / outside office hours, or contradicting stated hours.
- Confirming things it can't actually do (e.g., guaranteeing a controlled-substance
  early refill) or that were never verified.
- Hallucinated availability, insurance acceptance, prices, or policies.
- Wrong read-backs (date/time/name/medication) or double-booking / not cancelling.
- Giving medical advice / diagnosing (out of scope) or mishandling an urgent symptom.
- Broken turn-taking: ignoring interruptions, talking over, losing the latest request.
- Failing to confirm the outcome, or leaving the caller without a clear next step.

Do NOT report: minor wording, punctuation, filler words, or the caller's own behavior.
If the agent handled the call well, it is fine to return an empty bug list.

Important judgment rules (avoid inflated reports):
- The number called is a TEST LINE. When the agent says it is "connecting you to a
  representative" and the call then ends with "You've reached the Pretty Good AI test
  line. Goodbye," that goodbye is a HARNESS ARTIFACT, not a bug. Do not file the transfer
  ending itself as a bug. (Reaching for a transfer INSTEAD of completing a task the agent
  said it could do IS a valid bug.)
- Do not double-count: report each distinct problem once, even if it shows up in several
  turns. Prefer one well-described systemic bug over many near-duplicates.
- Reserve "High" for clear task failures, safety/compliance issues, or fabricated data.
  Use "Medium"/"Low" for messaging/expectation-setting issues. Don't default everything to High.

Return STRICT JSON with this shape:
{
  "call_quality": "<one sentence on overall agent + voice-interaction quality>",
  "bugs": [
    {
      "title": "<short bug title>",
      "severity": "High" | "Medium" | "Low",
      "timestamp": "<m:ss from the transcript if available, else empty>",
      "details": "<what happened and why it's a problem>",
      "expected_behavior": "<what a correct agent should have done>"
    }
  ]
}
"""

USER_TEMPLATE = """\
SCENARIO: {scenario_id} ({category})
CALLER GOAL: {goal}
WHAT A CORRECT AGENT SHOULD DO: {success_criteria}

TRANSCRIPT:
{transcript}
"""


def analyze_transcript(
    client: OpenAI, model: str, scenario_meta: Dict, transcript_text: str
) -> Dict:
    user = USER_TEMPLATE.format(
        scenario_id=scenario_meta.get("id", ""),
        category=scenario_meta.get("category", ""),
        goal=scenario_meta.get("goal", ""),
        success_criteria=scenario_meta.get("success_criteria", ""),
        transcript=transcript_text,
    )
    resp = client.chat.completions.create(
        model=model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    )
    try:
        data = json.loads(resp.choices[0].message.content)
    except (json.JSONDecodeError, TypeError):
        data = {"call_quality": "could not parse analysis", "bugs": []}
    data["scenario_id"] = scenario_meta.get("id", "")
    return data


SEV_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def write_bug_report(results: List[Dict], path: str) -> None:
    """Aggregate per-call analyses into a single curated-looking BUG_REPORT.md."""
    all_bugs = []
    for r in results:
        for b in r.get("bugs", []):
            b = dict(b)
            b["call"] = r.get("scenario_id", "")
            all_bugs.append(b)
    all_bugs.sort(key=lambda b: SEV_ORDER.get(b.get("severity", "Low"), 3))

    counts = {"High": 0, "Medium": 0, "Low": 0}
    for b in all_bugs:
        counts[b.get("severity", "Low")] = counts.get(b.get("severity", "Low"), 0) + 1

    lines: List[str] = []
    lines.append("# Bug Report — Pretty Good AI Agent")
    lines.append("")
    lines.append(
        "Issues found while stress-testing the agent at +1-805-439-8008 with a "
        "patient-simulator bot. Generated from call transcripts, then reviewed by hand."
    )
    lines.append("")
    lines.append(
        f"**Summary:** {len(all_bugs)} issues across {len(results)} calls "
        f"— {counts.get('High', 0)} High, {counts.get('Medium', 0)} Medium, "
        f"{counts.get('Low', 0)} Low."
    )
    lines.append("")
    lines.append("> Each entry cites the call (see `transcripts/<call>.txt` and "
                 "`recordings/<call>.mp3`) and an approximate timestamp.")
    lines.append("")

    for i, b in enumerate(all_bugs, 1):
        lines.append(f"## {i}. {b.get('title', 'Untitled')}")
        lines.append("")
        lines.append(f"- **Severity:** {b.get('severity', '')}")
        ts = b.get("timestamp", "")
        loc = f"`transcripts/{b.get('call','')}.txt`" + (f" at {ts}" if ts else "")
        lines.append(f"- **Where:** {loc}")
        lines.append(f"- **What happened:** {b.get('details', '')}")
        lines.append(f"- **Expected:** {b.get('expected_behavior', '')}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Per-call quality notes")
    lines.append("")
    for r in results:
        lines.append(f"- **{r.get('scenario_id','')}:** {r.get('call_quality','')}")
    lines.append("")

    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"wrote bug report -> {path} ({len(all_bugs)} issues)")
