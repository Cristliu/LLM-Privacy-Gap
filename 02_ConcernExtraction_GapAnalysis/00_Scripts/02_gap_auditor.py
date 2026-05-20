#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gap Analysis - Gap Auditor (Policy Coverage Analysis)
===================================================================
Analyzes whether user concerns are adequately addressed in privacy policies.
Identifies coverage gaps by comparing Stage 1 concerns against policy content.

Key Features:
- Processes Stage 1 output JSON (multi-concerns per record)
- Rebuilds conversation context for each concern
- Supports multiple topics per concern (topics array)
- Removed severity-related logic (too subjective)
- Uses ToT reasoning for gap classification

Input: extracted_concerns/concerns_{provider}_{timestamp}.json
Output: gap_results/gaps_{provider}_{timestamp}.json

Gap Categories (Final Taxonomy - 6 Types):
PRIVACY_POLICY_COVERAGE_GAPS (4 types):
  - PRIVACY_POLICY_DETAIL_VAGUE: Policy vague/generic
  - PRIVACY_AI_FEATURE_UNADDRESSED: AI-specific feature not covered
  - PRIVACY_VULNERABLE_GROUP_NEGLECTED: No vulnerable group provisions
  - PRIVACY_JURISDICTION_UNCLEAR: Cross-border issues unclear

PRIVACY_USER_PERCEPTION_GAPS (2 types):
  - PRIVACY_EXPLICIT_POLICY_DISTRUST: User distrusts policy
  - PRIVACY_POLICY_AWARENESS_DEFICIT: User unaware of policy

Usage:
    python 02_gap_auditor.py [--provider PROVIDER] [--test] [--concurrent N]
"""

import argparse
import sys
import json
import signal
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config_loader import load_config
from utils.file_utils import ensure_dir, save_json, load_json, read_text, get_timestamp
from utils.llm_client import LLMClient
from utils.logger import setup_logger, ProgressLogger

# Global flag for graceful exit
_SHUTDOWN_REQUESTED = False

def _signal_handler(signum, frame):
    global _SHUTDOWN_REQUESTED
    _SHUTDOWN_REQUESTED = True
    print("\n⚠️  Shutdown requested. Saving progress and exiting gracefully...")

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# =============================================================================
# Gap Type Taxonomy
# =============================================================================

GAP_CATEGORIES = {
    "PRIVACY_POLICY_COVERAGE_GAPS": [
        "PRIVACY_POLICY_DETAIL_VAGUE",        # G1: Policy vague/generic (general deficiencies)
        "PRIVACY_AI_FEATURE_UNADDRESSED",     # G2: AI-specific feature not covered (Memory, Multi-modal, Agent)
        "PRIVACY_VULNERABLE_GROUP_NEGLECTED", # G3: No vulnerable group provisions
        "PRIVACY_JURISDICTION_UNCLEAR",       # G4: Cross-border issues unclear
    ],
    "PRIVACY_USER_PERCEPTION_GAPS": [
        "PRIVACY_EXPLICIT_POLICY_DISTRUST",   # G5: User distrusts policy (requires policy to cover the topic)
        "PRIVACY_POLICY_AWARENESS_DEFICIT",   # G6: User unaware policy covers topic (requires policy coverage)
    ],
}

ALL_GAP_TYPES = GAP_CATEGORIES["PRIVACY_POLICY_COVERAGE_GAPS"] + GAP_CATEGORIES["PRIVACY_USER_PERCEPTION_GAPS"]


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class ConcernGapResult:
    """Gap analysis result for a single concern (embedded in concern object)."""
    # Gap detection result
    gap_detected: bool
    gap_category: str                       # "PRIVACY_POLICY_COVERAGE_GAPS" | "PRIVACY_USER_PERCEPTION_GAPS" | "NO_GAP"
    gap_types: List[str]                    # Can have multiple gap types
    coverage_status: str                    # "NOT_FOUND" | "VAGUE" | "INSUFFICIENT" | "ADEQUATE"
    
    # Analysis details
    policy_analysis: Dict[str, Any]         # searched_for, relevant_sections, found_content, assessment
    justification: str
    recommendation: Optional[str]
    confidence: float
    reasoning: str                          # ToT reasoning process
    
    # Optional: New gap type discovered
    new_gap_types: List[str] = field(default_factory=list)
    new_gap_descriptions: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConcernWithGap:
    """Concern data with gap analysis result (mirrors Stage 1 concern structure + gap_result)."""
    # From Stage 1
    topics: List[str]
    concern_statement: str
    user_assumption: str
    supporting_quote: str
    confidence: float
    reasoning: str
    
    # Gap analysis result (added in Stage 2)
    gap_result: Optional[ConcernGapResult] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = {
            "topics": self.topics,
            "concern_statement": self.concern_statement,
            "user_assumption": self.user_assumption,
            "supporting_quote": self.supporting_quote,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }
        if self.gap_result:
            d["gap_result"] = self.gap_result.to_dict()
        return d


@dataclass
class RecordWithGaps:
    """Record (post or comment) with concerns that have gap results."""
    record_id: str
    type: str                               # "post" or "comment"
    author: str
    body: str
    score: int
    created_utc: float
    is_concern_source: bool
    concerns: List[ConcernWithGap]
    
    # Comment-specific fields
    parent_id: Optional[str] = None
    chain_root_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = {
            "record_id": self.record_id,
            "type": self.type,
            "author": self.author,
            "body": self.body,
            "score": self.score,
            "created_utc": self.created_utc,
            "is_concern_source": self.is_concern_source,
            "concerns": [c.to_dict() for c in self.concerns]
        }
        if self.parent_id:
            d["parent_id"] = self.parent_id
        if self.chain_root_id:
            d["chain_root_id"] = self.chain_root_id
        return d


@dataclass
class ThreadGapResult:
    """Thread with gap analysis results - mirrors Stage 1 structure."""
    thread_id: str
    post_id: str
    subreddit: str
    title: str
    url: str
    permalink: str
    search_keyword: str
    
    # Stats
    total_concerns: int
    concerns_with_gaps: int
    
    # Structured data (mirrors Stage 1)
    post: Optional[RecordWithGaps] = None
    records: List[RecordWithGaps] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        d = {
            "thread_id": self.thread_id,
            "post_id": self.post_id,
            "subreddit": self.subreddit,
            "title": self.title,
            "url": self.url,
            "permalink": self.permalink,
            "search_keyword": self.search_keyword,
            "total_concerns": self.total_concerns,
            "concerns_with_gaps": self.concerns_with_gaps,
        }
        if self.post:
            d["post"] = self.post.to_dict()
        d["records"] = [r.to_dict() for r in self.records]
        return d


# =============================================================================
# Configuration
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = BASE_DIR / "02_Outputs"
DEFAULT_LOG_DIR = BASE_DIR / "03_Logs"
DEFAULT_PROMPT_DIR = BASE_DIR / "01_Prompts"
DEFAULT_POLICY_BASE = BASE_DIR.parent / "01_Data_Collection" / "02_Outputs" / "Policies"

PROVIDERS = ["chatgpt", "claude", "gemini", "grok", "deepseek"]


# =============================================================================
# Policy Loader
# =============================================================================

class PolicyLoader:
    """Loads and caches privacy policy content."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cache: Dict[str, str] = {}
        
        # Determine policy base path
        paths = config.get('paths', {})
        self.policy_base = Path(paths.get('policy_base', DEFAULT_POLICY_BASE))
        self.policy_main_dir = paths.get('policy_main', 'privacy_policies')
        self.policy_supplemental_dir = paths.get('policy_supplemental', 'supplemental_documents')
        
        # Provider to policy dir mapping
        self.provider_configs = {p['name']: p for p in config.get('providers', [])}
    
    def get_policy_text(self, provider: str) -> str:
        """Load and return full policy text for a provider."""
        if provider in self.cache:
            return self.cache[provider]
        
        policy_text = ""
        provider_cfg = self.provider_configs.get(provider, {})
        policy_dirs = provider_cfg.get('policy_dirs', [])
        supplemental_dirs = provider_cfg.get('supplemental_dirs', [])
        
        # Load main policy files
        main_dir = self.policy_base / self.policy_main_dir
        for policy_dir in policy_dirs:
            dir_path = main_dir / policy_dir
            if dir_path.exists():
                for f in sorted(dir_path.glob('*.md')):
                    policy_text += f"\n\n=== {f.name} ===\n"
                    policy_text += f.read_text(encoding='utf-8')
                for f in sorted(dir_path.glob('*.txt')):
                    policy_text += f"\n\n=== {f.name} ===\n"
                    policy_text += f.read_text(encoding='utf-8')
        
        # Load supplemental documents
        supp_dir = self.policy_base / self.policy_supplemental_dir
        for supp_name in supplemental_dirs:
            dir_path = supp_dir / supp_name
            if dir_path.exists():
                for f in sorted(dir_path.glob('*.md')):
                    policy_text += f"\n\n=== Supplemental: {f.name} ===\n"
                    policy_text += f.read_text(encoding='utf-8')
                for f in sorted(dir_path.glob('*.txt')):
                    policy_text += f"\n\n=== Supplemental: {f.name} ===\n"
                    policy_text += f.read_text(encoding='utf-8')
        
        self.cache[provider] = policy_text
        return policy_text


# =============================================================================
# Gap Auditor
# =============================================================================

class GapAuditor:
    """Audits privacy concerns against policies for coverage gaps."""
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        max_concurrent: int = 70,
        output_dir: Optional[Path] = None,
        log_dir: Optional[Path] = None
    ):
        self.config = config or {}
        self.max_concurrent = max_concurrent
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.log_dir = log_dir or DEFAULT_LOG_DIR
        
        self.logger = setup_logger(
            "GapAuditor",
            log_dir=self.log_dir,
            console=True
        )
        
        # Load prompt template
        prompt_path = DEFAULT_PROMPT_DIR / "gap_detection.txt"
        if prompt_path.exists():
            self.prompt_template = prompt_path.read_text(encoding='utf-8')
        else:
            self.logger.warning(f"Prompt not found: {prompt_path}, using default")
            self.prompt_template = self._get_default_prompt()
        
        # Initialize LLM client
        if config:
            self.llm = LLMClient.from_config(config)
        else:
            self.llm = LLMClient()
        self.llm.max_concurrent = max_concurrent
        
        # Policy loader
        self.policy_loader = PolicyLoader(config or {})
        
        # Thread-safe state
        self._lock = threading.Lock()
        self.processed_count: int = 0
        self.gaps_found: int = 0
        self.new_gap_types: Set[str] = set()
    
    def _get_default_prompt(self) -> str:
        """Fallback prompt if file not found."""
        return """You are a privacy policy analyst. Analyze whether this user concern is adequately addressed in the policy.

## Provider: {provider}

## User Concern
- Topics: {topics}
- Concern: {concern_statement}
- User Assumption: {user_assumption}
- Quote: "{supporting_quote}"

## Conversation Context
{context}

## Policy Content
{policy_text}

## Task
Determine if there is a coverage gap. Respond with JSON only.

```json
{
  "gap_detected": true/false,
  "gap_category": "PRIVACY_POLICY_COVERAGE_GAPS" | "PRIVACY_USER_PERCEPTION_GAPS" | "NO_GAP",
  "gap_types": ["DETAIL_INSUFFICIENT", ...],
  "coverage_status": "NOT_FOUND" | "VAGUE" | "INSUFFICIENT" | "ADEQUATE",
  "policy_analysis": {
    "searched_for": ["..."],
    "relevant_sections": ["..."],
    "found_content": "exact quote or N/A",
    "coverage_assessment": "..."
  },
  "justification": "...",
  "confidence": 0.0-1.0,
  "reasoning": "ToT reasoning process",
  "recommendation": "..."
}
```"""
    
    def _build_conversation_context(
        self,
        thread: Dict[str, Any],
        target_record_id: str,
        target_chain_root_id: Optional[str] = None
    ) -> str:
        """Build conversation context for a specific concern.
        
        Context includes:
        1. The original post (always included)
        2. For comments: the comment chain (same chain_root_id)
        """
        parts = []
        
        # Always include post
        post = thread.get('post', {})
        parts.append(f"[ORIGINAL POST] (id: {post.get('record_id', '')})")
        parts.append(f"Title: {thread.get('title', '')}")
        if post.get('body'):
            parts.append(f"Content: {post.get('body', '')}")
        parts.append(f"Author: {post.get('author', '[deleted]')}, Score: {post.get('score', 0)}")
        parts.append("")
        
        # If target is the post itself, we're done
        if target_record_id == post.get('record_id'):
            return "\n".join(parts)
        
        # For comments, include relevant chain
        records = thread.get('records', [])
        if target_chain_root_id:
            # Get all comments in the same chain
            chain_comments = [r for r in records if r.get('chain_root_id') == target_chain_root_id]
            # Sort by created_utc
            chain_comments.sort(key=lambda x: x.get('created_utc', 0))
            
            for i, record in enumerate(chain_comments, 1):
                is_target = ">>> TARGET <<<" if record.get('record_id') == target_record_id else ""
                parts.append(f"[COMMENT {i}] {is_target} (id: {record.get('record_id', '')})")
                parts.append(f"Content: {record.get('body', '')}")
                parts.append(f"Author: {record.get('author', '[deleted]')}, Score: {record.get('score', 0)}")
                parts.append("")
        
        return "\n".join(parts)
    
    def _prepare_prompt(
        self,
        concern: Dict[str, Any],
        context: str,
        provider: str,
        policy_text: str
    ) -> str:
        """Prepare gap detection prompt."""
        topics = concern.get('topics', [])
        if isinstance(topics, str):
            topics = [topics]
        topics_str = ", ".join(topics)
        
        prompt = self.prompt_template
        prompt = prompt.replace("{provider}", provider)
        prompt = prompt.replace("{topics}", topics_str)
        prompt = prompt.replace("{concern_statement}", concern.get('concern_statement', ''))
        prompt = prompt.replace("{user_assumption}", concern.get('user_assumption', ''))
        prompt = prompt.replace("{supporting_quote}", concern.get('supporting_quote', ''))
        prompt = prompt.replace("{context}", context)
        prompt = prompt.replace("{policy_text}", policy_text)
        
        return prompt
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM response."""
        try:
            text = response_text.strip()
            
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                text = text[start:end].strip()
            
            return json.loads(text)
            
        except json.JSONDecodeError as e:
            return {"gap_detected": False, "error": str(e)}
    
    def audit_concern(
        self,
        thread: Dict[str, Any],
        record: Dict[str, Any],
        concern: Dict[str, Any],
        provider: str,
        policy_text: str
    ) -> ConcernGapResult:
        """Audit a single concern for coverage gaps. Returns gap result only."""
        record_id = record.get('record_id', '')
        chain_root_id = record.get('chain_root_id')
        
        try:
            # Build conversation context
            context = self._build_conversation_context(thread, record_id, chain_root_id)
            
            # Prepare prompt
            prompt = self._prepare_prompt(concern, context, provider, policy_text)
            
            messages = [
                {
                    "role": "system",
                    "content": "You are a neutral privacy policy analyst. Use Tree of Thoughts reasoning to analyze coverage gaps. Respond only with valid JSON."
                },
                {"role": "user", "content": prompt}
            ]
            
            response = self.llm.chat(messages)
            
            # Handle response
            if isinstance(response, dict):
                if not response.get('success', False):
                    raise Exception(response.get('error', 'LLM request failed'))
                response_text = response.get('content', '')
            else:
                response_text = response
            
            parsed = self._parse_response(response_text)
            
            # Handle gap_types (array)
            gap_types = parsed.get('gap_types', [])
            if isinstance(gap_types, str):
                gap_types = [gap_types] if gap_types else []
            
            # Check for new gap types
            new_gap_types = [g for g in gap_types if g.startswith('NEW_')]
            for ng in new_gap_types:
                self.new_gap_types.add(ng)
            
            result = ConcernGapResult(
                gap_detected=parsed.get('gap_detected', False),
                gap_category=parsed.get('gap_category', 'NO_GAP'),
                gap_types=gap_types,
                coverage_status=parsed.get('coverage_status', 'UNKNOWN'),
                policy_analysis=parsed.get('policy_analysis', {}),
                justification=parsed.get('justification', ''),
                recommendation=parsed.get('recommendation'),
                confidence=float(parsed.get('confidence', 0.5)),
                reasoning=parsed.get('reasoning', ''),
                new_gap_types=new_gap_types,
                new_gap_descriptions=parsed.get('new_gap_descriptions', {})
            )
            
        except Exception as e:
            self.logger.warning(f"Error auditing {record_id}: {e}")
            
            result = ConcernGapResult(
                gap_detected=False,
                gap_category='ERROR',
                gap_types=[],
                coverage_status='ERROR',
                policy_analysis={'error': str(e)},
                justification=f"Error during analysis: {e}",
                recommendation=None,
                confidence=0,
                reasoning=''
            )
        
        return result
    
    def _build_record_with_gaps(
        self,
        thread: Dict[str, Any],
        record: Dict[str, Any],
        provider: str,
        policy_text: str
    ) -> RecordWithGaps:
        """Build a RecordWithGaps by auditing all concerns in a record."""
        concerns_with_gaps = []
        
        for concern in record.get('concerns', []):
            # Audit this concern
            gap_result = self.audit_concern(thread, record, concern, provider, policy_text)
            
            # Build ConcernWithGap
            topics = concern.get('topics', [])
            if isinstance(topics, str):
                topics = [topics]
            
            concern_with_gap = ConcernWithGap(
                topics=topics,
                concern_statement=concern.get('concern_statement', ''),
                user_assumption=concern.get('user_assumption', ''),
                supporting_quote=concern.get('supporting_quote', ''),
                confidence=float(concern.get('confidence', 0.8)),
                reasoning=concern.get('reasoning', ''),
                gap_result=gap_result
            )
            concerns_with_gaps.append(concern_with_gap)
        
        return RecordWithGaps(
            record_id=record.get('record_id', ''),
            type=record.get('type', 'comment'),
            author=record.get('author', '[deleted]'),
            body=record.get('body', ''),
            score=record.get('score', 0),
            created_utc=record.get('created_utc', 0),
            is_concern_source=record.get('is_concern_source', False),
            concerns=concerns_with_gaps,
            parent_id=record.get('parent_id'),
            chain_root_id=record.get('chain_root_id')
        )
    
    def _collect_concerns_from_thread(
        self,
        thread: Dict[str, Any]
    ) -> List[tuple]:
        """Collect all concerns from a thread as (record, concern, index) tuples."""
        concerns = []
        
        # Post concerns
        post = thread.get('post', {})
        post_concerns = post.get('concerns', [])
        for idx, concern in enumerate(post_concerns):
            concerns.append((post, concern, idx))
        
        # Record concerns
        for record in thread.get('records', []):
            record_concerns = record.get('concerns', [])
            for idx, concern in enumerate(record_concerns):
                concerns.append((record, concern, idx))
        
        return concerns
    
    def audit_thread(
        self,
        thread: Dict[str, Any],
        provider: str,
        policy_text: str
    ) -> ThreadGapResult:
        """Audit all concerns in a single thread. Preserves Stage 1 structure."""
        thread_id = thread.get('thread_id', '')
        
        # Build post with gaps
        post = thread.get('post', {})
        post_with_gaps = None
        total_concerns = 0
        concerns_with_gaps = 0
        
        if post:
            post_with_gaps = self._build_record_with_gaps(thread, post, provider, policy_text)
            total_concerns += len(post_with_gaps.concerns)
            concerns_with_gaps += sum(1 for c in post_with_gaps.concerns 
                                      if c.gap_result and c.gap_result.gap_detected)
        
        # Build records with gaps
        records_with_gaps = []
        for record in thread.get('records', []):
            record_with_gaps = self._build_record_with_gaps(thread, record, provider, policy_text)
            records_with_gaps.append(record_with_gaps)
            total_concerns += len(record_with_gaps.concerns)
            concerns_with_gaps += sum(1 for c in record_with_gaps.concerns 
                                      if c.gap_result and c.gap_result.gap_detected)
        
        return ThreadGapResult(
            thread_id=thread_id,
            post_id=thread.get('post_id', ''),
            subreddit=thread.get('subreddit', ''),
            title=thread.get('title', ''),
            url=thread.get('url', ''),
            permalink=thread.get('permalink', ''),
            search_keyword=thread.get('search_keyword', ''),
            total_concerns=total_concerns,
            concerns_with_gaps=concerns_with_gaps,
            post=post_with_gaps,
            records=records_with_gaps
        )
    
    def _process_thread_wrapper(
        self,
        thread: Dict[str, Any],
        provider: str,
        policy_text: str,
        progress: ProgressLogger
    ) -> ThreadGapResult:
        """Thread-safe wrapper for auditing a thread."""
        global _SHUTDOWN_REQUESTED
        
        if _SHUTDOWN_REQUESTED:
            return ThreadGapResult(
                thread_id=thread.get('thread_id', ''),
                post_id=thread.get('post_id', ''),
                subreddit=thread.get('subreddit', ''),
                title=thread.get('title', ''),
                url=thread.get('url', ''),
                permalink=thread.get('permalink', ''),
                search_keyword=thread.get('search_keyword', ''),
                total_concerns=0,
                concerns_with_gaps=0
            )
        
        result = self.audit_thread(thread, provider, policy_text)
        
        with self._lock:
            self.processed_count += 1
            self.gaps_found += result.concerns_with_gaps
        
        progress.update()
        return result
    
    def load_stage1_output(
        self,
        provider: str,
        test_mode: bool = False,
        input_file: Optional[Path] = None
    ) -> Optional[Dict[str, Any]]:
        """Load Stage 1 output for a provider.
        
        Args:
            provider: Provider name
            test_mode: Whether to look for test files
            input_file: Explicit input file path (for split processing)
        """
        if input_file:
            # Use explicit input file
            if not input_file.exists():
                self.logger.error(f"Input file not found: {input_file}")
                return None
            self.logger.info(f"Loading Stage 1 output: {input_file.name}")
            return load_json(input_file)
        
        # Auto-find latest file
        concerns_dir = self.output_dir / "extracted_concerns"
        
        suffix = "_test" if test_mode else ""
        pattern = f"concerns_{provider}{suffix}_*.json"
        
        files = sorted(concerns_dir.glob(pattern), reverse=True)
        if not files:
            self.logger.warning(f"No Stage 1 output found for {provider}")
            return None
        
        latest_file = files[0]
        self.logger.info(f"Loading Stage 1 output: {latest_file.name}")
        return load_json(latest_file)
    
    def run(
        self,
        provider: str,
        test_mode: bool = False,
        limit: Optional[int] = None,
        input_file: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Run gap analysis for a provider.
        
        Args:
            provider: Provider name
            test_mode: Whether to use test files
            limit: Limit number of threads to process
            input_file: Explicit input file path (for split processing)
        """
        global _SHUTDOWN_REQUESTED
        
        self.logger.info(f"Starting gap analysis for {provider}...")
        
        # Load Stage 1 output
        stage1_data = self.load_stage1_output(provider, test_mode, input_file)
        if not stage1_data:
            return {}
        
        threads = stage1_data.get('threads', [])
        if limit:
            threads = threads[:limit]
        
        # Load policy
        policy_text = self.policy_loader.get_policy_text(provider)
        if not policy_text:
            self.logger.error(f"No policy text found for {provider}")
            return {}
        
        self.logger.info(f"Loaded policy ({len(policy_text)} chars)")
        
        # Reset state
        self.processed_count = 0
        self.gaps_found = 0
        self.new_gap_types = set()
        
        # Count total concerns
        total_concerns = 0
        for thread in threads:
            total_concerns += len(self._collect_concerns_from_thread(thread))
        
        self.logger.info(f"Processing {len(threads)} threads ({total_concerns} concerns)")
        
        # Process threads
        progress = ProgressLogger(
            logger=self.logger,
            total=len(threads),
            prefix="Auditing gaps"
        )
        
        thread_results: List[ThreadGapResult] = []
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            futures = [
                executor.submit(
                    self._process_thread_wrapper, 
                    thread, provider, policy_text, progress
                )
                for thread in threads
            ]
            
            for future in as_completed(futures):
                if _SHUTDOWN_REQUESTED:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    result = future.result()
                    thread_results.append(result)
                except Exception as e:
                    self.logger.error(f"Thread processing error: {e}")
        
        progress.finish()
        
        # Build output
        timestamp = get_timestamp()
        test_suffix = "_test" if test_mode else ""
        
        # Determine part suffix from input file name (for split processing)
        part_suffix = ""
        if input_file:
            import re
            match = re.search(r'_part(\d+)', input_file.name)
            if match:
                part_suffix = f"_part{match.group(1)}"
        
        # Collect statistics from thread results - using gap_types for accurate counting
        total_audited = sum(tr.total_concerns for tr in thread_results)
        total_with_gaps = sum(tr.concerns_with_gaps for tr in thread_results)
        
        output = {
            "provider": provider,
            "timestamp": timestamp,
            "version": "1.0",
            "stage": "Stage2_GapAnalysis",
            "summary": {
                "total_threads": len(thread_results),
                "total_concerns_audited": total_audited,
                "concerns_with_gaps": total_with_gaps,
                "note": "Detailed statistics are generated by 03_gap_stats.py"
            },
            "threads": [tr.to_dict() for tr in thread_results]
        }
        
        # Save output
        output_dir = self.output_dir / "gap_results"
        ensure_dir(output_dir)
        output_file = output_dir / f"gaps_{provider}{part_suffix}{test_suffix}_{timestamp}.json"
        save_json(output, output_file)
        
        self.logger.info(f"Saved to: {output_file}")
        self.logger.info(f"Summary: {total_with_gaps} gaps found in {total_audited} concerns")
        
        return output


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Audit coverage gaps in privacy policies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a provider (auto-find latest concerns file):
  python 02_gap_auditor.py --provider chatgpt
  
  # Process a specific input file (for split processing):
  python 02_gap_auditor.py --provider chatgpt --input ../02_Outputs/extracted_concerns/concerns_chatgpt_20260202_122720_part1.json
  
  # Test mode with limited threads:
  python 02_gap_auditor.py --provider chatgpt --test --limit 10
        """
    )
    parser.add_argument("--provider", type=str, help="Process specific provider")
    parser.add_argument("--input", type=str, help="Explicit input file path (for split processing)")
    parser.add_argument("--test", action="store_true", help="Test mode (use test files)")
    parser.add_argument("--limit", type=int, help="Limit number of threads to process")
    parser.add_argument("--concurrent", type=int, default=70, help="Max concurrent requests")
    parser.add_argument("--config", type=str, help="Path to config file")
    
    args = parser.parse_args()
    
    # Load config
    config_path = args.config
    if not config_path:
        config_path = SCRIPT_DIR.parent / "configs" / "pipeline_config.yaml"
    
    config = load_config(config_path)
    
    # Initialize auditor
    auditor = GapAuditor(
        config=config,
        max_concurrent=args.concurrent
    )
    
    # Determine input file
    input_file = Path(args.input) if args.input else None
    
    # Get providers
    if args.input and not args.provider:
        # Try to extract provider from input filename
        import re
        match = re.search(r'concerns_(\w+)_', Path(args.input).name)
        if match:
            providers = [match.group(1)]
        else:
            print("Error: Cannot determine provider from input file. Please specify --provider")
            return 1
    else:
        providers = [args.provider] if args.provider else PROVIDERS
    
    for provider in providers:
        auditor.run(provider, test_mode=args.test, limit=args.limit, input_file=input_file)
    
    print("\n✅ Gap analysis complete!")


if __name__ == "__main__":
    main()