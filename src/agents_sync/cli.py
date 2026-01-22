"""CLI interface using Typer."""

import typer
import json
from typing import Optional, List
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
import inquirer

from .config import load_config, save_config, Config, save_skills_info, load_skills_info, BACKUP_DIR
from .platforms import Platform, get_all_platforms, get_platform_display_name, get_platform_paths
from .core import scan_skills, clean_skills, sync_skills, backup_skills, list_backups, restore_skills
from .mcp import read_claude_mcp_servers, clean_mcp_servers

app = typer.Typer(help="Skills Sync - Sync agent skills across platforms")
console = Console()


def display_platforms():
    """Display available platforms in a table."""
    table = Table(title="Available Platforms")
    table.add_column("Key", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Paths", style="yellow")
    
    platforms = get_all_platforms()
    for key, platform in platforms.items():
        paths = get_platform_paths(platform)
        path_str = "\n".join([str(p) for p in paths if p.exists()])
        if not path_str:
            path_str = "\n".join([str(p) for p in paths])
        table.add_row(key, get_platform_display_name(platform), path_str)
    
    console.print(table)


def select_forks_checklist(platforms: dict, master_key: str, current_forks: List[str]) -> List[str]:
    """Interactive checklist for selecting fork platforms."""
    available_keys = [k for k in platforms.keys() if k != master_key]
    
    if not available_keys:
        return []
    
    # Create checklist options with display names
    choices = []
    for key in available_keys:
        platform_name = get_platform_display_name(platforms[key])
        choices.append((f"{key} - {platform_name}", key))
    
    # Use inquirer checkbox
    questions = [
        inquirer.Checkbox(
            'forks',
            message="Select fork platforms (use space to toggle, enter to confirm)",
            choices=choices,
            default=[k for k in current_forks if k in available_keys],
        ),
    ]
    
    answers = inquirer.prompt(questions)
    
    if answers and 'forks' in answers:
        return answers['forks']
    return []


def select_master_checklist(platforms: dict, current_master: Optional[str]) -> str:
    """Interactive checklist for selecting master platform."""
    # Create list options with display names
    choices = []
    for key in platforms.keys():
        platform_name = get_platform_display_name(platforms[key])
        choices.append((f"{key} - {platform_name}", key))
    
    # Use inquirer list for single selection
    questions = [
        inquirer.List(
            'master',
            message="Select master platform",
            choices=choices,
            default=current_master or choices[0][1] if choices else None,
        ),
    ]
    
    answers = inquirer.prompt(questions)
    
    if answers and 'master' in answers:
        return answers['master']
    return current_master or list(platforms.keys())[0]


@app.command()
def config():
    """Configure master and fork platforms."""
    config = load_config()
    platforms = get_all_platforms()
    
    console.print("\n[bold cyan]Current Configuration:[/bold cyan]")
    console.print(f"Master: {config.master or 'Not set'}")
    console.print(f"Forks: {', '.join(config.forks) if config.forks else 'None'}")
    
    console.print("\n[bold cyan]Available Platforms:[/bold cyan]")
    display_platforms()
    
    # Select master using checklist
    master_key = select_master_checklist(platforms, config.master)
    
    # Select forks using checklist
    fork_keys = select_forks_checklist(platforms, master_key, config.forks)
    
    # Validate all keys
    invalid_keys = [k for k in [master_key] + fork_keys if k not in platforms]
    if invalid_keys:
        console.print(f"[bold red]Error: Invalid platform keys: {', '.join(invalid_keys)}[/bold red]")
        raise typer.Exit(1)
    
    config.master = master_key
    config.forks = fork_keys
    
    save_config(config)
    
    console.print("\n[bold green]Configuration saved![/bold green]")
    console.print(f"Master: {master_key}")
    console.print(f"Forks: {', '.join(fork_keys) if fork_keys else 'None'}")


@app.command()
def scan(
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform to scan (defaults to master)")
):
    """Scan skills in the master platform's skill folder."""
    platforms = get_all_platforms()
    
    if platform:
        if platform not in platforms:
            console.print(f"[bold red]Error: Invalid platform '{platform}'[/bold red]")
            raise typer.Exit(1)
        scan_platform = platforms[platform]
        platform_key = platform
    else:
        config = load_config()
        if not config.master:
            console.print("[bold red]Error: No master platform configured. Run 'skills config' first.[/bold red]")
            raise typer.Exit(1)
        scan_platform = platforms[config.master]
        platform_key = config.master
    
    console.print(f"\n[bold cyan]Scanning {get_platform_display_name(scan_platform)}...[/bold cyan]")
    
    skills = scan_skills(scan_platform)
    
    # Prepare skills info for saving
    skills_info = []
    for skill in skills:
        skills_info.append({
            "name": skill.name,
            "path": str(skill)
        })
    
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

    if not skills and not mcp_servers:
        console.print("[yellow]No skills or MCP servers found.[/yellow]")
        console.print(f"[dim]Info saved to config directory.[/dim]")
        return

    # Display skills
    if skills:
        table = Table(title=f"Found {len(skills)} skill(s)")
        table.add_column("Skill Name", style="cyan")
        table.add_column("Path", style="yellow")

        for skill in skills:
            table.add_row(skill.name, str(skill))

        console.print(table)

    # Display MCP servers
    if mcp_servers:
        console.print(f"\n[bold cyan]MCP Servers ({len(mcp_servers)}):[/bold cyan]")
        for source in mcp_sources:
            console.print(f"  • {source}")

    console.print(f"\n[dim]Info saved to config directory.[/dim]")


@app.command()
def clean(
    target: str = typer.Argument(..., help="'master' or 'fork'"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted without actually deleting")
):
    """Clean all skills from master or fork platforms."""
    config = load_config()
    platforms = get_all_platforms()
    
    if target == "master":
        if not config.master:
            console.print("[bold red]Error: No master platform configured. Run 'skills config' first.[/bold red]")
            raise typer.Exit(1)
        platform = platforms[config.master]
        platform_name = get_platform_display_name(platform)
    elif target == "fork":
        if not config.forks:
            console.print("[bold red]Error: No fork platforms configured. Run 'skills config' first.[/bold red]")
            raise typer.Exit(1)
        # Clean all forks
        for fork_key in config.forks:
            platform = platforms[fork_key]
            platform_name = get_platform_display_name(platform)
            console.print(f"\n[bold cyan]Cleaning {platform_name}...[/bold cyan]")
            deleted = clean_skills(platform, dry_run=dry_run)
            mcp_deleted = clean_mcp_servers(platform, dry_run=dry_run)
            if dry_run:
                console.print(f"[yellow]Would delete {deleted} skill(s), {mcp_deleted} MCP server(s)[/yellow]")
            else:
                console.print(f"[green]Deleted {deleted} skill(s), {mcp_deleted} MCP server(s)[/green]")
        return
    else:
        console.print(f"[bold red]Error: Target must be 'master' or 'fork', got '{target}'[/bold red]")
        raise typer.Exit(1)
    
    console.print(f"\n[bold cyan]Cleaning {platform_name}...[/bold cyan]")
    
    if not dry_run:
        if not Confirm.ask(f"Are you sure you want to delete all skills from {platform_name}?"):
            console.print("[yellow]Cancelled.[/yellow]")
            return
    
    deleted = clean_skills(platform, dry_run=dry_run)
    mcp_deleted = clean_mcp_servers(platform, dry_run=dry_run)

    if dry_run:
        console.print(f"[yellow]Would delete {deleted} skill(s), {mcp_deleted} MCP server(s)[/yellow]")
    else:
        console.print(f"[green]Deleted {deleted} skill(s), {mcp_deleted} MCP server(s)[/green]")


@app.command()
def sync(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without actually syncing")
):
    """Sync skills from master to all fork platforms."""
    config = load_config()
    platforms = get_all_platforms()
    
    if not config.master:
        console.print("[bold red]Error: No master platform configured. Run 'skills config' first.[/bold red]")
        raise typer.Exit(1)
    
    if not config.forks:
        console.print("[bold red]Error: No fork platforms configured. Run 'skills config' first.[/bold red]")
        raise typer.Exit(1)
    
    master_platform = platforms[config.master]
    fork_platforms = [platforms[key] for key in config.forks]
    
    console.print(f"\n[bold cyan]Syncing from {get_platform_display_name(master_platform)}...[/bold cyan]")
    
    results = sync_skills(master_platform, fork_platforms, config.master, dry_run=dry_run)
    
    # Check for error message
    if "error" in results:
        console.print(f"[bold red]Error: {results['error']}[/bold red]")
        raise typer.Exit(1)
    
    console.print(f"\n[bold green]Master Skills:[/bold green] {results['master_skills']}")
    console.print("\n[bold cyan]Synced to:[/bold cyan]")
    
    for fork_key, count in results['synced_to'].items():
        fork_name = get_platform_display_name(platforms[fork_key])
        if dry_run:
            console.print(f"  {fork_name}: [yellow]Would sync {count} skill(s)[/yellow]")
        else:
            console.print(f"  {fork_name}: [green]{count} skill(s) synced[/green]")


@app.command()
def backup(
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform to backup (defaults to master)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be backed up without actually backing up")
):
    """Backup all skills from master platform."""
    platforms = get_all_platforms()
    
    if platform:
        if platform not in platforms:
            console.print(f"[bold red]Error: Invalid platform '{platform}'[/bold red]")
            raise typer.Exit(1)
        backup_platform = platforms[platform]
    else:
        config = load_config()
        if not config.master:
            console.print("[bold red]Error: No master platform configured. Run 'skills config' first.[/bold red]")
            raise typer.Exit(1)
        backup_platform = platforms[config.master]
    
    console.print(f"\n[bold cyan]Backing up {get_platform_display_name(backup_platform)}...[/bold cyan]")
    
    backup_path = backup_skills(backup_platform, dry_run=dry_run)
    
    if dry_run:
        console.print(f"[yellow]Would backup to: {backup_path}[/yellow]")
    else:
        console.print(f"[green]Backup created at: {backup_path}[/green]")


@app.command()
def info():
    """Display current master-fork config and existing skills information."""
    config = load_config()
    platforms = get_all_platforms()
    skills_info = load_skills_info()
    
    # Display configuration
    console.print("\n[bold cyan]Configuration:[/bold cyan]")
    console.print(f"Master: {config.master or '[yellow]Not set[/yellow]'}")
    if config.forks:
        console.print(f"Forks: {', '.join(config.forks)}")
    else:
        console.print("Forks: [yellow]None[/yellow]")
    
    # Display skills information
    console.print("\n[bold cyan]Skills Information:[/bold cyan]")
    
    # Show master skills
    if config.master:
        master_platform = platforms.get(config.master)
        if master_platform:
            master_skills = skills_info.get(config.master, [])
            if master_skills:
                console.print(f"\n[bold green]Master ({get_platform_display_name(master_platform)}):[/bold green]")
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Skill Name", style="cyan")
                table.add_column("Path", style="yellow")
                for skill in master_skills:
                    table.add_row(skill["name"], skill["path"])
                console.print(table)
            else:
                console.print(f"\n[bold green]Master ({get_platform_display_name(master_platform)}):[/bold green] [yellow]No skills scanned[/yellow]")
    
    # Show fork skills
    if config.forks:
        console.print(f"\n[bold green]Forks:[/bold green]")
        for fork_key in config.forks:
            fork_platform = platforms.get(fork_key)
            if fork_platform:
                fork_skills = skills_info.get(fork_key, [])
                platform_name = get_platform_display_name(fork_platform)
                if fork_skills:
                    console.print(f"\n  [bold]{platform_name}:[/bold] {len(fork_skills)} skill(s)")
                    for skill in fork_skills:
                        console.print(f"    • {skill['name']}")
                else:
                    console.print(f"\n  [bold]{platform_name}:[/bold] [yellow]No skills scanned[/yellow]")
    
    if not config.master and not config.forks:
        console.print("\n[yellow]No configuration set. Run 'skills config' to configure master and forks.[/yellow]")


@app.command()
def platforms():
    """List all available platforms and their paths."""
    display_platforms()


def select_backup_checklist(backups: List[Path]) -> Optional[Path]:
    """Interactive checklist for selecting a backup to restore."""
    if not backups:
        return None
    
    # Create list options with display names
    choices = []
    for backup_path in backups:
        # Parse backup info to get platform and timestamp
        info_file = backup_path / "skills_info.json"
        if info_file.exists():
            try:
                with open(info_file, 'r') as f:
                    info = json.load(f)
                    platform = info.get("platform", "unknown")
                    timestamp = info.get("timestamp", "")
                    skill_count = len(info.get("skills", []))
                    
                    # Format timestamp for display
                    if timestamp:
                        try:
                            dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            time_str = timestamp
                    else:
                        time_str = backup_path.name
                    
                    display_name = f"{platform} - {time_str} ({skill_count} skills)"
                    choices.append((display_name, backup_path))
            except:
                # Fallback if we can't read the info file
                choices.append((backup_path.name, backup_path))
        else:
            choices.append((backup_path.name, backup_path))
    
    if not choices:
        return None
    
    # Use inquirer list for single selection
    questions = [
        inquirer.List(
            'backup',
            message="Select backup to restore",
            choices=choices,
        ),
    ]
    
    answers = inquirer.prompt(questions)
    
    if answers and 'backup' in answers:
        return answers['backup']
    return None


@app.command()
def restore(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be restored without actually restoring")
):
    """Restore skills from a backup."""
    # List all backups
    backups = list_backups()
    
    if not backups:
        console.print("[bold red]No backups found.[/bold red]")
        console.print(f"[dim]Backups are stored in: {BACKUP_DIR}[/dim]")
        raise typer.Exit(1)
    
    console.print(f"\n[bold cyan]Found {len(backups)} backup(s)[/bold cyan]")
    
    # Let user select a backup
    selected_backup = select_backup_checklist(backups)
    
    if not selected_backup:
        console.print("[yellow]No backup selected.[/yellow]")
        return
    
    console.print(f"\n[bold cyan]Restoring from backup: {selected_backup.name}[/bold cyan]")
    
    # Load backup info to show what will be restored
    info_file = selected_backup / "skills_info.json"
    skill_count = 0
    platform_name = "Unknown"
    
    if info_file.exists():
        with open(info_file, 'r') as f:
            backup_info = json.load(f)
            platform_key = backup_info.get("platform", "unknown")
            skill_count = len(backup_info.get("skills", []))
            
            platforms = get_all_platforms()
            if platform_key in platforms:
                platform_name = get_platform_display_name(platforms[platform_key])
                console.print(f"Platform: {platform_name}")
                console.print(f"Skills: {skill_count}")
    
    if not dry_run:
        if not Confirm.ask(f"Are you sure you want to restore {skill_count} skill(s) to {platform_name}?"):
            console.print("[yellow]Cancelled.[/yellow]")
            return
    
    # Restore skills
    try:
        results = restore_skills(selected_backup, dry_run=dry_run)
        
        if dry_run:
            console.print(f"\n[yellow]Would restore {results['restored']} skill(s) from {results['total']} total[/yellow]")
        else:
            console.print(f"\n[green]Restored {results['restored']} skill(s) from {results['total']} total[/green]")
            
            if results['errors']:
                console.print("\n[bold red]Errors:[/bold red]")
                for error in results['errors']:
                    console.print(f"  [red]• {error}[/red]")
    except Exception as e:
        console.print(f"[bold red]Error restoring backup: {str(e)}[/bold red]")
        raise typer.Exit(1)


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    app()
