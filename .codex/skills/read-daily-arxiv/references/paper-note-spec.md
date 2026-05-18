# TeX-First Paper Note Specification

Load this reference when writing per-paper notes for `$read-daily-arxiv`.

## Inputs

- A manifest paper object with at least `id`, `abs_url`, `pdf_url`, `source_dir`, and metadata from `metadata.jsonl`.
- Optional exact `output_note_path`; when provided, update that file and do not create another.
- Optional `output_dir`; default is the manifest `suggested_notes_root`.
- Optional `output_language`; default `zh-CN`.

## Derived Paths

If `output_note_path` is not provided:

- `paper_name`: title-derived sanitized name, falling back to `arxiv_{id}`.
- `paper_dir = {output_dir}/{paper_name}`
- `note_path = {paper_dir}/{paper_name}.md`
- `assets_dir = {paper_dir}/assets`

If `output_note_path` is provided:

- `note_path = output_note_path`
- `paper_dir = dirname(output_note_path)`
- `assets_dir = {paper_dir}/assets`

All generated assets go under `assets_dir` unless the user explicitly overrides it.

## Title and Filename

Prefer the title from TeX `\title{...}`; fall back to manifest title, then `arxiv_{id}`.

Sanitize `paper_name`:

1. Strip common LaTeX formatting commands and inline math best effort.
2. Replace forbidden filename chars `\/:*?"<>|` and control chars with `-`.
3. Collapse whitespace and repeated separators to a single `-`.
4. Trim leading/trailing `-`, `_`, `.`, and spaces.
5. Kebab-case by default; cap at 80 characters.
6. Fall back to `arxiv_{id}` if the result is empty.

## Reading Source

1. Prefer `00README.json` `usage: "toplevel"` files, then common names such as `main.tex`, `paper.tex`, `manuscript.tex`, `root.tex`.
2. If multiple candidates exist, choose a file with `\title`, `\author`, `\begin{document}`, and the most `\input`/`\include` references.
3. Recursively inline `\input{...}` and `\include{...}`. Resolve extensionless TeX paths by trying `.tex`.
4. Capture abstract, problem framing, contributions, method, training details, evaluation setup, results, limitations, and open questions.
5. Ignore binary files unless needed for figure extraction.

## Tables

Find candidate tables from:

- `\begin{table}...\end{table}`
- `\begin{tabular}...\end{tabular}`
- TeX table files referenced by `\input`

For each useful experimental table:

- Extract caption when available.
- Convert simple tabulars to Markdown with `&` as columns and `\\` as rows.
- Strip `\hline`, `\toprule`, `\midrule`, `\bottomrule`, simple formatting commands, and citations where they obscure values.
- If conversion is unsafe because of `multicolumn`, `multirow`, nested tabulars, or heavy macros, include a fenced raw LaTeX table and state the conversion reason.

Normalize these tables when the information exists:

| 表格类型 | 列 |
| --- | --- |
| 数据集与基准 | 数据集, 任务, 划分, 指标, 备注 |
| 主要结果 | 数据集, 指标, 基线, 本文方法, 差值 |
| 训练与计算 | 项目, 数值 |

Only include numeric values present in source text or tables.

## Pipeline Figure

Default behavior:

- `extract_pipeline_figure = true`
- `max_pipeline_figures = 1`
- `figure_output_dir = assets_dir`
- `figure_fallback_pdf = true`
- `figure_raster_dpi = 250`
- `figure_min_width_px = 800`

Candidate keywords:

```text
pipeline, framework, overview, architecture, method, model, proposed,
system, approach, workflow, diagram,
框架, 总体, 架构, 方法, 流程, 系统, 概览
```

TeX-first extraction:

1. Collect `figure` and `figure*` blocks.
2. Extract `caption`, `label`, and `\includegraphics` paths.
3. Resolve image paths by trying the literal path and extensions `.pdf`, `.png`, `.jpg`, `.jpeg`, `.eps`, `.svg`.
4. Score candidates:
   - `+5` per caption keyword hit
   - `+3` per label keyword hit
   - `+2` per filename keyword hit
   - `+2` for explicit overview/framework/architecture wording or Chinese synonyms
   - `-5` for likely unrelated dataset, qualitative, attention-map, or benchmark-only figures unless also pipeline-like
   - prefer larger images when dimensions are available
5. Copy or rasterize the top candidate to `assets_dir/pipeline_{arxiv_id}.{ext}`. If it exists, append `_2`, `_3`, etc.
6. For vector formats, also create a PNG when a local tool is available (`magick`, `convert`, `pdftoppm`, `rsvg-convert`, or similar).
7. Record relative `pipeline_figure`, `pipeline_caption`, and `pipeline_source`.

PDF fallback:

- Trigger only when no suitable TeX figure is found and `figure_fallback_pdf` is true.
- Prefer extracting embedded images from the cached/downloaded PDF and filter out tiny images.
- If image extraction fails, render a likely page containing `Figure` plus pipeline keywords.
- Mark `pipeline_source` as `PDF fallback` and state whether it is an extracted image or rendered page.

Do not claim a figure is the pipeline unless caption, label, or filename strongly supports it.

## Markdown Note

Write or overwrite exactly `note_path`. Preserve this block verbatim if already present:

```md
<!-- USER_NOTES_START -->
...
<!-- USER_NOTES_END -->
```

Use YAML frontmatter:

```yaml
---
title: "..."
authors: ["...", "..."]
arxiv_id: "..."
arxiv_url: "..."
pdf_url: "..."
published: YYYY-MM-DD
updated: YYYY-MM-DD
categories: ["cs.RO"]
tags: ["paper/arxiv", "status/read"]
status: "read"
code: ""
datasets: ["..."]
pipeline_figure: "assets/pipeline_XXXX.XXXXX.png"
pipeline_caption: "..."
pipeline_source: "..."
---
```

Use this exact body section order with Simplified Chinese headings. Do not leave English template labels in headings:

1. `## 简短总结`
   - 3-6 bullets.
2. `## 核心贡献`
3. `## 方法`
   - Prefer compact pseudocode or process bullets.
4. `## 流程图`
   - If present: `![[assets/pipeline_XXXX.XXXXX.png]]`
   - Include `图注：...` and `来源：...`, both written in Chinese. Translate source captions instead of pasting them verbatim; keep the original figure label or file path only as an identifier when useful.
5. `## 实验`
   - Include dataset, main result, and ablation/analysis tables when present.
6. `## 局限性与注意事项`
7. `## 可落地实现想法`
   - 2-5 practical ideas.
8. `## 开放问题与后续跟进`
9. `## 引用`
   - BibTeX if available, otherwise an arXiv citation line.

## Language Policy

- YAML frontmatter is the only default language exception. Write all content after the closing frontmatter `---` in Simplified Chinese by default, including headings, bullets, prose, table labels, figure-caption explanations, and source notes.
- Keep proper nouns, dataset names, metric names, model names, code identifiers, formulas, and numeric values in original form when needed.
- On first mention of a technical term, use Chinese plus original term when helpful, such as `对比学习（contrastive learning）`.
- If source text is ambiguous, include a short quoted source snippet only when needed, prefix it with `原文：`, and explain the ambiguity in Chinese.
- Do not leave English template labels such as `TL;DR`, `Pipeline Figure`, `Benchmarks`, `Main Results`, `Dataset`, `Task`, `Metric`, `Notes`, `Baseline`, `Ours`, `Delta`, `Item`, or `Value` in the body.

## Quality Checks

- Verify `note_path` exists and is non-empty.
- Verify frontmatter parses visually as YAML and includes arXiv id and URLs.
- Verify all Markdown content after the closing frontmatter `---` follows the language policy above.
- Verify every reported metric/value is backed by source text or a table.
- Verify asset links are relative to the note and point to existing files.
- Summarize any missing source, failed figure extraction, or skipped paper in the final response.
