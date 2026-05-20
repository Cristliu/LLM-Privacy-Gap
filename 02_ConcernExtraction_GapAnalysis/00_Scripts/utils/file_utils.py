# File Utilities
# Common file operations for the pipeline

import os
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Union


def ensure_dir(path: Union[str, Path]) -> Path:
    """
    Ensure directory exists, create if not.
    
    Args:
        path: Directory path to ensure
    
    Returns:
        Path object for the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_timestamp() -> str:
    """Get current timestamp string for filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_json(
    data: Any,
    filepath: Union[str, Path],
    pretty: bool = True,
    ensure_ascii: bool = False
) -> Path:
    """
    Save data to JSON file.
    
    Args:
        data: Data to save
        filepath: Output file path
        pretty: Whether to format with indentation
        ensure_ascii: Whether to escape non-ASCII characters
    
    Returns:
        Path to saved file
    """
    filepath = Path(filepath)
    ensure_dir(filepath.parent)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(
            data, f,
            indent=2 if pretty else None,
            ensure_ascii=ensure_ascii
        )
    
    return filepath


def load_json(filepath: Union[str, Path]) -> Any:
    """
    Load data from JSON file.
    
    Args:
        filepath: Path to JSON file
    
    Returns:
        Loaded data
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"JSON file not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_csv(
    data: List[Dict[str, Any]],
    filepath: Union[str, Path],
    fieldnames: Optional[List[str]] = None
) -> Path:
    """
    Save list of dicts to CSV file.
    
    Args:
        data: List of dictionaries to save
        filepath: Output file path
        fieldnames: Optional list of column names (auto-detected if None)
    
    Returns:
        Path to saved file
    """
    filepath = Path(filepath)
    ensure_dir(filepath.parent)
    
    if not data:
        # Write empty file with headers if provided
        if fieldnames:
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
        return filepath
    
    # Auto-detect fieldnames from first row if not provided
    if fieldnames is None:
        fieldnames = list(data[0].keys())
    
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)
    
    return filepath


def load_csv(filepath: Union[str, Path]) -> List[Dict[str, str]]:
    """
    Load CSV file as list of dicts.
    
    Args:
        filepath: Path to CSV file
    
    Returns:
        List of dictionaries
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def save_markdown(
    content: str,
    filepath: Union[str, Path]
) -> Path:
    """
    Save content to Markdown file.
    
    Args:
        content: Markdown content to save
        filepath: Output file path
    
    Returns:
        Path to saved file
    """
    filepath = Path(filepath)
    ensure_dir(filepath.parent)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return filepath


def read_text(filepath: Union[str, Path]) -> str:
    """
    Read text file content.
    
    Args:
        filepath: Path to text file
    
    Returns:
        File content as string
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def list_files(
    directory: Union[str, Path],
    pattern: str = "*",
    recursive: bool = False
) -> List[Path]:
    """
    List files in directory matching pattern.
    
    Args:
        directory: Directory to search
        pattern: Glob pattern to match
        recursive: Whether to search recursively
    
    Returns:
        List of matching file paths
    """
    directory = Path(directory)
    
    if not directory.exists():
        return []
    
    if recursive:
        return list(directory.rglob(pattern))
    else:
        return list(directory.glob(pattern))


def get_output_path(
    base_dir: Union[str, Path],
    prefix: str,
    provider: Optional[str] = None,
    extension: str = "json",
    include_timestamp: bool = True
) -> Path:
    """
    Generate standardized output file path.
    
    Args:
        base_dir: Base output directory
        prefix: File name prefix
        provider: Optional provider name
        extension: File extension
        include_timestamp: Whether to include timestamp
    
    Returns:
        Generated output path
    """
    parts = [prefix]
    
    if provider:
        parts.append(provider)
    
    if include_timestamp:
        parts.append(get_timestamp())
    
    filename = "_".join(parts) + f".{extension}"
    
    return Path(base_dir) / filename
