import math
from datetime import datetime, timedelta
from instrument import *
from log import logger

SECONDS_IN_DAY = 24 * 60 * 60
SECONDS_IN_YEAR = 365 * SECONDS_IN_DAY


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


class Pricer:

    def __init__(self, r: float):
        """
        Initialize the pricer with a fixed risk-free rate.
        """
        self.r = r

    def yte(self, option: Option, time: datetime) -> float:
        """
        Calculate the years to expiration (Yte) for the given option.
        """
        if option.expiration < time:
            return 0.0
        return (option.expiration - time).total_seconds() / SECONDS_IN_YEAR

    def estimate_vol(self, option: Option, yte: float, val: float) -> float:
        """
        Estimate the implied volatility based on empirical observations.
        TODO: use actual IV data
        """
        BASE_VOL = 0.15
        # TODO: model IV, especially how d(IV)/d(OTM) changes with OTM
        otm_factor = 1 + 3.0/(yte * 365)  # vol += otm_factor per 1% OTM
        otm = math.fabs(option.strike - val) / val
        vol = BASE_VOL + otm * otm_factor
        return vol

    def calculate_theo(self, option: Option, time: datetime, val: float) -> float:
        """
        Calculate the option theo price using a simple Black-Scholes model.
        """

        # estimate vol skew
        T = self.yte(option, time)
        skewed_vol = self.estimate_vol(option, T, val)

        # Black-Scholes
        K = option.strike
        S = val
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

    def log_price_matrix(self, val: float):
        """
        Log a matrix of option prices for different strikes and expirations.
        Useful for debugging.
        """
        print(f"Pricer sample matrix:")
        time = datetime.now()
        # header
        print("-" * 100)
        header = f"Call    | " + " | ".join(
            f"{dte:>14}d" for dte in [0, 1, 7, 30])
        print(header)
        # table
        for otm_pct in [0.0, 0.01, 0.02, 0.03]:
            price_and_vols = []
            strike = round(val * (1 + otm_pct))
            for dte in [0, 1, 7, 30]:
                expiration = to_expiration(time + timedelta(days=dte))
                option = Option("SPY", True, expiration, strike)
                yte = self.yte(option, time)
                vol = self.estimate_vol(option, yte, val)
                price = self.calculate_theo(option, datetime.now(), val)
                price_and_vols.append((price, vol))
            # print prices in a row with fixed width for each col
            row = f"${strike:<6} | "
            row += " | ".join(
                f"${price:<6.2f} {vol * 100:>6.2f}%" for price, vol in price_and_vols)
            print(row)
        # footer
        print("-" * 100)
