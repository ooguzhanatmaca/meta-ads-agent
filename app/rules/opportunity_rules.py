"""Heuristics that surface data-driven growth opportunities (the agent's "ideas").

Goes beyond cloning winners: finds under-targeted segments, budget reallocation,
scaling candidates and untested angles. Read-only; produces suggestions only.
"""

from typing import Any


def _f(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def best_segment(rows: list[dict[str, Any]], account_roas: float, min_spend: float = 300.0):
    """Return the breakdown segment with the best ROAS above the account average."""
    candidates = [
        r for r in rows
        if _f(r.get("spend")) >= min_spend and _f(r.get("roas")) > account_roas
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: _f(r.get("roas")))


def underspending_winner(rows: list[dict[str, Any]], account_roas: float):
    """A high-ROAS segment that receives a small share of spend (expand candidate)."""
    total_spend = sum(_f(r.get("spend")) for r in rows) or 1.0
    candidates = [
        r for r in rows
        if _f(r.get("roas")) >= account_roas * 1.2
        and _f(r.get("spend")) / total_spend < 0.2
        and _f(r.get("spend")) >= 100
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: _f(r.get("roas")))


def reallocation_candidates(campaigns: list[dict[str, Any]], account_roas: float):
    """Return (scale_up, scale_down) campaign lists for budget reallocation."""
    scale_up = [
        c for c in campaigns
        if _f(c.get("roas")) >= max(account_roas * 1.2, 3.0)
        and _f(c.get("purchases")) >= 3
        and _f(c.get("frequency")) < 3.0
    ]
    scale_down = [
        c for c in campaigns
        if account_roas > 0
        and _f(c.get("roas")) < account_roas * 0.6
        and _f(c.get("spend")) >= 300
    ]
    scale_up.sort(key=lambda c: _f(c.get("roas")), reverse=True)
    scale_down.sort(key=lambda c: _f(c.get("spend")), reverse=True)
    return scale_up[:3], scale_down[:3]


def scaling_candidate(adsets: list[dict[str, Any]]):
    """Best ad set worth duplicating/scaling (high ROAS, headroom on frequency)."""
    candidates = [
        a for a in adsets
        if _f(a.get("roas")) >= 4.0
        and _f(a.get("purchases")) >= 3
        and _f(a.get("frequency")) < 3.0
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda a: _f(a.get("roas")))
