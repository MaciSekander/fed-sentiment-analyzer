"""Fed Chair tenure eras, used to annotate the historical sentiment timeline.

Single source of truth for chair/date data -- the API serves this list
straight through to the frontend rather than duplicating it as a second
hand-maintained JS constant, so there's exactly one place to update when a
new chair is confirmed.

Dates before Volcker are month/day precision from federalreservehistory.org;
Volcker through Powell are normalized to month boundaries (the exact day
doesn't matter at this chart's granularity); Warsh's start date is exact
(sworn in), verified via web search rather than trusted from training data,
since a chair change this recent is unlikely to be reflected there.
"""

from __future__ import annotations

FED_CHAIRS: list[dict[str, str | None]] = [
    {"chair": "William McChesney Martin Jr.", "start": "1951-04-02", "end": "1970-01-30"},
    {"chair": "Arthur Burns", "start": "1970-01-31", "end": "1978-03-08"},
    {"chair": "G. William Miller", "start": "1978-03-08", "end": "1979-08-06"},
    {"chair": "Paul Volcker", "start": "1979-08-06", "end": "1987-08-31"},
    {"chair": "Alan Greenspan", "start": "1987-09-01", "end": "2006-01-31"},
    {"chair": "Ben Bernanke", "start": "2006-02-01", "end": "2014-01-31"},
    {"chair": "Janet Yellen", "start": "2014-02-01", "end": "2018-02-28"},
    {"chair": "Jerome Powell", "start": "2018-03-01", "end": "2026-05-21"},
    {"chair": "Kevin Warsh", "start": "2026-05-22", "end": None},
]


def chair_for_date(date: str | None) -> str | None:
    """Look up which chair was serving on a given ISO date string."""
    if not date:
        return None
    for era in FED_CHAIRS:
        if date >= era["start"] and (era["end"] is None or date <= era["end"]):
            return era["chair"]
    return None
