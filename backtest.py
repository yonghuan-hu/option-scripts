from instrument import *
from log import logger
from price import *
from strategy import OptionStrategy, Trade
from tick import MarketDataLoader


def backtest(strategy: OptionStrategy, pricer: Pricer, md: MarketDataLoader):
    """
    Run the backtest for the given strategy.
    This function is called in the main block.
    """
    logger.open(f"tmp/{strategy.name}.log")
    while md.has_next_tick:
        tick = md.next_tick()
        logger.settime(tick.time)
        # feed latest val to pricer and strategy
        pricer.val_event(tick.time, tick.stock_price.open)
        strategy.tick_event(tick.time, tick.stock_price.open)
        # check strategy orders
        remaining_orders = []
        for order in strategy.pending_orders:
            logger.info(f"Order {order}")
            trade = None
            if order.is_option:
                # option orders: always fill at market bbo
                # TODO: support limit option orders
                premium = pricer.market_price_or_theo(order.instrument)
                trade = Trade(order, premium, order.qty)
            else:
                # stock orders: check for price limit
                can_be_filled = (
                    order.price >= tick.stock_price.low and order.price <= tick.stock_price.high)
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
        if md.end_of_day:
            # check assigned / expired options
            expired_trades = []
            for trade in strategy.trades_option_open:
                assert trade.order.is_option
                if trade.order.instrument.expiration.date() <= tick.time.date():
                    option = trade.order.instrument
                    itm = (option.call and tick.stock_price.close >= option.strike) or (
                        not option.call and tick.stock_price.close <= option.strike)
                    if itm:
                        strategy.assignment_event(
                            trade, tick.stock_price.close)
                    else:
                        expired_trades.append(trade)
            # notify market close
            strategy.close_event(expired_trades)
            strategy.log_stats()
    logger.close()
