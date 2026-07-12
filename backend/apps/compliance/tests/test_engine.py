"""Unit tests for Sentinel-echo continuous compliance state machine."""

from apps.compliance.engine import (
    CLEAR,
    RESTRICTED,
    SUSPENDED,
    WATCH,
    evaluate_compliance,
)


def test_clear_driver():
    v = evaluate_compliance(0, 0.98, 0.94)
    assert v.state == CLEAR
    assert v.can_dispatch
    assert v.high_value_allowed


def test_watch_on_single_violation():
    v = evaluate_compliance(1, 0.95, 0.90)
    assert v.state == WATCH
    assert v.can_dispatch
    assert v.high_value_allowed


def test_restricted_austin_profile():
    # Seed Austin: viol=4, insp=0.70, ontime=0.60
    v = evaluate_compliance(4, 0.70, 0.60)
    assert v.state == RESTRICTED
    assert v.can_dispatch
    assert not v.high_value_allowed
    assert any("HOS" in r for r in v.reasons)


def test_suspended_on_many_violations():
    v = evaluate_compliance(5, 0.90, 0.90)
    assert v.state == SUSPENDED
    assert not v.can_dispatch
    assert not v.high_value_allowed


def test_suspended_on_low_score():
    v = evaluate_compliance(0, 0.50, 0.40)
    assert v.state == SUSPENDED
