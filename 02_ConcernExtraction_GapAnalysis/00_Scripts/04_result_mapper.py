#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gap Analysis - Result Mapper
===============================
Maps gap analysis results to comprehensive reports.
Generates JSON, CSV, and Markdown formats.

Dataset Structure:
- Gap results are embedded in thread.post.concerns[].gap_result and 
  thread.records[].concerns[].gap_result
- Each concern has exactly ONE topic (split at Stage 1)
- Gap types: G1-G6 (orthogonal taxonomy)

Usage:
    python 04_result_mapper.py [--provider PROVIDER] [--test]
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, field

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config_loader import load_config, list_providers
from utils.file_utils import (
    ensure_dir, save_json, load_json, save_csv, save_markdown,
    list_files, get_timestamp
)
from utils.logger import setup_logger

# Gap Type Constants (Orthogonal Taxonomy)
COVERAGE_GAP_TYPES = {
    "PRIVACY_POLICY_DETAIL_VAGUE",        # G1
    "PRIVACY_AI_FEATURE_UNADDRESSED",     # G2
    "PRIVACY_VULNERABLE_GROUP_NEGLECTED", # G3
    "PRIVACY_JURISDICTION_UNCLEAR"        # G4
}

PERCEPTION_GAP_TYPES = {
    "PRIVACY_EXPLICIT_POLICY_DISTRUST",   # G5
    "PRIVACY_POLICY_AWARENESS_DEFICIT"    # G6
}

ALL_GAP_TYPES = COVERAGE_GAP_TYPES | PERCEPTION_GAP_TYPES

# Gap type descriptions for reports
GAP_TYPE_DESCRIPTIONS = {
    "PRIVACY_POLICY_DETAIL_VAGUE": "Policy statements are vague or insufficient",
    "PRIVACY_AI_FEATURE_UNADDRESSED": "AI-specific features are not covered",
    "PRIVACY_VULNERABLE_GROUP_NEGLECTED": "Lack of protection for vulnerable groups",
    "PRIVACY_JURISDICTION_UNCLEAR": "Cross-border data rules are unclear",
    "PRIVACY_EXPLICIT_POLICY_DISTRUST": "User explicitly disavows trust in the policy",
    "PRIVACY_POLICY_AWARENESS_DEFICIT": "Users are unaware that the policy already applies"
}


@dataclass
class FlattenedGapRecord:
    """A flattened record for CSV/reporting purposes."""
    # Provider & Thread info
    provider: str
    thread_id: str
    title: str
    url: str
    subreddit: str
    search_keyword: str
    
    # Source info
    source_type: str  # 'post' or 'comment'
    record_id: str
    author: str
    body: str
    score: int
    created_utc: float
    
    # Concern info
    topic: str
    concern_statement: str
    user_assumption: str
    supporting_quote: str
    confidence: float
    
    # Gap info
    gap_detected: bool
    gap_category: str
    gap_types: List[str]
    coverage_status: str
    justification: str
    recommendation: str
    policy_quote: str
    gap_confidence: float


class ResultMapper:
    """Maps gap analysis results to reports."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = setup_logger(
            "ResultMapper",
            log_dir=config['paths'].get('logs'),
            console=True
        )
        
        # Data containers
        self.gap_data: Dict[str, Dict[str, Any]] = {}  # provider -> raw gap file data
        self.flattened_records: List[FlattenedGapRecord] = []
        self.test_mode: bool = False
    
    def load_gap_results(
        self,
        provider: Optional[str] = None,
        gap_file: Optional[str] = None,
        test_mode: bool = False
    ) -> int:
        """Load gap analysis results."""
        self.test_mode = test_mode
        gap_dir = Path(self.config['paths']['output_base']) / "gap_results"
        
        if gap_file:
            # Single file
            self.logger.info(f"Loading: {gap_file}")
            data = load_json(gap_file)
            prov = data.get('provider', 'unknown')
            self.gap_data[prov] = data
        elif provider:
            # Find files for specific provider
            pattern = f"gaps_{provider}_test_*.json" if test_mode else f"gaps_{provider}_*.json"
            files = list_files(gap_dir, pattern)
            if not files:
                self.logger.warning(f"No files found for {provider} (pattern: {pattern})")
                return 0
            
            # Load most recent
            latest = sorted(files)[-1]
            self.logger.info(f"Loading: {Path(latest).name}")
            data = load_json(latest)
            self.gap_data[provider] = data
        else:
            # Load all providers
            pattern = "gaps_*_test_*.json" if test_mode else "gaps_*.json"
            files = list_files(gap_dir, pattern)
            
            if not files:
                self.logger.error(f"No gap result files found (pattern: {pattern})")
                return 0
            
            self.logger.info(f"Loading {len(files)} gap result files...")
            for f in files:
                self.logger.info(f"  Loading: {Path(f).name}")
                data = load_json(f)
                prov = data.get('provider', 'unknown')
                # Keep the most recent per provider
                self.gap_data[prov] = data
        
        total_threads = sum(len(d.get('threads', [])) for d in self.gap_data.values())
        self.logger.info(f"Loaded {len(self.gap_data)} providers, {total_threads} threads total")
        return total_threads
    
    def flatten_records(self) -> List[FlattenedGapRecord]:
        """Flatten nested structure to flat records for CSV/reporting."""
        self.flattened_records = []
        
        for provider, data in self.gap_data.items():
            for thread in data.get('threads', []):
                thread_id = thread.get('thread_id', '')
                title = thread.get('title', '')
                url = thread.get('url', '')
                subreddit = thread.get('subreddit', '')
                search_keyword = thread.get('search_keyword', '')
                
                # Process post concerns
                post = thread.get('post', {})
                if post:
                    self._flatten_record_concerns(
                        provider, thread_id, title, url, subreddit, search_keyword,
                        post, 'post'
                    )
                
                # Process record concerns
                for record in thread.get('records', []):
                    self._flatten_record_concerns(
                        provider, thread_id, title, url, subreddit, search_keyword,
                        record, 'comment'
                    )
        
        self.logger.info(f"Flattened to {len(self.flattened_records)} records")
        return self.flattened_records
    
    def _flatten_record_concerns(
        self,
        provider: str,
        thread_id: str,
        title: str,
        url: str,
        subreddit: str,
        search_keyword: str,
        record: Dict[str, Any],
        source_type: str
    ):
        """Flatten concerns from a single record."""
        record_id = record.get('record_id', '')
        author = record.get('author', '[deleted]')
        body = record.get('body', '')
        score = record.get('score', 0)
        created_utc = record.get('created_utc', 0)
        
        for concern in record.get('concerns', []):
            # Topic (each concern has exactly one topic)
            topics = concern.get('topics', [])
            topic = topics[0] if topics else 'UNKNOWN'
            
            # Gap result
            gap_result = concern.get('gap_result', {})
            
            # Handle potential None values
            policy_analysis = gap_result.get('policy_analysis') or {}
            found_content = policy_analysis.get('found_content') or ''
            if len(found_content) > 300:
                found_content = found_content[:300] + '...'
            
            flat = FlattenedGapRecord(
                provider=provider,
                thread_id=thread_id,
                title=title,
                url=url,
                subreddit=subreddit,
                search_keyword=search_keyword,
                source_type=source_type,
                record_id=record_id,
                author=author,
                body=body[:500] + '...' if len(body) > 500 else body,
                score=score,
                created_utc=created_utc,
                topic=topic,
                concern_statement=concern.get('concern_statement') or '',
                user_assumption=concern.get('user_assumption') or '',
                supporting_quote=concern.get('supporting_quote') or '',
                confidence=concern.get('confidence') or 0,
                gap_detected=gap_result.get('gap_detected', False),
                gap_category=gap_result.get('gap_category') or '',
                gap_types=gap_result.get('gap_types') or [],
                coverage_status=gap_result.get('coverage_status') or '',
                justification=gap_result.get('justification') or '',
                recommendation=gap_result.get('recommendation') or '',
                policy_quote=found_content,
                gap_confidence=gap_result.get('confidence') or 0
            )
            self.flattened_records.append(flat)
    
    def generate_summary_stats(self) -> Dict[str, Any]:
        """Generate summary statistics."""
        stats = {
            "total_concerns": len(self.flattened_records),
            "concerns_with_gaps": sum(1 for r in self.flattened_records if r.gap_detected),
            "by_provider": defaultdict(lambda: {"total": 0, "with_gap": 0}),
            "by_gap_type": defaultdict(int),
            "by_topic": defaultdict(lambda: {"total": 0, "with_gap": 0}),
            "coverage_gaps_count": 0,
            "perception_gaps_count": 0,
            "new_gap_types": []
        }
        
        for r in self.flattened_records:
            # Provider stats
            stats["by_provider"][r.provider]["total"] += 1
            if r.gap_detected:
                stats["by_provider"][r.provider]["with_gap"] += 1
            
            # Topic stats
            stats["by_topic"][r.topic]["total"] += 1
            if r.gap_detected:
                stats["by_topic"][r.topic]["with_gap"] += 1
            
            # Gap type stats (orthogonal counting)
            has_coverage = False
            has_perception = False
            
            for gt in r.gap_types:
                stats["by_gap_type"][gt] += 1
                
                if gt in COVERAGE_GAP_TYPES:
                    has_coverage = True
                elif gt in PERCEPTION_GAP_TYPES:
                    has_perception = True
                elif gt not in ALL_GAP_TYPES and gt != "NO_GAP":
                    if gt not in stats["new_gap_types"]:
                        stats["new_gap_types"].append(gt)
            
            if has_coverage:
                stats["coverage_gaps_count"] += 1
            if has_perception:
                stats["perception_gaps_count"] += 1
        
        # Convert defaultdicts
        stats["by_provider"] = dict(stats["by_provider"])
        stats["by_gap_type"] = dict(stats["by_gap_type"])
        stats["by_topic"] = dict(stats["by_topic"])
        
        return stats
    
    def generate_markdown_report(self) -> str:
        """Generate comprehensive Markdown report."""
        stats = self.generate_summary_stats()
        
        lines = [
            "# Privacy Gap Analysis Report",
            f"\nGenerated: {get_timestamp()}",
            f"\nTest Mode: {self.test_mode}",
            
            "\n## 1. Global Summary",
            "| Metric | Count |",
            "|:-------|------:|",
            f"| Total Concerns Analyzed | {stats['total_concerns']} |",
            f"| Concerns with Gaps | {stats['concerns_with_gaps']} |",
            f"| Coverage Gaps (G1-G4) | {stats['coverage_gaps_count']} |",
            f"| Perception Gaps (G5-G6) | {stats['perception_gaps_count']} |",
            
            "\n## 2. Summary by Provider",
            "| Provider | Total Concerns | With Gaps | Gap Rate |",
            "|:---------|---------------:|----------:|---------:|"
        ]
        
        for provider, pstats in sorted(stats["by_provider"].items()):
            total = pstats["total"]
            with_gap = pstats["with_gap"]
            rate = (with_gap / total * 100) if total > 0 else 0
            lines.append(f"| {provider} | {total} | {with_gap} | {rate:.1f}% |")
        
        lines.extend([
            "\n## 3. Gap Types Distribution",
            "| Gap Type | Count | Description |",
            "|:---------|------:|:------------|"
        ])
        
        for gt, count in sorted(stats["by_gap_type"].items(), key=lambda x: -x[1]):
            desc = GAP_TYPE_DESCRIPTIONS.get(gt, "Unknown")
            lines.append(f"| {gt} | {count} | {desc} |")
        
        lines.extend([
            "\n## 4. Top Privacy Topics with Gaps",
            "| Topic | Total | With Gap | Gap Rate |",
            "|:------|------:|---------:|---------:|"
        ])
        
        # Sort by with_gap count descending
        sorted_topics = sorted(
            stats["by_topic"].items(),
            key=lambda x: -x[1]["with_gap"]
        )[:20]
        
        for topic, tstats in sorted_topics:
            total = tstats["total"]
            with_gap = tstats["with_gap"]
            rate = (with_gap / total * 100) if total > 0 else 0
            lines.append(f"| {topic} | {total} | {with_gap} | {rate:.1f}% |")
        
        # Gap examples section
        lines.extend([
            "\n## 5. Sample Gaps by Type",
        ])
        
        # Group by gap type
        gaps_by_type: Dict[str, List[FlattenedGapRecord]] = defaultdict(list)
        for r in self.flattened_records:
            if r.gap_detected:
                for gt in r.gap_types:
                    gaps_by_type[gt].append(r)
        
        for gt in ALL_GAP_TYPES:
            if gt in gaps_by_type:
                lines.append(f"\n### {gt}")
                lines.append(f"*{GAP_TYPE_DESCRIPTIONS.get(gt, '')}*\n")
                
                # Show up to 3 examples
                for r in gaps_by_type[gt][:3]:
                    quote = r.supporting_quote[:200] + '...' if len(r.supporting_quote) > 200 else r.supporting_quote
                    lines.extend([
                        f"**[{r.provider}] {r.topic}**",
                        f"- Thread: [{r.title[:60]}...]({r.url})",
                        f"- Concern: {r.concern_statement[:150]}...",
                        f"- Quote: \"{quote}\"",
                        f"- Recommendation: {r.recommendation[:200]}..." if r.recommendation else "",
                        ""
                    ])
        
        # New gap types warning
        if stats["new_gap_types"]:
            lines.extend([
                "\n## ⚠️ New Gap Types Discovered",
                "The following gap types were not in the predefined taxonomy:",
                ""
            ])
            for gt in stats["new_gap_types"]:
                lines.append(f"- `{gt}`")
        
        return "\n".join(lines)
    
    def save_results(
        self,
        output_dir: Optional[str] = None,
        formats: Optional[List[str]] = None
    ) -> Dict[str, Path]:
        """Save mapped results in multiple formats."""
        if output_dir is None:
            output_dir = Path(self.config['paths']['output_base']) / "final_reports"
        
        if formats is None:
            formats = ['json', 'csv', 'markdown']
        
        output_dir = ensure_dir(output_dir)
        saved_paths = {}
        timestamp = get_timestamp()
        test_suffix = "_test" if self.test_mode else ""
        
        # Flatten records if not done
        if not self.flattened_records:
            self.flatten_records()
        
        # JSON
        if 'json' in formats:
            json_path = output_dir / f"gap_report{test_suffix}_{timestamp}.json"
            save_json({
                "version": "1.0",
                "timestamp": timestamp,
                "test_mode": self.test_mode,
                "summary": self.generate_summary_stats(),
                "records": [r.__dict__ for r in self.flattened_records]
            }, json_path)
            saved_paths["json"] = json_path
            self.logger.info(f"Saved: {json_path.name}")
        
        # CSV
        if 'csv' in formats:
            csv_path = output_dir / f"gap_report{test_suffix}_{timestamp}.csv"
            # Convert to dicts and handle list fields
            csv_records = []
            for r in self.flattened_records:
                d = r.__dict__.copy()
                d['gap_types'] = '|'.join(d['gap_types'])  # Join list for CSV
                csv_records.append(d)
            save_csv(csv_records, csv_path)
            saved_paths["csv"] = csv_path
            self.logger.info(f"Saved: {csv_path.name}")
        
        # Markdown
        if 'markdown' in formats:
            md_path = output_dir / f"gap_report{test_suffix}_{timestamp}.md"
            save_markdown(self.generate_markdown_report(), md_path)
            saved_paths["markdown"] = md_path
            self.logger.info(f"Saved: {md_path.name}")
        
        return saved_paths


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Gap Analysis Result Mapper")
    parser.add_argument("--provider", type=str, help="Specific provider to process")
    parser.add_argument("--gap-file", type=str, help="Path to specific gap results file")
    parser.add_argument("--config", type=str, help="Path to config file")
    parser.add_argument("--output", type=str, help="Output directory")
    parser.add_argument("--format", type=str, nargs='+',
                        choices=['json', 'csv', 'markdown'],
                        default=['json', 'csv', 'markdown'],
                        help="Output formats")
    parser.add_argument("--test", action="store_true", help="Test mode - use test gap results")
    
    args = parser.parse_args()
    
    config = load_config(args.config)
    mapper = ResultMapper(config)
    
    # Load gap results
    loaded = mapper.load_gap_results(
        provider=args.provider,
        gap_file=args.gap_file,
        test_mode=args.test
    )
    
    if loaded == 0:
        print("No gap results found. Run 02_gap_auditor.py first.")
        return
    
    # Flatten and save
    mapper.flatten_records()
    paths = mapper.save_results(args.output, args.format)
    
    print(f"\n✅ Result mapping complete!")
    print(f"   Processed {len(mapper.flattened_records)} concern records")
    for fmt, path in paths.items():
        print(f"   - {fmt}: {path}")


if __name__ == "__main__":
    main()
