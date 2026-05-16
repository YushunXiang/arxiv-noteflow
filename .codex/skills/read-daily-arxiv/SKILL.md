---
name: read-daily-arxiv
description: Download the latest papers from arXiv recent pages with the local daily-arxiv Python CLI, then read each downloaded LaTeX source project and write one Obsidian-compatible Markdown note per paper. Use when asked to read today's, daily, latest, or date-specific arXiv papers; batch-digest arXiv recent papers; create per-paper Markdown notes; or turn daily-arxiv downloads into Chinese research notes.
---

# Read Daily arXiv

## Overview

Use this skill to run a daily arXiv reading batch: fetch recent papers with the `daily-arxiv` repository CLI, inspect each extracted source tree, and write one Markdown note per paper. Default note body language is Simplified Chinese unless the user explicitly requests another language.

The expected local repository is `/Users/ysxiang/Documents/daily-arxiv` when no repo path is given.

## Workflow

1. Resolve inputs:
   - `category`: default to `cs.RO` unless the user names another arXiv category.
   - `date`: omit for the latest visible recent-page group; pass `--date YYYY-MM-DD` only when the user asks for a specific visible arXiv recent date.
   - `download_output`: default `downloads`.
   - `notes_output`: default `papers`.
   - `output_language`: default `zh-CN`.
2. Prepare the batch manifest:
   - Run `scripts/prepare_daily_batch.py` from this skill to call the repo CLI and produce a manifest.
   - Use `--skip-download` only when the source archives are already downloaded and extracted.
   - If the helper script is not suitable, run `uv run daily-arxiv download <category> --output downloads --keep-going` directly in the repo and read `downloads/<date>/metadata.jsonl`.
3. For each manifest paper whose status is not `failed`:
   - Read `00README.json` first when present; prefer entries marked `usage: "toplevel"` as TeX entrypoints.
   - Recursively read the TeX project from the entrypoint, following `\input{...}` and `\include{...}`.
   - Load `references/paper-note-spec.md` and follow it for title sanitization, figure extraction, table handling, frontmatter, note section order, and quality checks.
4. Write exactly one note per paper:
   - If the user provided a note path for a paper, update that exact file.
   - Otherwise create `{notes_output}/{date}/{paper_name}/{paper_name}.md` and put generated assets under `{notes_output}/{date}/{paper_name}/assets/`.
   - Preserve an existing `<!-- USER_NOTES_START --> ... <!-- USER_NOTES_END -->` block verbatim if present.
5. Report a concise batch summary:
   - notes written or updated
   - papers skipped or failed, with reasons
   - verification performed

## Commands

Prepare today's latest batch:

```bash
python3 /Users/ysxiang/Documents/daily-arxiv/.codex/skills/read-daily-arxiv/scripts/prepare_daily_batch.py \
  --repo /Users/ysxiang/Documents/daily-arxiv \
  --category cs.RO \
  --download-output downloads \
  --notes-output papers \
  --keep-going
```

Prepare an already-downloaded date without network:

```bash
python3 /Users/ysxiang/Documents/daily-arxiv/.codex/skills/read-daily-arxiv/scripts/prepare_daily_batch.py \
  --repo /Users/ysxiang/Documents/daily-arxiv \
  --category cs.RO \
  --date 2026-05-15 \
  --download-output downloads \
  --notes-output papers \
  --skip-download
```

The script prints and writes a JSON manifest containing `metadata_path`, `source_dir`, `toplevel_tex`, `abs_url`, `pdf_url`, and `suggested_notes_root` for each paper.

## Reading Rules

- Prefer source-first reading. Use PDF only when source is unavailable, incomplete, or figure extraction requires a fallback.
- Do not hallucinate numbers, dataset names, baselines, or metrics. Use `未报告` when the source does not provide a value.
- Keep proper nouns, model names, dataset names, metric names, and code identifiers in their original form where useful.
- Include only figures that are strongly supported as pipeline/framework/architecture/method figures by caption, label, or filename.
- Keep generated run output out of source control unless the user explicitly asks to commit it.

## Resources

- `scripts/prepare_daily_batch.py`: Calls the local daily-arxiv CLI when needed and emits a deterministic manifest for the reading batch.
- `references/paper-note-spec.md`: Detailed TeX-first single-paper note specification.
