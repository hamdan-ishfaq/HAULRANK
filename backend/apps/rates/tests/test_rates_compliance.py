from apps.fleet.reliability import eligible_for_high_value, reliability_score
from apps.rates.models import benchmark


def test_reliability_penalizes_violations():
    good = reliability_score(0, 0.98, 0.95)
    bad = reliability_score(5, 0.6, 0.5)
    assert good > bad
    assert 0 <= bad <= 1


def test_high_value_gate():
    assert eligible_for_high_value(0.9, 3000) is True
    assert eligible_for_high_value(0.4, 3000) is False
    assert eligible_for_high_value(0.4, 500) is True


def test_benchmark_flags():
    hist = [2.5, 2.6, 2.55, 2.58, 2.52, 2.57]
    low = benchmark(2.0, hist)
    high = benchmark(3.2, hist)
    mid = benchmark(2.55, hist)
    assert low["flag"] == "below_market"
    assert high["flag"] == "above_market"
    assert mid["flag"] == "typical"
