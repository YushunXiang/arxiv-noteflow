# Daily arXiv CLI Design

## Context

Build a Python CLI tool that downloads the LaTeX source archives for papers listed on an arXiv category recent page. The first target is Robotics (`cs.RO`), but the category must be supplied as a CLI argument so the same tool can work for other arXiv categories.

The source archive URL format is:

```text
https://arxiv.org/src/<arxiv-id>
```

The project will use `uv` for Python environment and command management.

## References Reviewed

- Reddit/Gist arXiv script: a simple one-file command-line script that fetches metadata and supports source downloads. Useful as a minimal baseline, but it relies on older command-line patterns and brittle HTML string parsing.
- `jacquerie/arxiv-cli`: a Python package with a clear split between CLI commands and an API client. Useful for packaging, console entry points, timeout configuration, and test fixture patterns.
- `AstraBert/arxiv-cli`: a modern CLI that saves metadata as JSONL, cleans filenames, separates download logic from CLI parsing, and reports network errors with context.

This tool will borrow the separation of CLI and core logic, JSONL metadata output, conservative request handling, and focused tests. It will not use the arXiv Atom API as the primary source of truth because the requirement is to match the visible date groups on `https://arxiv.org/list/<category>/recent`.

## Goals

- Provide a `uv`-managed Python CLI.
- Accept the arXiv category as a required CLI argument.
- Parse `https://arxiv.org/list/<category>/recent`.
- By default, select the first date group on the recent page.
- Support `--date YYYY-MM-DD` to select a visible date group from the recent page.
- Download each paper's LaTeX source archive from `https://arxiv.org/src/<id>`.
- Keep both the original archive and an extracted source directory.
- Write JSONL metadata for the run.
- Make repeated runs idempotent by skipping already downloaded or extracted outputs.
- Keep tests independent from live arXiv network requests by default.

## Non-Goals

- Do not implement historical search outside the current `recent` page.
- Do not use the arXiv Atom API to infer date groups in the first version.
- Do not download PDFs, summaries, or HTML unless added in a future feature.
- Do not schedule recurring downloads in the first version.
- Do not implement parallel downloads in the first version; use a conservative sequential flow.

## CLI Interface

The console command will be `daily-arxiv`.

Primary commands:

```bash
uv run daily-arxiv list cs.RO
uv run daily-arxiv list cs.RO --date 2026-05-15
uv run daily-arxiv download cs.RO
uv run daily-arxiv download cs.RO --date 2026-05-15
```

Options:

- `category`: required positional argument, such as `cs.RO`, `cs.CL`, or `stat.ML`.
- `--date YYYY-MM-DD`: optional ISO date. If omitted, use the first date group in the recent page HTML.
- `--output PATH`: output root directory. Default: `downloads`.
- `--delay SECONDS`: delay between source archive download requests. Default: `3`.
- `--timeout SECONDS`: HTTP timeout. Default: `30`.
- `--keep-going`: continue downloading remaining papers when one paper fails.

`list` prints the selected date group and the papers that would be downloaded. `download` performs the same selection and then downloads and extracts the source archives.

## Output Layout

For a selected date of `2026-05-15`, output will be:

```text
downloads/
  2026-05-15/
    metadata.jsonl
    archives/
      2605.15157.tar.gz
    sources/
      2605.15157/
```

Archive filenames use the normalized arXiv ID without version unless the recent page includes a versioned ID. The metadata records the exact ID parsed from the page and the source URL used for download.

## Package Layout

```text
pyproject.toml
README.md
src/daily_arxiv/
  __init__.py
  cli.py
  arxiv_recent.py
  downloader.py
  extractor.py
  models.py
tests/
  fixtures/
  test_arxiv_recent.py
  test_downloader.py
  test_extractor.py
  test_cli.py
```

Module responsibilities:

- `cli.py`: parse command-line arguments, call application functions, print concise results, and set exit behavior.
- `arxiv_recent.py`: fetch and parse recent page HTML into date-grouped paper data.
- `downloader.py`: download source archives with timeout, user agent, temporary files, idempotent skip behavior, and optional keep-going behavior.
- `extractor.py`: safely extract tar archives into per-paper directories.
- `models.py`: define typed data models such as `Paper`, `DateGroup`, and `DownloadResult`.

## Dependencies

Runtime dependencies:

- `httpx` for HTTP requests.
- `beautifulsoup4` for HTML parsing.
- `typer` for CLI structure.

Development dependencies:

- `pytest` for tests.
- `respx` or `pytest-httpx` for HTTP mocking.

## Recent Page Parsing

The parser will:

1. Fetch `https://arxiv.org/list/<category>/recent`.
2. Locate date group headings inside the articles list.
3. Convert headings such as `Fri, 15 May 2026` to ISO dates such as `2026-05-15`.
4. If `--date` is omitted, select the first parsed date group.
5. If `--date` is provided, select the matching parsed date group.
6. Extract each paper's arXiv ID, title, authors, subjects, abstract URL, and source URL.

If no date groups are found, the command fails with a clear parse error. If `--date` is provided but the date is not visible on the recent page, the command fails with:

```text
No entries found for 2026-05-15 in cs.RO recent page
```

## Download Flow

For each selected paper:

1. Build the source URL as `https://arxiv.org/src/<id>`.
2. Download into a temporary file in the target archive directory.
3. On success, atomically replace the final archive path.
4. If the final archive already exists and is non-empty, skip the download.
5. Extract the archive into `sources/<id>/`.
6. If the source directory already exists and is non-empty, skip extraction.
7. Append a JSONL metadata record for the paper.

Requests are sequential, with `--delay` applied between downloads. The tool sets a user agent and timeout for arXiv requests.

## Metadata

`metadata.jsonl` will contain one JSON object per paper. Fields:

- `id`
- `title`
- `authors`
- `subjects`
- `date`
- `category`
- `abs_url`
- `src_url`
- `archive_path`
- `source_dir`
- `status`
- `error`

`status` values:

- `downloaded`
- `skipped`
- `failed`

`error` is `null` unless the paper failed.

## Error Handling

- Recent page fetch failures return a non-zero exit code with the URL and HTTP status or network exception.
- HTML parse failures return a non-zero exit code with the category and a short explanation.
- Missing requested dates return a non-zero exit code and list the visible dates.
- A single paper download failure stops the command by default.
- With `--keep-going`, failures are recorded in metadata and the command continues. If any paper failed, the final exit code remains non-zero.
- Archive extraction rejects unsafe paths that would write outside the target source directory.
- Partial downloads are left as temporary files only and are not treated as completed archives.

## Testing

Default tests will not call live arXiv.

Coverage:

- Parse a fixture of the current `cs.RO` recent page and select the first date group.
- Parse a fixture with `--date 2026-05-15`.
- Fail clearly when a requested date is absent.
- Extract paper ID, title, authors, subjects, abstract URL, and source URL.
- Download a mocked source archive to the expected archive path.
- Skip a non-empty existing archive.
- Extract a valid tar archive to `sources/<id>/`.
- Reject a tar archive with path traversal entries.
- Verify CLI `list` output and `download` output layout in a temporary directory.
- Verify `--keep-going` records failures and continues.

An optional manual integration command can be documented for live arXiv verification, but it will not be part of default tests.

## Acceptance Criteria

- `uv sync` creates the development environment.
- `uv run daily-arxiv list cs.RO` prints the latest visible recent-page date group and paper IDs.
- `uv run daily-arxiv download cs.RO` creates archive and source outputs for the latest visible date group.
- `uv run daily-arxiv download cs.RO --date 2026-05-15` selects that visible date group if present.
- Existing archives and extracted directories are skipped without corrupting outputs.
- `uv run pytest` passes without live network access.

