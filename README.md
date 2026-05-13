# Streamdown

A modern asyncio-based HTTP(S) downloader with intelligent multi-connection downloads and streaming-optimized chunk selection. Built with pure Python 3.11+, Streamdown enables video playback before complete download and provides robust resume capabilities with a beautiful terminal interface.

## Features

- **Multi-connection parallel downloads** - Split files into chunks and download simultaneously
- **Smart chunk planning** - Prioritize early file segments for streaming video playback
- **Robust resume capabilities** - Automatically resume interrupted downloads with metadata validation
- **Rich terminal interface** - Real-time progress bars with speed and ETA
- **Responsive display** - Automatically adapts to narrow terminals and mobile devices
- **Pure Python implementation** - No C extensions required, works with uv and modern Python tooling
- **Configurable retry logic** - Automatic retry with exponential backoff for transient failures
- **Multiple download modes** - Queue and download multiple files concurrently
- **Streaming modes** - Choose between default, inorder, or geometric chunk selection strategies

## Mobile and Narrow Terminal Support

Streamdown automatically detects your terminal width and adapts the display for optimal readability on narrow screens, including mobile terminal emulators like Termux, iSH, or SSH sessions on phones.

### Adaptive Display Behavior

The progress display intelligently adjusts based on terminal width:

**Wide Terminal (≥80 columns):**
```
Writing.With.Fire.2021.1080p.WEBRip.x264.AAC-[YTS.MX].mp4 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 99.8% • 1.7/68.2 GB • 0:00 • downloading
```

**Narrow Terminal (<80 columns):**
```
Writing...YTS.MX].mp4 ━━━━━━━━━━ 99.8% • 1.7GB • downloading
```

### What Changes on Narrow Terminals

When Streamdown detects a terminal width less than 80 columns, it automatically:

- **Truncates long filenames** while preserving file extensions (e.g., `Writing...YTS.MX].mp4`)
- **Scales progress bar width** proportionally to available space (minimum 10 characters)
- **Prioritizes essential information**: filename, percentage, and status always visible
- **Compacts size display**: Shows `1.7GB` instead of `1.7 GB / 68.2 GB`
- **Omits URLs** from progress lines (shown only in initial log message)
- **Removes optional details**: ETA and detailed speed metrics hidden when space is limited

### Mobile Terminal Emulators

Streamdown works great on mobile devices with terminal emulators:

- **Termux** (Android) - Full support with automatic width detection
- **a-Shell** (iOS) - Use the `python3 -m streamdown` form if the console script is not on `PATH`
- **iSH** (iOS) - Adapts to small screen sizes
- **SSH clients** (iOS/Android) - Responsive display for remote sessions
- **Blink Shell** (iOS) - Works seamlessly with adaptive layout

Simply run Streamdown as you would on desktop - the display automatically adapts to your screen size.

### Testing Terminal Width

You can test the responsive display by resizing your terminal window. Streamdown detects the width on each update and adjusts the layout in real-time.

## Requirements

- Python 3.11 or higher

## Installation

### Using uv (Recommended)

```bash
uv tool install streamdown
```

### Using pip

```bash
pip install streamdown
```

### Latest `main` from GitHub zip archive

For a clean reinstall in a-Shell and similar iOS terminal apps, install directly from the `main` branch zip archive. Run these commands one at a time; avoid pasting them as one wrapped line.

```bash
python3 -m pip uninstall -y streamdown
```

```bash
python3 -m pip install --user --upgrade --no-cache-dir --progress-bar off "https://github.com/pankaj28843/streamdown/archive/refs/heads/main.zip"
```

```bash
python3 -m streamdown --help
```

`--progress-bar off` avoids pip's Rich/live progress renderer, which can be unstable in some iOS terminal environments.

Streamdown refreshes live progress at most every 30 seconds by default on manual-refresh terminals. If a-Shell is still unstable, increase the interval before running downloads:

```bash
export STREAMDOWN_PROGRESS_REFRESH_INTERVAL=120
python3 -m streamdown URL
```

If a-Shell fails while preparing metadata from the source zip, install the prebuilt wheel checked in on `main` instead:

```bash
python3 -m pip install --user --upgrade --force-reinstall --no-cache-dir --progress-bar off "https://raw.githubusercontent.com/pankaj28843/streamdown/main/dist/streamdown-0.1.0-py3-none-any.whl"
```

If your shell exposes pip-installed scripts on `PATH`, this should also work after install:

```bash
streamdown --help
```

### From Source

```bash
git clone https://github.com/yourusername/streamdown.git
cd streamdown
uv pip install -e .
```

## Usage

### Basic Usage

Download a single file:

```bash
streamdown https://example.com/file.zip
```

Download to a specific directory:

```bash
streamdown -d ~/Downloads https://example.com/file.zip
```

Download with a custom filename:

```bash
streamdown -o myfile.zip https://example.com/file.zip
```

### Advanced Usage

#### High-Speed Downloads

Use more parallel connections for faster downloads:

```bash
streamdown -s 16 -x 16 https://example.com/large-file.iso
```

- `-s 16`: Split file into 16 chunks
- `-x 16`: Allow up to 16 concurrent connections per host

#### Video Streaming Mode

Download videos with prioritized early chunks for immediate playback:

```bash
streamdown --streaming-mode inorder https://example.com/movie.mp4
```

Streaming modes:
- `default`: Round-robin chunk selection (balanced)
- `inorder`: Sequential from beginning (best for video streaming)
- `geom`: Geometric spacing (dense at start, exponential gaps)

#### Multiple Files

Download multiple files concurrently:

```bash
streamdown -j 2 https://example.com/file1.zip https://example.com/file2.zip
```

The `-j` flag controls how many downloads run simultaneously.

#### Resume Downloads

Resume is enabled by default. To disable:

```bash
streamdown --no-continue https://example.com/file.zip
```

To force overwrite existing files:

```bash
streamdown --allow-overwrite https://example.com/file.zip
```

To auto-rename files if they exist:

```bash
streamdown --auto-file-renaming https://example.com/file.zip
```

#### Custom Chunk Size

Adjust chunk size for your network conditions:

```bash
streamdown -k 512K https://example.com/file.zip  # 512 KiB chunks
streamdown -k 5M https://example.com/file.zip    # 5 MiB chunks
```

#### Retry Configuration

Configure retry behavior for unreliable connections:

```bash
streamdown -m 10 --retry-wait 2.0 https://example.com/file.zip
```

- `-m 10`: Retry up to 10 times
- `--retry-wait 2.0`: Wait 2 seconds between retries

#### Timeout Configuration

Adjust timeouts for slow or fast connections:

```bash
streamdown --connect-timeout 30 --read-timeout 600 https://example.com/file.zip
```

#### Quiet Mode

Suppress progress bars and only show final results:

```bash
streamdown -q https://example.com/file.zip
```

#### Debug Logging

Enable debug logging for troubleshooting:

```bash
streamdown --log-level debug https://example.com/file.zip
```

#### Authentication with netrc

Streamdown supports automatic HTTP Basic Authentication using netrc credentials. By default, it reads credentials from `~/.netrc` (or `~/_netrc` on Windows).

**Example netrc file format:**

```
machine example.com
login myusername
password mypassword

machine downloads.example.org
login user@example.com
password secret123
```

**Security Note**: The netrc file must have permissions set to 600 (read/write for owner only) on Unix systems. Streamdown will ignore the file and log a warning if permissions are too permissive.

Set permissions correctly:

```bash
chmod 600 ~/.netrc
```

**Using netrc:**

```bash
# Use default ~/.netrc file (enabled by default)
streamdown https://example.com/protected/file.zip

# Disable netrc authentication
streamdown --no-netrc https://example.com/protected/file.zip

# Use custom netrc file location
streamdown --netrc-path /path/to/custom-netrc https://example.com/protected/file.zip
```

**Behavior:**
- Netrc support is **enabled by default**
- If no netrc file exists, downloads proceed without authentication
- If netrc file has incorrect permissions (not 600), it is ignored with a warning
- If netrc file contains syntax errors, it is ignored with a warning
- Credentials are loaded at startup and applied to matching hosts automatically

## CLI Options

### Positional Arguments

- `URL` - One or more URLs to download

### Options

#### Output Options

- `-d, --dir PATH` - Download directory (default: current directory)
- `-o, --out NAME` - Output filename (single URL only)
- `--auto-file-renaming` - Auto-append .1, .2 to avoid conflicts (default: disabled)
- `--allow-overwrite` - Allow overwriting complete files (default: disabled)

#### Connection Options

- `-s, --splits N` - Parallel chunks per download (default: 8, range: 1-128)
- `-x, --max-connections-per-host N` - Max connections per host (default: 8, range: 1-128)
- `-j, --max-concurrent-downloads N` - Concurrent downloads (default: 4, range: 1-32)
- `-k, --piece-size SIZE` - Chunk size with K/M suffix (default: 1M)

#### Resume Options

- `-c, --continue` - Resume from existing .part file (default: enabled)
- `-C, --no-continue` - Disable resume and start fresh

#### Streaming Options

- `--streaming-mode MODE` - Chunk selection strategy: default, inorder, geom (default: default)

#### Retry Options

- `-m, --max-tries N` - Max retry attempts (default: 5, range: 1-100)
- `--retry-wait SECONDS` - Wait between retries (default: 0.0)

#### Timeout Options

- `--connect-timeout SECONDS` - Connection timeout (default: 60.0)
- `--read-timeout SECONDS` - Read timeout (default: 300.0)

#### Authentication Options

- `-n, --no-netrc` - Disable netrc authentication (default: netrc enabled)
- `--netrc-path PATH` - Custom netrc file path (default: ~/.netrc)

#### Other Options

- `--user-agent STRING` - HTTP User-Agent header (default: streamdown/0.1.0)
- `-q, --quiet` - Suppress progress bars
- `--log-level LEVEL` - Logging level: debug, info, warn, error (default: info)
- `--insecure` - Disable HTTPS certificate validation (not recommended)

## Common Scenarios

### Download a Large File Quickly

```bash
streamdown -s 16 -x 16 -k 2M https://example.com/ubuntu.iso
```

### Download Video for Immediate Playback

```bash
streamdown --streaming-mode inorder https://example.com/movie.mp4
```

While downloading, you can open the `.part` file in a video player to start watching immediately.

### Download Multiple Files with Limited Bandwidth

```bash
streamdown -j 1 -s 4 https://example.com/file1.zip https://example.com/file2.zip
```

### Resume After Network Interruption

```bash
streamdown https://example.com/large-file.zip
# ... network interruption ...
streamdown https://example.com/large-file.zip  # Automatically resumes
```

### Download from Unreliable Server

```bash
streamdown -m 20 --retry-wait 5.0 --read-timeout 120 https://slow-server.com/file.zip
```

### Download from Authenticated Server

Set up your `~/.netrc` file with credentials:

```bash
# Create netrc file
cat > ~/.netrc << 'EOF'
machine downloads.example.com
login myusername
password mypassword
EOF

# Set correct permissions (required)
chmod 600 ~/.netrc

# Download will automatically use credentials
streamdown https://downloads.example.com/protected/file.zip
```

## Troubleshooting

### Download Fails Immediately

**Problem**: Download fails with connection error

**Solutions**:
- Check your internet connection
- Verify the URL is accessible in a browser
- Try increasing `--connect-timeout`: `streamdown --connect-timeout 120 https://example.com/file.zip`
- Check if you need authentication (see Authentication section)

### Download Stalls or Times Out

**Problem**: Download starts but stops making progress

**Solutions**:
- Reduce the number of splits: `streamdown -s 4 https://example.com/file.zip`
- Increase read timeout: `streamdown --read-timeout 600 https://example.com/file.zip`
- Enable retry with wait: `streamdown -m 10 --retry-wait 2.0 https://example.com/file.zip`

### Resume Not Working

**Problem**: Download restarts from beginning instead of resuming

**Solutions**:
- Check if the server supports byte ranges (HEAD request shows `Accept-Ranges: bytes`)
- Verify the `.part.meta.json` file exists in the download directory
- The server may have changed the file (different ETag or Last-Modified), requiring a fresh download
- Try with `--log-level debug` to see why resume was rejected

### Authentication Failures

**Problem**: Download fails with 401 Unauthorized or 403 Forbidden

**Solutions**:
- Set up netrc file with correct credentials (see Authentication section)
- Verify netrc file permissions are 600: `ls -l ~/.netrc`
- Check credentials are correct for the host
- Enable debug logging to see if netrc is being loaded: `streamdown --log-level debug https://example.com/file.zip`
- If netrc file has wrong permissions, you'll see a warning in the logs
- If netrc file has syntax errors, you'll see a warning in the logs

### Certificate Validation Errors

**Problem**: HTTPS download fails with certificate error

**Solutions**:
- Update your system's CA certificates
- For testing only, use `--insecure` flag (not recommended for production)
- Check if you're behind a corporate proxy that intercepts HTTPS

### File Already Exists Error

**Problem**: Download fails because file already exists

**Solutions**:
- Use `--allow-overwrite` to replace the existing file
- Use `--auto-file-renaming` to create a new file with numeric suffix
- Manually delete or rename the existing file
- Use `-o` to specify a different output name

### Out of Disk Space

**Problem**: Download fails with disk write error

**Solutions**:
- Free up disk space
- Change download directory to a different drive: `streamdown -d /path/to/drive https://example.com/file.zip`
- Check available space before downloading large files

### Too Many Connections Error

**Problem**: Server rejects connections or rate limits

**Solutions**:
- Reduce splits: `streamdown -s 4 https://example.com/file.zip`
- Reduce max connections per host: `streamdown -x 4 https://example.com/file.zip`
- Add retry wait: `streamdown --retry-wait 1.0 https://example.com/file.zip`

### Memory Usage Too High

**Problem**: Streamdown uses too much memory

**Solutions**:
- Reduce concurrent downloads: `streamdown -j 2 https://example.com/file1.zip https://example.com/file2.zip`
- Reduce splits per download: `streamdown -s 4 https://example.com/file.zip`
- Memory usage should scale with connections, not file size (typically under 100 MiB)

### Corrupted Downloads

**Problem**: Downloaded file is corrupted or incomplete

**Solutions**:
- Delete the `.part` file and `.part.meta.json` file and retry
- Use `--no-continue` to force a fresh download
- Check server logs or try downloading with a browser to verify the file
- Enable debug logging: `streamdown --log-level debug https://example.com/file.zip`

### Progress Bar Not Showing

**Problem**: No progress bar displayed during download

**Solutions**:
- Check if you're using `-q` or `--quiet` flag
- Verify your terminal supports rich output
- Try without piping output to another command

### Display Wrapping or Garbled on Mobile

**Problem**: Progress display wraps or looks garbled on mobile terminal

**Solutions**:
- Streamdown automatically detects terminal width and adapts the display
- If detection fails, try resizing your terminal window
- Ensure your terminal emulator reports width correctly (most modern ones do)
- On very narrow terminals (<40 columns), some wrapping may still occur
- Use `-q` (quiet mode) for minimal output on extremely narrow screens

## Exit Codes

- `0` - All downloads completed successfully
- `1` - One or more downloads failed
- `2` - Invalid command-line arguments
- `3` - Fatal error (unexpected exception)

## Architecture

Streamdown follows Domain-Driven Design principles with clear separation of concerns:

- **Domain Layer**: Core business logic (entities, value objects, domain services)
- **Application Layer**: Use cases and orchestration
- **Infrastructure Layer**: HTTP client, file I/O, metadata persistence
- **Interface Layer**: CLI with typer and rich

The system uses Python 3.11+ structured concurrency with `asyncio.TaskGroup` for clean async patterns.

## Development

### Install Development Dependencies

```bash
uv pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=streamdown --cov-report=html
```

### Format and Lint

```bash
ruff format .
ruff check .
```

### Run Property-Based Tests

```bash
pytest tests/ -v -k "test_property"
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with [httpx](https://www.python-httpx.org/) for HTTP client
- Terminal UI powered by [rich](https://rich.readthedocs.io/)
- CLI framework using [typer](https://typer.tiangolo.com/)
- Async file I/O with [aiofiles](https://github.com/Tinche/aiofiles)
