"""Regression: analysis timeout must scale with graph size.

Bug: A-share runs (7 analysts) hit the hardcoded 30-minute limit before
completing, because the timeout was sized for the 4-analyst US graph.
The fix scales the timeout with analyst count and debate depth.
"""

import pytest
from tradingagents_api.runner import compute_analysis_timeout_minutes


class TestComputeAnalysisTimeoutMinutes:
    def test_astock_seven_analysts_exceeds_thirty(self):
        """7 analysts at medium depth (3 rounds) must get more than 30 min."""
        timeout = compute_analysis_timeout_minutes(n_analysts=7, debate_rounds=3, risk_rounds=3)
        assert timeout > 30

    def test_us_four_analysts_keeps_thirty(self):
        """4 analysts at medium depth keeps the historical 30-min baseline."""
        timeout = compute_analysis_timeout_minutes(n_analysts=4, debate_rounds=3, risk_rounds=3)
        assert timeout >= 30

    def test_minimum_never_below_thirty(self):
        """Even a trivial graph gets at least 30 minutes."""
        timeout = compute_analysis_timeout_minutes(n_analysts=1, debate_rounds=1, risk_rounds=1)
        assert timeout >= 30

    def test_scales_with_analyst_count(self):
        more_analysts = compute_analysis_timeout_minutes(7, 3, 3)
        fewer_analysts = compute_analysis_timeout_minutes(4, 3, 3)
        assert more_analysts > fewer_analysts

    def test_deep_mode_gets_more_time(self):
        shallow = compute_analysis_timeout_minutes(7, 1, 1)
        deep = compute_analysis_timeout_minutes(7, 5, 5)
        assert deep > shallow
