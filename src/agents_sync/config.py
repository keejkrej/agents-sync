"""Configuration management."""

import json
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict


CONFIG_DIR = Path.home() / ".config" / "agents-sync"
CONFIG_FILE = CONFIG_DIR / "config.json"
AGENTS_INFO_FILE = CONFIG_DIR / "agents_info.json"
BACKUP_DIR = CONFIG_DIR / "backups"


@dataclass
class Config:
    """Configuration data structure."""
    master: Optional[str] = None
    forks: List[str] = None
    
    def __post_init__(self):
        if self.forks is None:
            self.forks = []


def ensure_config_dir():
    """Ensure config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    """Load configuration from file."""
    ensure_config_dir()
    
    if not CONFIG_FILE.exists():
        return Config()
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            return Config(**data)
    except (json.JSONDecodeError, KeyError):
        return Config()


def save_config(config: Config):
    """Save configuration to file."""
    ensure_config_dir()
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(asdict(config), f, indent=2)


def get_config_path() -> Path:
    """Get the config file path."""
    return CONFIG_FILE


def save_agents_info(platform_key: str, info: dict):
    """
    Save skills and MCP information for a platform.

    Args:
        platform_key: The platform key
        info: Dictionary with 'skills' list and optional 'mcpServers' dict
    """
    ensure_config_dir()

    # Load existing info
    if AGENTS_INFO_FILE.exists():
        try:
            with open(AGENTS_INFO_FILE, 'r') as f:
                all_info = json.load(f)
        except (json.JSONDecodeError, KeyError):
            all_info = {}
    else:
        all_info = {}

    # Update info for this platform
    all_info[platform_key] = info

    # Save back to file
    with open(AGENTS_INFO_FILE, 'w') as f:
        json.dump(all_info, f, indent=2)


def load_agents_info() -> dict:
    """Load all agents information (skills and MCP servers)."""
    ensure_config_dir()

    if not AGENTS_INFO_FILE.exists():
        return {}

    try:
        with open(AGENTS_INFO_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, KeyError):
        return {}
