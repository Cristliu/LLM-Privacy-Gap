# Logger Utility
# Configures logging for the pipeline

import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Union

from .file_utils import ensure_dir


def setup_logger(
    name: str,
    log_dir: Optional[Union[str, Path]] = None,
    level: int = logging.INFO,
    console: bool = True,
    file_log: bool = True
) -> logging.Logger:
    """
    Set up a configured logger instance.
    
    Args:
        name: Logger name (typically script name)
        log_dir: Directory for log files
        level: Logging level
        console: Whether to log to console
        file_log: Whether to log to file
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Log format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if file_log and log_dir:
        log_dir = ensure_dir(log_dir)
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = log_dir / f"{name}_{timestamp}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger by name.
    
    Args:
        name: Logger name
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class ProgressLogger:
    """Helper class for logging progress of batch operations."""
    
    def __init__(
        self,
        logger: logging.Logger,
        total: int,
        prefix: str = "Processing",
        log_interval: int = 10
    ):
        """
        Initialize progress logger.
        
        Args:
            logger: Logger instance
            total: Total number of items
            prefix: Log message prefix
            log_interval: Log every N items
        """
        self.logger = logger
        self.total = total
        self.prefix = prefix
        self.log_interval = log_interval
        self.current = 0
        self.start_time = datetime.now()
    
    def update(self, message: str = ""):
        """Update progress counter and optionally log."""
        self.current += 1
        
        if self.current % self.log_interval == 0 or self.current == self.total:
            now = datetime.now()
            elapsed = (now - self.start_time).total_seconds()
            rate = self.current / elapsed if elapsed > 0 else 0
            
            # Calculate ETA
            if rate > 0:
                remaining_items = self.total - self.current
                eta_seconds = remaining_items / rate
                
                # Format ETA string
                if eta_seconds > 3600:
                    eta_str = f"{int(eta_seconds//3600)}h {int((eta_seconds%3600)//60)}m"
                elif eta_seconds > 60:
                    eta_str = f"{int(eta_seconds//60)}m {int(eta_seconds%60)}s"
                else:
                    eta_str = f"{int(eta_seconds)}s"
                    
                # Calculate estimated completion time
                completion_time = (now + timedelta(seconds=eta_seconds)).strftime("%H:%M:%S")
                time_info = f"ETA: {eta_str} (Finish: {completion_time})"
            else:
                time_info = "ETA: Calculating..."
            
            log_msg = f"{self.prefix}: {self.current}/{self.total} ({rate:.1f}/s) | {time_info}"
            if message:
                log_msg += f" - {message}"
            
            self.logger.info(log_msg)
    
    def finish(self, message: str = "Complete"):
        """Log completion message."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.logger.info(
            f"{self.prefix}: {message}. "
            f"Total: {self.current}, Time: {elapsed:.1f}s"
        )
