# Skills Sync

A simple Python CLI tool for syncing agent skills across different platforms. No overengineering, just straightforward file copying.

## Philosophy

**Global Skills Only**: This tool only manages global skills stored in platform-specific directories (e.g., `~/.claude/skills`, `~/.cursor/skills`). These are your personal, cross-project skills that you want available everywhere.

**Repo-Specific Skills**: Skills that are synced to git repositories (project-specific skills) should be manually handpicked and managed by you, not automated by any tool. These belong in your project's version control and should be intentionally selected and maintained.

**Transparency Through Explicit Commands**: Each command does one thing. There are no "do everything" commands that combine multiple operations. You run commands one by one (`scan`, `clean`, `sync`, `backup`, `restore`) so you know exactly what each step does. This way, you understand what happened by typing each command explicitly, rather than having one command that does multiple things behind the scenes.

## Features

- **Configure** master and fork platforms
- **Scan** skills in master platform
- **Clean** skills from master or fork platforms (including Claude Code plugins)
- **Sync** skills from master to all fork platforms (hard copy, no symlinks)
- **Backup** master skills to `~/.config/skills-sync/backups/` (includes path information)
- **Restore** skills from backups with interactive selection

## Supported Platforms

- **Claude Code**: `~/.claude/skills` and `~/.claude/plugins/marketplaces/.../skills`
- **OpenCode**: `~/.opencode/skill`
- **Codex**: `~/.codex/skills`
- **Cursor**: `~/.cursor/skills`
- **Windsurf**: `~/.windsurf/skills`

## Installation

### Install from Git (Recommended)

Using `uv tool install` to install globally from the git repository:

```bash
uv tool install git+https://github.com/keejkrej/skills-sync.git
```

After installation, use the `skills` command directly:

```bash
skills config
```

**Note**: This installs the tool globally and makes the `skills` and `skills-sync` commands available system-wide.

### Local Installation (Development)

Using `uv` (editable mode - picks up code changes automatically):

```bash
uv pip install -e .
```

After installation, use the `skills` command directly:

```bash
skills config
```

**Note**: Editable mode means you don't need to reinstall when you make code changes - just use `skills` directly!

### Using uvx (Run without installing)

Run directly from git without installing:

```bash
uvx --from git+https://github.com/keejkrej/skills-sync.git skills config
```

Or use the full command name:

```bash
uvx --from git+https://github.com/keejkrej/skills-sync.git skills-sync config
```

Use `--refresh` to pick up code changes:

```bash
uvx --refresh --from git+https://github.com/keejkrej/skills-sync.git skills config
```

**Note**: `uvx` caches packages, so use `--refresh` flag when you make code changes, or clear cache with `uv cache clean` (but this deletes all cached packages).

### Using pip

```bash
pip install git+https://github.com/keejkrej/skills-sync.git
```

Or for editable installation:

```bash
pip install -e .
```

## Usage

### Configure master and fork platforms

```bash
skills config
```

This will prompt you to select:
- Master platform (source of truth)
- Fork platforms (destinations for syncing)

Configuration is saved to `~/.config/skills-sync/config.json`.

### Scan skills

```bash
skills scan
```

Scans the master platform's skill folder and displays all found skills. This saves the skills information to `skills_info.json`, which is used by the sync command.

**Important**: If you add new skills to the master platform, you must run `skills scan` first before syncing, so the new skills are discovered and included in the sync operation.

You can also scan a specific platform:

```bash
skills scan --platform cursor
```

### Clean skills

Delete all skills from master:

```bash
skills clean master
```

Delete all skills from all fork platforms:

```bash
skills clean fork
```

**Important**: 
- This only affects **global skills** in platform directories (e.g., `~/.claude/skills`, `~/.cursor/skills`)
- **Repo-specific skills** (in git repositories) are never touched by this tool
- For Claude Code, this also cleans skills from plugin directories (`~/.claude/plugins/.../skills`)
- The command will show you exactly what will be deleted before proceeding

Use `--dry-run` to preview what would be deleted without actually deleting:

```bash
skills clean master --dry-run
```

### Sync skills

Copy all skills from master to all configured fork platforms:

```bash
skills sync
```

This will copy all skills from master to each fork platform (hard copy, no symlinks). Existing skills in fork platforms will be overwritten.

**Important**: Sync only syncs what has been scanned. If you add new skills to the master platform, you must run `skills scan` first to discover the new skills, then run `skills sync` to sync them.

**Explicit workflow** (recommended for transparency):
1. Scan to discover skills: `skills scan` (required if master has new skills)
2. Clean forks explicitly: `skills clean fork`
3. Then sync: `skills sync`

Or use `--dry-run` to preview what sync would do:

```bash
skills sync --dry-run
```

### Backup skills

Backup all skills from master platform:

```bash
skills backup
```

Backups are saved to `~/.config/skills-sync/backups/` with timestamps. Each backup includes:
- All skill files and directories
- `skills_info.json` with platform, timestamp, and path information for restoration

You can also backup a specific platform:

```bash
skills backup --platform cursor
```

Use `--dry-run` to preview what would be backed up:

```bash
skills backup --dry-run
```

### Restore skills

Restore skills from a previous backup:

```bash
skills restore
```

This will:
1. List all available backups in an interactive checklist
2. Show platform, timestamp, and skill count for each backup
3. Prompt you to select a backup to restore
4. Restore skills to their original locations (using path information from `skills_info.json`)

Use `--dry-run` to preview what would be restored:

```bash
skills restore --dry-run
```

**Note**: Restore uses the `skills_info.json` file saved with each backup to restore skills to the correct locations, including Claude Code plugin directories.

### List platforms

View all available platforms and their paths:

```bash
skills platforms
```

## Notes

- **Global skills only**: This tool only manages skills in platform directories (e.g., `~/.claude/skills`). Repo-specific skills synced to git should be manually managed
- **Explicit commands**: Each command does one thing. Run them one by one (`scan`, `clean`, `sync`, `backup`, `restore`) to understand exactly what each step does
- **Scan before sync**: Sync only syncs what has been scanned. If you add new skills to master, run `skills scan` first, then `skills sync`
- All file operations use **hard copies** (no symlinks)
- Backups are timestamped and stored in `~/.config/skills-sync/backups/`
- Each backup includes `skills_info.json` with path information for accurate restoration
- Clean operations handle Claude Code plugin directories recursively
- Restore automatically matches paths, with fallback logic for plugin directories
