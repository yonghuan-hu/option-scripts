from instrument import *
from log import logger
from price import *
from strategy import OptionStrategy, Trade
from tick import TickData


def backtest(strategy: OptionStrategy, pricer: Pricer, data: List[TickData]):
    """
    Run the backtest for the given strategy.
    This function is called in the main block.
    """
    logger.open(f"tmp/{strategy.name}.log")
    for tick_idx, tick in enumerate(data):
        logger.settime(tick.time)
        # feed latest val to pricer and strategy
        pricer.val_event(tick.time, tick.open)
        strategy.tick_event(tick.time, tick.open)
        # check strategy orders
        remaining_orders = []
        for order in strategy.pending_orders:
            logger.info(f"Order {order}")
            trade = None
            if order.is_option:
                # option orders: always fill at market bbo
                premium = pricer.calculate_theo(order.instrument)
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
        # feed full tick data to pricer
        pricer.tick_event(tick)
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
    logger.close()
