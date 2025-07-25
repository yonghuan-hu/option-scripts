from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Union
from zoneinfo import ZoneInfo


class InstrumentType(Enum):
    OPTION = "OPTION"
    STOCK = "STOCK"


def to_expiration(date: date) -> datetime:
    """
    Create a datetime object for the given year, month, and day.
    If the given day falls on a weekend, the next Monday will be selected.
    Options stop trading at 4pm ET (3 CT), but can be exercised until 5:30pm ET (4:30 CT).
    """
    if date.weekday() >= 5:
        # If the date is Saturday or Sunday, move to next Monday
        date = date + timedelta(days=(7 - date.weekday()))
    return datetime(date.year, date.month, date.day, 16, 30, tzinfo=ZoneInfo("America/Chicago"))


def round_strike(price: float, granularity: int) -> int:
    """
    Convert a price to a strike.
    Strikes are rounded to the nearest multiple of granularity.
    """
    assert granularity > 0
    return int(round(price / granularity) * granularity)


def compute_strike(price: float, otm_pct: float, granularity: int) -> int:
    return round_strike(price * (1.0 + otm_pct), granularity=granularity)


@dataclass
class Option:
    product: str
    call: bool
    expiration: datetime
    strike: int

    def __hash__(self):
        return hash((self.call, self.expiration, self.strike))

    def __str__(self):
        """
        OCC Option Symbology
        """
        return f"{self.product}{self.expiration.strftime('%y%m%d')}{'C' if self.call else 'P'}{int(self.strike * 1000):08d}"

    def __repr__(self):
        return str(self)


@dataclass
class Order:
    """
    Option order: assume filled at market price.
    Stock order: assume filled at limit price. `price` means limit.
    """
    id: int
    buy: bool  # False = sell
    product: str
    instrument_type: InstrumentType
    price: float
    qty: int
    instrument: Union[Option, str]  # stock represented as str

    def __str__(self):
        return f"id={self.id} {'BUY' if self.buy else 'SELL'} {self.instrument} at ${self.price} x {self.qty}qty"

    def __repr__(self):
        return str(self)

    @property
    def is_option(self) -> bool:
        if self.instrument_type == InstrumentType.OPTION:
            assert type(self.instrument) == Option, "Instrument must be Option"
            return type(self.instrument) == Option
        return False


@dataclass
class Trade:
    order: Order
    price: float
    qty: int

    @property
    def premium(self) -> float:
        """
        The cash premium to be paid/received for this trade.
        """
        contract_size = 100 if self.order.is_option else 1
        return self.price * self.qty * contract_size
