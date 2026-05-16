# daily-arxiv

Download LaTeX source archives from arXiv category recent pages.

The tool reads `https://arxiv.org/list/<category>/recent`, selects a visible date group, downloads each paper's source archive from `https://arxiv.org/src/<id>`, and extracts it.

## Development

```bash
uv sync
uv run pytest
```

## Usage

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

## Output

```text
downloads/
  2026-05-15/
    metadata.jsonl
    archives/
      2605.15157.tar.gz
    sources/
      2605.15157/
```

`--date` only selects dates visible on the current arXiv recent page. It does not search historical archives.
