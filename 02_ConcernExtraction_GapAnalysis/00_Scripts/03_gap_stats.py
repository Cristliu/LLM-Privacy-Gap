#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gap Analysis - Statistics Generator
================================================
Calculates detailed statistics from existing gap analysis results.
Separates data processing from data analysis to allow metric iteration
without re-running costly LLM audits.

Input: gap_results/gaps_{provider}_{timestamp}.json
Output: gap_stats/stats_{provider}_{timestamp}.json

Usage:
    python 03_gap_stats.py --input <path_to_gaps_json>
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Set
from datetime import datetime

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.file_utils import ensure_dir, save_json, load_json

# =============================================================================
# Gap Type Taxonomy (Must match Auditor)
# =============================================================================

GAP_CATEGORIES = {
    "PRIVACY_POLICY_COVERAGE_GAPS": [
        "PRIVACY_POLICY_DETAIL_VAGUE",        # G1
        "PRIVACY_AI_FEATURE_UNADDRESSED",     # G2
        "PRIVACY_VULNERABLE_GROUP_NEGLECTED", # G3
        "PRIVACY_JURISDICTION_UNCLEAR",       # G4
    ],
    "PRIVACY_USER_PERCEPTION_GAPS": [
        "PRIVACY_EXPLICIT_POLICY_DISTRUST",   # G5
        "PRIVACY_POLICY_AWARENESS_DEFICIT",   # G6
    ],
}

ALL_KNOWN_GAP_TYPES = GAP_CATEGORIES["PRIVACY_POLICY_COVERAGE_GAPS"] + GAP_CATEGORIES["PRIVACY_USER_PERCEPTION_GAPS"]

class GapStatsGenerator:
    def __init__(self):
        self.stats = {
            "total_threads_audited": 0,
            "total_concerns_audited": 0,
            "concerns_with_gaps": 0,        # Number of concerns that have ANY gap
            "concerns_without_gaps": 0,     # Number of concerns with NO gaps
            
            # Instance Counts (One concern can have multiple gap instances)
            "total_gap_instances": 0,       # Total number of gap tags found
            "coverage_gap_instances": 0,    # Total G1-G4 tags
            "perception_gap_instances": 0,  # Total G5-G6 tags
            "new_gap_instances": 0,         # Total NEW_xxx instance count
            "new_gap_type_count": 0,        # Number of unique NEW_xxx types
            
            # Detailed breakdowns
            "by_gap_type": {},
            "by_topic": {},
            "new_gap_types_discovered": set()  # List of unique NEW_xxx type names
        }

    def process_concern(self, concern: Dict[str, Any]):
        self.stats["total_concerns_audited"] += 1
        
        gap_result = concern.get("gap_result")
        if not gap_result:
            # Should not happen if audited, but treat as no gap or error
            self.stats["concerns_without_gaps"] += 1
            return

        gap_detected = gap_result.get("gap_detected", False)
        gap_types = gap_result.get("gap_types", [])
        
        # --- Update Topic Stats ---
        topics = concern.get("topics", [])
        for topic in topics:
            if topic not in self.stats["by_topic"]:
                self.stats["by_topic"][topic] = {"total": 0, "with_gap": 0}
            self.stats["by_topic"][topic]["total"] += 1
            if gap_detected:
                self.stats["by_topic"][topic]["with_gap"] += 1

        # --- Update Gap Stats ---
        
        # Check if it's truly a "No Gap" concern
        # Logic: gap_detected is False OR no gap types listed
        if not gap_detected or not gap_types:
            self.stats["concerns_without_gaps"] += 1
            return
        
        # If we are here, it has gaps
        self.stats["concerns_with_gaps"] += 1
        
        for gt in gap_types:
            # 1. Count by specific type
            self.stats["by_gap_type"][gt] = self.stats["by_gap_type"].get(gt, 0) + 1
            self.stats["total_gap_instances"] += 1
            
            # 2. categorise
            if gt in GAP_CATEGORIES["PRIVACY_POLICY_COVERAGE_GAPS"]:
                self.stats["coverage_gap_instances"] += 1
            elif gt in GAP_CATEGORIES["PRIVACY_USER_PERCEPTION_GAPS"]:
                self.stats["perception_gap_instances"] += 1
            else:
                self.stats["new_gap_instances"] += 1
                self.stats["new_gap_types_discovered"].add(gt)

    def run(self, input_file: Path):
        print(f"Loading results from: {input_file}")
        data = load_json(input_file)
        
        if not data:
            print("Error: Could not load data.")
            return

        threads = data.get("threads", [])
        self.stats["total_threads_audited"] = len(threads)
        
        print(f"Processing {len(threads)} threads...")
        
        for thread in threads:
            # check post
            if thread.get("post"):
                for concern in thread["post"].get("concerns", []):
                    self.process_concern(concern)
            
            # check records/comments
            for record in thread.get("records", []):
                for concern in record.get("concerns", []):
                    self.process_concern(concern)
        
        # convert set to list for json serialization
        self.stats["new_gap_types_discovered"] = sorted(list(self.stats["new_gap_types_discovered"]))
        
        # Calculate new gap type count 
        self.stats["new_gap_type_count"] = len(self.stats["new_gap_types_discovered"])
        
        # Sort by_gap_type
        self.stats["by_gap_type"] = dict(sorted(self.stats["by_gap_type"].items(), key=lambda x: -x[1]))
        
        # Generate output
        output_data = {
            "source_file": str(input_file.name),
            "generated_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "provider": data.get("provider", "unknown"),
            "statistics": self.stats
        }
        
        # Save
        output_dir = input_file.parent.parent / "gap_stats" # assuming structure 02_Outputs/gap_results -> 02_Outputs/gap_stats
        ensure_dir(output_dir)
        output_path = output_dir / f"stats_{data.get('provider', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        save_json(output_data, output_path)
        print("\n✅ Statistics generated successfully!")
        print(f"   Output: {output_path}")
        print("   Summary:")
        print(f"   - Total Concerns: {self.stats['total_concerns_audited']}")
        print(f"   - With Gaps: {self.stats['concerns_with_gaps']}")
        print(f"   - Without Gaps: {self.stats['concerns_without_gaps']}")
        print(f"   - Total Gap Instances: {self.stats['total_gap_instances']}")
        print(f"     * Coverage (G1-G4): {self.stats['coverage_gap_instances']}")
        print(f"     * Perception (G5-G6): {self.stats['perception_gap_instances']}")
        print(f"     * New Types: {self.stats['new_gap_type_count']}, {self.stats['new_gap_instances']}")

def main():
    parser = argparse.ArgumentParser(description="Generate statistics from Gap Analysis results")
    parser.add_argument("--input", required=True, type=str, help="Path to gaps result JSON file")
    args = parser.parse_args()
    
    generator = GapStatsGenerator()
    generator.run(Path(args.input))

if __name__ == "__main__":
    main()
