import math
from datetime import datetime

from instrument import *
from strategy_base import OptionStrategy


class WheelStrategy(OptionStrategy):

    def __init__(self, *args, put_otm_pct: float, call_otm_pct: float, dte: int, **kwargs):
        super().__init__(*args, **kwargs)
        self.put_otm_pct = put_otm_pct
        self.call_otm_pct = call_otm_pct
        self.dte = dte

    def tick_logic(self, time: datetime, price: float):
        if time.hour >= 10 and not self.trades_option_open:
            if self.holding_stock:
                # sell call
                strike = compute_strike(price, self.call_otm_pct, 5)
                self.send_order_option(
                    buy=False, call=True, dte=self.dte, strike=strike, qty=1)
            else:
                # sell put
                strike = compute_strike(price, -self.put_otm_pct, 5)
                self.send_order_option(
                    buy=False, call=False, dte=self.dte, strike=strike, qty=1)


class SellCoveredCallStrategy(OptionStrategy):

    def __init__(self, *args, call_otm_pct: float, dte: int, **kwargs):
        super().__init__(*args, **kwargs)
        self.call_otm_pct = call_otm_pct
        self.dte = dte

    def tick_logic(self, time: datetime, price: float):
        if time.hour >= 10 and not self.trades_option_open:
            if self.holding_stock:
                # sell call
                strike = compute_strike(price, self.call_otm_pct, 5)
                self.send_order_option(
                    buy=False, call=True, dte=self.dte, strike=strike, qty=1)
            else:
                # buy stock
                max_qty = math.floor(self.cash / price)
                self.send_order_stock(
                    buy=True, price=price, qty=max_qty)


class SellPutStrategy(OptionStrategy):

    def __init__(self, *args, put_otm_pct: float, dte: int, **kwargs):
        super().__init__(*args, **kwargs)
        self.put_otm_pct = put_otm_pct
        self.dte = dte

    def tick_logic(self, time: datetime, price: float):
        if self.holding_stock:
            # exit the stock position asap
            qty = self.positions[self.product]
            assert qty > 0
            self.send_order_stock(
                buy=False, price=price, qty=qty)
        else:
            # sell put daily
            if time.hour >= 10 and not self.trades_option_open:
                strike = compute_strike(price, -self.put_otm_pct, 5)
                self.send_order_option(
                    buy=False, call=False, dte=self.dte, strike=strike, qty=1)


class HoldStockStrategy(OptionStrategy):

    def tick_logic(self, time: datetime, price: float):
        if not self.holding_stock:
            max_qty = math.floor(self.cash / price)
            self.send_order_stock(
                buy=True, price=price, qty=max_qty)
