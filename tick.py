import csv
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterator, Optional
from zoneinfo import ZoneInfo


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


# TODO: only advance stock time and gather options before each stock time

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
        self.tick_count = 0
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
                time=datetime.fromtimestamp(
                    int(row['time']), tz=ZoneInfo("America/Chicago")),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close'])
            )

    def _option_generator(self) -> Iterator[tuple[datetime, Dict[str, OptionData]]]:
        current_time = None
        chain: Dict[str, OptionData] = {}
        for row in self.option_reader:
            time = datetime.fromtimestamp(
                int(row['timestamp']), tz=ZoneInfo("America/Chicago"))
            symbol = row['contractSymbol']
            data = OptionData(
                time=time,
                bid=float(row['bid']) if row['bid'] else 0,
                ask=float(row['ask']) if row['bid'] else 0,
                last=float(row['lastPrice']),
                iv=float(row['impliedVolatility']),
                volume=int(row['volume']) if row['volume'] else 0,
            )
            if current_time is None:
                current_time = time

            # check data quality
            if data.bid == 0 and data.ask == 0:
                print(
                    f"Found 0x0 option quotes for {symbol} at {time}, please check data quality!")

            # when we see a new timestamp, yield the current chain
            if time != current_time:
                yield current_time, chain
                current_time = time
                chain = {}

            chain[symbol] = data

        assert current_time
        yield current_time, chain

    @property
    def has_next_tick(self) -> bool:
        # TODO: also check options
        return self.next_stock is not None

    @property
    def next_tick_time(self) -> datetime:
        """
        Find the next tick time based on the next stock and option times, whichever earlier.
        Caller must check has_next_tick before calling.
        """
        assert self.has_next_tick, "No more ticks available"

        next_times = []
        if self.next_stock:
            next_times.append(self.next_stock.time)
        if self.next_option_time:
            next_times.append(self.next_option_time)

        return min(next_times)

    @property
    def end_of_day(self) -> bool:
        """
        Check if the next tick is on a different day.
        If there is no next tick, return True.
        """
        # TODO: handle out of order ticks
        if not self.has_next_tick:
            return True

        return self.next_tick_time.date() != self.latest_stock.time.date()

    def next_tick(self) -> TickData:
        """
        Fetch the next tick and advance iters.
        Caller must check has_next_tick before calling.
        """
        assert self.has_next_tick, "No more ticks available"

        time = self.next_tick_time
        self.tick_count += 1

        # advance stock and/or option iterators
        if self.next_stock and self.next_stock.time == time:
            self.latest_stock = self.next_stock
            self.next_stock = next(self.stock_iter, None)
        if self.next_option_time and self.next_option_time == time:
            self.latest_options.update(self.next_option_chain)
            self.next_option_time, self.next_option_chain = next(
                self.option_iter, (None, {}))

        return TickData(
            time=time,
            stock_price=self.latest_stock,
            option_prices=self.latest_options
        )


if __name__ == "__main__":
    # Example usage
    md = MarketDataLoader(
        stock_filename='data/SPY-202507-15min.csv',
        option_filename='data/SPY-options.csv'
    )
    while md.has_next_tick:
        tick = md.next_tick()
        print(tick.time, tick.stock_price.open, len(tick.option_prices))
