import math
from typing import List
from matplotlib import pyplot as plt

from instrument import *
from tick import TickData
from price import calculate_option_price
from strategy import OptionStrategy, Trade


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
