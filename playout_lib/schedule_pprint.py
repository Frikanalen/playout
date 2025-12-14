"""Pretty-print schedule items using rich formatting."""

import asyncio

from frikanalen_django_api_client import Client
from frikanalen_django_api_client.models import ScheduleitemRead
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .schedule_api import ScheduleFetcher


def create_schedule_table(items: list[ScheduleitemRead], title: str = "Schedule Items") -> Table:
    """
    Create a rich Table displaying a list of ScheduleitemReads.

    Args:
        items: List of ScheduleitemRead objects to display
        title: Title for the table

    Returns:
        A formatted rich Table object
    """
    table = Table(title=title, expand=True, show_lines=True)

    # Add columns with appropriate styling
    table.add_column("ID", style="cyan", no_wrap=True, width=6)
    table.add_column("Video ID", style="blue", no_wrap=True, width=8)
    table.add_column("Start Time", style="green", no_wrap=True, width=19)
    table.add_column("End Time", style="yellow", no_wrap=True, width=19)
    table.add_column("Video Title", style="bold white", width=30)
    table.add_column("Organization", style="cyan", width=20)

    for item in items:
        # Format datetime
        start_str = item.starttime.strftime("%Y-%m-%d %H:%M:%S")
        end_str = item.endtime.strftime("%Y-%m-%d %H:%M:%S")

        # Get video details
        video = item.video
        video_title = Text(video.name, overflow="fold")
        org_name = Text(video.organization.name, overflow="fold")

        table.add_row(
            str(item.id),
            str(video.id),
            start_str,
            end_str,
            video_title,
            org_name,
        )

    return table


if __name__ == "__main__":
    logger.info("Starting schedule fetcher")
    console = Console()

    client = Client("https://frikanalen.no/")
    fetcher = ScheduleFetcher(client)

    async def main():
        # Fetch today's schedule
        try:
            async with client:
                schedule_items = await fetcher.get_schedule(date="today", days=1, surrounding=True)

                if not schedule_items:
                    console.print("[yellow]No schedule items found.[/yellow]")
                else:
                    console.print(f"[green]Retrieved {len(schedule_items)} schedule items[/green]")
                    table = create_schedule_table(schedule_items, title="Today's Schedule")
                    console.print(table)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise

    asyncio.run(main())
