---
name: read-daily-arxiv
description: Download the latest papers from arXiv recent pages with the local daily-arxiv Python CLI, then read each downloaded LaTeX source project and write one Obsidian-compatible Markdown note per paper. Use when asked to read today's, daily, latest, or date-specific arXiv papers; batch-digest arXiv recent papers; create per-paper Markdown notes; turn daily-arxiv downloads into Chinese research notes; or sync generated paper Markdown notes to a Lark/Feishu Drive folder.
---

# Read Daily arXiv

## Overview

Use this skill to run a daily arXiv reading batch: fetch recent papers with the `daily-arxiv` repository CLI, inspect each extracted source tree, and write one Markdown note per paper. The YAML frontmatter may keep structured source metadata in its original language, but all generated content after the closing frontmatter `---` must be written in Simplified Chinese (`zh-CN`) unless the user explicitly requests another language.

The expected local repository is `/Users/ysxiang/Documents/daily-arxiv` when no repo path is given.

## Workflow

1. Resolve inputs:
   - `category`: default to `cs.RO` unless the user names another arXiv category.
   - `date`: omit for the latest visible recent-page group; pass `--date YYYY-MM-DD` only when the user asks for a specific visible arXiv recent date.
   - `download_output`: default `downloads`.
   - `notes_output`: default `papers`.
   - `output_language`: default `zh-CN`.
   - `lark_parent_folder_token`: read from `LARK_PARENT_FOLDER_TOKEN` in `.env` or the shell environment when syncing to Lark; never hardcode folder tokens in repository files.
   - `lark_date_folder_name`: default to the resolved `date`, for example `2026-05-15`.
2. Prepare the batch manifest:
   - Run `scripts/prepare_daily_batch.py` from this skill to call the repo CLI and produce a manifest.
   - Use `--skip-download` only when the source archives are already downloaded and extracted.
   - If the helper script is not suitable, run `uv run daily-arxiv download <category> --output downloads --keep-going` directly in the repo and read `downloads/<date>/metadata.jsonl`.
3. Read papers with multi-agent parallelism:
   - Build the readable paper list from manifest entries whose status is not `failed`.
   - If there is only one readable paper, the current agent may read and write it directly. If there are two or more readable papers, dispatch parallel worker agents by default.
   - Prefer one worker agent per paper. For very large batches, split into small disjoint shards and keep each shard's write set explicit.
   - Give each worker only the context it needs: the manifest item(s), `source_dir`, resolved `note_path` or output root, `assets_dir`, arXiv metadata, output language, and the requirement to load `references/paper-note-spec.md`.
   - Tell workers they are not alone in the workspace. Each worker may read shared downloads and source files, but may write only its assigned note path(s) and asset directory/directories; it must not edit the skill, repo code, other papers, or unrelated generated output.
   - Each worker must read `00README.json` first when present, prefer entries marked `usage: "toplevel"` as TeX entrypoints, recursively follow `\input{...}` and `\include{...}`, then write the assigned note(s) according to `references/paper-note-spec.md`.
   - The coordinating agent should continue useful coordination while workers run, then review worker summaries, inspect changed paths, rerun or repair failed/low-quality notes, and produce one batch summary.
4. Write exactly one note per paper:
   - If the user provided a note path for a paper, update that exact file.
   - Otherwise create `{notes_output}/{date}/{paper_name}/{paper_name}.md` and put generated assets under `{notes_output}/{date}/{paper_name}/assets/`.
   - Treat YAML frontmatter as the only default language exception. Write every Markdown heading, bullet, paragraph, table heading, table column label, figure-caption explanation, and source note after the closing `---` in Simplified Chinese (`zh-CN`) unless the user explicitly requests another language.
   - Keep paper titles, author names, proper nouns, dataset names, metric names, model names, code identifiers, formulas, numeric values, URLs, and BibTeX keys in their original form where needed, but explain them in Chinese.
   - Do not leave English template labels such as `TL;DR`, `Pipeline Figure`, `Benchmarks`, `Main Results`, `Dataset`, `Task`, `Metric`, `Notes`, `Baseline`, `Ours`, `Delta`, `Item`, or `Value` in the body; translate them before writing the note.
   - Preserve an existing `<!-- USER_NOTES_START --> ... <!-- USER_NOTES_END -->` block verbatim if present.
5. Report a concise batch summary:
   - notes written or updated
   - papers skipped or failed, with reasons
   - verification performed
6. If the user asks for `lark-sync` or syncing notes to Feishu/Lark:
   - Use `--as user`; Drive resources are user-owned unless the user explicitly asks for bot ownership.
   - Load private values from the repo-root `.env` file or the shell environment. Copy `example.env` to `.env` and set `LARK_PARENT_FOLDER_TOKEN` before syncing, or pass `--parent-folder-token` explicitly for one-off runs.
   - Before creating any folder, search the target parent folder for an exact same-title folder. Reuse an existing folder token when found; only call `lark-cli drive +create-folder` when no exact match exists. If multiple exact matches exist, reuse the earliest-created one and report the duplicate folder tokens instead of creating another.
   - Resolve a date child folder named `lark_date_folder_name` directly under `lark_parent_folder_token`, matching the local date directory such as `papers/2026-05-15`; do not create a remote `papers` folder.
   - Import only Markdown files for the requested date: `{notes_output}/{date}/**/*.md`.
   - Use `lark-cli drive +import --type docx --file <path> --folder-token <date_folder_token>` to convert each local `.md` file into a Lark online document (`docx`) in the date folder, and keep a JSON import report with `successes[].file`, `successes[].url`, and document tokens.
   - After Markdown import, embed local pipeline images into the corresponding Feishu online documents before treating Lark sync as complete. Markdown import does not resolve Obsidian local image links such as `![[assets/pipeline_*.png]]`.
     - For each successful import report item, read the local Markdown file, find the first Obsidian pipeline image link matching `![[assets/pipeline_*]]`, and resolve it relative to the note directory.
     - If the asset is `.pdf`, `.eps`, or another non-web image format, convert it to a PNG in the same `assets/` directory with an available local tool such as `sips`, `qlmanage`, `rsvg-convert`, `pdftoppm`, or `magick`; record the converted path in the sync report.
     - Insert the image into the matching Feishu document with `lark-cli docs +media-insert --as user --doc <successes[].url> --file <asset_or_converted_png> --selection-with-ellipsis "流程图" --align center --width 800 --caption <pipeline_asset_stem>`.
     - Remove the original Obsidian placeholder text from the online document with `lark-cli docs +update --as user --api-version v2 --doc <url> --command str_replace --pattern '![[assets/pipeline_...]]' --content ""`.
     - Verify by fetching the Feishu document's `流程图` section with `lark-cli docs +fetch --as user --api-version v2 --doc <url> --scope keyword --keyword "流程图" --detail with-ids`, then `--scope section` on the returned heading block id; the section must contain an `<img ...>` block and must not contain the old `![[assets/...]]` placeholder.
     - Skip only notes that genuinely have no reliable local pipeline asset, and report them explicitly.
   - If the user asks to include images/assets, run the Lark sync helper with `--sync-assets`. It creates one remote folder per local paper directory under the date folder, creates/reuses an `assets` child folder, then mirrors the local `assets/` directory with `lark-cli drive +push --if-exists smart`.
   - `--sync-assets` uploads image files to Drive for access and organization, but it is not a substitute for the online-document image insertion step above.
   - Report whether the Lark parent folder token was configured, the date folder token, the number of Markdown files imported as online documents, the number of pipeline images embedded into Feishu documents, skipped image reasons, the number of asset folders synced, and any duplicate folder tokens reused.
7. If the user asks for a Feishu/Lark webhook summary after reading a date:
   - First ensure the requested date's Markdown notes exist under `{notes_output}/{date}/`.
   - If the user wants references to the corresponding Feishu documents, sync/import the Markdown notes to Lark first and keep the generated JSON report containing `successes[].file` and `successes[].url`, for example `downloads/{date}/lark-reimport-report.json` or `downloads/{date}/lark-import-report.json`.
   - Run the local webhook summary helper with `uv run python scripts/send_focus_summary_to_feishu.py --date <date>`. Pass the webhook through `FEISHU_WEBHOOK_URL` in `.env` or the shell environment, or use `--webhook-url` for one-off runs; do not hardcode webhook URLs in repository files.
   - The webhook message must summarize the requested date's notes in Chinese, prioritize Long-horizon, Egocentric, UMI, and VLA, and include both the arXiv URL and the corresponding `飞书文档：<url>` line for each highlighted paper whenever a Lark import report provides it.
   - Use `--max-chars 18000` when the message can fit in one Feishu text message. If chunking is necessary, keep `--send-interval` nonzero and allow `--rate-limit-retries` to avoid Feishu custom bot frequency limits such as `code=11232`.

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

Sync generated Markdown notes for one date to Lark Drive as online documents:

```bash
find_or_create_lark_folder() {
  parent_token="$1"
  folder_name="$2"
  folder_name_json=$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$folder_name")

  existing_token=$(lark-cli drive +search \
    --as user \
    --query "$folder_name" \
    --doc-types folder \
    --only-title \
    --folder-tokens "$parent_token" \
    --page-size 20 \
    --jq ".data.results
      | map(select((.title_highlighted | gsub(\"<[^>]+>\"; \"\")) == $folder_name_json))
      | sort_by(.result_meta.create_time)
      | .[0].result_meta.token // empty")

  if [ -n "$existing_token" ]; then
    printf '%s\n' "$existing_token"
  else
    lark-cli drive +create-folder \
      --as user \
      --folder-token "$parent_token" \
      --name "$folder_name" \
      --jq '.data.folder_token'
  fi
}

set -a
[ -f .env ] && . ./.env
set +a
: "${LARK_PARENT_FOLDER_TOKEN:?Set LARK_PARENT_FOLDER_TOKEN in .env or the shell environment}"

date_folder_token=$(find_or_create_lark_folder "$LARK_PARENT_FOLDER_TOKEN" 2026-05-15)
```

Import Markdown notes from the matching local date directory into that date folder as Lark online documents:

```bash
find papers/2026-05-15 -type f -name '*.md' -print0 |
while IFS= read -r -d '' f; do
  lark-cli drive +import \
    --as user \
    --type docx \
    --folder-token "$date_folder_token" \
    --file "$f"
done
```

Preferred helper for repeatable Lark sync:

```bash
python3 /Users/ysxiang/Documents/daily-arxiv/.codex/skills/read-daily-arxiv/scripts/sync_lark_notes.py \
  --repo /Users/ysxiang/Documents/daily-arxiv \
  --date 2026-05-18 \
  --papers-root papers
```

Include each paper's local image assets, such as `papers/2026-05-18/<paper>/assets/`, by adding `--sync-assets`:

```bash
python3 /Users/ysxiang/Documents/daily-arxiv/.codex/skills/read-daily-arxiv/scripts/sync_lark_notes.py \
  --repo /Users/ysxiang/Documents/daily-arxiv \
  --date 2026-05-18 \
  --papers-root papers \
  --sync-assets
```

The helper prints JSON with `parent_folder_token_configured`, `date_folder_token`, `imported_markdown`, `synced_assets`, and `duplicate_folder_tokens`.

After importing Markdown as Feishu online documents, embed pipeline figures into each imported document instead of leaving Obsidian placeholders:

```bash
# Use the import report produced by the sync/import step.
# For each successes[] item:
#   1. Read successes[].file and locate ![[assets/pipeline_*]]
#   2. Convert non-web image assets to PNG when needed.
#   3. Insert into the Feishu doc's 流程图 section.
#   4. Remove the old ![[assets/...]] placeholder.
#   5. Fetch the 流程图 section and verify it contains <img ...>.
lark-cli docs +media-insert \
  --as user \
  --doc "https://<tenant>.feishu.cn/docx/..." \
  --file papers/2026-05-18/<paper>/assets/pipeline_<arxiv_id>.png \
  --selection-with-ellipsis "流程图" \
  --align center \
  --width 800 \
  --caption "pipeline_<arxiv_id>"

lark-cli docs +update \
  --as user \
  --api-version v2 \
  --doc "https://<tenant>.feishu.cn/docx/..." \
  --command str_replace \
  --pattern '![[assets/pipeline_<arxiv_id>.png]]' \
  --content ""
```

Send a focused Feishu webhook summary for a date after notes are generated:

```bash
uv run python scripts/send_focus_summary_to_feishu.py \
  --date 2026-05-18 \
  --max-chars 18000
```

The helper reads `papers/<date>/**/*.md`, prioritizes Long-horizon, Egocentric, UMI, and VLA, and automatically looks for Lark import reports at `downloads/<date>/lark-reimport-report.json` and `downloads/<date>/lark-import-report.json`. When a report maps a local Markdown path to a Feishu document URL, the webhook item must include that `飞书文档：...` reference. If reports live elsewhere, pass them explicitly:

```bash
uv run python scripts/send_focus_summary_to_feishu.py \
  --date 2026-05-18 \
  --lark-report downloads/2026-05-18/lark-reimport-report.json \
  --webhook-url "$FEISHU_WEBHOOK_URL" \
  --max-chars 18000
```

## Reading Rules

- Prefer source-first reading. Use PDF only when source is unavailable, incomplete, or figure extraction requires a fallback.
- Do not hallucinate numbers, dataset names, baselines, or metrics. Use `未报告` when the source does not provide a value.
- Keep proper nouns, model names, dataset names, metric names, and code identifiers in their original form where useful.
- Include only figures that are strongly supported as pipeline/framework/architecture/method figures by caption, label, or filename.
- Before reporting a note as complete, scan the Markdown body after frontmatter for leftover English template headings, table labels, and copied source captions. Rewrite them in Chinese unless they are proper nouns, identifiers, formulas, URLs, or deliberately quoted source snippets marked with `原文：`.
- Keep generated run output out of source control unless the user explicitly asks to commit it.

## Resources

- `scripts/prepare_daily_batch.py`: Calls the local daily-arxiv CLI when needed and emits a deterministic manifest for the reading batch.
- `scripts/sync_lark_notes.py`: Imports generated Markdown notes to Lark Drive and optionally mirrors each paper's `assets/` folder with `--sync-assets`.
- Repo-root `scripts/send_focus_summary_to_feishu.py`: Reads generated Markdown notes, ranks Long-horizon/Egocentric/UMI/VLA papers, attaches arXiv and Feishu document links from Lark import reports, and sends a Chinese summary to a Feishu webhook.
- `references/paper-note-spec.md`: Detailed TeX-first single-paper note specification.
