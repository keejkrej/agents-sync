"""Core functionality for scanning, cleaning, syncing, and backing up skills."""

import shutil
import json
from pathlib import Path
from typing import List, Set, Optional
from datetime import datetime

from .platforms import Platform, get_platform_paths, get_all_platforms
from .config import BACKUP_DIR, ensure_config_dir, load_agents_info, save_agents_info, AGENTS_INFO_FILE
from .mcp import write_mcp_servers


def scan_skills(platform: Platform) -> List[Path]:
    """
    Scan for skills in the master platform's skill folders.
    Skills are identified as directories containing SKILL.md files.
    
    Args:
        platform: The platform to scan
        
    Returns:
        List of skill paths (directories containing SKILL.md)
    """
    skill_paths = get_platform_paths(platform)
    skills = []
    seen_skills = set()  # Track by absolute path to avoid duplicates
    
    for skill_dir in skill_paths:
        if skill_dir.exists() and skill_dir.is_dir():
            # For Claude Code, search recursively for SKILL.md files
            if platform == Platform.CLAUDE_CODE:
                for skill_md in skill_dir.rglob("SKILL.md"):
                    skill_path = skill_md.parent
                    abs_path = skill_path.resolve()
                    if abs_path not in seen_skills:
                        skills.append(skill_path)
                        seen_skills.add(abs_path)
            else:
                # For other platforms, check direct subdirectories
                for item in skill_dir.iterdir():
                    if item.is_dir():
                        # Check if it contains SKILL.md or is a skill directory
                        skill_md = item / "SKILL.md"
                        if skill_md.exists() or item.is_dir():
                            abs_path = item.resolve()
                            if abs_path not in seen_skills:
                                skills.append(item)
                                seen_skills.add(abs_path)
    
    return skills


def clean_skills(platform: Platform, dry_run: bool = False) -> int:
    """
    Delete all skills from a platform.
    For Claude Code, this includes skills in plugin directories.
    
    Args:
        platform: The platform to clean
        dry_run: If True, only show what would be deleted
        
    Returns:
        Number of skills deleted
    """
    skill_paths = get_platform_paths(platform)
    deleted_count = 0
    seen_skills = set()  # Track by absolute path to avoid duplicates
    
    for skill_dir in skill_paths:
        if skill_dir.exists() and skill_dir.is_dir():
            if platform == Platform.CLAUDE_CODE:
                # For Claude Code, recursively find all SKILL.md files and delete their parent directories
                for skill_md in skill_dir.rglob("SKILL.md"):
                    skill_path = skill_md.parent
                    abs_path = skill_path.resolve()
                    if abs_path not in seen_skills:
                        if not dry_run:
                            shutil.rmtree(skill_path)
                        deleted_count += 1
                        seen_skills.add(abs_path)
            else:
                # For other platforms, delete direct subdirectories
                for item in skill_dir.iterdir():
                    if item.is_dir():
                        abs_path = item.resolve()
                        if abs_path not in seen_skills:
                            if not dry_run:
                                shutil.rmtree(item)
                            deleted_count += 1
                            seen_skills.add(abs_path)
    
    return deleted_count


def sync_skills(master_platform: Platform, fork_platforms: List[Platform], master_platform_key: str, dry_run: bool = False) -> dict:
    """
    Copy skills from master to all fork platforms.
    Uses agents_info.json to determine which skills to sync (only syncs what has been scanned).
    
    Args:
        master_platform: The master platform to copy from
        fork_platforms: List of fork platforms to copy to
        master_platform_key: The platform key (e.g., "claude-code", "cursor") for loading skills_info
        dry_run: If True, only show what would be synced
        
    Returns:
        Dictionary with sync results
    """
    # Load skills info from saved scan results
    if not AGENTS_INFO_FILE.exists():
        return {"master_skills": 0, "synced_to": {}, "error": "No scan data found. Run 'agents scan' first."}

    all_info = load_agents_info()
    platform_info = all_info.get(master_platform_key, {})

    # Handle both new format (dict with 'skills' key) and old format (list of skills)
    if isinstance(platform_info, dict):
        master_skills_info = platform_info.get("skills", [])
        master_mcp_servers = platform_info.get("mcpServers", {})
    else:
        master_skills_info = platform_info  # Old format compatibility
        master_mcp_servers = {}

    if not master_skills_info:
        return {"master_skills": 0, "synced_to": {}, "error": f"No skills found for platform '{master_platform_key}'. Run 'agents scan' first."}

    # Convert path strings back to Path objects
    master_skills = [Path(skill_info["path"]) for skill_info in master_skills_info if "path" in skill_info]

    if not master_skills:
        return {"master_skills": 0, "synced_to": {}, "error": f"No valid skill paths found for platform '{master_platform_key}'. Run 'agents scan' first."}
    
    # Get master skill paths (the parent directories)
    master_paths = get_platform_paths(master_platform)
    
    results = {
        "master_skills": len(master_skills),
        "synced_to": {}
    }
    
    for fork_platform in fork_platforms:
        fork_paths = get_platform_paths(fork_platform)
        synced_count = 0
        
        # Use the first available fork path (or create it)
        if fork_paths:
            fork_dir = fork_paths[0]
            fork_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy each skill from master to fork (overwrites existing)
            for master_skill in master_skills:
                # Determine relative path from master skill directory
                relative_path = None
                for master_path in master_paths:
                    try:
                        relative_path = master_skill.relative_to(master_path)
                        break
                    except ValueError:
                        continue
                
                if relative_path:
                    fork_skill_path = fork_dir / relative_path
                    
                    if not dry_run:
                        # Remove existing skill if it exists, then copy
                        if fork_skill_path.exists():
                            shutil.rmtree(fork_skill_path)
                        # Hard copy the entire directory tree
                        shutil.copytree(master_skill, fork_skill_path)
                    synced_count += 1
        
        results["synced_to"][fork_platform.value] = synced_count

    # Sync MCP servers
    if master_mcp_servers:
        for fork_platform in fork_platforms:
            if not dry_run:
                write_mcp_servers(fork_platform, master_mcp_servers)

    results["mcp_synced"] = len(master_mcp_servers)

    return results


def backup_skills(platform: Platform, dry_run: bool = False) -> Path:
    """
    Backup all skills from master platform to backup directory.
    Also saves agents_info.json to the backup directory.
    
    Args:
        platform: The platform to backup
        dry_run: If True, only show what would be backed up
        
    Returns:
        Path to the backup directory
    """
    ensure_config_dir()
    
    # Create timestamped backup directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{platform.value}_{timestamp}"
    
    if not dry_run:
        backup_path.mkdir(parents=True, exist_ok=True)
    
    master_skills = scan_skills(platform)
    master_paths = get_platform_paths(platform)
    
    # Prepare skills info for backup
    skills_info = []
    for skill in master_skills:
        # Determine relative path from master skill directory
        relative_path = None
        for master_path in master_paths:
            try:
                relative_path = skill.relative_to(master_path)
                break
            except ValueError:
                continue
        
        if relative_path:
            skills_info.append({
                "name": skill.name,
                "path": str(skill),
                "relative_path": str(relative_path),
                "master_path": str(master_path)
            })
    
    if not dry_run:
        # Save agents_info.json to backup directory
        backup_info_file = backup_path / "agents_info.json"
        with open(backup_info_file, 'w') as f:
            json.dump({
                "platform": platform.value,
                "timestamp": timestamp,
                "skills": skills_info
            }, f, indent=2)
        
        # Copy skills
        for master_skill in master_skills:
            # Determine relative path from master skill directory
            relative_path = None
            for master_path in master_paths:
                try:
                    relative_path = master_skill.relative_to(master_path)
                    break
                except ValueError:
                    continue
            
            if relative_path:
                backup_skill_path = backup_path / relative_path
                # Hard copy the entire directory tree
                shutil.copytree(master_skill, backup_skill_path, dirs_exist_ok=True)
    
    return backup_path


def list_backups(platform: Optional[Platform] = None) -> List[Path]:
    """
    List all available backup directories.
    
    Args:
        platform: Optional platform to filter backups by
        
    Returns:
        List of backup directory paths, sorted by creation time (newest first)
    """
    ensure_config_dir()
    
    if not BACKUP_DIR.exists():
        return []
    
    backups = []
    for backup_path in BACKUP_DIR.iterdir():
        if backup_path.is_dir():
            # Check if it's a valid backup (has agents_info.json)
            info_file = backup_path / "agents_info.json"
            if info_file.exists():
                # Filter by platform if specified
                if platform:
                    backup_platform = backup_path.name.split('_')[0]
                    if backup_platform == platform.value:
                        backups.append(backup_path)
                else:
                    backups.append(backup_path)
    
    # Sort by modification time (newest first)
    backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return backups


def restore_skills(backup_path: Path, dry_run: bool = False) -> dict:
    """
    Restore skills from a backup directory.
    Uses agents_info.json to restore skills to their original locations.
    
    Args:
        backup_path: Path to the backup directory
        dry_run: If True, only show what would be restored
        
    Returns:
        Dictionary with restore results
    """
    info_file = backup_path / "agents_info.json"
    
    if not info_file.exists():
        raise ValueError(f"Backup directory {backup_path} does not contain agents_info.json")
    
    # Load backup info
    with open(info_file, 'r') as f:
        backup_info = json.load(f)
    
    platform_key = backup_info.get("platform")
    skills_info = backup_info.get("skills", [])
    
    if not platform_key:
        raise ValueError("Backup info does not contain platform information")
    
    # Get platform enum
    all_platforms = get_all_platforms()
    if platform_key not in all_platforms:
        raise ValueError(f"Unknown platform in backup: {platform_key}")
    
    platform = all_platforms[platform_key]
    platform_paths = get_platform_paths(platform)
    
    restored_count = 0
    errors = []
    
    for skill_info in skills_info:
            skill_name = skill_info.get("name")
            relative_path_str = skill_info.get("relative_path")
            master_path_str = skill_info.get("master_path")
            
            if not relative_path_str:
                errors.append(f"Skill {skill_name}: Missing relative_path in backup info")
                continue
            
            # Find the matching master path
            master_path = None
            
            # First, try exact match (resolve paths to handle ~ expansion)
            master_path_resolved = Path(master_path_str).expanduser().resolve() if master_path_str else None
            for mp in platform_paths:
                mp_resolved = mp.expanduser().resolve()
                if mp_resolved == master_path_resolved:
                    master_path = mp
                    break
            
            # If no exact match, try to find a path with similar structure
            if not master_path and master_path_str:
                # For Claude Code, try to match plugin paths more flexibly
                if platform == Platform.CLAUDE_CODE:
                    # Check if the original path was under plugins
                    if 'plugins' in master_path_str:
                        # Find any plugins path
                        for mp in platform_paths:
                            if 'plugins' in str(mp):
                                master_path = mp
                                break
                
                # If still no match, use the first available path
                # This works for non-plugin paths where structure is consistent
                if not master_path and platform_paths:
                    master_path = platform_paths[0]
            elif not master_path and platform_paths:
                # Fallback: use first available path
                master_path = platform_paths[0]
            
            if not master_path:
                errors.append(f"Skill {skill_name}: Could not determine restore location")
                continue
            
            # Check if backup file exists
            backup_skill_path = backup_path / relative_path_str
            if not backup_skill_path.exists():
                errors.append(f"Skill {skill_name}: Backup file not found at {backup_skill_path}")
                continue
            
            # Count as would-be-restored (for dry_run) or actually restore
            if dry_run:
                restored_count += 1
            else:
                # Ensure master path exists
                master_path.mkdir(parents=True, exist_ok=True)
                
                # Restore skill
                restore_skill_path = master_path / relative_path_str
                
                try:
                    # Remove existing skill if it exists
                    if restore_skill_path.exists():
                        shutil.rmtree(restore_skill_path)
                    
                    # Copy skill from backup
                    shutil.copytree(backup_skill_path, restore_skill_path)
                    restored_count += 1
                except Exception as e:
                    errors.append(f"Skill {skill_name}: Failed to restore - {str(e)}")
    
    return {
        "restored": restored_count,
        "total": len(skills_info),
        "errors": errors,
        "platform": platform_key
    }
