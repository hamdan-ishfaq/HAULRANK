"""Sentinel-echo continuous compliance — pure rules, no ORM, no LLM.

States (strictest wins):
  clear      → full dispatch eligibility
  watch      → eligible; elevated monitoring badge
  restricted → high-value loads gated (same bar as reliability gate)
  suspended  → no new assignments / rank refused

This only *revokes eligibility*. It never auto-accepts, auto-assigns, or
moves freight — Spotter Sentinel-shaped monitoring, not autonomy.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.fleet.reliability import reliability_score

CLEAR = "clear"
WATCH = "watch"
RESTRICTED = "restricted"
SUSPENDED = "suspended"

STATES = (CLEAR, WATCH, RESTRICTED, SUSPENDED)


@dataclass(frozen=True)
class ComplianceVerdict:
    state: str
    score: float
    reasons: tuple[str, ...]

    @property
    def can_dispatch(self) -> bool:
        return self.state != SUSPENDED

    @property
    def high_value_allowed(self) -> bool:
        return self.state in (CLEAR, WATCH)


def evaluate_compliance(
    hos_violations_90d: int,
    inspection_pass_rate: float,
    on_time_pct: float,
) -> ComplianceVerdict:
    score = reliability_score(hos_violations_90d, inspection_pass_rate, on_time_pct)
    reasons: list[str] = []

    if hos_violations_90d >= 5:
        reasons.append(f"HOS violations_90d={hos_violations_90d} ≥ 5")
    if inspection_pass_rate < 0.65:
        reasons.append(f"inspection_pass_rate={inspection_pass_rate:.2f} < 0.65")
    if score < 0.40:
        reasons.append(f"reliability_score={score} < 0.40")
    if reasons:
        return ComplianceVerdict(SUSPENDED, score, tuple(reasons))

    reasons = []
    if hos_violations_90d >= 3:
        reasons.append(f"HOS violations_90d={hos_violations_90d} ≥ 3")
    if inspection_pass_rate < 0.80:
        reasons.append(f"inspection_pass_rate={inspection_pass_rate:.2f} < 0.80")
    if score < 0.55:
        reasons.append(f"reliability_score={score} < 0.55")
    if on_time_pct < 0.70:
        reasons.append(f"on_time_pct={on_time_pct:.2f} < 0.70")
    if reasons:
        return ComplianceVerdict(RESTRICTED, score, tuple(reasons))

    reasons = []
    if hos_violations_90d >= 1:
        reasons.append(f"HOS violations_90d={hos_violations_90d} ≥ 1")
    if score < 0.75:
        reasons.append(f"reliability_score={score} < 0.75")
    if inspection_pass_rate < 0.90:
        reasons.append(f"inspection_pass_rate={inspection_pass_rate:.2f} < 0.90")
    if reasons:
        return ComplianceVerdict(WATCH, score, tuple(reasons))

    return ComplianceVerdict(CLEAR, score, ())
