from backtest import *
from strategy import *
from tick import load_csv

if __name__ == "__main__":
    data = load_csv("data/SPY-2019-2025-30min.csv")
    strategies = [
        SellCoveredCallStrategy("covered-call", "SPY", 50000,
                                call_otm_pct=0.03),
        WheelStrategy("wheel-0dte-1pct", "SPY", 50000,
                      dte=0, put_otm_pct=0.01, call_otm_pct=0.01),
        WheelStrategy("wheel-1dte-1pct", "SPY", 50000,
                      dte=1, put_otm_pct=0.01, call_otm_pct=0.01),
        HoldStockStrategy("SPY spot", "SPY", 50000),
    ]
    for strategy in strategies:
        print(f"Running backtest for {strategy.name}...")
        backtest(strategy, data)
        print(f"Backtest completed for {strategy.name}.")
        # plot strategy PnL
        plot([
            ("Asset Value", strategy.asset_value_history),
            ("Stock Value", strategy.stock_value_history),
        ], f"tmp/{strategy.name}.png")
    # plot all strategies PnL together
    all_strategies_value_history = [
        (strategy.name, strategy.asset_value_history) for strategy in strategies]
    plot(all_strategies_value_history, f"tmp/combined.png")
