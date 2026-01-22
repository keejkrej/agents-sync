# Agents-Sync Rebrand & MCP Sync Design

## Overview

Rebrand `skills-sync` to `agents-sync` and add MCP (Model Context Protocol) server configuration syncing alongside existing skills syncing.

## Architecture

### Master/Fork Model

Same unified master/fork architecture for both skills and MCP:
- One platform is **master** (source of truth)
- Other platforms are **forks** (sync destinations)
- Single `config` command configures both skills and MCP syncing

### Data Flow

```
scan → saves Claude format to info.json
sync → translates Claude format → target platform format, full overwrite
clean → removes skills AND MCP entries from targets
```

## MCP Configuration Locations

| Platform | File | Key | Format |
|----------|------|-----|--------|
| Claude Code | `~/.claude.json` | `mcpServers` | JSON |
| Claude Code | `.mcp.json` per plugin | `mcpServers` | JSON |
| Codex | `~/.codex/config.toml` | `[mcp_servers.*]` | TOML |
| OpenCode | `~/.config/opencode/opencode.json` | `mcp` | JSON |
| Cursor | `~/.cursor/mcp.json` | `mcpServers` | JSON |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | `mcpServers` | JSON |

## Config Directory

Changed from `~/.config/skills-sync/` to `~/.config/agents-sync/`

### Updated info.json Structure

```json
{
  "claude-code": {
    "skills": [
      {"name": "my-skill", "path": "/home/user/.claude/skills/my-skill"}
    ],
    "mcpServers": {
      "github": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_TOKEN": "..."}
      }
    }
  }
}
```

## Scanning

### Claude Code MCP Sources

1. `~/.claude.json` → top-level `mcpServers` object (global)
2. `~/.claude/plugins/cache/**/.mcp.json` → each plugin's `mcpServers`

### Merge Strategy

- Combine all servers into one flat `mcpServers` object
- If same server name exists in multiple places, global (`~/.claude.json`) wins
- Log which servers came from which source for transparency

## Sync Translation

### Claude → Cursor/Windsurf (direct copy)

```json
{"mcpServers": {...}}  →  {"mcpServers": {...}}
```

### Claude → OpenCode

```json
// From Claude
{"mcpServers": {
  "github": {"type": "stdio", "command": "npx", "args": ["arg1"], "env": {"KEY": "val"}}
}}

// To OpenCode
{"mcp": {
  "github": {"type": "local", "command": ["npx", "arg1"], "environment": {"KEY": "val"}, "enabled": true}
}}
```

### Claude → Codex

```json
// From Claude
{"mcpServers": {
  "github": {"type": "stdio", "command": "npx", "args": ["arg1"], "env": {"KEY": "val"}}
}}
```

```toml
# To Codex
[mcp_servers.github]
command = "npx"
args = ["arg1"]
env = { KEY = "val" }
```

## Cleaning

### Behavior Per Platform

| Platform | Action |
|----------|--------|
| Claude Code | Remove `mcpServers` from `~/.claude.json`, delete `.mcp.json` from plugins |
| Cursor | Remove `mcpServers` section from `~/.cursor/mcp.json` |
| Windsurf | Remove `mcpServers` section from `mcp_config.json` |
| OpenCode | Remove `mcp` section from `opencode.json` |
| Codex | Remove all `[mcp_servers.*]` sections from `config.toml` |

### Preservation Rule

For files with mixed content (OpenCode, Codex), only remove MCP sections and preserve all other settings.

## File Changes

### Rename Operations

- `src/skills_sync/` → `src/agents_sync/`
- `pyproject.toml`: package name `agents-sync`, entry points `agents`, `agents-sync` (keep `skills` alias)
- `README.md`: update name and document MCP features
- Config dir: `~/.config/skills-sync/` → `~/.config/agents-sync/`

### Modified Files

| File | Changes |
|------|---------|
| `config.py` | Change config dir, update info structure for `mcpServers` |
| `platforms.py` | Add `get_mcp_paths()` function |
| `core.py` | Add `scan_mcp_servers()`, `clean_mcp_servers()`, `sync_mcp_servers()` |
| `cli.py` | Update `scan`, `clean`, `sync` to handle MCP alongside skills |

### New Module

| File | Purpose |
|------|---------|
| `mcp.py` | MCP reading/writing, format translation functions |

### New Dependencies

- `tomli` (Python 3.8-3.10) / `tomllib` (3.11+) for reading TOML
- `tomli_w` for writing TOML
