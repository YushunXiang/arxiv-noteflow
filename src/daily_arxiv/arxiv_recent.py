from __future__ import annotations

from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from daily_arxiv.models import DateGroup, Paper


ARXIV_BASE_URL = "https://arxiv.org"
USER_AGENT = "daily-arxiv/0.1.0 (+https://arxiv.org)"


class RecentPageError(Exception):
    pass


class DateGroupNotFoundError(RecentPageError):
    pass


def build_recent_url(category: str) -> str:
    return f"{ARXIV_BASE_URL}/list/{category}/recent"


def fetch_recent_page(category: str, timeout: float = 30.0) -> str:
    try:
        response = httpx.get(
            build_recent_url(category),
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RecentPageError(f"Failed to fetch {category} recent page: {exc}") from exc
    return response.text


def parse_recent_page(html: str, category: str) -> list[DateGroup]:
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.select_one("dl#articles")
    if articles is None:
        return []

    groups: list[DateGroup] = []
    current_group: DateGroup | None = None
    pending_dt: Tag | None = None

    for child in articles.children:
        if not isinstance(child, Tag):
            continue

        if child.name == "h3":
            heading = _clean_heading(child.get_text(" ", strip=True))
            current_group = DateGroup(
                date=_parse_heading_date(heading),
                heading=heading,
                category=category,
                papers=[],
            )
            groups.append(current_group)
            pending_dt = None
        elif child.name == "dt":
            pending_dt = child
        elif child.name == "dd" and current_group is not None and pending_dt is not None:
            current_group.papers.append(_parse_paper(pending_dt, child, category, current_group.date))
            pending_dt = None

    return groups


def select_date_group(groups: list[DateGroup], requested_date: str | None = None) -> DateGroup:
    if requested_date is None:
        if groups:
            return groups[0]
        raise DateGroupNotFoundError("No date groups found in recent page")

    for group in groups:
        if group.date == requested_date:
            return group

    category = groups[0].category if groups else "unknown category"
    visible_dates = ", ".join(group.date for group in groups) if groups else "none"
    raise DateGroupNotFoundError(
        f"No entries found for {requested_date} in {category} recent page. "
        f"Visible dates: {visible_dates}"
    )


def _clean_heading(text: str) -> str:
    return text.split("(", maxsplit=1)[0].strip()


def _parse_heading_date(heading: str) -> str:
    return datetime.strptime(heading, "%a, %d %b %Y").date().isoformat()


def _parse_paper(dt: Tag, dd: Tag, category: str, date: str) -> Paper:
    abstract_link = dt.find("a", title="Abstract")
    if not isinstance(abstract_link, Tag):
        raise RecentPageError("Recent page entry is missing an abstract link")

    paper_id = str(abstract_link.get("id") or abstract_link.get_text(strip=True).removeprefix("arXiv:"))
    return Paper(
        id=paper_id,
        title=_parse_title(dd),
        authors=_parse_authors(dd),
        subjects=_parse_subjects(dd),
        category=category,
        date=date,
        abs_url=urljoin(ARXIV_BASE_URL, f"/abs/{paper_id}"),
        src_url=urljoin(ARXIV_BASE_URL, f"/src/{paper_id}"),
    )


def _parse_title(dd: Tag) -> str:
    title = dd.select_one(".list-title")
    if title is None:
        return ""
    return _text_without_descriptor(title)


def _parse_authors(dd: Tag) -> list[str]:
    authors = dd.select_one(".list-authors")
    if authors is None:
        return []
    return [author.get_text(" ", strip=True) for author in authors.find_all("a")]


def _parse_subjects(dd: Tag) -> list[str]:
    subjects = dd.select_one(".list-subjects")
    if subjects is None:
        return []
    text = _text_without_descriptor(subjects)
    return [subject.strip() for subject in text.split(";") if subject.strip()]


def _text_without_descriptor(tag: Tag) -> str:
    tag_copy = BeautifulSoup(str(tag), "html.parser")
    descriptor = tag_copy.select_one(".descriptor")
    if descriptor is not None:
        descriptor.decompose()
    return tag_copy.get_text(" ", strip=True)
