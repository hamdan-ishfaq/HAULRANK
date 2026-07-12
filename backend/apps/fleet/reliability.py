"""Driver reliability (Sentinel-echo) — synthetic compliance signals."""

from __future__ import annotations


def reliability_score(
    hos_violations_90d: int,
    inspection_pass_rate: float,
    on_time_pct: float,
) -> float:
    """Return 0..1. Higher is better."""
    viol_pen = max(0.0, 1.0 - 0.15 * max(0, hos_violations_90d))
    insp = min(1.0, max(0.0, inspection_pass_rate))
    ontime = min(1.0, max(0.0, on_time_pct))
    return round(0.35 * viol_pen + 0.30 * insp + 0.35 * ontime, 3)


def eligible_for_high_value(score: float, rate_usd: float, threshold_usd: float = 2000.0) -> bool:
    """Gate high-value loads when reliability is weak."""
    if rate_usd < threshold_usd:
        return True
    return score >= 0.55
