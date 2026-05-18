# daily-arxiv

[中文文档](README.zh-CN.md)

Download and extract LaTeX source archives from arXiv category recent pages.

`daily-arxiv` is a small Python 3.12 CLI for repeatable daily paper intake. It reads
`https://arxiv.org/list/<category>/recent`, selects a visible date group, downloads
each paper source archive from `https://arxiv.org/src/<id>`, safely extracts it, and
writes deterministic metadata under `downloads/<date>/`.

The repository also includes local automation helpers for reading downloaded papers
into Markdown notes, syncing generated notes to Lark/Feishu Drive, and sending a
focused Feishu webhook summary.

## Features

- List the latest visible arXiv recent-page date group for a category.
- Download source archives and extract them into per-paper source directories.
- Keep JSON Lines metadata for every downloaded paper.
- Continue batch downloads after individual paper failures with `--keep-going`.
- Prepare deterministic reading manifests for agent-assisted paper note generation.
- Sync generated Markdown notes to Lark/Feishu Drive with private tokens loaded from `.env`.
- Send focused Feishu webhook summaries from generated Markdown notes.

## Requirements

- Python 3.12
- [`uv`](https://docs.astral.sh/uv/)

Optional workflow helpers:

- `lark-cli` for Lark/Feishu Drive and document sync
- Feishu custom bot webhook URL for summary push notifications

## Installation

```bash
uv sync
```

Run the test suite:

```bash
uv run pytest
```

## CLI Usage

List the latest visible date group:

```bash
uv run daily-arxiv list cs.RO
```

List a specific visible date group:

```bash
uv run daily-arxiv list cs.RO --date 2026-05-15
```

Download and extract source archives:

```bash
uv run daily-arxiv download cs.RO
uv run daily-arxiv download cs.RO --date 2026-05-15
```

Use a custom output directory:

```bash
uv run daily-arxiv download cs.RO --output downloads
```

Continue after individual paper failures:

```bash
uv run daily-arxiv download cs.RO --keep-going
```

Useful network controls:

```bash
uv run daily-arxiv download cs.RO --timeout 30 --delay 1.0 --keep-going
```

`--date` only selects dates visible on the current arXiv recent page. It does not
search historical archives.

## Output Layout

```text
downloads/
  2026-05-15/
    metadata.jsonl
    archives/
      2605.15157.tar.gz
    sources/
      2605.15157/
```

Generated paper notes are normally written outside the downloader output tree:

```text
papers/
  2026-05-15/
    paper-slug/
      paper-slug.md
      assets/
```

`downloads/` and `papers/` are runtime output and are ignored by git.

## Environment Variables

Private Lark/Feishu values are read from the shell environment or a local `.env`
file. Start from the template:

```bash
cp example.env .env
```

Then fill in:

```dotenv
LARK_PARENT_FOLDER_TOKEN=
FEISHU_WEBHOOK_URL=
```

Do not commit `.env`. It is ignored by `.gitignore`.

## Daily Reading Workflow

Prepare a reading manifest for the latest `cs.RO` recent-page group:

```bash
python3 .codex/skills/read-daily-arxiv/scripts/prepare_daily_batch.py \
  --repo . \
  --category cs.RO \
  --download-output downloads \
  --notes-output papers \
  --keep-going
```

Prepare a manifest from an already-downloaded date:

```bash
python3 .codex/skills/read-daily-arxiv/scripts/prepare_daily_batch.py \
  --repo . \
  --category cs.RO \
  --date 2026-05-15 \
  --download-output downloads \
  --notes-output papers \
  --skip-download
```

The manifest includes each paper's metadata path, extracted source directory,
top-level TeX candidates, arXiv URLs, and suggested note output path.

## Lark/Feishu Sync

Sync generated Markdown notes for one date into the configured Lark Drive folder:

```bash
python3 .codex/skills/read-daily-arxiv/scripts/sync_lark_notes.py \
  --repo . \
  --date 2026-05-18 \
  --papers-root papers
```

Include local note assets:

```bash
python3 .codex/skills/read-daily-arxiv/scripts/sync_lark_notes.py \
  --repo . \
  --date 2026-05-18 \
  --papers-root papers \
  --sync-assets
```

The sync helper expects `LARK_PARENT_FOLDER_TOKEN` from `.env` or the shell
environment unless `--parent-folder-token` is passed explicitly.

## Feishu Webhook Summary

Send a focused Chinese summary for a date after notes have been generated:

```bash
uv run python scripts/send_focus_summary_to_feishu.py \
  --date 2026-05-18 \
  --max-chars 18000
```

The summary helper reads `papers/<date>/**/*.md`, prioritizes Long-horizon,
Egocentric, UMI, and VLA topics, attaches arXiv links, and includes Feishu
document links when Lark import reports are available.

Use `--dry-run` to preview without sending:

```bash
uv run python scripts/send_focus_summary_to_feishu.py \
  --date 2026-05-18 \
  --dry-run
```

## Development Notes

- Runtime code lives in `src/daily_arxiv/`.
- Tests live in `tests/`.
- Network behavior is tested with mocked HTTP responses.
- Keep generated output, virtual environments, caches, and `.env` files out of source control.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
