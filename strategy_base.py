from typing import Dict, List, Tuple, Union
from datetime import datetime, timedelta

from instrument import *
from log import logger
from price import round_to_cent


class OptionStrategy:

    def __init__(self, name: str, product: str, cash: float):
        # Built-in strategy states
        # User should not modify
        self.next_order_id: int = 0
        self.time: datetime = datetime.fromtimestamp(0)
        self.cash: float = cash
        self.option_premium_sum: float = 0
        self.positions: Dict[Union[Option, str], int] = {}
        self.pending_orders: List[Order] = []
        self.trades: List[Trade] = []
        self.trades_option_open: List[Trade] = []
        self.trades_option_expired: List[Trade] = []
        self.trades_option_assigned: List[Trade] = []
        self.product: str = product
        self.product_val: float = 0.0

        # Stats
        self.name: str = name
        self.log_file = open(f"tmp/{name}.log", "w")
        self.asset_value_history: List[Tuple[datetime, float]] = []
        self.stock_value_history: List[Tuple[datetime, float]] = []
        self.option_premium_history: List[Tuple[datetime, float]] = []

    # Helper functions

    @property
    def num_option_trades(self) -> int:
        return len(self.trades_option_open) + len(self.trades_option_assigned) + len(self.trades_option_expired)

    def log_stats(self):
        logger.info(f"Strategy stats:")
        avg_premium = 0.0 if self.num_option_trades == 0 else round_to_cent(
            self.option_premium_sum / self.num_option_trades)
        logger.info(
            f"\tTrades: {len(self.trades_option_open)} open, {len(self.trades_option_assigned)} assigned, {len(self.trades_option_expired)} expired, avg premium = ${avg_premium}")
        logger.info(f"\tCash: ${self.cash:.2f}")
        logger.info(f"\tPosition: {self.positions}")

    def add_position(self, instrument: Union[Option, str], qty: int):
        if instrument not in self.positions:
            self.positions[instrument] = 0
        self.positions[instrument] += qty
        if self.positions[instrument] == 0:
            del self.positions[instrument]

    @property
    def holding_stock(self) -> bool:
        return (self.product in self.positions and self.positions[self.product] > 0)

    # Market access

    def send_order_option(self, buy: bool, call: bool, dte: int, strike: int, qty: int):
        """
        Place an option order. The order is queued in pending_orders and will be handled by the backtest framework.
        """
        expiration = to_expiration(self.time + timedelta(days=dte))
        option = Option(self.product, call, expiration, strike)
        order = Order(self.next_order_id, buy, self.product,
                      InstrumentType.OPTION, 0, qty, option)
        self.next_order_id += 1
        self.pending_orders.append(order)

    def send_order_stock(self, buy: bool, price: float, qty: int):
        """
        Place a stock order. The order is queued in pending_orders and will be handled by the backtest framework.
        """
        order = Order(self.next_order_id, buy, self.product,
                      InstrumentType.STOCK, price, qty, self.product)
        self.next_order_id += 1
        self.pending_orders.append(order)

    # Market events

    def fill_event(self, trade: Trade):
        """
        Handler for order execution.
        """
        logger.info(
            f"Order id={trade.order.id} filled at ${trade.price} x {trade.qty}qty")
        order = trade.order
        if order.buy:
            self.cash -= trade.premium
            if order.is_option:
                self.option_premium_sum -= trade.premium
            self.add_position(order.instrument, trade.qty)
        else:
            self.cash += trade.premium
            if order.is_option:
                self.option_premium_sum += trade.premium
            self.add_position(order.instrument, -1 * trade.qty)
        if order.is_option:
            self.trades_option_open.append(trade)

    def assignment_event(self, trade: Trade, spot_price: float):
        """
        Handler for option assignment.
        """
        logger.info(
            f"Assigned {trade.order.instrument}, spot price = ${spot_price}")
        order = trade.order
        # we must have sold an option
        assert order.is_option
        assert type(order.instrument) == Option
        assert not order.buy
        self.add_position(order.instrument, trade.qty)
        # add/remove stock and cash
        if order.instrument.call:
            self.add_position(order.product, -1 * trade.qty * 100)
            self.cash += order.instrument.strike * 100
        else:
            self.add_position(order.product, trade.qty * 100)
            self.cash -= order.instrument.strike * 100
        # update trade records
        self.trades_option_open.remove(trade)
        self.trades_option_assigned.append(trade)

    def close_event(self, expired_trades: List[Trade]):
        """
        Handler for market close.
        """
        for trade in expired_trades:
            assert trade.order.is_option
            # remove expired options from positions
            if trade.order.buy:
                self.add_position(trade.order.instrument, -1 * trade.qty)
            else:
                self.add_position(trade.order.instrument, trade.qty)
            # update trade records
            self.trades_option_open.remove(trade)
            self.trades_option_expired.append(trade)
        # track daily NAV
        stock_value = self.positions.get(self.product, 0) * self.product_val
        nav = self.cash + stock_value
        self.asset_value_history.append((self.time, nav))
        self.stock_value_history.append((self.time, stock_value))
        self.option_premium_history.append(
            (self.time, self.option_premium_sum))

    def tick_event(self, time: datetime, price: float):
        """
        Handler for tick data update.
        """
        self.time = time
        self.product_val = price
        self.tick_logic(time, price)

    # Interfaces to be implemented by subclasses

    def tick_logic(self, time: datetime, price: float):
        raise TypeError("Base class tick_logic is virtual!")
