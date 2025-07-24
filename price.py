import math
from typing import Dict, List, Tuple
from matplotlib import pyplot as plt
from matplotlib import ticker as ticker

from datetime import datetime, timedelta
from typing import List

from instrument import *
from log import logger
from tick import OptionData, TickData

SECONDS_IN_DAY = 24 * 60 * 60
SECONDS_IN_YEAR = 365 * SECONDS_IN_DAY
TRADING_DAYS_IN_YEAR = 252
MIN_TICKS_REQUIRED = 10
DEFAULT_VOL = 0.10

type Line = Tuple[str, List[Tuple[datetime, float]]]


def plot(lines: List[Line], plot_path: str, tick: int, unit: str):
    plt.figure(figsize=(20, 10))
    for name, line in lines:
        times, values = zip(*line)
        plt.plot(times, values, label=name)
    plt.xlabel("Date")
    plt.ylabel(f"Value ({unit})")
    plt.gca().yaxis.set_major_locator(ticker.MultipleLocator(tick * 5))
    plt.gca().yaxis.set_minor_locator(ticker.MultipleLocator(tick))
    plt.legend()
    plt.grid(True)
    plt.savefig(plot_path)


def cdf(x: float) -> float:
    # Abramowitz and Stegun formula 7.1.26
    # Accurate to about 1e-4
    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    t = 1 / (1 + 0.3275911 * x)
    a1, a2, a3, a4, a5 = 0.254829592, - \
        0.284496736, 1.421413741, -1.453152027, 1.061405429
    erf_approx = 1 - (((((a5 * t + a4) * t + a3) * t + a2)
                       * t + a1) * t * math.exp(-x * x))
    return 0.5 * (1 + sign * erf_approx)


def round_to_cent(x: float) -> float:
    """
    Round a float to the nearest cent.
    """
    cent_price = round(x * 100.0) / 100.0
    return max(cent_price, 0.01)


def yte(option: Option, time: datetime) -> float:
    """
    Calculate the years to expiration (Yte) for the given option.
    """
    if option.expiration < time:
        return 0.0
    return (option.expiration - time).total_seconds() / SECONDS_IN_YEAR


def compute_realized_vol(ticks: List[TickData]) -> float:
    """
    Given a list of TickData, compute the realized volatility.
    Returns DEFAULT_VOL if not enough data.
    """
    if len(ticks) < MIN_TICKS_REQUIRED:
        return DEFAULT_VOL

    log_returns = []
    for i in range(1, len(ticks)):
        p0 = ticks[i - 1].stock_price.close
        p1 = ticks[i].stock_price.close
        if p0 > 0 and p1 > 0:
            log_returns.append(math.log(p1 / p0))

    # Calculate standard deviation
    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / \
        (len(log_returns) - 1)
    std = math.sqrt(variance)

    # Estimate average time delta between ticks
    time_deltas = [
        (ticks[i].time - ticks[i - 1].time).total_seconds()
        for i in range(1, len(ticks))
    ]
    avg_seconds = sum(time_deltas) / len(time_deltas)

    return std * math.sqrt(SECONDS_IN_YEAR / avg_seconds)


class Pricer:
    """
    Theo calculator based on BSM and historical volatility.
    """

    time: datetime
    val: float
    option_prices: Dict[str, OptionData] = {}
    tick_history: List[TickData] = []

    # EVENT HANDLERS

    def __init__(self, r: float):
        """
        Initialize the pricer with a fixed risk-free rate.
        """
        self.r = r

    def val_event(self, time: datetime, price: float):
        """
        Handler for latest val update.
        """
        self.time = time
        self.val = price

    def tick_event(self, tick: TickData):
        """
        Handler for full tick data update.
        """
        self.tick_history.append(tick)
        for option, price in tick.option_prices.items():
            self.option_prices[option] = price
        # clean up data older than 1 year
        cutoff = self.time - timedelta(days=365)
        self.tick_history = [t for t in self.tick_history if t.time >= cutoff]

    # NUMERIC METHODS

    def estimate_vol(self, option: Option, yte: float) -> float:
        """
        Determine the vol for pricing.
        """

        lookback_period_days = max(7, int(yte * 365))
        # find ticks that are within the lookback period
        ticks = [
            t for t in self.tick_history if t.time >= self.time - timedelta(days=lookback_period_days)]

        vol = compute_realized_vol(ticks)

        # Vol skew adjustment
        # TODO: improve IV model, especially how d(IV)/d(OTM) changes with OTM
        otm_factor = 1 + 3.0/(yte * 365)  # vol += otm_factor per 1% OTM
        otm_pct = math.fabs(option.strike - self.val) / self.val
        vol += otm_pct * otm_factor
        return vol

    def calculate_theo(self, option: Option) -> float:
        """
        Calculate the option theo price using a simple Black-Scholes model.
        """

        # estimate vol skew
        T = yte(option, self.time)
        skewed_vol = self.estimate_vol(option, T)

        # Black-Scholes
        K = option.strike
        S = self.val
        sigma = skewed_vol

        d1 = (math.log(S / K) + (self.r + 0.5 * sigma**2) * T) / \
            (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        if option.call:
            price = S * cdf(d1) - K * math.exp(-self.r * T) * cdf(d2)
        else:
            price = K * math.exp(-self.r * T) * cdf(-d2) - S * cdf(-d1)

        theo = round_to_cent(price)

        return theo

    def market_price_or_theo(self, option: Option) -> float:
        """
        Find the latest market price for an option, or calculate_theo if not available.
        """
        if option in self.option_prices:
            price = self.option_prices[str(option)]
            logger.info(
                f"Market price for {option} is {price.last} ({price.iv * 100}% IV), last trade at {price.time}")
            return price.last
        else:
            theo = self.calculate_theo(option)
            logger.info(f"Market price for {option} not found, theo is {theo}")
            return theo

    # HELPERS

    def plot_vols(self, plot_path: str):
        """
        Plot 7d, 14d, and 30d historical volatility.
        """
        assert len(
            self.tick_history) >= MIN_TICKS_REQUIRED, "Not enough tick data to calculate volatilities."

        windows = [7, 14, 30]
        lines = []

        for window in windows:
            vol_percents = []
            for i in range(len(self.tick_history)):
                window_start = self.tick_history[i].time - \
                    timedelta(days=window)
                window_ticks = [
                    t for t in self.tick_history if window_start <= t.time <= self.tick_history[i].time
                ]
                vol = compute_realized_vol(window_ticks)
                vol_percents.append((self.tick_history[i].time, vol * 100))

            lines.append((f"{window}d Vol", vol_percents))

        plot(lines, plot_path, tick=1, unit='%')

    def log_price_matrix(self):
        """
        Log a matrix of option prices for different strikes and expirations.
        Useful for debugging.
        """
        print(f"Pricer sample matrix:")
        # header
        print("-" * 100)
        header = f"Call    | " + " | ".join(
            f"{dte:>14}d" for dte in [0, 1, 7, 30])
        print(header)
        # table
        for otm_pct in [0.0, 0.01, 0.02, 0.03]:
            price_and_vols = []
            strike = round(self.val * (1 + otm_pct))
            for dte in [0, 1, 7, 30]:
                expiration = to_expiration(self.time + timedelta(days=dte))
                option = Option("SPY", True, expiration, strike)
                T = yte(option, self.time)
                vol = self.estimate_vol(option, T)
                price = self.calculate_theo(option)
                price_and_vols.append((price, vol))
            # print prices in a row with fixed width for each col
            row = f"${strike:<6} | "
            row += " | ".join(
                f"${price:<6.2f} {vol * 100:>6.2f}%" for price, vol in price_and_vols)
            print(row)
        # footer
        print("-" * 100)
