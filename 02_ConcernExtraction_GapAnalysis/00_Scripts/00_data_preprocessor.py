"""
Gap Analysis - Data Preprocessor

Purpose:
    Load cleaned Reddit data and prepare it for Gap Analysis pipeline.
    This script extracts thread data with proper thread_id, URL, metadata,
    and critically preserves parent_id for building conversation chains.

Input: reddit_cleaned_YYYYMMDD_HHMMSS.csv
Output: gap_threads_{provider}_{timestamp}.json per provider

Usage:
    python 00_data_preprocessor.py [--input <csv_path>] [--test]
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict

import pandas as pd
from tqdm import tqdm

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))
from utils import setup_logger, load_config, save_json

# =============================================================================
# Configuration
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "configs" / "pipeline_config.yaml"

# Default input file
DEFAULT_INPUT = BASE_DIR.parent / "01_Data_Collection" / "04_Data_Cleaning" / "outputs" / "reddit_cleaned.csv"

# Output directories
OUTPUT_DIR = BASE_DIR / "02_Outputs" / "preprocessed_threads"

# Session timestamp
SESSION_TS = datetime.now().strftime("%Y%m%d_%H%M%S")

# Reddit base URL
REDDIT_BASE_URL = "https://www.reddit.com"


# =============================================================================
# Provider Mapping
# =============================================================================

SUBREDDIT_TO_PROVIDER: Dict[str, str] = {
    # ChatGPT (OpenAI)
    "chatgpt": "chatgpt",
    "openai": "chatgpt",
    # Gemini (Google)
    "bard": "gemini",
    "geminiAI": "gemini",
    "gemini": "gemini",
    "google_bard": "gemini",
    # Claude (Anthropic)
    "claudeai": "claude",
    "claude_ai": "claude",
    "anthropic": "claude",
    # Grok (xAI)
    "grok": "grok",
    "xai": "grok",
    # DeepSeek
    "deepseek": "deepseek",
    "deepseekAI": "deepseek",
}

PROVIDERS = ["chatgpt", "claude", "gemini", "grok", "deepseek"]


def get_provider(subreddit: str) -> Optional[str]:
    """Map subreddit name to LLM provider (lowercase)."""
    return SUBREDDIT_TO_PROVIDER.get(subreddit.lower(), None)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class Comment:
    """A single comment in a thread."""

    comment_id: str
    author: str
    body: str
    score: int
    created_utc: float
    parent_id: str  # Critical for building conversation chains
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass 
class GapThread:
    """A Reddit thread prepared for Gap Analysis."""
    thread_id: str           # Unique ID: {Provider}_{post_id}
    post_id: str             # Original Reddit post ID
    subreddit: str           # Subreddit name
    provider: str            # LLM provider (lowercase)
    title: str               # Post title
    selftext: str            # Post body
    author: str              # Post author
    score: int               # Upvotes
    created_utc: float       # Unix timestamp
    num_comments: int        # Comment count
    url: str                 # Full Reddit URL
    permalink: str           # Reddit permalink
    search_keyword: str      # Privacy keyword that matched
    comments: List[Comment] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "thread_id": self.thread_id,
            "post_id": self.post_id,
            "subreddit": self.subreddit,
            "provider": self.provider,
            "title": self.title,
            "selftext": self.selftext,
            "author": self.author,
            "score": self.score,
            "created_utc": self.created_utc,
            "num_comments": self.num_comments,
            "url": self.url,
            "permalink": self.permalink,
            "search_keyword": self.search_keyword,
            "comments": [c.to_dict() for c in self.comments]
        }
    
    def get_full_text(self) -> str:
        """Get full thread text for analysis (title + selftext + comments)."""
        parts = [f"[Title]: {self.title}"]
        if self.selftext and self.selftext.strip():
            parts.append(f"[Post Content]: {self.selftext}")
        if self.comments:
            parts.append(f"[Comments ({len(self.comments)})]:")
            for i, c in enumerate(self.comments[:20], 1):  # Limit to top 20 comments
                parts.append(f"  [{i}] (score:{c.score}) {c.body[:500]}")
        return "\n".join(parts)
    
    def build_comment_tree(self) -> Dict[str, List[Comment]]:
        """
        Build a tree structure of comments by parent_id.
        Returns: Dict mapping parent_id -> list of child comments
        """
        tree: Dict[str, List[Comment]] = {}
        for comment in self.comments:
            parent = comment.parent_id
            if parent not in tree:
                tree[parent] = []
            tree[parent].append(comment)
        return tree
    
    def get_comment_chain(self, comment_id: str) -> List[Comment]:
        """
        Get the conversation chain leading to a specific comment.
        Returns comments from root to the specified comment.
        """
        # Build lookup dict
        comment_dict = {c.comment_id: c for c in self.comments}
        
        chain = []
        current_id = comment_id
        
        while current_id in comment_dict:
            comment = comment_dict[current_id]
            chain.append(comment)
            current_id = comment.parent_id
        
        # Reverse to get root -> target order
        chain.reverse()
        return chain


# =============================================================================
# Main Preprocessor
# =============================================================================

class GapDataPreprocessor:
    """Preprocessor for Gap Analysis pipeline."""
    
    def __init__(self, input_path: Path, test_mode: bool = False):
        self.input_path = input_path
        self.test_mode = test_mode
        self.logger = setup_logger(
            "GapPreprocessor",
            log_dir=BASE_DIR / "03_Logs",
            console=True
        )
        
        # Ensure output directory exists
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        self.df: Optional[pd.DataFrame] = None
        self.threads_by_provider: Dict[str, List[GapThread]] = {p: [] for p in PROVIDERS}
    
    def load_data(self) -> int:
        """Load cleaned Reddit CSV data."""
        self.logger.info(f"Loading data from: {self.input_path}")
        
        if not self.input_path.exists():
            self.logger.error(f"Input file not found: {self.input_path}")
            return 0
        
        self.df = pd.read_csv(self.input_path, low_memory=False)
        self.logger.info(f"Loaded {len(self.df)} rows")
        
        # Log column info
        self.logger.info(f"Columns: {list(self.df.columns)}")
        
        # Verify parent_id column exists
        if 'parent_id' not in self.df.columns:
            self.logger.warning("WARNING: 'parent_id' column not found! Conversation chains cannot be built.")
        else:
            self.logger.info("✓ 'parent_id' column found - conversation chains enabled")
        
        return len(self.df)
    
    def build_threads(self) -> int:
        """Build thread objects from DataFrame."""
        if self.df is None:
            self.logger.error("No data loaded. Call load_data() first.")
            return 0
        
        self.logger.info("Building threads by provider...")
        
        # Separate posts and comments
        posts_df = self.df[self.df['type'] == 'post'].copy()
        comments_df = self.df[self.df['type'] == 'comment'].copy()
        
        self.logger.info(f"Found {len(posts_df)} posts, {len(comments_df)} comments")
        
        # Build post_id -> comments mapping (with parent_id)
        comments_by_post: Dict[str, List[Comment]] = {}
        for _, row in comments_df.iterrows():
            # link_id format: t3_xxxxx
            link_id = str(row.get('link_id', ''))
            if link_id.startswith('t3_'):
                post_id = link_id  # Keep full format
            else:
                post_id = f"t3_{link_id}"
            
            if post_id not in comments_by_post:
                comments_by_post[post_id] = []
            
            # Include parent_id for conversation chain building
            comment = Comment(
                comment_id=str(row.get('id', '')),
                author=str(row.get('author', '[deleted]') or '[deleted]'),
                body=str(row.get('body', '') or ''),
                score=int(row.get('score', 0) or 0),
                created_utc=float(row.get('created_utc', 0) or 0),
                parent_id=str(row.get('parent_id', '') or '')  # Critical field
            )
            comments_by_post[post_id].append(comment)
        
        # Sort comments by score (descending) for each post
        for post_id in comments_by_post:
            comments_by_post[post_id].sort(key=lambda c: c.score, reverse=True)
        
        # Build threads from posts
        skipped_unknown_provider = 0
        
        for _, row in tqdm(posts_df.iterrows(), total=len(posts_df), desc="Building threads"):
            subreddit = str(row.get('subreddit', ''))
            provider = get_provider(subreddit)
            
            if provider is None:
                skipped_unknown_provider += 1
                continue
            
            post_id = str(row.get('id', ''))
            
            # Build full URL from permalink
            permalink = str(row.get('permalink', ''))
            if permalink and not permalink.startswith('http'):
                url = f"{REDDIT_BASE_URL}{permalink}"
            else:
                url = permalink
            
            # Create unique thread_id
            thread_id = f"{provider.capitalize()}_{post_id}"
            
            thread = GapThread(
                thread_id=thread_id,
                post_id=post_id,
                subreddit=subreddit,
                provider=provider,
                title=str(row.get('title', '') or ''),
                selftext=str(row.get('selftext', '') or ''),
                author=str(row.get('author', '[deleted]') or '[deleted]'),
                score=int(row.get('score', 0) or 0),
                created_utc=float(row.get('created_utc', 0) or 0),
                num_comments=int(row.get('num_comments', 0) or 0),
                url=url,
                permalink=permalink,
                search_keyword=str(row.get('search_keyword', '') or ''),
                comments=comments_by_post.get(post_id, [])
            )
            
            self.threads_by_provider[provider].append(thread)
        
        if skipped_unknown_provider > 0:
            self.logger.warning(f"Skipped {skipped_unknown_provider} posts with unknown provider")
        
        # Log counts per provider
        total_threads = 0
        for provider in PROVIDERS:
            count = len(self.threads_by_provider[provider])
            total_threads += count
            self.logger.info(f"  {provider}: {count} threads")
        
        self.logger.info(f"Total threads built: {total_threads}")
        return total_threads
    
    def save_threads(self) -> Dict[str, Path]:
        """Save threads to JSON files, one per provider."""
        self.logger.info("Saving threads to JSON files...")
        
        saved_files: Dict[str, Path] = {}
        
        for provider in PROVIDERS:
            threads = self.threads_by_provider[provider]
            
            if not threads:
                self.logger.warning(f"No threads for provider: {provider}")
                continue
            
            # In test mode, limit to 2 threads per provider (faster testing)
            if self.test_mode:
                threads = threads[:2]
                self.logger.info(f"  [TEST MODE] Limiting {provider} to {len(threads)} threads")
            
            output_data = {
                "provider": provider,
                "timestamp": SESSION_TS,
                "total_threads": len(threads),
                "test_mode": self.test_mode,
                "threads": [t.to_dict() for t in threads]
            }
            
            filename = f"gap_threads_{provider}_{SESSION_TS}.json"
            output_path = OUTPUT_DIR / filename
            
            save_json(output_data, output_path)
            saved_files[provider] = output_path
            
            self.logger.info(f"  Saved {len(threads)} threads to: {output_path.name}")
        
        return saved_files
    
    def generate_summary(self, saved_files: Dict[str, Path]) -> Path:
        """Generate preprocessing summary."""
        summary = {
            "timestamp": SESSION_TS,
            "input_file": str(self.input_path),
            "test_mode": self.test_mode,
            "total_rows": len(self.df) if self.df is not None else 0,
            "version": "1.0",
            "features": ["parent_id_preserved", "conversation_chain_support"],
            "providers": {}
        }
        
        for provider in PROVIDERS:
            threads = self.threads_by_provider[provider]
            if self.test_mode:
                threads = threads[:10]
            
            # Count comments with valid parent_id
            total_comments = sum(len(t.comments) for t in threads)
            comments_with_parent = sum(
                1 for t in threads 
                for c in t.comments 
                if c.parent_id and c.parent_id.strip()
            )
            
            summary["providers"][provider] = {
                "thread_count": len(threads),
                "total_comments": total_comments,
                "comments_with_parent_id": comments_with_parent,
                "output_file": str(saved_files.get(provider, "N/A")),
                "top_keywords": self._get_top_keywords(threads, n=5)
            }
        
        summary_path = OUTPUT_DIR / f"preprocessing_summary_{SESSION_TS}.json"
        save_json(summary, summary_path)
        
        self.logger.info(f"Saved summary to: {summary_path.name}")
        return summary_path
    
    def _get_top_keywords(self, threads: List[GapThread], n: int = 5) -> List[str]:
        """Get top N search keywords from threads."""
        from collections import Counter
        keywords = [t.search_keyword for t in threads if t.search_keyword]
        return [kw for kw, _ in Counter(keywords).most_common(n)]
    
    def run(self) -> bool:
        """Run full preprocessing pipeline."""
        self.logger.info("=" * 60)
        self.logger.info("Gap Analysis Data Preprocessor")
        self.logger.info("  Feature: parent_id preserved for conversation chains")
        if self.test_mode:
            self.logger.info("🧪 TEST MODE: Limited to 2 threads per provider")
        self.logger.info("=" * 60)
        
        # Step 1: Load data
        if self.load_data() == 0:
            return False
        
        # Step 2: Build threads
        if self.build_threads() == 0:
            return False
        
        # Step 3: Save threads
        saved_files = self.save_threads()
        
        # Step 4: Generate summary
        self.generate_summary(saved_files)
        
        self.logger.info("=" * 60)
        self.logger.info("Preprocessing complete!")
        self.logger.info(f"Output directory: {OUTPUT_DIR}")
        self.logger.info("=" * 60)
        
        return True


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Gap Analysis Data Preprocessor")
    parser.add_argument(
        "--input", "-i",
        type=str,
        default=str(DEFAULT_INPUT),
        help="Path to cleaned Reddit CSV file"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: limit to 2 threads per provider"
    )
    
    args = parser.parse_args()
    
    preprocessor = GapDataPreprocessor(
        input_path=Path(args.input),
        test_mode=args.test
    )
    
    success = preprocessor.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
