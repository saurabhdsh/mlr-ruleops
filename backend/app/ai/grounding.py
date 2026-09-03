from __future__ import annotations

import re
from typing import Any

from app.rules.dsl import ChangeIntent


def ground_intent_citations(intent: ChangeIntent, title: str, description: str, citations: list[Any]) -> ChangeIntent:
    """Resolve free-text citation mentions to catalog IDs. Does not invent IDs."""
    text = f"{title}\n{description}"
    by_id = {c.citation_id: c for c in citations if getattr(c, "citation_id", None)}
    mentioned_ids = [cid for cid in by_id if cid in text]
    years = set(re.findall(r"\b(?:19|20)\d{2}\b", text))
    by_year: dict[str, list[Any]] = {}
    for c in citations:
        by_year.setdefault(str(c.year), []).append(c)
    for year in by_year:
        by_year[year] = sorted(by_year[year], key=lambda c: c.citation_id)

    def pick(year: str | None) -> str | None:
        if not year:
            return None
        for cid in mentioned_ids:
            if str(by_id[cid].year) == year:
                return cid
        rows = by_year.get(year) or []
        return rows[0].citation_id if rows else None

    add = intent.citation_to_add
    remove = intent.citation_to_remove
    if add and add not in by_id:
        found = re.findall(r"\b(?:19|20)\d{2}\b", add)
        add = pick(found[0]) if found else None
    if remove and remove not in by_id:
        found = re.findall(r"\b(?:19|20)\d{2}\b", remove)
        remove = pick(found[0]) if found else None

    lower = text.lower()
    if not remove and re.search(r"\b(remove|replace|retire|withdraw)\b", lower):
        for year in sorted(years):
            if add and add in by_id and str(by_id[add].year) == year:
                continue
            if year in lower:
                remove = pick(year)
                if remove:
                    break
    if not add and re.search(r"\b(add|include|new|update)\b", lower):
        for year in sorted(years, reverse=True):
            if remove and remove in by_id and str(by_id[remove].year) == year:
                continue
            add = pick(year)
            if add:
                break

    intent.citation_to_add = add
    intent.citation_to_remove = remove
    return intent
