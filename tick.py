import csv
from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class TickData:
    time: datetime
    high: float
    low: float
    open: float
    close: float


def load_csv(filename: str) -> List[TickData]:
    tick_data = []
    cnt = 0
    with open(filename, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            time = datetime.fromtimestamp(int(row['time']))
            # progress output
            if cnt % 1000 == 0:
                print(f"Loading {time} tick data, cnt = {cnt}")
            cnt += 1
            # construct tick data and add to collection
            tick = TickData(
                time=time,
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close'])
            )
            tick_data.append(tick)
    print(f"Finished loading data, last tick = {tick_data[-1].time}")
    return tick_data
