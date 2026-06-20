"""Environment configuration and validation."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    vapi_api_key: str
    vapi_phone_number_id: str
    openai_api_key: str
    target_number: str
    in_call_model: str
    analyzer_model: str
    max_call_seconds: int

    @classmethod
    def load(cls) -> "Config":
        cfg = cls(
            vapi_api_key=os.getenv("VAPI_API_KEY", ""),
            vapi_phone_number_id=os.getenv("VAPI_PHONE_NUMBER_ID", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            target_number=os.getenv("TARGET_NUMBER", "+18054398008"),
            in_call_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            analyzer_model=os.getenv("ANALYZER_MODEL", "gpt-4o"),
            max_call_seconds=int(os.getenv("MAX_CALL_SECONDS", "180")),
        )
        return cfg

    def require_for_calls(self) -> None:
        """Validate the vars needed to place calls; raise a clear error if missing."""
        missing = [
            name
            for name, val in {
                "VAPI_API_KEY": self.vapi_api_key,
                "VAPI_PHONE_NUMBER_ID": self.vapi_phone_number_id,
            }.items()
            if not val
        ]
        if missing:
            raise SystemExit(
                f"Missing required env vars for placing calls: {', '.join(missing)}.\n"
                "Copy .env.example to .env and fill them in (see README)."
            )

    def require_for_analysis(self) -> None:
        if not self.openai_api_key:
            raise SystemExit(
                "Missing OPENAI_API_KEY (needed for the bug-analysis pass). "
                "Copy .env.example to .env and fill it in."
            )
