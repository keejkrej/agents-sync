"""MCP configuration reading, writing, and translation."""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# TOML imports with Python version compatibility
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
import tomli_w

from .platforms import Platform, get_mcp_paths


def read_claude_mcp_servers() -> Tuple[Dict[str, Any], List[str]]:
    """
    Read MCP servers from Claude Code configuration.

    Returns:
        Tuple of (merged mcpServers dict, list of source descriptions)
    """
    mcp_paths = get_mcp_paths(Platform.CLAUDE_CODE)
    servers = {}
    sources = []

    # Read global config
    global_path = mcp_paths.get("global")
    if global_path and global_path.exists():
        try:
            with open(global_path, 'r') as f:
                data = json.load(f)
                global_servers = data.get("mcpServers", {})
                for name, config in global_servers.items():
                    servers[name] = config
                    sources.append(f"{name} (from ~/.claude.json)")
        except (json.JSONDecodeError, IOError):
            pass

    # Read plugin configs
    plugins_path = mcp_paths.get("plugins")
    if plugins_path and plugins_path.exists():
        for mcp_json in plugins_path.rglob(".mcp.json"):
            try:
                with open(mcp_json, 'r') as f:
                    data = json.load(f)
                    plugin_servers = data.get("mcpServers", {})
                    plugin_name = mcp_json.parent.name
                    for name, config in plugin_servers.items():
                        # Global wins if duplicate
                        if name not in servers:
                            servers[name] = config
                            sources.append(f"{name} (from {plugin_name} plugin)")
            except (json.JSONDecodeError, IOError):
                pass

    return servers, sources


def write_mcp_servers(platform: Platform, servers: Dict[str, Any], dry_run: bool = False) -> bool:
    """
    Write MCP servers to a platform's config file.
    Translates from Claude format to target format.

    Returns:
        True if successful
    """
    mcp_paths = get_mcp_paths(platform)
    global_path = mcp_paths.get("global")

    if not global_path:
        return False

    if dry_run:
        return True

    # Ensure parent directory exists
    global_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if platform == Platform.CLAUDE_CODE:
            _write_claude_mcp(global_path, servers)
        elif platform == Platform.CODEX:
            _write_codex_mcp(global_path, servers)
        elif platform == Platform.OPENCODE:
            _write_opencode_mcp(global_path, servers)
        elif platform in (Platform.CURSOR, Platform.WINDSURF):
            _write_cursor_windsurf_mcp(global_path, servers)
        return True
    except IOError:
        return False


def _write_claude_mcp(path: Path, servers: Dict[str, Any]):
    """Write MCP servers to Claude config."""
    data = {}
    if path.exists():
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            pass

    data["mcpServers"] = servers
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def _write_codex_mcp(path: Path, servers: Dict[str, Any]):
    """Write MCP servers to Codex config.toml."""
    data = {}
    if path.exists():
        try:
            with open(path, 'rb') as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError:
            pass

    # Convert Claude format to Codex format
    codex_servers = {}
    for name, config in servers.items():
        codex_config = {}
        if "command" in config:
            codex_config["command"] = config["command"]
        if "args" in config:
            codex_config["args"] = config["args"]
        if "env" in config:
            codex_config["env"] = config["env"]
        codex_servers[name] = codex_config

    data["mcp_servers"] = codex_servers
    with open(path, 'wb') as f:
        tomli_w.dump(data, f)


def _write_opencode_mcp(path: Path, servers: Dict[str, Any]):
    """Write MCP servers to OpenCode config."""
    data = {}
    if path.exists():
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            pass

    # Convert Claude format to OpenCode format
    opencode_servers = {}
    for name, config in servers.items():
        server_type = config.get("type", "stdio")
        if server_type == "stdio":
            command_list = [config.get("command", "")]
            if "args" in config:
                command_list.extend(config["args"])
            opencode_config = {
                "type": "local",
                "command": command_list,
                "enabled": True,
            }
            if "env" in config:
                opencode_config["environment"] = config["env"]
        else:  # http
            opencode_config = {
                "type": "remote",
                "url": config.get("url", ""),
                "enabled": True,
            }
            if "headers" in config:
                opencode_config["headers"] = config["headers"]
        opencode_servers[name] = opencode_config

    data["mcp"] = opencode_servers
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def _write_cursor_windsurf_mcp(path: Path, servers: Dict[str, Any]):
    """Write MCP servers to Cursor/Windsurf config (same format as Claude)."""
    data = {}
    if path.exists():
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            pass

    data["mcpServers"] = servers
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def _count_mcp_servers(platform: Platform) -> int:
    """Count MCP servers in a platform's config (for clean reporting)."""
    mcp_paths = get_mcp_paths(platform)
    global_path = mcp_paths.get("global")

    if not global_path or not global_path.exists():
        return 0

    try:
        if platform == Platform.CLAUDE_CODE:
            servers, _ = read_claude_mcp_servers()
            return len(servers)
        elif platform == Platform.CODEX:
            with open(global_path, 'rb') as f:
                data = tomllib.load(f)
            return len(data.get("mcp_servers", {}))
        elif platform == Platform.OPENCODE:
            with open(global_path, 'r') as f:
                data = json.load(f)
            return len(data.get("mcp", {}))
        elif platform in (Platform.CURSOR, Platform.WINDSURF):
            with open(global_path, 'r') as f:
                data = json.load(f)
            return len(data.get("mcpServers", {}))
    except (json.JSONDecodeError, IOError, tomllib.TOMLDecodeError):
        pass

    return 0


def clean_mcp_servers(platform: Platform, dry_run: bool = False) -> int:
    """
    Remove MCP servers from a platform's config.

    Returns:
        Number of servers removed
    """
    mcp_paths = get_mcp_paths(platform)
    removed_count = _count_mcp_servers(platform)

    if dry_run or removed_count == 0:
        return removed_count

    global_path = mcp_paths.get("global")

    try:
        if platform == Platform.CLAUDE_CODE:
            # Clean global config
            if global_path and global_path.exists():
                with open(global_path, 'r') as f:
                    data = json.load(f)
                if "mcpServers" in data:
                    del data["mcpServers"]
                    with open(global_path, 'w') as f:
                        json.dump(data, f, indent=2)

            # Clean plugin .mcp.json files
            plugins_path = mcp_paths.get("plugins")
            if plugins_path and plugins_path.exists():
                for mcp_json in plugins_path.rglob(".mcp.json"):
                    mcp_json.unlink()

        elif platform == Platform.CODEX:
            if global_path and global_path.exists():
                with open(global_path, 'rb') as f:
                    data = tomllib.load(f)
                if "mcp_servers" in data:
                    del data["mcp_servers"]
                    with open(global_path, 'wb') as f:
                        tomli_w.dump(data, f)

        elif platform == Platform.OPENCODE:
            if global_path and global_path.exists():
                with open(global_path, 'r') as f:
                    data = json.load(f)
                if "mcp" in data:
                    del data["mcp"]
                    with open(global_path, 'w') as f:
                        json.dump(data, f, indent=2)

        elif platform in (Platform.CURSOR, Platform.WINDSURF):
            if global_path and global_path.exists():
                with open(global_path, 'r') as f:
                    data = json.load(f)
                if "mcpServers" in data:
                    del data["mcpServers"]
                    with open(global_path, 'w') as f:
                        json.dump(data, f, indent=2)

    except (json.JSONDecodeError, IOError, tomllib.TOMLDecodeError):
        pass

    return removed_count
