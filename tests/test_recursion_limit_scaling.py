"""Regression: recursion limit must scale with graph size.

Bug (GUI, A-share mode): ``GraphRecursionError: Recursion limit of 100
reached``. A-share runs append 3 extra analysts (7 total); each analyst
consumes 5-9 supersteps (agent -> tools loop -> clear), plus research and
risk debate rounds. The hardcoded ``max_recur_limit=100`` was sized for
4 analysts and runs out mid-analysis, aborting the run.

The fix derives the limit from the graph shape: analyst count and debate
rounds. Tests assert the formula produces a budget that fits the A-share
7-analyst graph and keeps the historical 100 floor for smaller graphs.
"""

import pytest

from tradingagents.graph.propagation import compute_recursion_limit


class TestComputeRecursionLimit:
    def test_astock_seven_analysts_medium_exceeds_hundred(self):
        """The exact bug scenario: 7 analysts, medium depth (3 rounds).

        7 analysts need ~35-63 steps alone; with debates the total runs
        90-110+, so the limit must exceed the old hardcoded 100.
        """
        limit = compute_recursion_limit(
            n_analysts=7, debate_rounds=3, risk_rounds=3
        )
        assert limit > 100

    def test_us_four_analysts_keeps_hundred_floor(self):
        """4-analyst graphs historically fit in 100; keep the floor."""
        limit = compute_recursion_limit(
            n_analysts=4, debate_rounds=3, risk_rounds=3
        )
        assert limit >= 100

    def test_minimum_graph_fits_default(self):
        limit = compute_recursion_limit(
            n_analysts=1, debate_rounds=1, risk_rounds=1
        )
        assert limit >= 100

    def test_scales_with_analyst_count(self):
        """More analysts must never shrink the budget."""
        small = compute_recursion_limit(4, 3, 3)
        large = compute_recursion_limit(7, 3, 3)
        assert large > small

    def test_scales_with_debate_rounds(self):
        shallow = compute_recursion_limit(7, 1, 1)
        deep = compute_recursion_limit(7, 5, 5)
        assert deep > shallow

    def test_budget_covers_worst_case_step_estimate(self):
        """The limit must cover a pessimistic superstep estimate.

        Worst realistic case per analyst: 6 tool-loop rounds =
        13 supersteps; research debate (2 debators x rounds + judge);
        risk debate (3 debators x rounds + portfolio); fixed nodes.
        """
        n_analysts, debate_rounds, risk_rounds = 7, 3, 3
        worst_case = (
            n_analysts * 13
            + debate_rounds * 2
            + 2
            + risk_rounds * 3
            + 2
            + 5
        )
        limit = compute_recursion_limit(n_analysts, debate_rounds, risk_rounds)
        assert limit >= worst_case
