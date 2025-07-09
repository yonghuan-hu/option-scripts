from backtest import *
from strategy import *
from tick_legacy import load_csv

INTEREST_RATE = 0.04

if __name__ == "__main__":
    data = load_csv("data/SPY-2019-2025-30min.csv")
    strategies = [
        SellCoveredCallStrategy("covered-call", "SPY", 50000,
                                dte=7, call_otm_pct=0.02),
        SellPutStrategy("sell-put", "SPY", 50000,
                        dte=0, put_otm_pct=0.01),
        WheelStrategy("wheel-0dte-1pct", "SPY", 50000,
                      dte=0, put_otm_pct=0.01, call_otm_pct=0.01),
        WheelStrategy("wheel-1dte-1pct", "SPY", 50000,
                      dte=1, put_otm_pct=0.01, call_otm_pct=0.01),
        HoldStockStrategy("SPY spot", "SPY", 50000),
    ]
    for strategy in strategies:
        pricer = Pricer(INTEREST_RATE)
        print(f"Strategy {strategy.name} backtesting ...")
        backtest(strategy, pricer, data)
        print(f"Strategy {strategy.name} finished")
        # plot strategy PnL
        plot([
            ("Asset Value", strategy.asset_value_history),
            ("Stock Value", strategy.stock_value_history),
            ("Earned Premium", strategy.option_premium_history),
        ], f"tmp/{strategy.name}.png", tick=10000, unit='$')
    # plot pricer history
    pricer.plot_vols("tmp/vols.png")
    pricer.log_price_matrix()
    # plot all strategies PnL together
    all_strategies_value_history = [
        (strategy.name, strategy.asset_value_history) for strategy in strategies]
    plot(all_strategies_value_history, f"tmp/combined.png", tick=10000, unit='$')
