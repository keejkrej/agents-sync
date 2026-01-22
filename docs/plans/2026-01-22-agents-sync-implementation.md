# Agents-Sync Rebrand & MCP Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebrand skills-sync to agents-sync and add MCP server configuration syncing across Claude Code, Codex, OpenCode, Cursor, and Windsurf.

**Architecture:** Unified master/fork model where Claude Code format is canonical. Scan reads MCP from `~/.claude.json` and plugin `.mcp.json` files. Sync translates to target formats on-the-fly. Clean removes both skills and MCP entries.

**Tech Stack:** Python 3.8+, Typer, Rich, tomli/tomllib, tomli_w

---

## Task 1: Add TOML Dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`

**Step 1: Update pyproject.toml**

Add tomli_w dependency. Use tomllib (stdlib) for Python 3.11+, tomli for earlier versions.

```toml
dependencies = [
    "typer>=0.9.0",
    "rich>=13.0.0",
    "inquirer>=3.1.0",
    "tomli>=2.0.0;python_version<'3.11'",
    "tomli_w>=1.0.0",
]
```

**Step 2: Update requirements.txt**

```
typer>=0.9.0
rich>=13.0.0
inquirer>=3.1.0
tomli>=2.0.0
tomli_w>=1.0.0
```

**Step 3: Commit**

```bash
git add pyproject.toml requirements.txt
git commit -m "chore: add TOML dependencies for Codex config support"
```

---

## Task 2: Rename Package Directory

**Files:**
- Rename: `src/skills_sync/` → `src/agents_sync/`

**Step 1: Rename the directory**

```bash
mv src/skills_sync src/agents_sync
```

**Step 2: Remove pycache**

```bash
rm -rf src/agents_sync/__pycache__
```

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: rename skills_sync package to agents_sync"
```

---

## Task 3: Update pyproject.toml Package Config

**Files:**
- Modify: `pyproject.toml`

**Step 1: Update package name and paths**

```toml
[tool.hatchling.build.targets.wheel]
packages = ["src/agents_sync"]
sources = ["src"]

[project]
name = "agents-sync"
version = "0.2.0"
description = "A simple CLI tool for syncing agent skills and MCP servers across platforms"

[project.scripts]
agents = "agents_sync.cli:main"
agents-sync = "agents_sync.cli:main"
skills = "agents_sync.cli:main"
skills-sync = "agents_sync.cli:main"
```

**Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "refactor: update pyproject.toml for agents-sync package"
```

---

## Task 4: Update Config Paths

**Files:**
- Modify: `src/agents_sync/config.py`

**Step 1: Update config directory paths**

Change line 9:
```python
CONFIG_DIR = Path.home() / ".config" / "agents-sync"
```

**Step 2: Commit**

```bash
git add src/agents_sync/config.py
git commit -m "refactor: change config directory to agents-sync"
```

---

## Task 5: Add MCP Path Mappings to platforms.py

**Files:**
- Modify: `src/agents_sync/platforms.py`

**Step 1: Add get_mcp_paths function**

Add after line 72 (after `get_platform_paths`):

```python
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
```

**Step 2: Commit**

```bash
git add src/agents_sync/platforms.py
git commit -m "feat: add MCP config path mappings for all platforms"
```

---

## Task 6: Create MCP Module - Reading Functions

**Files:**
- Create: `src/agents_sync/mcp.py`

**Step 1: Create mcp.py with reading functions**

```python
"""MCP configuration reading, writing, and translation."""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

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


def read_mcp_servers(platform: Platform) -> Dict[str, Any]:
    """
    Read MCP servers from a platform's config file.

    Returns:
        Dictionary of MCP server configurations in Claude format
    """
    mcp_paths = get_mcp_paths(platform)
    global_path = mcp_paths.get("global")

    if not global_path or not global_path.exists():
        return {}

    try:
        if platform == Platform.CLAUDE_CODE:
            servers, _ = read_claude_mcp_servers()
            return servers

        elif platform == Platform.CODEX:
            with open(global_path, 'rb') as f:
                data = tomllib.load(f)
            return _codex_to_claude_format(data.get("mcp_servers", {}))

        elif platform == Platform.OPENCODE:
            with open(global_path, 'r') as f:
                data = json.load(f)
            return _opencode_to_claude_format(data.get("mcp", {}))

        elif platform in (Platform.CURSOR, Platform.WINDSURF):
            with open(global_path, 'r') as f:
                data = json.load(f)
            return data.get("mcpServers", {})

    except (json.JSONDecodeError, IOError, tomllib.TOMLDecodeError):
        pass

    return {}


def _codex_to_claude_format(codex_servers: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Codex mcp_servers format to Claude mcpServers format."""
    claude_servers = {}
    for name, config in codex_servers.items():
        claude_config = {"type": "stdio"}
        if "command" in config:
            claude_config["command"] = config["command"]
        if "args" in config:
            claude_config["args"] = config["args"]
        if "env" in config:
            claude_config["env"] = config["env"]
        claude_servers[name] = claude_config
    return claude_servers


def _opencode_to_claude_format(opencode_servers: Dict[str, Any]) -> Dict[str, Any]:
    """Convert OpenCode mcp format to Claude mcpServers format."""
    claude_servers = {}
    for name, config in opencode_servers.items():
        server_type = config.get("type", "local")
        if server_type == "local":
            command_list = config.get("command", [])
            claude_config = {
                "type": "stdio",
                "command": command_list[0] if command_list else "",
                "args": command_list[1:] if len(command_list) > 1 else [],
            }
            if "environment" in config:
                claude_config["env"] = config["environment"]
        else:  # remote
            claude_config = {
                "type": "http",
                "url": config.get("url", ""),
            }
            if "headers" in config:
                claude_config["headers"] = config["headers"]
        claude_servers[name] = claude_config
    return claude_servers
```

**Step 2: Commit**

```bash
git add src/agents_sync/mcp.py
git commit -m "feat: add MCP module with reading functions"
```

---

## Task 7: Add MCP Writing Functions

**Files:**
- Modify: `src/agents_sync/mcp.py`

**Step 1: Add writing and translation functions**

Append to `mcp.py`:

```python
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
```

**Step 2: Commit**

```bash
git add src/agents_sync/mcp.py
git commit -m "feat: add MCP writing and translation functions"
```

---

## Task 8: Add MCP Cleaning Functions

**Files:**
- Modify: `src/agents_sync/mcp.py`

**Step 1: Add cleaning functions**

Append to `mcp.py`:

```python
def clean_mcp_servers(platform: Platform, dry_run: bool = False) -> int:
    """
    Remove MCP servers from a platform's config.

    Returns:
        Number of servers removed
    """
    mcp_paths = get_mcp_paths(platform)
    removed_count = 0

    # Count existing servers first
    existing_servers = read_mcp_servers(platform)
    removed_count = len(existing_servers)

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
```

**Step 2: Commit**

```bash
git add src/agents_sync/mcp.py
git commit -m "feat: add MCP cleaning function"
```

---

## Task 9: Update Core Module for MCP

**Files:**
- Modify: `src/agents_sync/core.py`

**Step 1: Add MCP import**

Add to imports at top of file:

```python
from .mcp import read_claude_mcp_servers, read_mcp_servers, write_mcp_servers, clean_mcp_servers
```

**Step 2: Update sync_skills to sync MCP**

Modify `sync_skills` function - add after skills sync loop (around line 165), before the return:

```python
    # Sync MCP servers
    master_mcp = all_skills_info.get("mcpServers", {})
    if master_mcp:
        for fork_platform in fork_platforms:
            if not dry_run:
                write_mcp_servers(fork_platform, master_mcp)
            results["synced_to"][fork_platform.value + "_mcp"] = len(master_mcp)
```

**Step 3: Commit**

```bash
git add src/agents_sync/core.py
git commit -m "feat: integrate MCP sync into core module"
```

---

## Task 10: Update CLI Scan Command

**Files:**
- Modify: `src/agents_sync/cli.py`

**Step 1: Add MCP import**

Add to imports:

```python
from .mcp import read_claude_mcp_servers, clean_mcp_servers
```

**Step 2: Update scan command to include MCP**

Modify the `scan` function. After saving skills_info (around line 163), add MCP scanning:

```python
    # Scan MCP servers (only for Claude Code as master)
    mcp_servers = {}
    mcp_sources = []
    if scan_platform == Platform.CLAUDE_CODE:
        mcp_servers, mcp_sources = read_claude_mcp_servers()

    # Save combined info
    combined_info = {
        "skills": skills_info,
        "mcpServers": mcp_servers
    }
    save_skills_info(platform_key, combined_info)
```

Update the display section to show MCP servers:

```python
    # Display MCP servers
    if mcp_servers:
        console.print(f"\n[bold cyan]MCP Servers ({len(mcp_servers)}):[/bold cyan]")
        for source in mcp_sources:
            console.print(f"  • {source}")
```

**Step 3: Commit**

```bash
git add src/agents_sync/cli.py
git commit -m "feat: add MCP scanning to scan command"
```

---

## Task 11: Update CLI Clean Command

**Files:**
- Modify: `src/agents_sync/cli.py`

**Step 1: Update clean command to include MCP**

In the `clean` function, after each `clean_skills` call, add MCP cleaning. For the fork loop (around line 206):

```python
            mcp_deleted = clean_mcp_servers(platform, dry_run=dry_run)
            if dry_run:
                console.print(f"[yellow]Would delete {deleted} skill(s), {mcp_deleted} MCP server(s)[/yellow]")
            else:
                console.print(f"[green]Deleted {deleted} skill(s), {mcp_deleted} MCP server(s)[/green]")
```

And for master clean (around line 224):

```python
    mcp_deleted = clean_mcp_servers(platform, dry_run=dry_run)

    if dry_run:
        console.print(f"[yellow]Would delete {deleted} skill(s), {mcp_deleted} MCP server(s)[/yellow]")
    else:
        console.print(f"[green]Deleted {deleted} skill(s), {mcp_deleted} MCP server(s)[/green]")
```

**Step 2: Commit**

```bash
git add src/agents_sync/cli.py
git commit -m "feat: add MCP cleaning to clean command"
```

---

## Task 12: Update CLI Sync Command

**Files:**
- Modify: `src/agents_sync/cli.py`

**Step 1: Add MCP sync import**

Add to imports:

```python
from .mcp import write_mcp_servers
```

**Step 2: Update sync command display**

In the `sync` function, update the results display to show MCP sync status. After line 268, add:

```python
    # Display MCP sync results
    mcp_count = results.get('mcp_synced', 0)
    if mcp_count > 0:
        console.print(f"\n[bold cyan]MCP Servers Synced:[/bold cyan] {mcp_count}")
```

**Step 3: Commit**

```bash
git add src/agents_sync/cli.py
git commit -m "feat: add MCP sync display to sync command"
```

---

## Task 13: Update Core Sync to Return MCP Count

**Files:**
- Modify: `src/agents_sync/core.py`

**Step 1: Update sync_skills return value**

Add to the results dict before return:

```python
    results["mcp_synced"] = len(master_mcp) if master_mcp else 0
```

**Step 2: Commit**

```bash
git add src/agents_sync/core.py
git commit -m "feat: return MCP count from sync function"
```

---

## Task 14: Update Config Load/Save for New Structure

**Files:**
- Modify: `src/agents_sync/config.py`

**Step 1: Update save_skills_info for combined structure**

The function already handles dict values, but update the docstring:

```python
def save_skills_info(platform_key: str, info: dict):
    """
    Save skills and MCP information for a platform.

    Args:
        platform_key: The platform key
        info: Dictionary with 'skills' list and optional 'mcpServers' dict
    """
```

**Step 2: Commit**

```bash
git add src/agents_sync/config.py
git commit -m "docs: update config docstring for combined info structure"
```

---

## Task 15: Update README

**Files:**
- Modify: `README.md`

**Step 1: Update README with new name and MCP features**

Replace the entire README content with updated documentation reflecting:
- New name: agents-sync
- New commands: `agents` (with `skills` as alias)
- MCP sync feature documentation
- Updated installation commands

Key sections to update:
- Title and description
- Features list (add MCP sync)
- Installation commands (git URL)
- Usage examples
- Platform table (add MCP paths)

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for agents-sync rebrand and MCP features"
```

---

## Task 16: Update CLI App Description

**Files:**
- Modify: `src/agents_sync/cli.py`

**Step 1: Update app help text**

Change line 17:

```python
app = typer.Typer(help="Agents Sync - Sync agent skills and MCP servers across platforms")
```

**Step 2: Commit**

```bash
git add src/agents_sync/cli.py
git commit -m "docs: update CLI help text for agents-sync"
```

---

## Task 17: Final Integration Test

**Step 1: Install package locally**

```bash
uv pip install -e .
```

**Step 2: Test commands**

```bash
agents --help
agents platforms
agents config
agents scan
agents sync --dry-run
agents clean fork --dry-run
```

**Step 3: Verify aliases work**

```bash
skills --help
agents-sync --help
skills-sync --help
```

**Step 4: Commit any fixes if needed**

---

## Task 18: Final Commit

**Step 1: Verify all changes**

```bash
git status
git diff --stat HEAD~15
```

**Step 2: Tag release**

```bash
git tag -a v0.2.0 -m "Release v0.2.0: Rebrand to agents-sync, add MCP sync"
```
