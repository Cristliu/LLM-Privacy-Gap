#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gap Analysis - Unified Concern Extractor
===================================================================
Extracts privacy concerns from Reddit threads using a single LLM call per thread.

Key Features:
- ONE prompt per thread (no two-phase overhead)
- Filters out chains with no concerns
- Outputs flat records list with chain_root_id for context grouping

Input: preprocessed_threads/gap_threads_{provider}_{timestamp}.json
Output: extracted_concerns/concerns_{provider}_{timestamp}.json

Usage:
    python 01_concern_extractor.py [--provider PROVIDER] [--limit N] [--test] [--concurrent N]
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
from collections import defaultdict

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

# Global flag for graceful exit
_SHUTDOWN_REQUESTED = False

def _signal_handler(signum, frame):
    global _SHUTDOWN_REQUESTED
    _SHUTDOWN_REQUESTED = True
    print("\n⚠️  Shutdown requested. Saving progress and exiting gracefully...")

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

from utils.config_loader import load_config
from utils.file_utils import ensure_dir, save_json, load_json, get_timestamp
from utils.llm_client import LLMClient
from utils.logger import setup_logger, ProgressLogger


# =============================================================================
# Privacy Topic Taxonomy
# =============================================================================

TOPIC_CODES = {
    # GROUP A: DATA LIFECYCLE
    "A1.1_INPUT_CONTENT": "User input content handling (prompts, conversations, files, voice, video)",
    "A1.2_BEHAVIORAL_METADATA": "Behavioral data & metadata collection (usage patterns, device info, IP)",
    "A2.1_SERVICE_PROVISION": "Data used for service delivery (responses, personalization)",
    "A2.2_MODEL_TRAINING": "Data used for AI model training & improvement",
    "A3.1_RETENTION_DURATION": "Data retention period, storage location, lifecycle",
    "A3.2_DELETION_MECHANISM": "Deletion request handling, verification, completeness",
    "A4.1_THIRD_PARTY_SHARING": "Data sharing with third parties (advertisers, partners, government)",
    "A4.2_PLUGIN_EXTENSION_ACCESS": "Plugin/GPTs/Actions/Extensions access to user data",
    
    # GROUP B: USER RIGHTS & CONTROL
    "B1.1_CONSENT_MECHANISM": "Privacy consent methods (opt-in/opt-out, defaults)",
    "B1.2_GRANULAR_CONTROL": "Fine-grained privacy controls (Memory toggle, training opt-out)",
    "B1.3_TRANSPARENCY_DISCLOSURE": "Transparency of data processing disclosure",
    "B1.4_POLICY_CHANGE_NOTIFICATION": "Privacy policy change notification & communication",
    
    # GROUP C: AI-SPECIFIC
    "C1.1_OUTPUT_PRIVACY_RISK": "Privacy risks in AI outputs (leaking, inference, hallucination)",
    "C1.2_MEMORY_PERSONALIZATION": "Memory feature & personalization privacy impact",
    "C2.1_AGENT_AUTONOMOUS_ACTIONS": "AI Agent autonomous operations privacy boundaries",
    "C2.2_DOWNSTREAM_INTEGRATION": "LLM integrated into downstream apps (API, embodied AI, IoT)",
    
    # GROUP D: COMPLIANCE & PROTECTION
    "D1.1_JURISDICTION_LAW": "Applicable laws, cross-border transfer, regional rights (GDPR, CCPA)",
    "D1.2_VULNERABLE_POPULATION": "Vulnerable group privacy protection (children, elderly)",
    "D2.1_DATA_SECURITY": "Privacy data security measures (encryption, access control)",
    "D2.2_BREACH_NOTIFICATION": "Data breach notification & remediation",
}


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class ConcernData:
    """Concern metadata extracted by LLM."""
    topics: List[str]                       # Array of topic codes (usually 1, max 2)
    concern_statement: str
    user_assumption: str
    supporting_quote: str = ""
    confidence: float = 0.8
    reasoning: str = ""                     # Explanation for topic selection
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topics": self.topics,
            "concern_statement": self.concern_statement,
            "user_assumption": self.user_assumption,
            "supporting_quote": self.supporting_quote,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }


@dataclass 
class RecordItem:
    """A single record (post or comment)."""
    record_id: str
    type: str                               # "post" or "comment"
    author: str
    body: str
    score: int
    created_utc: float
    parent_id: Optional[str] = None
    chain_root_id: Optional[str] = None    
    is_concern_source: bool = False
    concerns: List[ConcernData] = field(default_factory=list)  # Support multiple concerns per record
    
    def to_dict(self) -> Dict[str, Any]:
        d = {
            "record_id": self.record_id,
            "type": self.type,
            "author": self.author,
            "body": self.body,
            "score": self.score,
            "created_utc": self.created_utc,
            "is_concern_source": self.is_concern_source,
        }
        if self.parent_id:
            d["parent_id"] = self.parent_id
        if self.chain_root_id:
            d["chain_root_id"] = self.chain_root_id
        d["concerns"] = [c.to_dict() for c in self.concerns] if self.concerns else []
        return d


@dataclass
class ThreadResult:
    """Extraction result for a single thread."""
    thread_id: str
    post_id: str
    subreddit: str
    title: str
    url: str
    permalink: str
    search_keyword: str
    post: Optional[RecordItem] = None
    records: List[RecordItem] = field(default_factory=list)
    extraction_success: bool = True
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        d = {
            "thread_id": self.thread_id,
            "post_id": self.post_id,
            "subreddit": self.subreddit,
            "title": self.title,
            "url": self.url,
            "permalink": self.permalink,
            "search_keyword": self.search_keyword,
            "extraction_success": self.extraction_success,
        }
        if self.post:
            d["post"] = self.post.to_dict()
        d["records"] = [r.to_dict() for r in self.records]
        if self.error_message:
            d["error_message"] = self.error_message
        return d


# =============================================================================
# Configuration
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = BASE_DIR / "02_Outputs"
DEFAULT_LOG_DIR = BASE_DIR / "03_Logs"
DEFAULT_PROMPT_DIR = BASE_DIR / "01_Prompts"

PROVIDERS = ["chatgpt", "claude", "gemini", "grok", "deepseek"]


# =============================================================================
# Unified Concern Extractor
# =============================================================================

class UnifiedConcernExtractor:
    """Single-pass concern extractor using one LLM call per thread."""
    
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
            "UnifiedConcernExtractor",
            log_dir=self.log_dir,
            console=True
        )
        
        # Load prompt template
        prompt_path = DEFAULT_PROMPT_DIR / "concern_extraction.txt"
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
        
        # Thread-safe state
        self._lock = threading.Lock()
        self.thread_results: List[ThreadResult] = []
        self.processed_count: int = 0
        self.concern_count: int = 0
        self.new_topics: Set[str] = set()
    
    def _get_default_prompt(self) -> str:
        return """You are a privacy research assistant analyzing Reddit discussions about {provider}.

## Thread Information
- Title: {title}
- URL: {url}

## Thread Content
{content}

## Topic Taxonomy
{taxonomy}

## Task
Identify ALL records (post and comments) that express privacy concerns.

## Output Format (JSON only)
```json
{
  "thread_has_concerns": true,
  "concerns": [
    {
      "source_type": "post",
      "source_id": "t3_xxx",
      "topic": "A1.1_INPUT_CONTENT",
      "concern_statement": "...",
      "user_assumption": "...",
      "confidence": 0.85
    }
  ]
}
```

Respond with valid JSON only."""
    
    def _build_comment_chains(
        self,
        comments: List[Dict[str, Any]],
        post_id: str
    ) -> Dict[str, str]:
        """Build mapping: comment_id -> chain_root_id."""
        comment_lookup = {c.get('comment_id', ''): c for c in comments if c.get('comment_id')}
        comment_to_chain: Dict[str, str] = {}
        
        def find_chain_root(comment_id: str, visited: Set[str] = None) -> str:
            if visited is None:
                visited = set()
            if comment_id in visited:
                return comment_id
            visited.add(comment_id)
            
            if comment_id not in comment_lookup:
                return comment_id
            
            parent_id = comment_lookup[comment_id].get('parent_id', '')
            if parent_id == post_id or parent_id.startswith('t3_'):
                return comment_id
            
            return find_chain_root(parent_id, visited)
        
        for comment_id in comment_lookup:
            comment_to_chain[comment_id] = find_chain_root(comment_id)
        
        return comment_to_chain
    
    def _format_thread_content(self, thread: Dict[str, Any]) -> str:
        """Format thread for prompt."""
        parts = []
        post_id = thread.get('post_id', '')
        comments = thread.get('comments', [])
        comment_to_chain = self._build_comment_chains(comments, post_id)
        
        # Post
        parts.append(f"[POST] (id: {post_id})")
        parts.append(f"Title: {thread.get('title', '')}")
        if thread.get('selftext'):
            parts.append(f"Content: {thread.get('selftext', '')}")
        parts.append(f"Author: {thread.get('author', '[deleted]')}, Score: {thread.get('score', 0)}")
        parts.append("")
        
        # Comments with chain info
        for i, comment in enumerate(comments, 1):
            cid = comment.get('comment_id', '')
            chain_root = comment_to_chain.get(cid, '')
            parent = comment.get('parent_id', '')
            
            parts.append(f"[COMMENT {i}] (id: {cid}, chain: {chain_root}, parent: {parent})")
            parts.append(f"Content: {comment.get('body', '')}")
            parts.append(f"Author: {comment.get('author', '[deleted]')}, Score: {comment.get('score', 0)}")
            parts.append("")
        
        return "\n".join(parts)
    
    def _format_taxonomy(self) -> str:
        lines = [f"- {code}: {desc}" for code, desc in TOPIC_CODES.items()]
        return "\n".join(lines)
    
    def _prepare_prompt(self, thread: Dict[str, Any], provider: str) -> str:
        url = thread.get('url', '')
        if not url and thread.get('permalink'):
            url = f"https://www.reddit.com{thread.get('permalink')}"
        
        prompt = self.prompt_template
        prompt = prompt.replace("{provider}", provider)
        prompt = prompt.replace("{title}", thread.get('title', ''))
        prompt = prompt.replace("{url}", url)
        prompt = prompt.replace("{content}", self._format_thread_content(thread))
        prompt = prompt.replace("{taxonomy}", self._format_taxonomy())
        
        return prompt
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
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
            self.logger.debug(f"JSON parse error: {e}")
            return {"thread_has_concerns": False, "concerns": []}
    
    def extract_from_thread(
        self,
        thread: Dict[str, Any],
        provider: str
    ) -> ThreadResult:
        """Extract concerns from a single thread with ONE LLM call."""
        thread_id = thread.get('thread_id', '')
        post_id = thread.get('post_id', '')
        url = thread.get('url', '')
        if not url and thread.get('permalink'):
            url = f"https://www.reddit.com{thread.get('permalink')}"
        
        comments = thread.get('comments', [])
        comment_lookup = {c.get('comment_id', ''): c for c in comments if c.get('comment_id')}
        comment_to_chain = self._build_comment_chains(comments, post_id)
        
        try:
            # Single LLM call
            prompt = self._prepare_prompt(thread, provider)
            messages = [
                {
                    "role": "system",
                    "content": "You are a privacy research assistant. Analyze Reddit discussions to identify privacy concerns using Tree of Thoughts reasoning. Respond only with valid JSON."
                },
                {"role": "user", "content": prompt}
            ]
            
            response = self.llm.chat(messages)
            
            if isinstance(response, dict):
                if not response.get('success', False):
                    raise Exception(response.get('error', 'LLM request failed'))
                response_text = response.get('content', '')
            else:
                response_text = response
            
            parsed = self._parse_response(response_text)
            concerns = parsed.get('concerns', []) if parsed.get('thread_has_concerns') else []
            
            # Build concern lookup: record_id -> list of concerns (one record may have multiple concerns)
            concern_lookup: Dict[str, List[Dict]] = defaultdict(list)
            for c in concerns:
                source_id = c.get('source_id', '')
                if source_id:
                    concern_lookup[source_id].append(c)
                    # Track new topics (topics is now an array)
                    topics = c.get('topics', [])
                    if isinstance(topics, str):
                        topics = [topics]  # Handle legacy format
                    for topic in topics:
                        if topic.startswith('NEW_'):
                            self.new_topics.add(topic)
            
            # Helper function to create ConcernData list from concern dicts
            # IMPORTANT: If a concern has multiple topics, split into separate concerns (one per topic)
            def make_concerns(concern_list: List[Dict]) -> List[ConcernData]:
                result = []
                for c in concern_list:
                    topics = c.get('topics', [])
                    if isinstance(topics, str):
                        topics = [topics]  # Handle legacy single topic format
                    
                    # Split multi-topic concerns into separate single-topic concerns
                    if len(topics) == 0:
                        continue
                    
                    for topic in topics:
                        result.append(ConcernData(
                            topics=[topic],  # Each concern now has exactly ONE topic
                            concern_statement=c.get('concern_statement', ''),
                            user_assumption=c.get('user_assumption', ''),
                            supporting_quote=c.get('supporting_quote', ''),
                            confidence=float(c.get('confidence', 0.8)),
                            reasoning=c.get('reasoning', '')
                        ))
                return result
            
            # Build post record
            post_concerns = concern_lookup.get(post_id, [])
            post_record = RecordItem(
                record_id=post_id,
                type="post",
                author=thread.get('author', '[deleted]'),
                body=thread.get('selftext', ''),
                score=thread.get('score', 0),
                created_utc=thread.get('created_utc', 0),
                is_concern_source=(len(post_concerns) > 0),
                concerns=make_concerns(post_concerns)
            )
            
            # Find chains that have concerns
            chains_with_concerns: Set[str] = set()
            for comment_id in comment_lookup:
                if comment_id in concern_lookup:
                    chain_root = comment_to_chain.get(comment_id, comment_id)
                    chains_with_concerns.add(chain_root)
            
            # Build records list (only from chains with concerns)
            records: List[RecordItem] = []
            for comment in comments:
                comment_id = comment.get('comment_id', '')
                chain_root = comment_to_chain.get(comment_id, '')
                
                # Only include comments from chains that have at least one concern
                if chain_root not in chains_with_concerns:
                    continue
                
                comment_concerns = concern_lookup.get(comment_id, [])
                records.append(RecordItem(
                    record_id=comment_id,
                    type="comment",
                    author=comment.get('author', '[deleted]'),
                    body=comment.get('body', ''),
                    score=comment.get('score', 0),
                    created_utc=comment.get('created_utc', 0),
                    parent_id=comment.get('parent_id', ''),
                    chain_root_id=chain_root,
                    is_concern_source=(len(comment_concerns) > 0),
                    concerns=make_concerns(comment_concerns)
                ))
            
            # Sort by created_utc
            records.sort(key=lambda x: x.created_utc)
            
            return ThreadResult(
                thread_id=thread_id,
                post_id=post_id,
                subreddit=thread.get('subreddit', ''),
                title=thread.get('title', ''),
                url=url,
                permalink=thread.get('permalink', ''),
                search_keyword=thread.get('search_keyword', ''),
                post=post_record,
                records=records,
                extraction_success=True
            )
            
        except Exception as e:
            self.logger.warning(f"Error extracting from {thread_id}: {e}")
            return ThreadResult(
                thread_id=thread_id,
                post_id=post_id,
                subreddit=thread.get('subreddit', ''),
                title=thread.get('title', ''),
                url=url,
                permalink=thread.get('permalink', ''),
                search_keyword=thread.get('search_keyword', ''),
                extraction_success=False,
                error_message=str(e)
            )
    
    def _process_thread_wrapper(
        self,
        thread: Dict[str, Any],
        provider: str,
        progress: ProgressLogger
    ) -> ThreadResult:
        global _SHUTDOWN_REQUESTED
        
        if _SHUTDOWN_REQUESTED:
            return ThreadResult(
                thread_id=thread.get('thread_id', ''),
                post_id=thread.get('post_id', ''),
                subreddit=thread.get('subreddit', ''),
                title=thread.get('title', ''),
                url='',
                permalink=thread.get('permalink', ''),
                search_keyword=thread.get('search_keyword', ''),
                extraction_success=False,
                error_message="Shutdown requested"
            )
        
        result = self.extract_from_thread(thread, provider)
        
        with self._lock:
            self.thread_results.append(result)
            self.processed_count += 1
            
            # Count concerns (now counting individual concern entries, not just records)
            if result.post and result.post.is_concern_source:
                self.concern_count += len(result.post.concerns)
            for r in result.records:
                if r.is_concern_source:
                    self.concern_count += len(r.concerns)
        
        progress.update()
        return result
    
    def run(
        self,
        input_path: Path,
        provider: str,
        limit: Optional[int] = None,
        test_mode: bool = False
    ) -> Dict[str, Any]:
        """Run extraction on preprocessed threads."""
        global _SHUTDOWN_REQUESTED
        
        self.logger.info(f"Loading threads from {input_path}")
        data = load_json(input_path)
        threads = data.get('threads', [])
        
        if limit:
            threads = threads[:limit]
        
        total = len(threads)
        self.logger.info(f"Processing {total} threads (single-pass extraction)")
        
        # Reset state
        self.thread_results = []
        self.processed_count = 0
        self.concern_count = 0
        self.new_topics = set()
        
        # Process threads
        progress = ProgressLogger(
            logger=self.logger,
            total=total,
            prefix="Extracting concerns"
        )
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            futures = [
                executor.submit(self._process_thread_wrapper, thread, provider, progress)
                for thread in threads
            ]
            
            for future in as_completed(futures):
                if _SHUTDOWN_REQUESTED:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Thread processing error: {e}")
        
        progress.finish()
        
        # Build output
        timestamp = get_timestamp()
        test_suffix = "_test" if test_mode else ""
        output_filename = f"concerns_{provider}{test_suffix}_{timestamp}.json"
        
        # Aggregate topic distribution (now handling topics array)
        topic_distribution: Dict[str, int] = defaultdict(int)
        for result in self.thread_results:
            if result.post and result.post.concerns:
                for concern in result.post.concerns:
                    for topic in concern.topics:
                        topic_distribution[topic] += 1
            for record in result.records:
                if record.is_concern_source and record.concerns:
                    for concern in record.concerns:
                        for topic in concern.topics:
                            topic_distribution[topic] += 1
        
        output_data = {
            "provider": provider,
            "timestamp": timestamp,
            "version": "1.0",
            "stage": "Stage1_ConcernExtraction",
            "total_threads_processed": self.processed_count,
            "successful_extractions": sum(1 for r in self.thread_results if r.extraction_success),
            "total_concerns_extracted": self.concern_count,
            "new_topics_identified": list(self.new_topics),
            "topic_distribution": dict(topic_distribution),
            "threads": [r.to_dict() for r in self.thread_results]
        }
        
        # Save output
        output_dir = ensure_dir(self.output_dir / "extracted_concerns")
        output_path = output_dir / output_filename
        save_json(output_data, output_path)
        
        self.logger.info(f"Results saved to {output_path}")
        self.logger.info(f"Extracted {self.concern_count} concerns from {self.processed_count}/{total} threads")
        
        return {
            "output_path": str(output_path),
            "total_threads": total,
            "processed": self.processed_count,
            "concerns": self.concern_count,
            "new_topics": list(self.new_topics)
        }


# =============================================================================
# Main
# =============================================================================

def find_latest_preprocessed(provider: str, output_dir: Path) -> Optional[Path]:
    preprocessed_dir = output_dir / "preprocessed_threads"
    if not preprocessed_dir.exists():
        return None
    pattern = f"gap_threads_{provider}_*.json"
    files = sorted(preprocessed_dir.glob(pattern), reverse=True)
    return files[0] if files else None


def main():
    parser = argparse.ArgumentParser(description="Unified Concern Extractor")
    parser.add_argument("--provider", type=str, default="chatgpt", choices=PROVIDERS)
    parser.add_argument("--input", type=str, help="Input preprocessed threads file")
    parser.add_argument("--limit", type=int, help="Limit threads to process")
    parser.add_argument("--test", action="store_true", help="Test mode")
    parser.add_argument("--concurrent", type=int, default=70, help="Max concurrent requests")
    parser.add_argument("--config", type=str, help="Config file path")
    
    args = parser.parse_args()
    
    # Load config
    config = None
    if args.config:
        config = load_config(args.config)
    else:
        default_config = BASE_DIR / "configs" / "pipeline_config.yaml"
        if default_config.exists():
            config = load_config(default_config)
    
    # Find input file
    if args.input:
        input_path = Path(args.input)
    else:
        input_path = find_latest_preprocessed(args.provider, DEFAULT_OUTPUT_DIR)
    
    if not input_path or not input_path.exists():
        print(f"Error: No input file found for provider '{args.provider}'")
        sys.exit(1)
    
    print(f"Input: {input_path}")
    
    # Run extractor
    extractor = UnifiedConcernExtractor(
        config=config,
        max_concurrent=args.concurrent,
        output_dir=DEFAULT_OUTPUT_DIR,
        log_dir=DEFAULT_LOG_DIR
    )
    
    result = extractor.run(
        input_path=input_path,
        provider=args.provider,
        limit=args.limit,
        test_mode=args.test
    )
    
    print(f"\n✅ Extraction complete!")
    print(f"   Output: {result['output_path']}")
    print(f"   Threads: {result['processed']}/{result['total_threads']}")
    print(f"   Concerns: {result['concerns']}")
    if result['new_topics']:
        print(f"   New topics: {result['new_topics']}")


if __name__ == "__main__":
    main()
