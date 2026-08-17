"""Graph setup wires conditional edges for every analyst via
``getattr(conditional_logic, f"should_continue_{spec.key}")``. The A-share
analysts (policy / hot_money / lockup) must have matching router methods on
``ConditionalLogic`` or graph setup raises AttributeError mid-run.

Regression guard for the missing should_continue_policy / hot_money / lockup.
"""

from types import SimpleNamespace

from tradingagents.graph.analyst_execution import ALL_ANALYST_SPECS
from tradingagents.graph.conditional_logic import ConditionalLogic


def _message(tool_calls):
    return SimpleNamespace(tool_calls=tool_calls)


class TestAStockConditionalRouting:
    def test_every_analyst_has_a_router_method(self):
        cl = ConditionalLogic()
        for key, spec in ALL_ANALYST_SPECS.items():
            method = getattr(cl, f"should_continue_{key}", None)
            assert method is not None, f"missing router method: should_continue_{key}"

    def test_router_returns_tool_node_on_tool_calls(self):
        cl = ConditionalLogic()
        for key, spec in ALL_ANALYST_SPECS.items():
            method = getattr(cl, f"should_continue_{key}")
            state = {"messages": [_message(tool_calls=[{"name": "t"}])]}
            assert method(state) == spec.tool_node, key

    def test_router_returns_clear_node_without_tool_calls(self):
        cl = ConditionalLogic()
        for key, spec in ALL_ANALYST_SPECS.items():
            method = getattr(cl, f"should_continue_{key}")
            state = {"messages": [_message(tool_calls=[])]}
            assert method(state) == spec.clear_node, key
