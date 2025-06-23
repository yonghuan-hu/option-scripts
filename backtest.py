import math
from typing import Dict, List, Tuple, Union
from datetime import datetime, timedelta

from matplotlib import pyplot as plt
from instrument import *
from tick import TickData, load_csv
from price import calculate_option_price


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
        # Tuple(time, total_nav, stock_value)
        self.name: str = name
        self.asset_value_history: List[Tuple[datetime, float, float]] = []

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
        self.asset_value_history.append((self.time, nav, stock_value))

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

    def __init__(self, name: str, product: str, cash: float, otm_pct: float):
        super().__init__(name, product, cash)
        self.otm_pct = otm_pct

    @property
    def holding_stock(self) -> bool:
        return (self.product in self.positions and self.positions[self.product] > 0)

    def tick_logic(self, time: datetime, price: float):
        otm_price_offset = self.otm_pct * price
        if time.hour == 8 and time.minute == 30:
            if self.holding_stock:
                # sell call
                strike = math.floor(price + otm_price_offset)
                self.send_order_option(
                    buy=False, call=True, dte=0, strike=strike, qty=1)
            else:
                # sell put
                strike = math.ceil(price - otm_price_offset)
                self.send_order_option(
                    buy=False, call=False, dte=0, strike=strike, qty=1)


def backtest(strategy: OptionStrategy, data: List[TickData], plot_path: str):
    """
    Run the backtest for the given strategy.
    This function is called in the main block.
    """
    for tick_idx, tick in enumerate(data):
        strategy.tick_event(tick.time, tick.open)
        # check strategy orders
        remaining_orders = []
        for order in strategy.pending_orders:
            strategy.log(f"Order {order}")
            trade = None
            if order.is_option:
                # option orders: always fill at market bbo
                # assume atm at 20% IV, 1% otm at 30% IV, 2% otm at 40% IV
                # TODO: use actual IV data
                otm_pct = math.fabs(
                    order.instrument.strike - tick.open) / tick.open
                iv = 0.20 + otm_pct * 10
                premium = calculate_option_price(
                    order.instrument, tick.time, tick.open, iv)
                trade = Trade(order, premium, order.qty)
            else:
                # stock orders: check for price limit
                can_be_filled = (
                    order.price >= tick.low and order.price <= tick.high)
                if can_be_filled:
                    trade = Trade(order, order.price, order.qty)
                else:
                    remaining_orders.append(order)
            # notify strategy when filled
            if trade:
                strategy.trades.append(trade)
                strategy.fill_event(trade)
        strategy.pending_orders = remaining_orders
        # EOD events
        is_last_tick_of_day = (
            tick_idx + 1 < len(data) and data[tick_idx + 1].time.date() != tick.time.date())
        if is_last_tick_of_day:
            # check assigned / expired options
            expired_trades = []
            for trade in strategy.trades:
                # todo: don't traverse all trades
                if trade.order.is_option and trade.order.instrument.expiration.date() == tick.time.date():
                    option = trade.order.instrument
                    spot_exceeds_strike = (option.call and tick.close >= option.strike) or (
                        not option.call and tick.close <= option.strike)
                    if spot_exceeds_strike:
                        strategy.assignment_event(trade, tick.close)
                    else:
                        expired_trades.append(trade)
            # notify market close
            strategy.close_event(expired_trades)
            strategy.log_stats()

    # plot daily P&L
    times, aums, stock_values = zip(*strategy.asset_value_history)
    filtered_stock = [(t, v) for t, v in zip(times, stock_values) if v != 0.0]
    plt.figure(figsize=(20, 10))
    plt.plot(times, aums, label="Total NAV")
    plt.plot(times, stock_values, label="Stock Value")
    plt.title("Daily AUM Breakdown")
    plt.xlabel("Date")
    plt.ylabel("Value ($)")
    plt.legend()
    plt.grid(True)
    plt.savefig(plot_path)


if __name__ == "__main__":
    data = load_csv("data/SPY-2019-2025-30min.csv")
    strategies = [
        WheelStrategy("wheel-1pct", "SPY", 50000, 0.01),
        WheelStrategy("wheel-2pct", "SPY", 50000, 0.02),
    ]
    for strategy in strategies:
        print(f"Running backtest for {strategy.name}...")
        backtest(strategy, data, f"tmp/{strategy.name}.png")
        print(f"Backtest completed for {strategy.name}.")
