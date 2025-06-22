from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Union


class InstrumentType(Enum):
    OPTION = "OPTION"
    STOCK = "STOCK"


@dataclass
class Option:
    product: str
    call: bool
    expiration: datetime
    strike: int

    def __hash__(self):
        return hash((self.call, self.expiration, self.strike))

    def __str__(self):
        return f"{self.product}{self.expiration.strftime('%Y%m%d')}-{'C' if self.call else 'P'}{self.strike}"

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
        return self.instrument_type == InstrumentType.OPTION


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
