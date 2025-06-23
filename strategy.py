import math
from typing import Dict, List, Tuple, Union
from datetime import datetime, timedelta

from instrument import *


class OptionStrategy:

    def __init__(self, name: str, product: str, cash: float):
        # Built-in strategy states
        # User should not modify
        self.next_order_id: int = 0
        self.time: datetime = datetime.strptime(
            "2000-01-01 00:00:00", "%Y-%m-%d %H:%M:%S")
        self.cash: float = cash
        self.positions: Dict[Union[Option, str], int] = {}
        self.pending_orders: List[Order] = []
        self.trades: List[Trade] = []
        self.trades_expired: List[Trade] = []
        self.trades_assigned: List[Trade] = []
        self.product: str = product
        self.product_val: float = 0.0

        # Stats over time
        self.name: str = name
        self.asset_value_history: List[Tuple[datetime, float]] = []
        self.stock_value_history: List[Tuple[datetime, float]] = []

    # Helper functions

    def log(self, logstr: str):
        print(f"[{self.time}] {logstr}")

    def log_stats(self):
        print(f"[{self.time}] Strategy stats:")
        print(
            f"\tTrades: {len(self.trades)} total, {len(self.trades_assigned)} assigned, {len(self.trades_expired)} expired")
        print(f"\tCash: ${self.cash:.2f}")
        print(f"\tPosition: {self.positions}")

    def add_position(self, instrument: Union[Option, str], qty: int):
        if instrument not in self.positions:
            self.positions[instrument] = 0
        self.positions[instrument] += qty
        if self.positions[instrument] == 0:
            del self.positions[instrument]

    # Market access

    def send_order_option(self, buy: bool, call: bool, dte: int, strike: int, qty: int):
        """
        Place an option order. The order is queued in pending_orders and will be handled by the backtest framework.
        """
        # options stop trading at 4pm ET (3 CT), but can be exercised until 5:30pm ET (4:30 CT)
        expiration_date = (self.time + timedelta(days=dte)).date()
        expiration = datetime.combine(
            expiration_date, datetime.strptime("16:30:00", "%H:%M:%S").time())
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
        print(
            f"[{self.time}] Order id={trade.order.id} filled at ${trade.price} x {trade.qty}qty")
        order = trade.order
        if order.buy:
            self.cash -= trade.premium
            self.add_position(order.instrument, trade.qty)
        else:
            self.cash += trade.premium
            self.add_position(order.instrument, -1 * trade.qty)

    def assignment_event(self, trade: Trade, spot_price: float):
        """
        Handler for option assignment.
        """
        self.log(
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
        self.trades_assigned.append(trade)

    def close_event(self, expired_trades: List[Trade]):
        """
        Handler for market close.
        """
        # remove expired options
        for trade in expired_trades:
            assert trade.order.is_option
            if trade.order.buy:
                self.add_position(trade.order.instrument, -1 * trade.qty)
            else:
                self.add_position(trade.order.instrument, trade.qty)
        self.trades_expired.extend(expired_trades)
        # track daily NAV
        stock_value = self.positions.get(self.product, 0) * self.product_val
        nav = self.cash + stock_value
        self.asset_value_history.append((self.time, nav))
        self.stock_value_history.append((self.time, stock_value))

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


class WheelStrategy(OptionStrategy):

    def __init__(self, *args, put_otm_pct: float, call_otm_pct: float, **kwargs):
        super().__init__(*args, **kwargs)
        self.put_otm_pct = put_otm_pct
        self.call_otm_pct = call_otm_pct

    @property
    def holding_stock(self) -> bool:
        return (self.product in self.positions and self.positions[self.product] > 0)

    def tick_logic(self, time: datetime, price: float):
        if time.hour == 8 and time.minute == 30:
            if self.holding_stock:
                # sell call
                strike = math.floor(price * (1.0 + self.call_otm_pct))
                self.send_order_option(
                    buy=False, call=True, dte=0, strike=strike, qty=1)
            else:
                # sell put
                strike = math.ceil(price * (1.0 - self.call_otm_pct))
                self.send_order_option(
                    buy=False, call=False, dte=0, strike=strike, qty=1)


class HoldStockStrategy(OptionStrategy):

    def tick_logic(self, time: datetime, price: float):
        if not self.product in self.positions:
            self.send_order_stock(
                buy=True, price=price, qty=100)
