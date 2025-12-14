"""Pretty-print scheduler tasks and schedule items using rich formatting."""

import asyncio
import sys
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.text import Text

from playout_lib.video import PrerecordedVideo

from .video import PrerecordedVideo

# Add parent directory to path for module imports when run as script
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from playout_lib.items import Graphic, localtime
    from playout_lib.scheduler import Scheduler
else:
    from .items import Graphic, localtime
    from .scheduler import Scheduler


def create_schedule_tasks_table(scheduler: Scheduler, title: str = "Scheduler Tasks") -> Table:
    """
    Create a rich Table displaying scheduler tasks and their associated items.

    Args:
        scheduler: The Scheduler instance with loaded schedule
        title: Title for the table

    Returns:
        A formatted rich Table object
    """
    table = Table(title=title, expand=True, show_lines=True)

    # Add columns with appropriate styling
    table.add_column("Type", style="magenta", no_wrap=True, width=10)
    table.add_column("Status", style="cyan", no_wrap=True, width=12)
    table.add_column("Start Time", style="green", no_wrap=True, width=19)
    table.add_column("End Time", style="yellow", no_wrap=True, width=19)
    table.add_column("Time Until", style="blue", no_wrap=True, width=12)
    table.add_column("Details", style="white", width=40)

    now = localtime()

    for item in scheduler.schedule:
        # Determine item type
        if isinstance(item, PrerecordedVideo):
            item_type = "Video"
            details = f"ID: {item.video_id}, File: {getattr(item, 'filename', 'N/A')}"
        elif isinstance(item, Graphic):
            item_type = "Graphic"
            details = f"URL: {item.url}"
        else:
            item_type = "Unknown"
            details = str(item)

        # Determine status
        if item.already_done():
            status = Text("Done", style="dim")
            time_until = "-"
        elif now >= item.start_time:
            status = Text("Playing", style="bold green")
            seconds_left = (item.end_time - now).total_seconds()
            time_until = f"-{int(seconds_left)}s left"
        else:
            status = Text("Pending", style="yellow")
            seconds_until = (item.start_time - now).total_seconds()
            time_until = f"+{int(seconds_until)}s"

        # Format datetime
        start_str = item.start_time.strftime("%Y-%m-%d %H:%M:%S")
        end_str = item.end_time.strftime("%Y-%m-%d %H:%M:%S")

        # Truncate details if too long
        details_text = Text(details[:80], overflow="fold")

        table.add_row(
            item_type,
            status,
            start_str,
            end_str,
            time_until,
            details_text,
        )

    return table


if __name__ == "__main__":
    from playout_lib.api import load_schedule
    from playout_lib.config import API_URL

    console = Console()
    logger.info("Starting scheduler task viewer")

    async def main():
        scheduler = Scheduler()

        try:
            # Load schedule once to display
            scheduler.schedule = await load_schedule(API_URL)
            scheduler.last_refreshed = localtime()

            console.print("\n[bold cyan]Schedule Overview[/bold cyan]\n")
            table = create_schedule_tasks_table(scheduler, title="Current Schedule")
            console.print(table)

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise

    asyncio.run(main())
