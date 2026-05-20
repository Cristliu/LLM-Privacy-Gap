#!/usr/bin/env python3
"""
Gap Sample Extractor

This script extracts stratified samples from gap analysis results:
1. For each category-gap combination with >=3 gaps, randomly sample 3
2. For combinations with <3 gaps, extract all
3. For any combination containing "NEW" (topic or gap type), extract all

Author: Auto-generated
"""

import json
import os
import random
from collections import defaultdict
from pathlib import Path
from datetime import datetime

# Set random seed for reproducibility
random.seed(42)

# Sample size threshold
SAMPLE_SIZE = 3


def load_indexed_gaps(file_path: str) -> dict:
    """Load the indexed gaps JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_samples_for_provider(provider: str, indexed_gaps: dict) -> dict:
    """
    Extract stratified samples for a single provider.
    
    Rules:
    - If category-gap contains "NEW", extract all
    - If count >= SAMPLE_SIZE, randomly sample SAMPLE_SIZE
    - If count < SAMPLE_SIZE, extract all
    
    Returns:
        dict with sampled gaps and statistics
    """
    sampled_gaps = {}
    statistics = {
        "category_gap_samples": {},
        "total_sampled": 0,
        "total_available": 0,
        "new_category_gaps": [],
        "full_extraction_categories": [],  # categories where all were extracted (< SAMPLE_SIZE)
        "sampled_categories": [],  # categories where sampling was done (>= SAMPLE_SIZE)
    }
    
    for category_gap, gaps_dict in sorted(indexed_gaps.items()):
        gap_count = len(gaps_dict)
        statistics["total_available"] += gap_count
        
        # Check if this category contains "NEW"
        contains_new = "NEW" in category_gap
        
        if contains_new:
            # Extract all for NEW categories
            sampled_gaps[category_gap] = gaps_dict
            sample_count = gap_count
            statistics["new_category_gaps"].append(category_gap)
            statistics["category_gap_samples"][category_gap] = {
                "available": gap_count,
                "sampled": sample_count,
                "method": "ALL (contains NEW)"
            }
        elif gap_count < SAMPLE_SIZE:
            # Extract all if less than SAMPLE_SIZE
            sampled_gaps[category_gap] = gaps_dict
            sample_count = gap_count
            statistics["full_extraction_categories"].append(category_gap)
            statistics["category_gap_samples"][category_gap] = {
                "available": gap_count,
                "sampled": sample_count,
                "method": f"ALL (< {SAMPLE_SIZE})"
            }
        else:
            # Random sample SAMPLE_SIZE
            all_indices = list(gaps_dict.keys())
            sampled_indices = random.sample(all_indices, SAMPLE_SIZE)
            sampled_gaps[category_gap] = {
                idx: gaps_dict[idx] for idx in sampled_indices
            }
            sample_count = SAMPLE_SIZE
            statistics["sampled_categories"].append(category_gap)
            statistics["category_gap_samples"][category_gap] = {
                "available": gap_count,
                "sampled": sample_count,
                "method": f"RANDOM {SAMPLE_SIZE}"
            }
        
        statistics["total_sampled"] += sample_count
    
    return {
        "sampled_gaps": sampled_gaps,
        "statistics": statistics
    }


def generate_sample_report(all_samples: dict) -> str:
    """Generate a markdown report of the sampling results."""
    lines = [
        "# Gap Sample Extraction Report",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Sampling Rules",
        "",
        f"1. For category-gap combinations with >= {SAMPLE_SIZE} gaps: **randomly sample {SAMPLE_SIZE}**",
        f"2. For category-gap combinations with < {SAMPLE_SIZE} gaps: **extract all**",
        "3. For any combination containing **NEW** (topic or gap type): **extract all**",
        "",
        "---",
        "",
        "## Summary by Provider",
        "",
        "| Provider | Available | Sampled | Sampling Rate | NEW Categories | Full Extract | Random Sample |",
        "|:---|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    
    grand_total_available = 0
    grand_total_sampled = 0
    
    for provider, data in sorted(all_samples.items()):
        stats = data["statistics"]
        available = stats["total_available"]
        sampled = stats["total_sampled"]
        rate = (sampled / available * 100) if available > 0 else 0
        new_count = len(stats["new_category_gaps"])
        full_count = len(stats["full_extraction_categories"])
        random_count = len(stats["sampled_categories"])
        
        lines.append(f"| {provider.upper()} | {available} | {sampled} | {rate:.1f}% | {new_count} | {full_count} | {random_count} |")
        
        grand_total_available += available
        grand_total_sampled += sampled
    
    grand_rate = (grand_total_sampled / grand_total_available * 100) if grand_total_available > 0 else 0
    lines.append(f"| **TOTAL** | **{grand_total_available}** | **{grand_total_sampled}** | **{grand_rate:.1f}%** | - | - | - |")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Detailed breakdown for each provider
    for provider, data in sorted(all_samples.items()):
        stats = data["statistics"]
        
        lines.append(f"## {provider.upper()}")
        lines.append("")
        lines.append(f"**Total Available**: {stats['total_available']} | **Total Sampled**: {stats['total_sampled']}")
        lines.append("")
        
        # Category-gap breakdown table
        lines.append("### Category-Gap Breakdown")
        lines.append("")
        lines.append("| Category-Gap | Available | Sampled | Method |")
        lines.append("|:---:|:---:|:---:|:---|")
        
        for cat_gap, sample_info in sorted(stats["category_gap_samples"].items()):
            lines.append(f"| {cat_gap} | {sample_info['available']} | {sample_info['sampled']} | {sample_info['method']} |")
        
        lines.append("")
        
        # NEW categories
        if stats["new_category_gaps"]:
            lines.append("**NEW Category-Gaps (all extracted):**")
            lines.append(f"- {', '.join(stats['new_category_gaps'])}")
            lines.append("")
        
        # Full extraction categories
        if stats["full_extraction_categories"]:
            lines.append(f"**Full Extraction Categories (< {SAMPLE_SIZE}):**")
            lines.append(f"- {', '.join(stats['full_extraction_categories'])}")
            lines.append("")
        
        # Random sampled categories
        if stats["sampled_categories"]:
            lines.append(f"**Random Sampled Categories (>= {SAMPLE_SIZE}):**")
            lines.append(f"- {', '.join(stats['sampled_categories'])}")
            lines.append("")
        
        lines.append("---")
        lines.append("")
    
    # Cross-provider comparison
    lines.append("## Cross-Provider Sample Distribution")
    lines.append("")
    
    # Collect all unique category-gaps
    all_cat_gaps = set()
    for data in all_samples.values():
        all_cat_gaps.update(data["statistics"]["category_gap_samples"].keys())
    all_cat_gaps = sorted(all_cat_gaps)
    
    providers = sorted(all_samples.keys())
    header = "| Category-Gap | " + " | ".join(p.upper() for p in providers) + " | **Total** |"
    separator = "|:---:|" + ":---:|" * (len(providers) + 1)
    
    lines.append(header)
    lines.append(separator)
    
    for cat_gap in all_cat_gaps:
        row_values = []
        row_total = 0
        for provider in providers:
            sample_info = all_samples[provider]["statistics"]["category_gap_samples"].get(cat_gap, {})
            count = sample_info.get("sampled", 0)
            row_values.append(str(count))
            row_total += count
        lines.append(f"| {cat_gap} | " + " | ".join(row_values) + f" | **{row_total}** |")
    
    # Add totals row
    provider_totals = [str(all_samples[p]["statistics"]["total_sampled"]) for p in providers]
    grand_total = sum(all_samples[p]["statistics"]["total_sampled"] for p in providers)
    lines.append(f"| **Total** | " + " | ".join(provider_totals) + f" | **{grand_total}** |")
    
    lines.append("")
    
    return "\n".join(lines)


def main():
    """Main function to extract gap samples."""
    
    # Define paths
    script_dir = Path(__file__).parent
    output_dir = script_dir.parent / "02_Outputs"
    indexed_gaps_path = output_dir / "indexed_gaps.json"
    
    # Load indexed gaps
    if not indexed_gaps_path.exists():
        print(f"Error: indexed_gaps.json not found at {indexed_gaps_path}")
        print("Please run generate_gap_index.py first.")
        return
    
    print(f"Loading indexed gaps from: {indexed_gaps_path}")
    data = load_indexed_gaps(str(indexed_gaps_path))
    
    providers_data = data.get("providers", {})
    
    if not providers_data:
        print("Error: No provider data found in indexed_gaps.json")
        return
    
    print(f"Found {len(providers_data)} providers")
    
    # Extract samples for each provider
    all_samples = {}
    all_sampled_data = {}
    
    for provider, indexed_gaps in sorted(providers_data.items()):
        print(f"\nProcessing: {provider.upper()}")
        result = extract_samples_for_provider(provider, indexed_gaps)
        all_samples[provider] = result
        all_sampled_data[provider] = result["sampled_gaps"]
        
        stats = result["statistics"]
        print(f"  - Available: {stats['total_available']}")
        print(f"  - Sampled: {stats['total_sampled']}")
        print(f"  - NEW categories: {len(stats['new_category_gaps'])}")
        print(f"  - Full extraction: {len(stats['full_extraction_categories'])}")
        print(f"  - Random sampled: {len(stats['sampled_categories'])}")
    
    # Generate report
    report = generate_sample_report(all_samples)
    report_path = output_dir / "gap_sample_extraction_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\nSample extraction report saved to: {report_path}")
    
    # Save sampled gaps as JSON
    sampled_output_path = output_dir / "sampled_gaps.json"
    with open(sampled_output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "generated": datetime.now().isoformat(),
            "sampling_rules": {
                "sample_size": SAMPLE_SIZE,
                "new_category_rule": "Extract all gaps for categories containing NEW",
                "small_category_rule": f"Extract all gaps for categories with < {SAMPLE_SIZE} items",
                "large_category_rule": f"Random sample {SAMPLE_SIZE} gaps for categories with >= {SAMPLE_SIZE} items",
                "random_seed": 42
            },
            "providers": all_sampled_data,
            "statistics": {
                provider: result["statistics"]
                for provider, result in all_samples.items()
            }
        }, f, ensure_ascii=False, indent=2)
    print(f"Sampled gaps saved to: {sampled_output_path}")
    
    # Print summary
    print("\n" + "=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)
    
    grand_total_available = 0
    grand_total_sampled = 0
    
    for provider, result in sorted(all_samples.items()):
        stats = result["statistics"]
        available = stats["total_available"]
        sampled = stats["total_sampled"]
        rate = (sampled / available * 100) if available > 0 else 0
        
        grand_total_available += available
        grand_total_sampled += sampled
        
        print(f"\n{provider.upper()}:")
        print(f"  Available: {available}")
        print(f"  Sampled: {sampled} ({rate:.1f}%)")
        print(f"  Category breakdown:")
        
        # Show top categories by sampled count
        sorted_cats = sorted(
            stats["category_gap_samples"].items(),
            key=lambda x: x[1]["sampled"],
            reverse=True
        )[:5]
        for cat_gap, info in sorted_cats:
            print(f"    - {cat_gap}: {info['sampled']}/{info['available']} ({info['method']})")
    
    print(f"\n{'='*70}")
    grand_rate = (grand_total_sampled / grand_total_available * 100) if grand_total_available > 0 else 0
    print(f"GRAND TOTAL: {grand_total_sampled} sampled from {grand_total_available} available ({grand_rate:.1f}%)")
    print("=" * 70)


if __name__ == "__main__":
    main()
