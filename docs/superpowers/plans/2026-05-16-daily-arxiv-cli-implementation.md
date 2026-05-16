# Daily arXiv CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a uv-managed Python CLI that lists and downloads LaTeX source archives for a selected visible date group on an arXiv category recent page.

**Architecture:** The CLI is a thin Typer layer over focused modules for recent-page parsing, source downloading, archive extraction, and run orchestration. The recent page HTML is the source of truth for date groups; downloads are sequential and idempotent.

**Tech Stack:** Python 3.12, uv, Typer, httpx, BeautifulSoup, pytest.

---

## File Structure

- Create `pyproject.toml`: project metadata, uv dependency declarations, console script entry point, pytest configuration.
- Create `README.md`: concise usage and development commands.
- Create `src/daily_arxiv/__init__.py`: package version.
- Create `src/daily_arxiv/models.py`: dataclasses for `Paper`, `DateGroup`, and `PaperResult`.
- Create `src/daily_arxiv/arxiv_recent.py`: recent URL building, HTML parsing, date selection, page fetching.
- Create `src/daily_arxiv/extractor.py`: safe tar extraction into a per-paper directory.
- Create `src/daily_arxiv/downloader.py`: source archive download, idempotent skip behavior, orchestration, metadata JSONL writing.
- Create `src/daily_arxiv/cli.py`: Typer commands `list` and `download`.
- Create `tests/fixtures/cs_ro_recent.html`: compact representative recent-page HTML with two date groups.
- Create `tests/test_arxiv_recent.py`: parser and date selection tests.
- Create `tests/test_extractor.py`: safe and unsafe archive extraction tests.
- Create `tests/test_downloader.py`: mocked download, skip, metadata, and keep-going tests.
- Create `tests/test_cli.py`: CLI command tests.

## Task 1: Project Scaffold and CLI Smoke Test

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/daily_arxiv/__init__.py`
- Create: `src/daily_arxiv/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI help test**

Create `tests/test_cli.py`:

```python
from typer.testing import CliRunner

from daily_arxiv.cli import app


runner = CliRunner()


def test_help_shows_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "list" in result.output
    assert "download" in result.output
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_cli.py::test_help_shows_commands -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'daily_arxiv'` or a uv project configuration error because the package is not scaffolded yet.

- [ ] **Step 3: Create the minimal uv project and CLI app**

Create `pyproject.toml`:

```toml
[project]
name = "daily-arxiv"
version = "0.1.0"
description = "Download LaTeX source archives from arXiv recent category pages."
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "beautifulsoup4>=4.12.3",
    "httpx>=0.27.0",
    "typer>=0.12.5",
]

[project.scripts]
daily-arxiv = "daily_arxiv.cli:app"

[dependency-groups]
dev = [
    "pytest>=8.3.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

Create `README.md`:

````markdown
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
````

Create `src/daily_arxiv/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/daily_arxiv/cli.py`:

```python
import typer

app = typer.Typer(help="Download LaTeX source archives from arXiv recent pages.")


@app.command("list")
def list_papers(category: str) -> None:
    typer.echo(f"Listing recent papers for {category}")


@app.command()
def download(category: str) -> None:
    typer.echo(f"Downloading recent source archives for {category}")
```

- [ ] **Step 4: Run the smoke test to verify it passes**

Run:

```bash
uv run pytest tests/test_cli.py::test_help_shows_commands -v
```

Expected: PASS.

- [ ] **Step 5: Commit the scaffold**

```bash
git add pyproject.toml README.md src/daily_arxiv/__init__.py src/daily_arxiv/cli.py tests/test_cli.py
git commit -m "feat: scaffold daily arxiv cli"
```

## Task 2: Recent Page Models and HTML Parsing

**Files:**
- Create: `src/daily_arxiv/models.py`
- Create: `src/daily_arxiv/arxiv_recent.py`
- Create: `tests/fixtures/cs_ro_recent.html`
- Create: `tests/test_arxiv_recent.py`

- [ ] **Step 1: Write parser tests and fixture**

Create `tests/fixtures/cs_ro_recent.html`:

```html
<!DOCTYPE html>
<html lang="en">
<body>
<dl id="articles">
  <h3>Fri, 15 May 2026 (showing 2 of 2 entries )</h3>
  <dt>
    <a name="item1">[1]</a>
    <a href="/abs/2605.15157" title="Abstract" id="2605.15157">arXiv:2605.15157</a>
    [<a href="/pdf/2605.15157">pdf</a>, <a href="/format/2605.15157">other</a>]
  </dt>
  <dd>
    <div class="meta">
      <div class="list-title mathjax"><span class="descriptor">Title:</span>
        Hand-in-the-Loop: Improving Dexterous VLA via Seamless Interventional Correction
      </div>
      <div class="list-authors"><a>Zhuohang Li</a>, <a>Liqun Huang</a></div>
      <div class="list-subjects"><span class="descriptor">Subjects:</span>
        <span class="primary-subject">Robotics (cs.RO)</span>; Machine Learning (cs.LG)
      </div>
    </div>
  </dd>
  <dt>
    <a name="item2">[2]</a>
    <a href="/abs/2605.15153" title="Abstract" id="2605.15153">arXiv:2605.15153</a>
    [<a href="/pdf/2605.15153">pdf</a>, <a href="/format/2605.15153">other</a>]
  </dt>
  <dd>
    <div class="meta">
      <div class="list-title mathjax"><span class="descriptor">Title:</span>
        Pelican-Unified 1.0
      </div>
      <div class="list-authors"><a>Yi Zhang</a>, <a>Yinda Chen</a></div>
      <div class="list-subjects"><span class="descriptor">Subjects:</span>
        <span class="primary-subject">Robotics (cs.RO)</span>
      </div>
    </div>
  </dd>
  <h3>Thu, 14 May 2026 (showing 1 of 1 entries )</h3>
  <dt>
    <a name="item3">[3]</a>
    <a href="/abs/2605.14000" title="Abstract" id="2605.14000">arXiv:2605.14000</a>
  </dt>
  <dd>
    <div class="meta">
      <div class="list-title mathjax"><span class="descriptor">Title:</span> Older Robotics Paper</div>
      <div class="list-authors"><a>Ada Lovelace</a></div>
      <div class="list-subjects"><span class="descriptor">Subjects:</span> Robotics (cs.RO)</div>
    </div>
  </dd>
</dl>
</body>
</html>
```

Create `tests/test_arxiv_recent.py`:

```python
from pathlib import Path

import pytest

from daily_arxiv.arxiv_recent import DateGroupNotFoundError, parse_recent_page, select_date_group


FIXTURE = Path(__file__).parent / "fixtures" / "cs_ro_recent.html"


def test_parse_recent_page_groups_papers_by_date() -> None:
    groups = parse_recent_page(FIXTURE.read_text(), category="cs.RO")

    assert [group.date for group in groups] == ["2026-05-15", "2026-05-14"]
    assert groups[0].heading == "Fri, 15 May 2026"
    assert [paper.id for paper in groups[0].papers] == ["2605.15157", "2605.15153"]
    assert groups[0].papers[0].title == "Hand-in-the-Loop: Improving Dexterous VLA via Seamless Interventional Correction"
    assert groups[0].papers[0].authors == ["Zhuohang Li", "Liqun Huang"]
    assert groups[0].papers[0].subjects == ["Robotics (cs.RO)", "Machine Learning (cs.LG)"]
    assert groups[0].papers[0].abs_url == "https://arxiv.org/abs/2605.15157"
    assert groups[0].papers[0].src_url == "https://arxiv.org/src/2605.15157"


def test_select_date_group_defaults_to_first_group() -> None:
    groups = parse_recent_page(FIXTURE.read_text(), category="cs.RO")

    selected = select_date_group(groups)

    assert selected.date == "2026-05-15"


def test_select_date_group_uses_requested_iso_date() -> None:
    groups = parse_recent_page(FIXTURE.read_text(), category="cs.RO")

    selected = select_date_group(groups, requested_date="2026-05-14")

    assert selected.date == "2026-05-14"
    assert [paper.id for paper in selected.papers] == ["2605.14000"]


def test_select_date_group_reports_visible_dates_when_missing() -> None:
    groups = parse_recent_page(FIXTURE.read_text(), category="cs.RO")

    with pytest.raises(DateGroupNotFoundError) as exc_info:
        select_date_group(groups, requested_date="2026-05-13")

    message = str(exc_info.value)
    assert "No entries found for 2026-05-13 in cs.RO recent page" in message
    assert "Visible dates: 2026-05-15, 2026-05-14" in message
```

- [ ] **Step 2: Run parser tests to verify they fail**

Run:

```bash
uv run pytest tests/test_arxiv_recent.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `daily_arxiv.arxiv_recent`.

- [ ] **Step 3: Implement models and parser**

Create `src/daily_arxiv/models.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Paper:
    id: str
    title: str
    authors: list[str]
    subjects: list[str]
    category: str
    date: str
    abs_url: str
    src_url: str


@dataclass(frozen=True)
class DateGroup:
    date: str
    heading: str
    category: str
    papers: list[Paper]


@dataclass(frozen=True)
class PaperResult:
    paper: Paper
    archive_path: str
    source_dir: str
    status: str
    error: str | None = None
```

Create `src/daily_arxiv/arxiv_recent.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Iterable

import httpx
from bs4 import BeautifulSoup, Tag

from daily_arxiv.models import DateGroup, Paper

ARXIV_BASE_URL = "https://arxiv.org"
USER_AGENT = "daily-arxiv/0.1.0 (+https://arxiv.org)"


class RecentPageError(RuntimeError):
    pass


class DateGroupNotFoundError(RecentPageError):
    pass


def build_recent_url(category: str) -> str:
    return f"{ARXIV_BASE_URL}/list/{category}/recent"


def fetch_recent_page(category: str, timeout: float = 30.0) -> str:
    url = build_recent_url(category)
    headers = {"User-Agent": USER_AGENT}
    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise RecentPageError(f"Failed to fetch {url}: HTTP {status}") from exc
    except httpx.HTTPError as exc:
        raise RecentPageError(f"Failed to fetch {url}: {exc}") from exc
    return response.text


def parse_recent_page(html: str, category: str) -> list[DateGroup]:
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.find("dl", id="articles")
    if not isinstance(articles, Tag):
        raise RecentPageError(f"Could not find article list for {category}")

    groups: list[DateGroup] = []
    current_heading: str | None = None
    current_date: str | None = None
    current_papers: list[Paper] = []

    for child in articles.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "h3":
            if current_heading is not None and current_date is not None:
                groups.append(DateGroup(current_date, current_heading, category, current_papers))
            current_heading = _normalize_heading(child.get_text(" ", strip=True))
            current_date = _heading_to_iso_date(current_heading)
            current_papers = []
            continue
        if child.name != "dt" or current_date is None:
            continue

        dd = _next_dd(child)
        if dd is None:
            continue
        current_papers.append(_parse_paper(child, dd, category, current_date))

    if current_heading is not None and current_date is not None:
        groups.append(DateGroup(current_date, current_heading, category, current_papers))

    if not groups:
        raise RecentPageError(f"Could not find date groups for {category}")

    return groups


def select_date_group(groups: Iterable[DateGroup], requested_date: str | None = None) -> DateGroup:
    group_list = list(groups)
    if not group_list:
        raise DateGroupNotFoundError("No date groups were parsed from recent page")
    if requested_date is None:
        return group_list[0]
    for group in group_list:
        if group.date == requested_date:
            return group
    visible_dates = ", ".join(group.date for group in group_list)
    category = group_list[0].category
    raise DateGroupNotFoundError(
        f"No entries found for {requested_date} in {category} recent page. Visible dates: {visible_dates}"
    )


def _normalize_heading(text: str) -> str:
    return text.split("(", 1)[0].strip()


def _heading_to_iso_date(heading: str) -> str:
    parsed = datetime.strptime(heading, "%a, %d %b %Y")
    return parsed.date().isoformat()


def _next_dd(dt: Tag) -> Tag | None:
    sibling = dt.find_next_sibling()
    while sibling is not None:
        if isinstance(sibling, Tag) and sibling.name == "dd":
            return sibling
        if isinstance(sibling, Tag) and sibling.name in {"dt", "h3"}:
            return None
        sibling = sibling.find_next_sibling()
    return None


def _parse_paper(dt: Tag, dd: Tag, category: str, date: str) -> Paper:
    abs_link = dt.find("a", href=lambda value: isinstance(value, str) and value.startswith("/abs/"))
    if not isinstance(abs_link, Tag):
        raise RecentPageError(f"Could not parse paper id in {category} for {date}")
    paper_id = abs_link.get("id") or abs_link.get_text(" ", strip=True).removeprefix("arXiv:")
    paper_id = str(paper_id).strip()
    return Paper(
        id=paper_id,
        title=_clean_descriptor(dd, "list-title"),
        authors=[a.get_text(" ", strip=True) for a in dd.select(".list-authors a")],
        subjects=_parse_subjects(dd),
        category=category,
        date=date,
        abs_url=f"{ARXIV_BASE_URL}/abs/{paper_id}",
        src_url=f"{ARXIV_BASE_URL}/src/{paper_id}",
    )


def _clean_descriptor(dd: Tag, class_name: str) -> str:
    node = dd.find(class_=class_name)
    if not isinstance(node, Tag):
        return ""
    descriptor = node.find(class_="descriptor")
    if isinstance(descriptor, Tag):
        descriptor.extract()
    return " ".join(node.get_text(" ", strip=True).split())


def _parse_subjects(dd: Tag) -> list[str]:
    node = dd.find(class_="list-subjects")
    if not isinstance(node, Tag):
        return []
    descriptor = node.find(class_="descriptor")
    if isinstance(descriptor, Tag):
        descriptor.extract()
    text = " ".join(node.get_text(" ", strip=True).split())
    return [part.strip() for part in text.split(";") if part.strip()]
```

- [ ] **Step 4: Run parser tests to verify they pass**

Run:

```bash
uv run pytest tests/test_arxiv_recent.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit parser work**

```bash
git add src/daily_arxiv/models.py src/daily_arxiv/arxiv_recent.py tests/fixtures/cs_ro_recent.html tests/test_arxiv_recent.py
git commit -m "feat: parse arxiv recent date groups"
```

## Task 3: Safe Archive Extraction

**Files:**
- Create: `src/daily_arxiv/extractor.py`
- Create: `tests/test_extractor.py`

- [ ] **Step 1: Write extraction tests**

Create `tests/test_extractor.py`:

```python
import io
import tarfile

import pytest

from daily_arxiv.extractor import UnsafeArchiveError, extract_archive


def _write_tar(path, members: dict[str, bytes]) -> None:
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def test_extract_archive_creates_target_directory(tmp_path) -> None:
    archive = tmp_path / "paper.tar.gz"
    target = tmp_path / "sources" / "2605.15157"
    _write_tar(archive, {"main.tex": b"\\documentclass{article}"})

    result = extract_archive(archive, target)

    assert result == target
    assert (target / "main.tex").read_bytes() == b"\\documentclass{article}"


def test_extract_archive_skips_existing_non_empty_directory(tmp_path) -> None:
    archive = tmp_path / "paper.tar.gz"
    target = tmp_path / "sources" / "2605.15157"
    target.mkdir(parents=True)
    (target / "main.tex").write_text("existing")
    _write_tar(archive, {"main.tex": b"new"})

    result = extract_archive(archive, target)

    assert result == target
    assert (target / "main.tex").read_text() == "existing"


def test_extract_archive_rejects_path_traversal(tmp_path) -> None:
    archive = tmp_path / "bad.tar.gz"
    target = tmp_path / "sources" / "2605.15157"
    _write_tar(archive, {"../escape.tex": b"bad"})

    with pytest.raises(UnsafeArchiveError):
        extract_archive(archive, target)

    assert not (tmp_path / "escape.tex").exists()
```

- [ ] **Step 2: Run extraction tests to verify they fail**

Run:

```bash
uv run pytest tests/test_extractor.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `daily_arxiv.extractor`.

- [ ] **Step 3: Implement safe extraction**

Create `src/daily_arxiv/extractor.py`:

```python
from __future__ import annotations

from pathlib import Path
import tarfile


class UnsafeArchiveError(RuntimeError):
    pass


def extract_archive(archive_path: Path, target_dir: Path) -> Path:
    archive_path = Path(archive_path)
    target_dir = Path(target_dir)
    if target_dir.exists() and any(target_dir.iterdir()):
        return target_dir

    target_dir.mkdir(parents=True, exist_ok=True)
    target_root = target_dir.resolve()
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            member_path = (target_root / member.name).resolve()
            if not _is_relative_to(member_path, target_root):
                raise UnsafeArchiveError(f"Archive member escapes target directory: {member.name}")
        tar.extractall(target_root)
    return target_dir


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
```

- [ ] **Step 4: Run extraction tests to verify they pass**

Run:

```bash
uv run pytest tests/test_extractor.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit extractor work**

```bash
git add src/daily_arxiv/extractor.py tests/test_extractor.py
git commit -m "feat: add safe archive extraction"
```

## Task 4: Source Archive Downloading

**Files:**
- Create: `src/daily_arxiv/downloader.py`
- Create: `tests/test_downloader.py`

- [ ] **Step 1: Write archive download tests**

Create `tests/test_downloader.py`:

```python
import httpx
import pytest

from daily_arxiv.downloader import DownloadError, download_source_archive
from daily_arxiv.models import Paper


def _paper() -> Paper:
    return Paper(
        id="2605.15157",
        title="Hand-in-the-Loop",
        authors=["Zhuohang Li"],
        subjects=["Robotics (cs.RO)"],
        category="cs.RO",
        date="2026-05-15",
        abs_url="https://arxiv.org/abs/2605.15157",
        src_url="https://arxiv.org/src/2605.15157",
    )


def test_download_source_archive_writes_temp_then_final_file(tmp_path) -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, content=b"archive-bytes")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    archive_path, status = download_source_archive(_paper(), tmp_path, client)

    assert status == "downloaded"
    assert archive_path == tmp_path / "archives" / "2605.15157.tar.gz"
    assert archive_path.read_bytes() == b"archive-bytes"
    assert seen_urls == ["https://arxiv.org/src/2605.15157"]
    assert not list(archive_path.parent.glob("*.tmp"))


def test_download_source_archive_skips_existing_non_empty_file(tmp_path) -> None:
    archive_dir = tmp_path / "archives"
    archive_dir.mkdir()
    archive_path = archive_dir / "2605.15157.tar.gz"
    archive_path.write_bytes(b"existing")

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP should not be called when archive exists")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result_path, status = download_source_archive(_paper(), tmp_path, client)

    assert status == "skipped"
    assert result_path == archive_path
    assert archive_path.read_bytes() == b"existing"


def test_download_source_archive_raises_for_http_error(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"missing")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(DownloadError) as exc_info:
        download_source_archive(_paper(), tmp_path, client)

    assert "Failed to download https://arxiv.org/src/2605.15157: HTTP 404" in str(exc_info.value)
```

- [ ] **Step 2: Run downloader tests to verify they fail**

Run:

```bash
uv run pytest tests/test_downloader.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `daily_arxiv.downloader`.

- [ ] **Step 3: Implement archive downloading**

Create `src/daily_arxiv/downloader.py`:

```python
from __future__ import annotations

from pathlib import Path
import os
import time

import httpx

from daily_arxiv.models import DateGroup, Paper, PaperResult

USER_AGENT = "daily-arxiv/0.1.0 (+https://arxiv.org)"


class DownloadError(RuntimeError):
    pass


def archive_path_for(paper: Paper, output_dir: Path) -> Path:
    return Path(output_dir) / "archives" / f"{paper.id}.tar.gz"


def source_dir_for(paper: Paper, output_dir: Path) -> Path:
    return Path(output_dir) / "sources" / paper.id


def download_source_archive(paper: Paper, output_dir: Path, client: httpx.Client) -> tuple[Path, str]:
    archive_path = archive_path_for(paper, output_dir)
    if archive_path.exists() and archive_path.stat().st_size > 0:
        return archive_path, "skipped"

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = archive_path.with_suffix(archive_path.suffix + ".tmp")
    headers = {"User-Agent": USER_AGENT}
    try:
        with client.stream("GET", paper.src_url, headers=headers) as response:
            if response.status_code != 200:
                raise DownloadError(f"Failed to download {paper.src_url}: HTTP {response.status_code}")
            with tmp_path.open("wb") as file:
                for chunk in response.iter_bytes():
                    if chunk:
                        file.write(chunk)
    except httpx.HTTPError as exc:
        raise DownloadError(f"Failed to download {paper.src_url}: {exc}") from exc

    os.replace(tmp_path, archive_path)
    return archive_path, "downloaded"
```

- [ ] **Step 4: Run downloader tests to verify they pass**

Run:

```bash
uv run pytest tests/test_downloader.py -v
```

Expected: PASS for the three download tests.

- [ ] **Step 5: Commit download work**

```bash
git add src/daily_arxiv/downloader.py tests/test_downloader.py
git commit -m "feat: download source archives"
```

## Task 5: Download Orchestration, Extraction, and Metadata

**Files:**
- Modify: `src/daily_arxiv/downloader.py`
- Modify: `tests/test_downloader.py`

- [ ] **Step 1: Add orchestration tests**

Append to `tests/test_downloader.py`:

```python
import json
import tarfile
from io import BytesIO

from daily_arxiv.downloader import download_group
from daily_arxiv.models import DateGroup


def _tar_bytes() -> bytes:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        data = b"content"
        info = tarfile.TarInfo("main.tex")
        info.size = len(data)
        tar.addfile(info, BytesIO(data))
    return buffer.getvalue()


def test_download_group_downloads_extracts_and_writes_metadata(tmp_path) -> None:
    paper = _paper()
    group = DateGroup(date="2026-05-15", heading="Fri, 15 May 2026", category="cs.RO", papers=[paper])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_tar_bytes())

    client = httpx.Client(transport=httpx.MockTransport(handler))

    results = download_group(group, tmp_path, client=client, delay=0, keep_going=False)

    date_dir = tmp_path / "2026-05-15"
    assert results[0].status == "downloaded"
    assert (date_dir / "archives" / "2605.15157.tar.gz").exists()
    assert (date_dir / "sources" / "2605.15157" / "main.tex").read_text() == "content"
    records = [json.loads(line) for line in (date_dir / "metadata.jsonl").read_text().splitlines()]
    assert records == [
        {
            "id": "2605.15157",
            "title": "Hand-in-the-Loop",
            "authors": ["Zhuohang Li"],
            "subjects": ["Robotics (cs.RO)"],
            "date": "2026-05-15",
            "category": "cs.RO",
            "abs_url": "https://arxiv.org/abs/2605.15157",
            "src_url": "https://arxiv.org/src/2605.15157",
            "archive_path": str(date_dir / "archives" / "2605.15157.tar.gz"),
            "source_dir": str(date_dir / "sources" / "2605.15157"),
            "status": "downloaded",
            "error": None,
        }
    ]


def test_download_group_keep_going_records_failure(tmp_path) -> None:
    group = DateGroup(date="2026-05-15", heading="Fri, 15 May 2026", category="cs.RO", papers=[_paper()])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"error")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    results = download_group(group, tmp_path, client=client, delay=0, keep_going=True)

    assert results[0].status == "failed"
    assert "HTTP 500" in str(results[0].error)
    records = [json.loads(line) for line in (tmp_path / "2026-05-15" / "metadata.jsonl").read_text().splitlines()]
    assert records[0]["status"] == "failed"
    assert "HTTP 500" in records[0]["error"]
```

- [ ] **Step 2: Run orchestration tests to verify they fail**

Run:

```bash
uv run pytest tests/test_downloader.py::test_download_group_downloads_extracts_and_writes_metadata tests/test_downloader.py::test_download_group_keep_going_records_failure -v
```

Expected: FAIL with `ImportError` for `download_group`.

- [ ] **Step 3: Implement orchestration and metadata writing**

Append to `src/daily_arxiv/downloader.py`:

```python
import json

from daily_arxiv.extractor import extract_archive


def download_group(
    group: DateGroup,
    output_root: Path,
    client: httpx.Client | None = None,
    delay: float = 3.0,
    keep_going: bool = False,
) -> list[PaperResult]:
    date_dir = Path(output_root) / group.date
    date_dir.mkdir(parents=True, exist_ok=True)
    owns_client = client is None
    if client is None:
        client = httpx.Client(timeout=30.0)

    results: list[PaperResult] = []
    try:
        for index, paper in enumerate(group.papers):
            try:
                archive_path, status = download_source_archive(paper, date_dir, client)
                source_dir = source_dir_for(paper, date_dir)
                extract_archive(archive_path, source_dir)
                results.append(PaperResult(paper, str(archive_path), str(source_dir), status))
            except Exception as exc:
                result = PaperResult(paper, str(archive_path_for(paper, date_dir)), str(source_dir_for(paper, date_dir)), "failed", str(exc))
                results.append(result)
                if not keep_going:
                    _write_metadata(date_dir / "metadata.jsonl", results)
                    raise
            if delay > 0 and index < len(group.papers) - 1:
                time.sleep(delay)
    finally:
        if owns_client:
            client.close()

    _write_metadata(date_dir / "metadata.jsonl", results)
    return results


def _write_metadata(path: Path, results: list[PaperResult]) -> None:
    lines = [json.dumps(_metadata_record(result), ensure_ascii=False) for result in results]
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def _metadata_record(result: PaperResult) -> dict[str, object]:
    paper = result.paper
    return {
        "id": paper.id,
        "title": paper.title,
        "authors": paper.authors,
        "subjects": paper.subjects,
        "date": paper.date,
        "category": paper.category,
        "abs_url": paper.abs_url,
        "src_url": paper.src_url,
        "archive_path": result.archive_path,
        "source_dir": result.source_dir,
        "status": result.status,
        "error": result.error,
    }
```

- [ ] **Step 4: Run downloader tests to verify they pass**

Run:

```bash
uv run pytest tests/test_downloader.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit orchestration work**

```bash
git add src/daily_arxiv/downloader.py tests/test_downloader.py
git commit -m "feat: orchestrate source downloads"
```

## Task 6: Real CLI Behavior

**Files:**
- Modify: `src/daily_arxiv/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Replace smoke test with CLI behavior tests**

Replace `tests/test_cli.py` with:

```python
from typer.testing import CliRunner

from daily_arxiv import cli
from daily_arxiv.models import DateGroup, Paper, PaperResult


runner = CliRunner()


def _group() -> DateGroup:
    paper = Paper(
        id="2605.15157",
        title="Hand-in-the-Loop",
        authors=["Zhuohang Li"],
        subjects=["Robotics (cs.RO)"],
        category="cs.RO",
        date="2026-05-15",
        abs_url="https://arxiv.org/abs/2605.15157",
        src_url="https://arxiv.org/src/2605.15157",
    )
    return DateGroup(date="2026-05-15", heading="Fri, 15 May 2026", category="cs.RO", papers=[paper])


def test_help_shows_commands() -> None:
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "list" in result.output
    assert "download" in result.output


def test_list_prints_selected_group(monkeypatch) -> None:
    monkeypatch.setattr(cli, "fetch_recent_page", lambda category, timeout: "<html></html>")
    monkeypatch.setattr(cli, "parse_recent_page", lambda html, category: [_group()])
    monkeypatch.setattr(cli, "select_date_group", lambda groups, requested_date=None: groups[0])

    result = runner.invoke(cli.app, ["list", "cs.RO"])

    assert result.exit_code == 0
    assert "cs.RO 2026-05-15 Fri, 15 May 2026" in result.output
    assert "2605.15157  Hand-in-the-Loop" in result.output


def test_download_invokes_downloader(monkeypatch, tmp_path) -> None:
    group = _group()
    monkeypatch.setattr(cli, "fetch_recent_page", lambda category, timeout: "<html></html>")
    monkeypatch.setattr(cli, "parse_recent_page", lambda html, category: [group])
    monkeypatch.setattr(cli, "select_date_group", lambda groups, requested_date=None: group)

    def fake_download_group(selected_group, output_root, delay, keep_going):
        assert selected_group == group
        assert output_root == tmp_path
        assert delay == 0.0
        assert keep_going is True
        paper = group.papers[0]
        return [PaperResult(paper, str(tmp_path / "archive.tar.gz"), str(tmp_path / "source"), "downloaded")]

    monkeypatch.setattr(cli, "download_group", fake_download_group)

    result = runner.invoke(
        cli.app,
        ["download", "cs.RO", "--output", str(tmp_path), "--delay", "0", "--keep-going"],
    )

    assert result.exit_code == 0
    assert "Downloaded: 1" in result.output
    assert "Skipped: 0" in result.output
    assert "Failed: 0" in result.output


def test_download_returns_nonzero_when_keep_going_has_failures(monkeypatch, tmp_path) -> None:
    group = _group()
    monkeypatch.setattr(cli, "fetch_recent_page", lambda category, timeout: "<html></html>")
    monkeypatch.setattr(cli, "parse_recent_page", lambda html, category: [group])
    monkeypatch.setattr(cli, "select_date_group", lambda groups, requested_date=None: group)

    def fake_download_group(selected_group, output_root, delay, keep_going):
        paper = selected_group.papers[0]
        return [PaperResult(paper, str(tmp_path / "archive.tar.gz"), str(tmp_path / "source"), "failed", "HTTP 500")]

    monkeypatch.setattr(cli, "download_group", fake_download_group)

    result = runner.invoke(cli.app, ["download", "cs.RO", "--output", str(tmp_path), "--keep-going"])

    assert result.exit_code == 1
    assert "Failed: 1" in result.output
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
uv run pytest tests/test_cli.py -v
```

Expected: FAIL because `cli.py` still contains temporary command behavior.

- [ ] **Step 3: Implement CLI commands**

Replace `src/daily_arxiv/cli.py` with:

```python
from __future__ import annotations

from pathlib import Path

import typer

from daily_arxiv.arxiv_recent import fetch_recent_page, parse_recent_page, select_date_group
from daily_arxiv.downloader import download_group

app = typer.Typer(help="Download LaTeX source archives from arXiv recent pages.")


@app.command("list")
def list_papers(
    category: str,
    date: str | None = typer.Option(None, "--date", help="Visible recent-page date in YYYY-MM-DD format."),
    timeout: float = typer.Option(30.0, "--timeout", help="HTTP timeout in seconds."),
) -> None:
    html = fetch_recent_page(category, timeout=timeout)
    group = select_date_group(parse_recent_page(html, category), requested_date=date)
    typer.echo(f"{group.category} {group.date} {group.heading}")
    for paper in group.papers:
        typer.echo(f"{paper.id}  {paper.title}")


@app.command()
def download(
    category: str,
    date: str | None = typer.Option(None, "--date", help="Visible recent-page date in YYYY-MM-DD format."),
    output: Path = typer.Option(Path("downloads"), "--output", help="Output root directory."),
    delay: float = typer.Option(3.0, "--delay", help="Delay between source archive downloads in seconds."),
    timeout: float = typer.Option(30.0, "--timeout", help="HTTP timeout in seconds."),
    keep_going: bool = typer.Option(False, "--keep-going", help="Continue after individual paper failures."),
) -> None:
    html = fetch_recent_page(category, timeout=timeout)
    group = select_date_group(parse_recent_page(html, category), requested_date=date)
    results = download_group(group, output, delay=delay, keep_going=keep_going)
    downloaded = sum(1 for result in results if result.status == "downloaded")
    skipped = sum(1 for result in results if result.status == "skipped")
    failed = sum(1 for result in results if result.status == "failed")
    typer.echo(f"{group.category} {group.date} {group.heading}")
    typer.echo(f"Downloaded: {downloaded}")
    typer.echo(f"Skipped: {skipped}")
    typer.echo(f"Failed: {failed}")
    if failed:
        raise typer.Exit(1)
```

- [ ] **Step 4: Run CLI tests to verify they pass**

Run:

```bash
uv run pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit CLI work**

```bash
git add src/daily_arxiv/cli.py tests/test_cli.py
git commit -m "feat: wire real cli commands"
```

## Task 7: Final Verification and Documentation

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`

- [ ] **Step 1: Update README usage details**

Replace `README.md` with:

````markdown
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
````

- [ ] **Step 2: Run full test suite**

Run:

```bash
uv run pytest -v
```

Expected: PASS for all tests.

- [ ] **Step 3: Run CLI help manually**

Run:

```bash
uv run daily-arxiv --help
```

Expected: exit code 0 and visible `list` and `download` commands.

- [ ] **Step 4: Run parser command against live arXiv**

Run:

```bash
uv run daily-arxiv list cs.RO
```

Expected: exit code 0, a visible date heading, and one or more arXiv IDs. Do not require this command in automated tests.

- [ ] **Step 5: Check git status**

Run:

```bash
git status --short
```

Expected: only intentional README or lockfile changes are present.

- [ ] **Step 6: Commit final docs and lockfile changes**

```bash
git add README.md pyproject.toml uv.lock
git commit -m "docs: document daily arxiv usage"
```
