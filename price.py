import math
from datetime import datetime
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
    return round(x * 100.0) / 100.0


class Pricer:

    def __init__(self, vol: float, r: float):
        """
        Initialize the pricer with a fixed volatility and risk-free rate.
        """
        self.vol = vol
        self.r = r

    def estimate_vol_skew(self, option: Option, val: float) -> float:
        """
        Estimate the implied volatility skew based on empirical observations.
        TODO: use actual IV data
        """
        # every 1% otm, multiply vol by 1.10
        otm_pct = math.fabs(option.strike - val) / val
        return self.vol * (1.0 + 0.1 * otm_pct)

    def calculate_theo(self, option: Option, time: datetime, val: float) -> float:
        """
        Calculate the option theo price using a simple Black-Scholes model.
        """
        logger.info(
            f"Calculating option price for {option} with val={val}, vol={self.vol}, r={self.r}")

        # calculate Yte
        T = (option.expiration - time).total_seconds() / SECONDS_IN_YEAR
        if T < 0:
            return 0.0

        # estimate vol skew
        skewed_vol = self.estimate_vol_skew(option, val)

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

        return round_to_cent(price)
