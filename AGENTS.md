# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.12 package for downloading and extracting LaTeX source archives from arXiv recent pages. Runtime code lives in `src/daily_arxiv/`: `cli.py` defines the Typer CLI, `arxiv_recent.py` fetches/parses recent listings, `downloader.py` handles archive downloads and metadata, `extractor.py` safely extracts archives, and `models.py` contains shared data models. Tests live in `tests/`, with fixtures in `tests/fixtures/`. Generated output is written under `downloads/<date>/` with `archives/`, `sources/`, and `metadata.jsonl`; treat this as run output, not source.

## Build, Test, and Development Commands

- `uv sync`: create or update the local virtual environment from `pyproject.toml` and `uv.lock`.
- `uv run pytest`: run the full test suite configured for `tests/`.
- `uv run daily-arxiv list cs.RO`: list papers from the latest visible arXiv `cs.RO` recent date group.
- `uv run daily-arxiv download cs.RO --output downloads`: download and extract source archives into `downloads/`.

Use `--date YYYY-MM-DD`, `--timeout`, `--delay`, and `--keep-going` when exercising CLI edge cases.

## Coding Style & Naming Conventions

Follow the existing typed, straightforward Python style. Use 4-space indentation, `from __future__ import annotations` in runtime modules, `pathlib.Path` for filesystem paths, and explicit domain exceptions for expected failures. Keep function and test names in `snake_case`; name tests as `test_<behavior>`. Prefer small helpers such as `archive_path_for()` or `_validate_requested_date()` over duplicating path or validation logic.

## Testing Guidelines

Tests use `pytest`, `typer.testing.CliRunner`, `tmp_path`, `monkeypatch`, and `httpx.MockTransport` to avoid real network calls. Add or update tests for parser changes, CLI behavior, archive safety, metadata output, and error handling. Keep tests deterministic: use fixtures or mocked HTTP responses instead of live arXiv requests.

## Commit & Pull Request Guidelines

Git history uses short Conventional Commit-style subjects, especially `feat:`, `fix:`, and `docs:`. Keep commits focused, for example `fix: validate cli date before fetch`. Pull requests should describe the behavior change, list verification commands such as `uv run pytest`, mention linked issues when applicable, and include CLI output snippets only when user-facing behavior changes.

## Agent-Specific Notes

Do not revert user-generated artifacts or unrelated work. Avoid committing `downloads/`, `__pycache__/`, `.pytest_cache/`, or virtual environment files unless explicitly requested.
