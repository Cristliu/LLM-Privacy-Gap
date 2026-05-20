# Configuration Loader
# Loads and manages pipeline configuration

import yaml
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

# Default base path for the Gap Analysis module
BASE_DIR = Path(__file__).parent.parent.parent  # 02_Gap_Analysis/

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load pipeline configuration from YAML file.
    
    Args:
        config_path: Optional path to config file. 
                     Defaults to configs/pipeline_config.yaml
    
    Returns:
        Configuration dictionary
    """
    if config_path is None:
        config_path = BASE_DIR / "configs" / "pipeline_config.yaml"
    
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Resolve relative paths to absolute paths
    config = _resolve_paths(config)
    
    return config


def _resolve_paths(config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve relative paths in config to absolute paths."""
    paths = config.get('paths', {})
    
    # Convert relative paths to absolute
    for key, value in paths.items():
        if isinstance(value, str) and (value.startswith('./') or value.startswith('../')):
            # Resolve relative to BASE_DIR and normalize
            resolved = (BASE_DIR / value).resolve()
            paths[key] = str(resolved)
    
    config['paths'] = paths
    return config


def get_provider_config(config: Dict[str, Any], provider_name: str) -> Optional[Dict[str, Any]]:
    """
    Get configuration for a specific provider.
    
    Args:
        config: Full pipeline configuration
        provider_name: Name of the provider (e.g., 'chatgpt', 'claude')
    
    Returns:
        Provider configuration dict or None if not found
    """
    providers = config.get('providers', [])
    
    for provider in providers:
        if provider.get('name', '').lower() == provider_name.lower():
            return provider
    
    return None


def get_policy_paths(config: Dict[str, Any], provider_name: str) -> List[Path]:
    """
    Get all policy file paths for a specific provider.
    
    Args:
        config: Full pipeline configuration
        provider_name: Name of the provider
    
    Returns:
        List of paths to policy documents
    """
    provider_config = get_provider_config(config, provider_name)
    if not provider_config:
        return []
    
    paths = config.get('paths', {})
    policy_base = Path(paths.get('policy_base', ''))
    policy_main = paths.get('policy_main', 'privacy_policies')
    policy_supplemental = paths.get('policy_supplemental', 'supplemental_documents')
    
    policy_files = []
    
    # Main policy directories
    for policy_dir in provider_config.get('policy_dirs', []):
        main_path = policy_base / policy_main / policy_dir
        if main_path.exists():
            policy_files.extend(main_path.glob('*.md'))
    
    # Supplemental policy directories
    for supp_dir in provider_config.get('supplemental_dirs', []):
        supp_path = policy_base / policy_supplemental / supp_dir
        if supp_path.exists():
            policy_files.extend(supp_path.glob('*.md'))
    
    return policy_files


def get_reddit_data_path(config: Dict[str, Any], provider_name: str) -> Optional[Path]:
    """
    Get path to Reddit data file for a specific provider.
    
    Tries two locations:
    1. New preprocessed data: 02_Outputs/preprocessed_threads/gap_threads_{provider}_*.json
    2. Legacy data: paths.reddit_data/threads_{provider}_*.json
    
    Args:
        config: Full pipeline configuration
        provider_name: Name of the provider
    
    Returns:
        Path to the Reddit threads JSON file
    """
    paths = config.get('paths', {})
    
    # First try: new preprocessed data (preferred)
    preprocessed_dir = BASE_DIR / "02_Outputs" / "preprocessed_threads"
    if preprocessed_dir.exists():
        patterns = [
            f"gap_threads_{provider_name}_*.json",
            f"gap_threads_{provider_name.lower()}_*.json"
        ]
        for pattern in patterns:
            matches = list(preprocessed_dir.glob(pattern))
            if matches:
                return sorted(matches)[-1]
    
    # Fallback: legacy data location
    reddit_base = Path(paths.get('reddit_data', ''))
    
    # Try different filename patterns
    patterns = [
        f"threads_{provider_name}_*.json",
        f"threads_{provider_name.lower()}_*.json",
        f"threads_{provider_name}.json"
    ]
    
    for pattern in patterns:
        matches = list(reddit_base.glob(pattern))
        if matches:
            # Return the most recent file (by name, assuming timestamp)
            return sorted(matches)[-1]
    
    return None


def list_providers(config: Dict[str, Any]) -> List[str]:
    """
    List all configured provider names.
    
    Args:
        config: Full pipeline configuration
    
    Returns:
        List of provider names
    """
    return [p.get('name', '') for p in config.get('providers', [])]


if __name__ == "__main__":
    # Test configuration loading
    config = load_config()
    print("Configuration loaded successfully!")
    print(f"Providers: {list_providers(config)}")
    print(f"LLM Model: {config['llm']['model']}")
    print(f"Embedding Model: {config['clustering']['embedding_model']}")
