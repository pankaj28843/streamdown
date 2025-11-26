"""Main CLI entry point."""

import asyncio
import logging
from pathlib import Path
from typing import Annotated

import typer

from streamdown.application.dtos import DownloadOptions, DownloadResult
from streamdown.application.use_cases import start_download
from streamdown.cli.progress_display import ProgressDisplay
from streamdown.domain.enums import DownloadStatus, StreamingMode
from streamdown.infrastructure.logging import configure_logging

app = typer.Typer(
    name="streamdown",
    help="Modern asyncio HTTP(S) downloader with smart chunked streaming",
    add_completion=False,
)


def parse_piece_size(size_str: str) -> int:
    """
    Parse piece size with K/M suffix support.

    Examples:
        "1024" -> 1024
        "1K" -> 1024
        "1M" -> 1048576
        "512k" -> 524288

    Args:
        size_str: Size string with optional K/M suffix

    Returns:
        Size in bytes

    Raises:
        ValueError: If size string is invalid
    """
    size_str = size_str.strip().upper()

    if size_str.endswith("K"):
        return int(size_str[:-1]) * 1024
    elif size_str.endswith("M"):
        return int(size_str[:-1]) * 1024 * 1024
    else:
        return int(size_str)


@app.command()
def download(
    urls: Annotated[
        list[str],
        typer.Argument(
            help="URLs to download",
            metavar="URL",
        ),
    ],
    directory: Annotated[
        Path,
        typer.Option(
            "-d",
            "--dir",
            help="Download directory",
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = Path.cwd(),
    output_name: Annotated[
        str | None,
        typer.Option(
            "-o",
            "--out",
            help="Output filename (single URL only)",
        ),
    ] = None,
    splits: Annotated[
        int,
        typer.Option(
            "-s",
            "--splits",
            help="Parallel chunks per download",
            min=1,
            max=128,
        ),
    ] = 8,
    max_connections_per_host: Annotated[
        int,
        typer.Option(
            "-x",
            "--max-connections-per-host",
            help="Max connections per host",
            min=1,
            max=128,
        ),
    ] = 8,
    piece_size: Annotated[
        str,
        typer.Option(
            "-k",
            "--piece-size",
            help="Chunk size (supports K, M suffixes)",
        ),
    ] = "1M",
    continue_download: Annotated[
        bool,
        typer.Option(
            "-c/-C",
            "--continue/--no-continue",
            help="Resume from existing .part file",
        ),
    ] = True,
    allow_overwrite: Annotated[
        bool,
        typer.Option(
            "--allow-overwrite/--no-overwrite",
            help="Allow overwriting complete files",
        ),
    ] = False,
    auto_file_renaming: Annotated[
        bool,
        typer.Option(
            "--auto-file-renaming/--no-auto-file-renaming",
            help="Auto-append .1, .2 to avoid conflicts",
        ),
    ] = False,
    max_concurrent_downloads: Annotated[
        int,
        typer.Option(
            "-j",
            "--max-concurrent-downloads",
            help="Concurrent downloads",
            min=1,
            max=32,
        ),
    ] = 4,
    streaming_mode: Annotated[
        str,
        typer.Option(
            "--streaming-mode",
            help="Chunk selection strategy",
            case_sensitive=False,
        ),
    ] = "default",
    connect_timeout: Annotated[
        float,
        typer.Option(
            "--connect-timeout",
            help="Connection timeout (seconds)",
            min=0.1,
        ),
    ] = 60.0,
    read_timeout: Annotated[
        float,
        typer.Option(
            "--read-timeout",
            help="Read timeout (seconds)",
            min=0.1,
        ),
    ] = 300.0,
    max_tries: Annotated[
        int,
        typer.Option(
            "-m",
            "--max-tries",
            help="Max retry attempts",
            min=1,
            max=100,
        ),
    ] = 5,
    retry_wait: Annotated[
        float,
        typer.Option(
            "--retry-wait",
            help="Wait between retries (seconds)",
            min=0.0,
        ),
    ] = 0.0,
    user_agent: Annotated[
        str,
        typer.Option(
            "--user-agent",
            help="HTTP User-Agent header",
        ),
    ] = "streamdown/0.1.0",
    quiet: Annotated[
        bool,
        typer.Option(
            "-q",
            "--quiet",
            help="Suppress progress bars",
        ),
    ] = False,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            help="Logging level",
            case_sensitive=False,
        ),
    ] = "info",
    insecure: Annotated[
        bool,
        typer.Option(
            "--insecure",
            help="Disable HTTPS certificate validation",
        ),
    ] = False,
    no_netrc: Annotated[
        bool,
        typer.Option(
            "-n",
            "--no-netrc",
            help="Disable netrc authentication",
        ),
    ] = False,
    netrc_path: Annotated[
        Path | None,
        typer.Option(
            "--netrc-path",
            help="Custom netrc file path (default: ~/.netrc)",
            exists=False,
            file_okay=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ] = None,
) -> None:
    """
    Download files from HTTP(S) URLs with parallel connections.

    Examples:

        # Simple download
        streamdown https://example.com/file.zip

        # Custom output location
        streamdown -d ~/Downloads -o video.mp4 https://example.com/video.mp4

        # High-speed download with many connections
        streamdown -s 16 -x 16 https://example.com/large-file.iso

        # Video streaming mode
        streamdown --streaming-mode inorder https://example.com/movie.mp4

        # Multiple files
        streamdown -j 2 https://example.com/file1.zip https://example.com/file2.zip

    Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
    """
    # Validate option combinations
    if output_name and len(urls) > 1:
        typer.echo(
            "Error: -o/--out can only be used with a single URL",
            err=True,
        )
        raise typer.Exit(code=2)

    # Validate max_connections_per_host <= splits
    if max_connections_per_host > splits:
        typer.echo(
            f"Error: max-connections-per-host ({max_connections_per_host}) "
            f"cannot exceed splits ({splits})",
            err=True,
        )
        raise typer.Exit(code=2)

    # Parse piece size
    try:
        piece_size_bytes = parse_piece_size(piece_size)
    except (ValueError, IndexError) as e:
        typer.echo(
            f"Error: Invalid piece size '{piece_size}': {e}",
            err=True,
        )
        raise typer.Exit(code=2)

    # Parse streaming mode
    try:
        streaming_mode_enum = StreamingMode.from_string(streaming_mode)
    except ValueError as e:
        typer.echo(
            f"Error: {e}",
            err=True,
        )
        raise typer.Exit(code=2)

    # Validate log level
    valid_log_levels = ["debug", "info", "warn", "error"]
    if log_level.lower() not in valid_log_levels:
        typer.echo(
            f"Error: Invalid log level '{log_level}'. "
            f"Valid levels: {', '.join(valid_log_levels)}",
            err=True,
        )
        raise typer.Exit(code=2)

    # Create download options
    options = DownloadOptions(
        directory=directory,
        output_name=output_name,
        splits=splits,
        max_connections_per_host=max_connections_per_host,
        piece_size=piece_size_bytes,
        continue_download=continue_download,
        allow_overwrite=allow_overwrite,
        auto_file_renaming=auto_file_renaming,
        max_concurrent_downloads=max_concurrent_downloads,
        streaming_mode=streaming_mode_enum,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        max_tries=max_tries,
        retry_wait=retry_wait,
        user_agent=user_agent,
        quiet=quiet,
        log_level=log_level.lower(),
        insecure=insecure,
        no_netrc=no_netrc,
        netrc_path=netrc_path,
    )

    # Configure logging before any operations
    configure_logging(log_level.lower())
    logger = logging.getLogger("streamdown")

    # Show warning for insecure mode
    if insecure:
        logger.warning(
            "HTTPS certificate validation disabled. "
            "This is insecure and should only be used for testing."
        )

    # Log download start
    logger.info(f"Starting download of {len(urls)} URL(s)")
    logger.debug(f"Options: splits={splits}, piece_size={piece_size}, streaming_mode={streaming_mode}")

    # Execute downloads with progress display
    try:
        with ProgressDisplay(quiet=quiet) as progress:
            results = asyncio.run(start_download(urls, options, progress))

        # Display individual results if not quiet
        if not quiet:
            for result in results:
                if result.status == DownloadStatus.FAILED and result.error:
                    # Errors are already shown by progress display
                    pass

        # Determine exit code
        failed_count = sum(1 for r in results if r.status == DownloadStatus.FAILED)
        if failed_count > 0:
            raise typer.Exit(code=1)

    except typer.Exit:
        # Re-raise typer.Exit without catching it
        raise
    except KeyboardInterrupt:
        typer.echo("\nDownload cancelled by user", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        import traceback
        typer.echo(f"\nFatal error: {e}", err=True)
        typer.echo(f"\nTraceback:", err=True)
        traceback.print_exc()
        raise typer.Exit(code=3)


def _display_result(result: DownloadResult) -> None:
    """Display a single download result."""
    status_symbol = "✓" if result.status == DownloadStatus.COMPLETED else "✗"
    status_color = typer.colors.GREEN if result.status == DownloadStatus.COMPLETED else typer.colors.RED

    typer.secho(f"{status_symbol} {result.url}", fg=status_color)

    if result.status == DownloadStatus.COMPLETED and result.final_path:
        typer.echo(f"  → {result.final_path}")
        if result.bytes_downloaded > 0:
            size_mb = result.bytes_downloaded / (1024 * 1024)
            typer.echo(f"  → {size_mb:.2f} MB in {result.duration:.1f}s")
    elif result.error:
        typer.echo(f"  → Error: {result.error}")


def main() -> None:
    """Main entry point for the streamdown CLI."""
    # Ensure we have a clean event loop for async operations
    # This is needed when installed via uv tool or similar package managers
    try:
        loop = asyncio.get_running_loop()
        # If we're already in an event loop, something is wrong
        # Close it and create a new one
        loop.close()
    except RuntimeError:
        # No running loop, which is expected
        pass
    
    # Create and set a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        app()
    finally:
        # Clean up the event loop
        try:
            loop.close()
        except:
            pass


if __name__ == "__main__":
    main()
