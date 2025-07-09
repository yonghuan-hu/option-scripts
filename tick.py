import csv
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterator, Optional


@dataclass
class OptionData:
    time: datetime
    bid: float
    ask: float
    last: float
    iv: float
    volume: int


@dataclass
class StockData:
    time: datetime
    high: float
    low: float
    open: float
    close: float


@dataclass
class TickData:
    """
    Snapshot of the market combining both stock and options.
    """
    time: datetime
    stock_price: StockData
    option_prices: Dict[str, OptionData]


class MarketDataLoader:
    """
    A class to load market data from CSV files.
    """

    def __init__(self, stock_filename: str, option_filename: str):
        # file handles
        self.stock_reader = csv.DictReader(open(stock_filename, 'r'))
        self.option_reader = csv.DictReader(open(option_filename, 'r'))

        # file iters
        self.stock_iter: Iterator[StockData] = self._stock_generator()
        self.option_iter: Iterator[tuple[datetime,
                                         Dict[str, OptionData]]] = self._option_generator()

        # latest and next stock/options
        self.latest_stock: StockData = StockData(
            time=datetime.min,
            open=0.0,
            high=0.0,
            low=0.0,
            close=0.0
        )
        self.latest_options: Dict[str, OptionData] = {}
        self.next_stock = next(self.stock_iter, None)
        self.next_option_time, self.next_option_chain = next(
            self.option_iter, (None, {}))

    def _stock_generator(self) -> Iterator[StockData]:
        for row in self.stock_reader:
            yield StockData(
                time=datetime.fromtimestamp(int(row['time'])),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close'])
            )

    def _option_generator(self) -> Iterator[tuple[datetime, Dict[str, OptionData]]]:
        current_time = None
        chain: Dict[str, OptionData] = {}
        for row in self.option_reader:
            time = datetime.fromtimestamp(int(row['timestamp']))
            symbol = row['contractSymbol']
            data = OptionData(
                time=time,
                bid=float(row['bid']),
                ask=float(row['ask']),
                last=float(row['lastPrice']),
                iv=float(row['impliedVolatility']),
                volume=int(row['volume']) if row['volume'] else 0,
            )
            if current_time is None:
                current_time = time

            # when we see a new timestamp, yield the current chain
            if time != current_time:
                yield current_time, chain
                current_time = time
                chain = {}

            chain[symbol] = data

        assert current_time
        yield current_time, chain

    def next_tick(self) -> Optional[TickData]:
        if self.next_stock is None and self.next_option_time is None:
            return None

        next_times = []
        if self.next_stock:
            next_times.append(self.next_stock.time)
        if self.next_option_time:
            next_times.append(self.next_option_time)

        if not next_times:
            return None

        # advance to the whichever earlier ts in stock/options
        current_time = min(next_times)

        if self.next_stock and self.next_stock.time == current_time:
            self.latest_stock = self.next_stock
            self.next_stock = next(self.stock_iter, None)

        if self.next_option_time and self.next_option_time == current_time:
            self.latest_options = self.next_option_chain
            self.next_option_time, self.next_option_chain = next(
                self.option_iter, (None, {}))

        return TickData(
            time=current_time,
            stock_price=self.latest_stock,
            option_prices=self.latest_options
        )


if __name__ == "__main__":
    # Example usage
    md = MarketDataLoader(
        stock_filename='data/SPY-test.csv',
        option_filename='data/SPY-options.csv'
    )
    while True:
        tick = md.next_tick()
        if tick is None:
            break
        print(tick.time, tick.stock_price.open, len(tick.option_prices))
