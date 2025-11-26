# Requirements Document

## Introduction

Streamdown is a modern asyncio-based HTTP(S) downloader CLI tool written in pure Python 3.11+. It provides intelligent multi-connection downloads with smart chunk planning that prioritizes early file segments, enabling video playback before complete download. The tool offers robust resume capabilities and a rich terminal interface, serving as a focused alternative to aria2c for HTTP(S) downloads only.

## Glossary

- **Streamdown**: The download manager system being specified
- **Chunk**: A contiguous byte range of a file being downloaded
- **Part File**: A temporary file with .part extension containing partially downloaded data
- **Metadata File**: A JSON file with .part.meta.json extension storing download state and progress
- **Streaming Mode**: A chunk selection strategy that determines download order
- **Split**: A parallel connection downloading a portion of the file
- **Resume**: Continuing an interrupted download using existing partial data
- **ByteRange**: An HTTP range request specifying start and end byte positions

## Requirements

### Requirement 1

**User Story:** As a user, I want to download large files from HTTP(S) URLs using multiple parallel connections, so that I can maximize my bandwidth and reduce download time.

#### Acceptance Criteria

1. WHEN a user provides an HTTP(S) URL THEN Streamdown SHALL initiate a HEAD request to determine file size and range support
2. WHEN the server supports byte ranges THEN Streamdown SHALL split the file into chunks based on the specified split count and piece size
3. WHEN downloading with multiple splits THEN Streamdown SHALL maintain up to the specified number of concurrent connections per download
4. WHEN all chunks complete successfully THEN Streamdown SHALL rename the part file to the final output filename
5. WHEN the server does not support byte ranges THEN Streamdown SHALL fall back to single-stream download with progress tracking

### Requirement 2

**User Story:** As a user, I want to resume interrupted downloads automatically, so that I don't waste bandwidth re-downloading completed portions.

#### Acceptance Criteria

1. WHEN a download is interrupted THEN Streamdown SHALL persist chunk completion state to a metadata file
2. WHEN resuming with continue enabled THEN Streamdown SHALL load the metadata file and validate compatibility using ETag and Last-Modified headers
3. WHEN metadata is compatible THEN Streamdown SHALL skip completed chunks and download only pending chunks
4. WHEN metadata is incompatible with server response THEN Streamdown SHALL restart the download from the beginning
5. WHEN continue is disabled THEN Streamdown SHALL overwrite existing part files and start fresh

### Requirement 3

**User Story:** As a user, I want to preview video files while they download, so that I can start watching before the entire file completes.

#### Acceptance Criteria

1. WHEN streaming mode is set to inorder THEN Streamdown SHALL prioritize chunks sequentially from the beginning of the file
2. WHEN streaming mode is set to geom THEN Streamdown SHALL select chunks using geometric spacing starting from the beginning
3. WHEN early chunks complete THEN Streamdown SHALL write them to the part file at correct offsets to maintain file structure
4. WHEN a video player opens the part file THEN the file SHALL contain valid header data and sequential early content
5. WHILE downloading continues THEN Streamdown SHALL maintain the streaming priority strategy for remaining chunks

### Requirement 4

**User Story:** As a user, I want control over file overwriting behavior, so that I can prevent accidental data loss.

#### Acceptance Criteria

1. WHEN a complete file exists at the target path and allow-overwrite is disabled THEN Streamdown SHALL report an error and refuse to download
2. WHEN a complete file exists and allow-overwrite is enabled THEN Streamdown SHALL replace the existing file with the new download
3. WHEN auto-file-renaming is enabled and a file exists THEN Streamdown SHALL append a numeric suffix to create a unique filename
4. WHEN a part file exists and continue is enabled THEN Streamdown SHALL attempt to resume the download
5. WHEN the output directory does not exist THEN Streamdown SHALL create the directory before starting the download

### Requirement 5

**User Story:** As a user, I want to download multiple files concurrently, so that I can efficiently retrieve several resources in one command.

#### Acceptance Criteria

1. WHEN multiple URLs are provided THEN Streamdown SHALL queue all downloads for processing
2. WHEN max-concurrent-downloads is specified THEN Streamdown SHALL limit active downloads to that number
3. WHEN a download completes or fails THEN Streamdown SHALL start the next queued download if any remain
4. WHEN all downloads complete THEN Streamdown SHALL report the final status of each download
5. WHILE multiple downloads run THEN Streamdown SHALL aggregate and display total throughput statistics

### Requirement 6

**User Story:** As a user, I want a rich terminal interface with progress bars, so that I can monitor download status and performance.

#### Acceptance Criteria

1. WHEN a download starts THEN Streamdown SHALL display a progress bar showing filename, percentage, speed, and ETA
2. WHEN multiple downloads are active THEN Streamdown SHALL display separate progress bars for each download
3. WHEN download status changes THEN Streamdown SHALL update the progress bar with appropriate status indicators
4. WHEN quiet mode is enabled THEN Streamdown SHALL suppress progress bars and output only final results
5. WHEN errors occur THEN Streamdown SHALL display structured error messages with clear descriptions

### Requirement 7

**User Story:** As a user, I want sensible default settings, so that I can download files with minimal configuration.

#### Acceptance Criteria

1. WHEN no directory is specified THEN Streamdown SHALL download to the current working directory
2. WHEN no split count is specified THEN Streamdown SHALL use 8 parallel chunks by default
3. WHEN no piece size is specified THEN Streamdown SHALL use 1 MiB chunks by default
4. WHEN no continue flag is specified THEN Streamdown SHALL enable resume by default
5. WHEN no overwrite flag is specified THEN Streamdown SHALL prevent overwriting existing complete files by default

### Requirement 8

**User Story:** As a user, I want configurable connection limits and timeouts, so that I can optimize downloads for my network conditions.

#### Acceptance Criteria

1. WHEN max-connections-per-host is specified THEN Streamdown SHALL limit concurrent connections to each host to that value
2. WHEN connect-timeout is specified THEN Streamdown SHALL abort connection attempts exceeding that duration
3. WHEN read-timeout is specified THEN Streamdown SHALL abort stalled transfers exceeding that duration
4. WHEN max-tries is specified THEN Streamdown SHALL retry failed chunks up to that number of attempts
5. WHEN retry-wait is specified THEN Streamdown SHALL wait that duration between retry attempts

### Requirement 9

**User Story:** As a user, I want robust error handling and retry logic, so that transient network issues don't cause download failures.

#### Acceptance Criteria

1. WHEN a chunk download fails with a network error THEN Streamdown SHALL retry the chunk up to max-tries attempts
2. WHEN a chunk exceeds max-tries THEN Streamdown SHALL mark the download as failed and report the error
3. WHEN an HTTP error status is received THEN Streamdown SHALL categorize the error and determine if retry is appropriate
4. WHEN a connection times out THEN Streamdown SHALL treat it as a retryable error
5. WHEN disk write fails THEN Streamdown SHALL report a fatal error and halt the download

### Requirement 10

**User Story:** As a user, I want the tool to be installable via modern Python tooling, so that I can easily add it to my environment.

#### Acceptance Criteria

1. WHEN installing via uv tool install THEN Streamdown SHALL install successfully with all dependencies
2. WHEN the streamdown command is invoked THEN the CLI SHALL execute with the installed Python environment
3. WHEN dependencies are resolved THEN all dependencies SHALL be pure Python packages without mandatory C extensions
4. WHEN the package is imported THEN it SHALL work on Linux, macOS, and Windows platforms
5. WHEN Python version is less than 3.11 THEN the installation SHALL fail with a clear version requirement message

### Requirement 11

**User Story:** As a developer, I want the codebase to follow domain-driven design principles, so that the system is maintainable and extensible.

#### Acceptance Criteria

1. WHEN domain logic is implemented THEN it SHALL be independent of infrastructure concerns like HTTP and file I/O
2. WHEN application use cases are implemented THEN they SHALL coordinate domain objects and infrastructure adapters
3. WHEN infrastructure adapters are implemented THEN they SHALL implement protocol interfaces defined by the domain
4. WHEN the CLI is implemented THEN it SHALL only interact with the application layer, not domain or infrastructure directly
5. WHEN new features are added THEN the layered architecture SHALL facilitate extension without modifying existing layers

### Requirement 12

**User Story:** As a user, I want metadata files to survive crashes, so that I can always resume or restart cleanly after interruptions.

#### Acceptance Criteria

1. WHEN metadata is written THEN Streamdown SHALL use atomic file operations or crash-safe techniques
2. WHEN a crash occurs during metadata write THEN the metadata file SHALL either be valid or absent
3. WHEN loading corrupted metadata THEN Streamdown SHALL detect the corruption and restart the download
4. WHEN a download completes successfully THEN Streamdown SHALL remove the metadata file
5. WHEN chunk completion is recorded THEN Streamdown SHALL persist the update before considering the chunk complete

### Requirement 13

**User Story:** As a user, I want HTTPS certificate validation by default, so that my downloads are secure.

#### Acceptance Criteria

1. WHEN downloading from HTTPS URLs THEN Streamdown SHALL validate server certificates by default
2. WHEN certificate validation fails THEN Streamdown SHALL abort the download with a security error
3. WHEN an insecure flag is provided THEN Streamdown SHALL disable certificate validation and display a warning
4. WHEN downloading from HTTP URLs THEN Streamdown SHALL proceed without certificate validation
5. WHEN custom CA certificates are needed THEN Streamdown SHALL respect system certificate stores

### Requirement 14

**User Story:** As a user, I want efficient memory usage, so that I can download large files without consuming excessive RAM.

#### Acceptance Criteria

1. WHEN downloading file chunks THEN Streamdown SHALL stream data in fixed-size buffers rather than loading entire chunks in memory
2. WHEN writing to disk THEN Streamdown SHALL use buffered I/O with reasonable buffer sizes
3. WHEN multiple downloads are active THEN memory usage SHALL scale linearly with concurrent connections, not file sizes
4. WHEN a file is gigabytes in size THEN Streamdown SHALL maintain memory usage under 100 MiB regardless of file size
5. WHEN chunk data is received THEN Streamdown SHALL write it to disk promptly and release the buffer

### Requirement 15

**User Story:** As a user, I want automatic authentication using netrc credentials, so that I can download from authenticated servers without manually specifying credentials in commands.

#### Acceptance Criteria

1. WHEN netrc support is enabled and a netrc file exists THEN Streamdown SHALL read authentication credentials from the netrc file at startup
2. WHEN downloading from a host with netrc credentials THEN Streamdown SHALL include HTTP Basic Authentication headers in requests
3. WHEN the netrc file has permissions other than 600 THEN Streamdown SHALL ignore the file and log a warning
4. WHEN no-netrc is set to true THEN Streamdown SHALL disable netrc support and not read the netrc file
5. WHEN netrc-path is specified THEN Streamdown SHALL read credentials from the specified file instead of the default location
6. WHEN the default netrc file does not exist and no custom path is specified THEN Streamdown SHALL proceed without netrc authentication
7. WHEN netrc file contains invalid syntax THEN Streamdown SHALL log a warning and proceed without netrc authentication

### Requirement 16

**User Story:** As a user on a mobile device or small terminal, I want the progress display to adapt to narrow screens, so that I can monitor downloads without text wrapping or information being cut off.

#### Acceptance Criteria

1. WHEN the terminal width is less than 80 columns THEN Streamdown SHALL detect the narrow width and adjust the display layout
2. WHEN displaying filenames on narrow terminals THEN Streamdown SHALL truncate long filenames to fit within available space while preserving file extension
3. WHEN displaying progress information on narrow terminals THEN Streamdown SHALL prioritize essential information and omit or abbreviate less critical details
4. WHEN displaying URLs on narrow terminals THEN Streamdown SHALL truncate or omit URLs to prevent wrapping
5. WHEN the progress bar is displayed on narrow terminals THEN Streamdown SHALL scale the bar width proportionally to terminal width while maintaining readability
