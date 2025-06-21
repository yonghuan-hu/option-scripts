import math
from typing import Dict, List, Union
from datetime import datetime, timedelta
from instrument import *
from tick import load_csv


class OptionStrategy:

    def __init__(self, product: str):
        # Built-in strategy states
        # User should not modify
        self.next_order_id: int = 0
        self.time: datetime = datetime.strptime(
            "2000-01-01 00:00:00", "%Y-%m-%d %H:%M:%S")
        self.cash: float = 0.0
        self.positions: Dict[Union[Option, str], int] = {}
        self.pending_orders: List[Order] = []
        self.trades: List[Trade] = []
        self.product = product

    def send_order_option(self, buy: bool, call: bool, dte: int, strike: int, qty: int):
        """
        Place an option order. The order is queued in pending_orders and will be handled by the backtest framework.
        """
        expiration = self.time + timedelta(days=dte)
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

    def fill_event(self, trade: Trade):
        """
        Handler for order execution.
        """
        print(
            f"[{self.time}] Order id={trade.order.id} filled at ${trade.price} x{trade.qty}")
        order = trade.order
        if order.instrument not in self.positions:
            self.positions[order.instrument] = 0
        if order.product not in self.positions:
            self.positions[order.product] = 0
        if order.buy:
            self.cash -= trade.price
            self.positions[order.instrument] += 1
        else:
            self.cash += trade.price
            self.positions[order.instrument] -= 1

    def assignment_event(self, trade: Trade, spot_price: float):
        """
        Handler for option assignment.
        """
        print(
            f"[{self.time}] Assigned {trade.order.instrument}, spot price = ${spot_price}")
        order = trade.order
        # we must have sold an option
        assert order.is_option
        assert not order.buy
        self.positions[order.instrument] -= 1
        # add/remove stock and cash
        if order.instrument.call:
            self.positions[order.product] -= 100
            self.cash += order.instrument.strike * 100
        else:
            self.positions[order.product] += 100
            self.cash -= order.instrument.strike * 100

    def close_event(self, expired_trades: List[Trade]):
        """
        Handler for market close.
        """
        pass

    def tick_event(self, time: datetime, price: float):
        """
        Handler for tick data update.
        """
        self.time = time
        self.tick_logic(time, price)

    def tick_logic(self, time: datetime, price: float):
        raise "Base class tick_logic is virtual!"


class WheelStrategy(OptionStrategy):

    @property
    def holding_stock(self) -> bool:
        return (self.product in self.positions and self.positions[self.product] > 0)

    def tick_logic(self, time: datetime, price: float):
        otm_price_offset = 0.01 * price
        if time.hour == 10 and time.minute == 0:
            if self.holding_stock:
                # sell call
                strike = math.floor(price+otm_price_offset)
                self.send_order_option(
                    buy=False, call=True, dte=0, strike=strike, qty=1)
            else:
                # sell put
                strike = math.ceil(price+otm_price_offset)
                self.send_order_option(
                    buy=False, call=False, dte=0, strike=strike, qty=1)


if __name__ == "__main__":
    data = load_csv("data/SPY-2019-2025-30min.csv")
    strategy = WheelStrategy("SPY")
    for tick_idx, tick in enumerate(data):
        # feed tick data to strategy
        strategy.tick_event(tick.time, tick.open)
        # check strategy orders
        remaining_orders = []
        for order in strategy.pending_orders:
            print(f"[{tick.time}] Processing order {order}")
            trade = None
            if order.is_option:
                # option orders: always fill at market bbo
                strike = order.instrument.strike
                premium = 1.0  # todo: calculate premium using VIX
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
