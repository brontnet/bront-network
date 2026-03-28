# bront.network - Configuration Management
# Bront Language v3.5

"""
Configuration loading and management for Bront.

Handles:
- bront.conf file discovery
- Default configuration values
- Directory setup (WORKDIR, LOGDIR)
- Timestamp subdirectory options
"""

import os
import configparser
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BrontConfig:
    """Configuration container for Bront execution."""
    workdir: str = field(default_factory=lambda: os.path.join(os.getcwd(), 'bront_work'))
    logdir: str = field(default_factory=lambda: os.path.join(os.getcwd(), 'bront_logs'))
    timestamp_subdirs: bool = False
    config_file: Optional[str] = None
    
    def __post_init__(self):
        """Expand user paths after initialization."""
        self.workdir = os.path.expanduser(self.workdir)
        self.logdir = os.path.expanduser(self.logdir)


def load_config(config_path: Optional[str] = None) -> BrontConfig:
    """
    Load configuration from bront.conf file.
    
    Search order (if config_path not specified):
    1. ./bront.conf (current directory)
    2. ~/.bront.conf (home directory)
    3. /etc/bront.conf (system-wide)
    
    Args:
        config_path: Optional explicit path to config file
        
    Returns:
        BrontConfig object with loaded or default values
    """
    config = configparser.ConfigParser()
    
    # Default values
    defaults = BrontConfig()
    
    # Determine config file locations to check
    if config_path:
        config_locations = [config_path]
    else:
        config_locations = [
            'bront.conf',
            os.path.expanduser('~/.bront.conf'),
            '/etc/bront.conf'
        ]
    
    # Find and load config
    config_found = None
    for loc in config_locations:
        if os.path.exists(loc):
            config.read(loc)
            config_found = loc
            break
    
    # Extract values with defaults
    workdir = config.get('directories', 'WORKDIR', fallback=defaults.workdir)
    logdir = config.get('directories', 'LOGDIR', fallback=defaults.logdir)
    timestamp_subdirs = config.getboolean('logging', 'timestamp_subdirs', fallback=defaults.timestamp_subdirs)
    
    return BrontConfig(
        workdir=workdir,
        logdir=logdir,
        timestamp_subdirs=timestamp_subdirs,
        config_file=config_found
    )


def create_config_template() -> str:
    """
    Generate a template bront.conf file content.
    
    Returns:
        String containing template configuration
    """
    return """# Bront Language Configuration
# Place this file at: ./bront.conf, ~/.bront.conf, or /etc/bront.conf

[directories]
# Working directory for script execution and output files
WORKDIR = ~/bront_work

# Log directory for execution logs
LOGDIR = ~/bront_logs

[logging]
# Create timestamp-based subdirectories (YYYY/MM/DD)
timestamp_subdirs = false
"""
