"""Agent decision → akquant Strategy adapter.

Converts the text-based trade decision from a TradingAgents analysis run
into a concrete ``akquant.Strategy`` subclass that can be backtested.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _get_strategy_base():
    """Lazy-import akquant.Strategy base class."""
    try:
        import akquant as aq
        return aq.Strategy
    except ImportError:
        raise ImportError(
            "akquant is not installed. Install with: pip install akquant"
        )


class AgentDecisionStrategy:
    """Base strategy that translates an Agent's trade decision into bar-level actions.

    Subclass this or use it directly via ``AgentDecisionStrategy(decision="BUY")``.

    Attributes:
        decision: One of "BUY", "SELL", "HOLD".
        ticker: The stock symbol.
        holding_days: Number of bars to hold the position before closing.
    """

    def __init__(
        self,
        decision: str = "HOLD",
        ticker: str = "",
        holding_days: int = 5,
        **kwargs,
    ):
        # Will be set by akquant at runtime
        self.decision = decision.upper()
        self.ticker = ticker
        self.holding_days = holding_days
        self._bar_count = 0
        self._entry_price = None

    def on_bar(self, bar):
        """Called on each new bar. Implements the trading logic."""
        # First bar: record entry price
        if self._entry_price is None:
            self._entry_price = bar.close

        self._bar_count += 1

        if self.decision == "BUY":
            self._handle_buy(bar)
        elif self.decision == "SELL":
            self._handle_sell(bar)
        # HOLD: do nothing

    def _handle_buy(self, bar):
        """Buy on first bar, close after holding_days."""
        if self.get_position() == 0:
            # Buy with 95% of available cash
            self.buy(bar.close, percent=0.95)
            logger.debug("BUY at %.2f (bar %d)", bar.close, self._bar_count)
        elif self._bar_count >= self.holding_days:
            # Close position after holding period
            self.close_position()
            logger.debug("CLOSE after %d bars at %.2f", self._bar_count, bar.close)

    def _handle_sell(self, bar):
        """Sell on first bar if holding, otherwise short and cover after holding_days."""
        if self.get_position() > 0:
            self.close_position()
            logger.debug("CLOSE long at %.2f", bar.close)
        elif self.get_position() == 0 and self._bar_count <= 1:
            # Short sell (if supported by akquant)
            try:
                self.sell(bar.close, percent=0.95)
                logger.debug("SHORT at %.2f", bar.close)
            except AttributeError:
                # akquant may not support shorting for all markets
                logger.warning("Short selling not supported; holding cash instead")
        elif self._bar_count >= self.holding_days and self.get_position() < 0:
            self.close_position()
            logger.debug("COVER short after %d bars at %.2f", self._bar_count, bar.close)

    def on_order(self, order):
        """Called when an order is filled."""
        logger.debug("Order filled: %s", order)


def create_strategy_class(decision: str, ticker: str, holding_days: int = 5):
    """Factory: create a concrete Strategy subclass for a given decision.

    Returns a class (not instance) suitable for ``akquant.run_backtest(strategy=...)``.
    """
    StrategyBase = _get_strategy_base()

    class _Strategy(StrategyBase):
        def __init__(self):
            super().__init__()
            self.decision = decision.upper()
            self.ticker = ticker
            self.holding_days = holding_days
            self._bar_count = 0
            self._entry_price = None

        def on_bar(self, bar):
            if self._entry_price is None:
                self._entry_price = bar.close
            self._bar_count += 1

            if self.decision == "BUY":
                if self.get_position() == 0:
                    self.buy(bar.close, percent=0.95)
                elif self._bar_count >= self.holding_days:
                    self.close_position()
            elif self.decision == "SELL":
                if self.get_position() > 0:
                    self.close_position()
                elif self.get_position() == 0 and self._bar_count <= 1:
                    try:
                        self.sell(bar.close, percent=0.95)
                    except AttributeError:
                        pass
                elif self._bar_count >= self.holding_days and self.get_position() < 0:
                    self.close_position()

    _Strategy.__name__ = f"AgentStrategy_{decision}_{ticker}"
    _Strategy.__qualname__ = _Strategy.__name__
    return _Strategy
