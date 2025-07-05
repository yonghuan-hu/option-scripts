import math
from datetime import datetime, timedelta
from typing import List
from instrument import *
from log import logger
from tick import TickData

SECONDS_IN_DAY = 24 * 60 * 60
SECONDS_IN_YEAR = 365 * SECONDS_IN_DAY
TRADING_DAYS_IN_YEAR = 252
DEFAULT_VOL = 0.10


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


class Pricer:
    """
    Theo calculator based on BSM and historical volatility.
    """

    def __init__(self, r: float):
        """
        Initialize the pricer with a fixed risk-free rate.
        """
        self.r = r
        self.tick_history: List[TickData] = []

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
        # clean up data older than 1 year
        cutoff = self.time - timedelta(days=365)
        self.tick_history = [t for t in self.tick_history if t.time >= cutoff]

    def estimate_vol(self, option: Option, yte: float) -> float:
        """
        Determine the vol for pricing.
        """
        MIN_TICKS_REQUIRED = 10
        if len(self.tick_history) < MIN_TICKS_REQUIRED:
            return DEFAULT_VOL

        lookback_period_days = max(7, int(yte * 365))
        # find ticks that are within the lookback period
        ticks = [
            t for t in self.tick_history if t.time >= self.time - timedelta(days=lookback_period_days)]
        assert len(ticks) >= MIN_TICKS_REQUIRED

        # calculate log returns
        log_returns = []
        for i in range(1, len(ticks)):
            p0 = ticks[i-1].close
            p1 = ticks[i].close
            assert p0 > 0 and p1 > 0
            log_returns.append(math.log(p1 / p0))

        # compute standard deviation of log returns
        mean = sum(log_returns) / len(log_returns)
        variance = sum((r - mean) ** 2 for r in log_returns) / \
            (len(log_returns) - 1)
        std = math.sqrt(variance)

        # estimate average time delta
        time_deltas = [
            (ticks[i].time - ticks[i-1].time).total_seconds() for i in range(1, len(ticks))
        ]
        avg_seconds = sum(time_deltas) / len(time_deltas)

        vol = std * math.sqrt(SECONDS_IN_YEAR / avg_seconds)

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
