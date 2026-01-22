# Agents Sync

A simple Python CLI tool for syncing agent skills and MCP servers across different platforms. No overengineering, just straightforward file copying and config merging.

## Philosophy

**Global Skills Only**: This tool only manages global skills stored in platform-specific directories (e.g., `~/.claude/skills`, `~/.cursor/skills`). These are your personal, cross-project skills that you want available everywhere.

**Repo-Specific Skills**: Skills that are synced to git repositories (project-specific skills) should be manually handpicked and managed by you, not automated by any tool. These belong in your project's version control and should be intentionally selected and maintained.

**MCP Server Sync**: MCP servers are read from Claude Code (global `~/.claude.json` and plugin `.mcp.json` files) and synced to other platforms with automatic format translation.

**Transparency Through Explicit Commands**: Each command does one thing. There are no "do everything" commands that combine multiple operations. You run commands one by one (`scan`, `clean`, `sync`, `backup`, `restore`) so you know exactly what each step does. This way, you understand what happened by typing each command explicitly, rather than having one command that does multiple things behind the scenes.

## Features

### Skills
- **Configure** master and fork platforms
- **Scan** skills in master platform
- **Clean** skills from master or fork platforms (including Claude Code plugins)
- **Sync** skills from master to all fork platforms (hard copy, no symlinks)
- **Backup** master skills to `~/.config/agents-sync/backups/` (includes path information)
- **Restore** skills from backups with interactive selection

### MCP Servers
- **Scan** MCP servers from Claude Code (global + plugin configs)
- **Clean** MCP servers from master or fork platforms
- **Sync** MCP servers to fork platforms with automatic format translation
- Supports different config formats (JSON, TOML) across platforms

## Supported Platforms

| Platform | Skills Path | MCP Config |
|----------|-------------|------------|
| Claude Code | `~/.claude/skills` + plugins | `~/.claude.json` + plugin `.mcp.json` |
| OpenCode | `~/.opencode/skill` | `~/.config/opencode/opencode.json` |
| Codex | `~/.codex/skills` | `~/.codex/config.toml` |
| Cursor | `~/.cursor/skills` | `~/.cursor/mcp.json` |
| Windsurf | `~/.windsurf/skills` | `~/.codeium/windsurf/mcp_config.json` |

## Installation

### Install from Git (Recommended)

Using `uv tool install` to install globally from the git repository:

```bash
uv tool install git+https://github.com/keejkrej/agents-sync.git
```

After installation, use the `agents` command directly:

```bash
agents config
```

**Note**: This installs the tool globally and makes the `agents` and `agents-sync` commands available system-wide.

### Local Installation (Development)

Using `uv` (editable mode - picks up code changes automatically):

```bash
uv pip install -e .
```

After installation, use the `agents` command directly:

```bash
agents config
```

**Note**: Editable mode means you don't need to reinstall when you make code changes - just use `agents` directly!

### Using uvx (Run without installing)

Run directly from git without installing:

```bash
uvx --from git+https://github.com/keejkrej/agents-sync.git agents config
```

Or use the full command name:

```bash
uvx --from git+https://github.com/keejkrej/agents-sync.git agents-sync config
```

Use `--refresh` to pick up code changes:

```bash
uvx --refresh --from git+https://github.com/keejkrej/agents-sync.git agents config
```

**Note**: `uvx` caches packages, so use `--refresh` flag when you make code changes, or clear cache with `uv cache clean` (but this deletes all cached packages).

### Using pip

```bash
pip install git+https://github.com/keejkrej/agents-sync.git
```

Or for editable installation:

```bash
pip install -e .
```

## Usage

### Configure master and fork platforms

```bash
agents config
```

This will prompt you to select:
- Master platform (source of truth)
- Fork platforms (destinations for syncing)

Configuration is saved to `~/.config/agents-sync/config.json`.

### Scan skills and MCP servers

```bash
agents scan
```

Scans the master platform and displays:
- All found skills (saved to `agents_info.json`)
- All MCP servers (from global config and plugin `.mcp.json` files)

**Important**: If you add new skills to the master platform, you must run `agents scan` first before syncing, so the new skills are discovered and included in the sync operation.

You can also scan a specific platform:

```bash
agents scan --platform cursor
```

### Clean skills and MCP servers

Delete all skills and MCP servers from master:

```bash
agents clean master
```

Delete all skills and MCP servers from all fork platforms:

```bash
agents clean fork
```

**Important**:
- This only affects **global skills** in platform directories (e.g., `~/.claude/skills`, `~/.cursor/skills`)
- **Repo-specific skills** (in git repositories) are never touched by this tool
- For Claude Code, this also cleans skills from plugin directories (`~/.claude/plugins/.../skills`)
- MCP servers are removed from config files (the mcpServers/mcp section is deleted)
- The command will show you exactly what will be deleted before proceeding

Use `--dry-run` to preview what would be deleted without actually deleting:

```bash
agents clean master --dry-run
```

### Sync skills and MCP servers

Copy all skills and MCP servers from master to all configured fork platforms:

```bash
agents sync
```

This will:
- Copy all skills from master to each fork platform (hard copy, no symlinks)
- Sync MCP servers to fork platforms with automatic format translation
- Existing skills in fork platforms will be overwritten

**Important**: Sync only syncs what has been scanned. If you add new skills to the master platform, you must run `agents scan` first to discover the new skills, then run `agents sync` to sync them.

**Explicit workflow** (recommended for transparency):
1. Scan to discover skills and MCP servers: `agents scan` (required if master has new skills)
2. Clean forks explicitly: `agents clean fork`
3. Then sync: `agents sync`

Or use `--dry-run` to preview what sync would do:

```bash
agents sync --dry-run
```

### Backup skills

Backup all skills from master platform:

```bash
agents backup
```

Backups are saved to `~/.config/agents-sync/backups/` with timestamps. Each backup includes:
- All skill files and directories
- `agents_info.json` with platform, timestamp, and path information for restoration

You can also backup a specific platform:

```bash
agents backup --platform cursor
```

Use `--dry-run` to preview what would be backed up:

```bash
agents backup --dry-run
```

### Restore skills

Restore skills from a previous backup:

```bash
agents restore
```

This will:
1. List all available backups in an interactive checklist
2. Show platform, timestamp, and skill count for each backup
3. Prompt you to select a backup to restore
4. Restore skills to their original locations (using path information from `agents_info.json`)

Use `--dry-run` to preview what would be restored:

```bash
agents restore --dry-run
```

**Note**: Restore uses the `agents_info.json` file saved with each backup to restore skills to the correct locations, including Claude Code plugin directories.

### List platforms

View all available platforms and their paths:

```bash
agents platforms
```

## Notes

- **Global skills only**: This tool only manages skills in platform directories (e.g., `~/.claude/skills`). Repo-specific skills synced to git should be manually managed
- **MCP server sync**: MCP servers are read from Claude Code and translated to target platform formats automatically
- **Explicit commands**: Each command does one thing. Run them one by one (`scan`, `clean`, `sync`, `backup`, `restore`) to understand exactly what each step does
- **Scan before sync**: Sync only syncs what has been scanned. If you add new skills to master, run `agents scan` first, then `agents sync`
- All file operations use **hard copies** (no symlinks)
- Backups are timestamped and stored in `~/.config/agents-sync/backups/`
- Each backup includes `agents_info.json` with path information for accurate restoration
- Clean operations handle Claude Code plugin directories recursively
- Restore automatically matches paths, with fallback logic for plugin directories
