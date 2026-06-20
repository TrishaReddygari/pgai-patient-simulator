"""Download recordings and write human-readable transcripts to disk."""
from __future__ import annotations

import json
import os
import subprocess
from typing import Dict, List, Optional

import requests

# role -> who is speaking. Our Vapi assistant is the patient; the remote party
# (the Pretty Good AI agent that answered) shows up as "user".
ROLE_LABELS = {
    "assistant": "PATIENT (our bot)",
    "bot": "PATIENT (our bot)",
    "user": "AGENT (Pretty Good AI)",
}


def _ext_from_url(url: str) -> str:
    path = url.split("?", 1)[0]
    for ext in (".mp3", ".ogg", ".wav", ".m4a"):
        if path.lower().endswith(ext):
            return ext
    return ".mp3"


def _maybe_convert_to_mp3(src_path: str) -> str:
    """If the recording isn't already mp3/ogg, convert to mp3 via ffmpeg if present.

    The challenge requires ogg or mp3. If ffmpeg isn't installed we keep the
    original file and let the caller know.
    """
    base, ext = os.path.splitext(src_path)
    if ext.lower() in (".mp3", ".ogg"):
        return src_path
    if not _ffmpeg_available():
        print(f"    ! {ext} recording saved; install ffmpeg to auto-convert to mp3")
        return src_path
    dest = base + ".mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-i", src_path, dest],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.remove(src_path)
    return dest


def _ffmpeg_available() -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def download_recording(url: str, dest_dir: str, scenario_id: str) -> Optional[str]:
    if not url:
        print("    ! no recording URL on this call")
        return None
    os.makedirs(dest_dir, exist_ok=True)
    ext = _ext_from_url(url)
    raw_path = os.path.join(dest_dir, f"{scenario_id}{ext}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    with open(raw_path, "wb") as f:
        f.write(resp.content)
    final_path = _maybe_convert_to_mp3(raw_path)
    print(f"    saved recording -> {final_path}")
    return final_path


def format_transcript(messages: List[Dict], fallback: str = "") -> str:
    """Build a readable Patient/Agent transcript from Vapi messages."""
    lines: List[str] = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            continue
        text = m.get("message") or m.get("content") or ""
        if not text:
            continue
        label = ROLE_LABELS.get(role, role or "?")
        ts = m.get("secondsFromStart")
        stamp = f"[{int(ts // 60):d}:{int(ts % 60):02d}] " if isinstance(ts, (int, float)) else ""
        lines.append(f"{stamp}{label}: {text}")
    if not lines and fallback:
        return fallback
    return "\n".join(lines)


def save_transcript(
    artifacts: Dict, dest_dir: str, scenario_id: str, scenario_meta: Dict
) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    pretty = format_transcript(artifacts.get("messages", []), artifacts.get("transcript", ""))

    txt_path = os.path.join(dest_dir, f"{scenario_id}.txt")
    header = (
        f"Scenario: {scenario_id} ({scenario_meta.get('category', '')})\n"
        f"Goal: {scenario_meta.get('goal', '')}\n"
        f"Call status: {artifacts.get('status')} / {artifacts.get('ended_reason')}\n"
        f"Vapi call id: {artifacts.get('id')}\n"
        + "-" * 70
        + "\n"
    )
    with open(txt_path, "w") as f:
        f.write(header + pretty + "\n")

    json_path = os.path.join(dest_dir, f"{scenario_id}.json")
    with open(json_path, "w") as f:
        json.dump(
            {"scenario": scenario_meta, "artifacts": artifacts},
            f,
            indent=2,
            default=str,
        )
    print(f"    saved transcript -> {txt_path}")
    return txt_path
