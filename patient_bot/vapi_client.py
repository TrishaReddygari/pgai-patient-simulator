"""Thin wrapper over the Vapi REST API for placing and retrieving calls."""
from __future__ import annotations

import time
from typing import Dict

import requests

BASE_URL = "https://api.vapi.ai"
TERMINAL_STATUSES = {"ended", "failed", "busy", "no-answer", "canceled"}


class VapiClient:
    def __init__(self, api_key: str, phone_number_id: str):
        self.api_key = api_key
        self.phone_number_id = phone_number_id
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    def create_call(self, assistant: Dict, target_number: str, retries: int = 3) -> Dict:
        """Place an outbound call. Returns the created call object (incl. id).

        Retries on transient network errors (the Vapi API occasionally resets the
        connection during a long batch); does not retry on 4xx (real errors).
        """
        payload = {
            "phoneNumberId": self.phone_number_id,
            "assistant": assistant,
            "customer": {"number": target_number},
        }
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.post(f"{BASE_URL}/call", json=payload, timeout=30)
            except requests.exceptions.RequestException as e:
                last_err = e
                print(f"    network error on attempt {attempt}/{retries}: {e}")
                time.sleep(3 * attempt)
                continue
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Vapi create_call failed ({resp.status_code}): {resp.text}"
                )
            return resp.json()
        raise RuntimeError(f"Vapi create_call failed after {retries} attempts: {last_err}")

    def get_call(self, call_id: str) -> Dict:
        resp = self.session.get(f"{BASE_URL}/call/{call_id}", timeout=30)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Vapi get_call failed ({resp.status_code}): {resp.text}"
            )
        return resp.json()

    def poll_until_done(
        self, call_id: str, timeout_seconds: int = 360, interval: int = 5
    ) -> Dict:
        """Poll until the call reaches a terminal status (or we time out)."""
        deadline = time.monotonic() + timeout_seconds
        last = {}
        while time.monotonic() < deadline:
            last = self.get_call(call_id)
            status = last.get("status")
            if status in TERMINAL_STATUSES:
                return last
            print(f"    ...call {call_id[:8]} status={status}")
            time.sleep(interval)
        print(f"    ! timed out waiting for call {call_id[:8]} to end")
        return last


def extract_artifacts(call: Dict) -> Dict:
    """Pull the bits we care about out of a (finished) call object.

    Vapi has shifted these fields around across versions, so we look in a few
    places and degrade gracefully if something is missing.
    """
    artifact = call.get("artifact") or {}
    recording_url = (
        artifact.get("recordingUrl")
        or (artifact.get("recording") or {}).get("url")
        or call.get("recordingUrl")
    )
    stereo_url = (
        artifact.get("stereoRecordingUrl")
        or (artifact.get("recording") or {}).get("stereoUrl")
    )
    transcript = artifact.get("transcript") or call.get("transcript") or ""
    messages = artifact.get("messages") or call.get("messages") or []
    return {
        "recording_url": recording_url,
        "stereo_recording_url": stereo_url,
        "transcript": transcript,
        "messages": messages,
        "status": call.get("status"),
        "ended_reason": call.get("endedReason"),
        "cost": call.get("cost"),
        "id": call.get("id"),
    }
