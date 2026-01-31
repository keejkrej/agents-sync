"""Platform definitions and path management."""

import json
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


def _get_installed_plugin_paths() -> List[Path]:
    """
    Get paths of installed Claude plugins from installed_plugins.json.

    Returns paths from installed_plugins.json rather than scanning marketplaces/,
    since marketplaces/ contains all available plugins while installed_plugins.json
    tracks only what the user has actually installed.
    """
    home = Path.home()
    installed_file = home / ".claude" / "plugins" / "installed_plugins.json"
    plugin_paths = []

    if not installed_file.exists():
        return plugin_paths

    try:
        with open(installed_file, 'r') as f:
            data = json.load(f)

        plugins = data.get("plugins", {})
        for plugin_key, installs in plugins.items():
            # Each plugin can have multiple installs (scoped)
            # installs is a list of install records
            if isinstance(installs, list):
                for install in installs:
                    install_path = install.get("installPath")
                    if install_path:
                        path = Path(install_path)
                        if path.exists() and path.is_dir():
                            plugin_paths.append(path)
    except (json.JSONDecodeError, IOError):
        pass

    return plugin_paths


def _discover_claude_plugin_paths() -> List[Path]:
    """Discover skill paths from installed Claude plugins."""
    plugin_paths = _get_installed_plugin_paths()
    skill_paths = []

    for plugin_path in plugin_paths:
        # Search for 'skills' directories within each installed plugin
        for path in plugin_path.rglob("skills"):
            if path.is_dir():
                skill_paths.append(path)

        # Also include the plugin directory itself for recursive scanning
        skill_paths.append(plugin_path)

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
        Dictionary with 'global' and optionally 'plugins' (list of paths)
    """
    home = Path.home()

    mcp_paths = {
        Platform.CLAUDE_CODE: {
            "global": home / ".claude.json",
            "plugins": _get_installed_plugin_paths(),
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
