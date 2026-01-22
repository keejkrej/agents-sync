"""Platform definitions and path management."""

from pathlib import Path
from typing import Dict, List
from enum import Enum


class Platform(Enum):
    """Supported platforms."""
    CLAUDE_CODE = "claude-code"
    OPENCODE = "opencode"
    CODEX = "codex"
    CURSOR = "cursor"
    WINDSURF = "windsurf"


def _discover_claude_plugin_paths() -> List[Path]:
    """Discover skill paths under .claude/plugins/marketplaces only."""
    home = Path.home()
    marketplace_dir = home / ".claude" / "plugins" / "marketplaces"
    skill_paths = []
    
    if marketplace_dir.exists() and marketplace_dir.is_dir():
        # Recursively search for 'skills' directories under marketplace
        # These are parent directories that contain skill subdirectories
        for path in marketplace_dir.rglob("skills"):
            if path.is_dir():
                skill_paths.append(path)
        
        # Also include the marketplace directory for recursive scanning
        # This allows finding skills in any nested structure
        skill_paths.append(marketplace_dir)
    
    return skill_paths


def get_platform_paths(platform: Platform) -> List[Path]:
    """
    Get all skill paths for a given platform.
    
    Args:
        platform: The platform enum
        
    Returns:
        List of Path objects for skill directories
    """
    home = Path.home()
    
    # Base paths for Claude Code
    claude_base_paths = [
        home / ".claude" / "skills",
    ]
    # Add discovered plugin paths
    claude_base_paths.extend(_discover_claude_plugin_paths())
    
    platform_paths = {
        Platform.CLAUDE_CODE: claude_base_paths,
        Platform.OPENCODE: [
            home / ".opencode" / "skill",
        ],
        Platform.CODEX: [
            home / ".codex" / "skills",
        ],
        Platform.CURSOR: [
            home / ".cursor" / "skills",
        ],
        Platform.WINDSURF: [
            home / ".windsurf" / "skills",
        ],
    }
    
    return platform_paths.get(platform, [])


def get_mcp_paths(platform: Platform) -> dict:
    """
    Get MCP config file paths for a platform.

    Returns:
        Dictionary with 'global' and optionally 'plugins' paths
    """
    home = Path.home()

    mcp_paths = {
        Platform.CLAUDE_CODE: {
            "global": home / ".claude.json",
            "plugins": home / ".claude" / "plugins" / "cache",
        },
        Platform.CODEX: {
            "global": home / ".codex" / "config.toml",
        },
        Platform.OPENCODE: {
            "global": home / ".config" / "opencode" / "opencode.json",
        },
        Platform.CURSOR: {
            "global": home / ".cursor" / "mcp.json",
        },
        Platform.WINDSURF: {
            "global": home / ".codeium" / "windsurf" / "mcp_config.json",
        },
    }

    return mcp_paths.get(platform, {})


def get_all_platforms() -> Dict[str, Platform]:
    """Get all platforms as a dictionary."""
    return {p.value: p for p in Platform}


def get_platform_display_name(platform: Platform) -> str:
    """Get a display name for the platform."""
    names = {
        Platform.CLAUDE_CODE: "Claude Code",
        Platform.OPENCODE: "OpenCode",
        Platform.CODEX: "Codex",
        Platform.CURSOR: "Cursor",
        Platform.WINDSURF: "Windsurf",
    }
    return names.get(platform, platform.value)
