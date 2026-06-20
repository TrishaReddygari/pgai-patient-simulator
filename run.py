#!/usr/bin/env python3
"""Patient-simulator voice bot — single entrypoint.

Usage:
    python run.py --all                 # run every scenario, then analyze
    python run.py --scenario <id> ...   # run one or more scenarios, then analyze
    python run.py --analyze-only        # re-run bug analysis over saved transcripts
    python run.py --list                # list available scenarios
    python run.py --no-analyze          # run calls but skip the analysis pass

Calls are placed sequentially (kinder on rate limits and cost). After the calls,
each transcript is run through a GPT bug-analysis pass and aggregated into
BUG_REPORT.md.
"""
from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import os
import time
from typing import Dict, List

from openai import OpenAI

import scenarios as scenario_lib
from patient_bot import analyzer, collector
from patient_bot.config import Config
from patient_bot.persona import build_assistant
from patient_bot.vapi_client import VapiClient, extract_artifacts

ROOT = os.path.dirname(os.path.abspath(__file__))
RECORDINGS_DIR = os.path.join(ROOT, "recordings")
TRANSCRIPTS_DIR = os.path.join(ROOT, "transcripts")
RESULTS_DIR = os.path.join(ROOT, "results")
BUG_REPORT_PATH = os.path.join(ROOT, "BUG_REPORT.md")


def run_one_call(client: VapiClient, cfg: Config, scenario) -> Dict:
    print(f"\n=== {scenario.id} ({scenario.category}) ===")
    print(f"    goal: {scenario.goal}")
    assistant = build_assistant(scenario, cfg.in_call_model, cfg.max_call_seconds)
    call = client.create_call(assistant, cfg.target_number)
    call_id = call.get("id")
    print(f"    placed call {call_id} -> {cfg.target_number}")
    final = client.poll_until_done(call_id)
    artifacts = extract_artifacts(final)

    scenario_meta = dataclasses.asdict(scenario)
    collector.download_recording(artifacts.get("recording_url"), RECORDINGS_DIR, scenario.id)
    collector.save_transcript(artifacts, TRANSCRIPTS_DIR, scenario.id, scenario_meta)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, f"{scenario.id}.json"), "w") as f:
        json.dump({"scenario": scenario_meta, "artifacts": artifacts}, f, indent=2, default=str)
    return {"scenario": scenario_meta, "artifacts": artifacts}


def run_calls(scenario_ids: List[str], cfg: Config, delay: int) -> None:
    cfg.require_for_calls()
    client = VapiClient(cfg.vapi_api_key, cfg.vapi_phone_number_id)
    for i, sid in enumerate(scenario_ids):
        scenario = scenario_lib.get(sid)
        try:
            run_one_call(client, cfg, scenario)
        except Exception as e:  # keep going so one bad call doesn't kill the batch
            print(f"    ! call for {sid} failed: {e}")
        if i < len(scenario_ids) - 1 and delay:
            print(f"    (waiting {delay}s before next call)")
            time.sleep(delay)


def analyze_all(cfg: Config) -> None:
    cfg.require_for_analysis()
    oai = OpenAI(api_key=cfg.openai_api_key)
    results = []
    for path in sorted(glob.glob(os.path.join(TRANSCRIPTS_DIR, "*.json"))):
        with open(path) as f:
            saved = json.load(f)
        scenario_meta = saved.get("scenario", {})
        artifacts = saved.get("artifacts", {})
        transcript_text = collector.format_transcript(
            artifacts.get("messages", []), artifacts.get("transcript", "")
        )
        if not transcript_text.strip():
            print(f"    ! skipping {scenario_meta.get('id')} — empty transcript")
            continue
        print(f"    analyzing {scenario_meta.get('id')} ...")
        results.append(
            analyzer.analyze_transcript(oai, cfg.analyzer_model, scenario_meta, transcript_text)
        )
    if results:
        analyzer.write_bug_report(results, BUG_REPORT_PATH)
    else:
        print("    no transcripts to analyze yet — run some calls first.")


def main() -> None:
    parser = argparse.ArgumentParser(description="PGAI patient-simulator voice bot")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="run every scenario")
    group.add_argument("--scenario", nargs="+", metavar="ID", help="run specific scenario(s)")
    group.add_argument("--analyze-only", action="store_true", help="re-run analysis only")
    group.add_argument("--list", action="store_true", help="list scenarios and exit")
    parser.add_argument("--no-analyze", action="store_true", help="skip analysis after calls")
    parser.add_argument("--delay", type=int, default=10, help="seconds between calls")
    args = parser.parse_args()

    if args.list:
        for s in scenario_lib.SCENARIOS:
            print(f"  {s.id:22s} {s.category}")
        return

    cfg = Config.load()

    if args.analyze_only:
        analyze_all(cfg)
        return

    if args.all:
        ids = scenario_lib.all_ids()
    elif args.scenario:
        ids = args.scenario
    else:
        parser.print_help()
        return

    run_calls(ids, cfg, args.delay)
    if not args.no_analyze:
        print("\n=== Analyzing transcripts ===")
        analyze_all(cfg)


if __name__ == "__main__":
    main()
