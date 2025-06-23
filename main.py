from backtest import backtest
from tick import load_csv
from strategy import WheelStrategy

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
