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
