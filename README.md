# daily-arxiv

Download LaTeX source archives from arXiv category recent pages.

## Development

```bash
uv sync
uv run pytest
```

## Usage

```bash
uv run daily-arxiv list cs.RO
uv run daily-arxiv download cs.RO
uv run daily-arxiv download cs.RO --date 2026-05-15
```
