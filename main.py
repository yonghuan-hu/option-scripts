from backtest import *
from strategy import *
from tick import MarketDataLoader

INTEREST_RATE = 0.04

if __name__ == "__main__":
    strategies = [
        SellCoveredCallStrategy("covered-call", "SPY", 50000,
                                dte=7, call_otm_pct=0.02),
        SellPutStrategy("sell-put", "SPY", 50000,
                        dte=1, put_otm_pct=0.01),
        WheelStrategy("wheel-0dte-1pct", "SPY", 50000,
                      dte=0, put_otm_pct=0.01, call_otm_pct=0.01),
        WheelStrategy("wheel-1dte-1pct", "SPY", 50000,
                      dte=1, put_otm_pct=0.01, call_otm_pct=0.01),
        HoldStockStrategy("SPY spot", "SPY", 50000),
    ]
    for strategy in strategies:
        md = MarketDataLoader(
            stock_filename='data/SPY-202507-15min.csv',
            option_filename='data/SPY-options.csv'
        )
        pricer = Pricer(INTEREST_RATE)
        print(f"Strategy ({strategy.name}) backtesting ...")
        backtest(strategy, pricer, md)
        print(
            f"Strategy ({strategy.name}) finished, {md.tick_count} ticks replayed")
        # plot strategy PnL
        plot([
            ("Asset Value", strategy.asset_value_history),
            ("Stock Value", strategy.stock_value_history),
            ("Earned Premium", strategy.option_premium_history),
        ], f"tmp/{strategy.name}.png", tick=1000, unit='$')
    # plot pricer history
    # pricer.plot_vols("tmp/vols.png")
    pricer.log_price_matrix()
    # plot all strategies PnL together
    all_strategies_value_history = [
        (strategy.name, strategy.asset_value_history) for strategy in strategies]
    plot(all_strategies_value_history, f"tmp/combined.png", tick=1000, unit='$')
