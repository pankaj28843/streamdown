# Agent Instructions

This is the canonical repo instruction file. `CLAUDE.md` is a symlink for Claude Code compatibility. Do not recreate `.kiro/`; keep agent-facing guidance here and repo-local skills under `.agents/skills`.

## Compatibility layout

- `AGENTS.md` is canonical.
- `CLAUDE.md` is compatibility-only and should symlink to `AGENTS.md`.
- `.agents/skills` is canonical for repo-local skills.
- `.claude/skills`, `.codex/skills`, `.opencode/skills`, and `.github/skills` are compatibility symlinks to `.agents/skills`.
- `.github/copilot-instructions.md` is a compatibility symlink to `AGENTS.md` for GitHub Copilot Chat custom instructions.

## Project overview

Streamdown is a pure-Python 3.11+ asyncio HTTP(S) downloader CLI with multi-connection range downloads, resume metadata, streaming-oriented chunk ordering, netrc authentication, and Rich progress output.

## Architecture rules

- Preserve the layered design:
  - `src/streamdown/domain/`: entities, value objects, enums, exceptions, and pure domain services. Keep it free of HTTP, filesystem, CLI, and logging concerns.
  - `src/streamdown/application/`: DTOs, use cases, chunk workers, download coordination, and multi-download orchestration.
  - `src/streamdown/infrastructure/`: adapters for HTTP, file writing, metadata persistence, netrc, and logging.
  - `src/streamdown/cli/`: Typer CLI and Rich progress display; call the application layer rather than reaching into infrastructure/domain directly.
- Use Python 3.11+ async patterns. Prefer structured concurrency and bounded task/connection counts.
- Stream file data in bounded buffers; never load whole downloads or whole chunks into memory.
- Keep resume metadata crash-safe with atomic write/rename behavior.
- Keep HTTPS certificate validation enabled by default. Only disable it through the explicit insecure option.
- Netrc support must ignore insecure permission modes and continue gracefully for missing or malformed netrc files.

## Development commands

Install development dependencies:

```bash
uv sync --extra dev
```

Run checks from the repo root:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Useful focused checks:

```bash
uv run pytest tests/test_chunk_planner.py
uv run pytest tests/test_integration.py
uv run pytest -k netrc
```

## Testing guidance

- Add or update tests with behavior changes.
- Prefer unit tests for domain/application rules and integration tests for HTTP/file/resume flows.
- Use property-style tests where invariants matter, especially chunk planning, retry limits, concurrency limits, memory bounds, and responsive progress formatting.
- Keep CLI behavior covered through Typer/CliRunner or subprocess-style tests.

## Packaging notes

- Package metadata lives in `pyproject.toml`.
- The CLI entry point is `streamdown = "streamdown.cli.main:main"`.
- `python -m streamdown` should continue to work through `src/streamdown/__main__.py`.
