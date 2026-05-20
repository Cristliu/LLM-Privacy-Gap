#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gap Analysis Pipeline Runner
===============================
Orchestrates the pipeline for identifying coverage gaps in LLM privacy policies.

Pipeline Stages:
  0: Data Preprocessing (filter Reddit threads)
  1: Concern Extraction (extract privacy concerns, split multi-topic)
  2: Gap Auditing (analyze gaps with orthogonal G1-G6 taxonomy)
  3: Result Mapping (generate reports)

Usage:
    python run_pipeline.py --phase N [--provider PROVIDER] [--test] [--concurrent N]
    python run_pipeline.py --all [--test]
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# Pipeline phase definitions
PHASES = {
    0: {
        "name": "Data Preprocessing",
        "script": "00_data_preprocessor.py",
        "description": "Filter and prepare Reddit threads",
        "supports_concurrent": False
    },
    1: {
        "name": "Concern Extraction",
        "script": "01_concern_extractor.py",
        "description": "Extract privacy concerns (single-topic per concern)",
        "supports_concurrent": True
    },
    2: {
        "name": "Gap Auditing",
        "script": "02_gap_auditor.py",
        "description": "Detect gaps using G1-G6 orthogonal taxonomy",
        "supports_concurrent": True
    },
    3: {
        "name": "Result Mapping",
        "script": "04_result_mapper.py",
        "description": "Generate JSON/CSV/Markdown reports",
        "supports_concurrent": False
    }
}

# Provider list
PROVIDERS = ["chatgpt", "claude", "gemini", "grok", "deepseek"]


def run_phase(
    phase: int,
    provider: Optional[str] = None,
    test_mode: bool = False,
    concurrent: int = 70,
    extra_args: Optional[List[str]] = None
) -> int:
    """Run a single pipeline phase."""
    if phase not in PHASES:
        print(f"❌ Unknown phase: {phase}")
        return 1
    
    phase_info = PHASES[phase]
    script_dir = Path(__file__).parent
    script_path = script_dir / phase_info["script"]
    
    if not script_path.exists():
        print(f"❌ Script not found: {script_path}")
        return 1
    
    print(f"\n{'='*60}")
    print(f"Phase {phase}: {phase_info['name']}")
    print(f"Description: {phase_info['description']}")
    print(f"{'='*60}\n")
    
    # Build command
    cmd = [sys.executable, str(script_path)]
    
    if provider:
        cmd.extend(["--provider", provider])
    
    if test_mode:
        cmd.append("--test")
    
    # Add concurrent flag for phases that support it
    if phase_info["supports_concurrent"]:
        cmd.extend(["--concurrent", str(concurrent)])
    
    if extra_args:
        cmd.extend(extra_args)
    
    # Run
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print(f"❌ Phase {phase} failed with code {result.returncode}")
    else:
        print(f"✅ Phase {phase} completed successfully")
    
    return result.returncode


def run_all_phases(
    provider: Optional[str] = None,
    test_mode: bool = False,
    concurrent: int = 70,
    start_phase: int = 0
) -> int:
    """Run all pipeline phases in sequence."""
    print("\n" + "="*60)
    print("GAP ANALYSIS PIPELINE")
    print("="*60)
    print(f"Mode: {'TEST' if test_mode else 'FULL'}")
    print(f"Provider: {provider or 'ALL'}")
    print(f"Concurrency: {concurrent}")
    print("="*60 + "\n")
    
    for phase in sorted(PHASES.keys()):
        if phase < start_phase:
            continue
        
        result = run_phase(phase, provider, test_mode, concurrent)
        if result != 0:
            print(f"\n❌ Pipeline failed at phase {phase}")
            return result
    
    print("\n" + "="*60)
    print("✅ ALL PHASES COMPLETED SUCCESSFULLY")
    print("="*60)
    
    return 0


def run_by_provider(
    test_mode: bool = False,
    concurrent: int = 70,
    providers: Optional[List[str]] = None
) -> int:
    """Run phases 1-2 for each provider sequentially, then phase 3."""
    if providers is None:
        providers = PROVIDERS
    
    print("\n" + "="*60)
    print("GAP ANALYSIS PIPELINE (Per-Provider Mode)")
    print("="*60)
    print(f"Mode: {'TEST' if test_mode else 'FULL'}")
    print(f"Providers: {', '.join(providers)}")
    print(f"Concurrency: {concurrent}")
    print("="*60 + "\n")
    
    # Phase 0: Preprocessing (once for all)
    result = run_phase(0, None, test_mode, concurrent)
    if result != 0:
        return result
    
    # Phases 1-2: Per provider
    for provider in providers:
        print(f"\n{'#'*60}")
        print(f"# Processing Provider: {provider.upper()}")
        print(f"{'#'*60}")
        
        for phase in [1, 2]:
            result = run_phase(phase, provider, test_mode, concurrent)
            if result != 0:
                print(f"\n❌ Pipeline failed for {provider} at phase {phase}")
                return result
    
    # Phase 3: Result mapping (all providers)
    result = run_phase(3, None, test_mode, concurrent)
    if result != 0:
        return result
    
    print("\n" + "="*60)
    print("✅ ALL PROVIDERS COMPLETED SUCCESSFULLY")
    print("="*60)
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Gap Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Pipeline Phases:
  0: Data Preprocessing
  1: Concern Extraction (single-topic per concern)
  2: Gap Auditing (G1-G6 orthogonal taxonomy)
  3: Result Mapping (JSON/CSV/Markdown)

Examples:
  python run_pipeline.py --phase 1 --test              # Extract concerns (test)
  python run_pipeline.py --phase 2 --provider chatgpt  # Audit ChatGPT only
  python run_pipeline.py --all --test                  # All phases (test)
  python run_pipeline.py --all --concurrent 50         # Full run (50 threads)
  python run_pipeline.py --by-provider --test          # Run per provider
        """
    )
    
    parser.add_argument(
        "--phase", type=int, choices=list(PHASES.keys()),
        help="Run specific phase (0-3)"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run all phases sequentially"
    )
    parser.add_argument(
        "--by-provider", action="store_true",
        help="Run phases 1-2 per provider, then phase 3"
    )
    parser.add_argument(
        "--provider", type=str, choices=PROVIDERS,
        help="Process specific provider only"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Test mode (limited data)"
    )
    parser.add_argument(
        "--concurrent", type=int, default=70,
        help="Max concurrent API requests (default: 70)"
    )
    parser.add_argument(
        "--start", type=int, default=0,
        help="Start from specific phase (with --all)"
    )
    
    args = parser.parse_args()
    
    if args.by_provider:
        providers = [args.provider] if args.provider else None
        return run_by_provider(
            test_mode=args.test,
            concurrent=args.concurrent,
            providers=providers
        )
    elif args.all:
        return run_all_phases(
            provider=args.provider,
            test_mode=args.test,
            concurrent=args.concurrent,
            start_phase=args.start
        )
    elif args.phase is not None:
        return run_phase(
            phase=args.phase,
            provider=args.provider,
            test_mode=args.test,
            concurrent=args.concurrent
        )
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())