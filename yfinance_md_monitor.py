import os
import yfinance as yf
import pandas as pd
from time import sleep
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo


SYMBOLS = ["SPY", "QQQ"]
DTE_RANGE = 7


def save_realtime_data_1symbol(symbol: str):
    spy = yf.Ticker(symbol)
    now = datetime.now(ZoneInfo("America/Chicago"))
    print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')} CT")

    # determine expirations within the DTE range
    expirations = [
        date for date in spy.options
        if 0 <= (datetime.strptime(date, "%Y-%m-%d").date() - now.date()).days <= DTE_RANGE
    ]
    print(
        f"Fetching data for {len(expirations)} expirations (0-7 DTE): {expirations}")

    # fetch option chains for each expiration
    data = []
    for expiry in expirations:
        opt_chain = spy.option_chain(expiry)
        calls = opt_chain.calls.copy()
        puts = opt_chain.puts.copy()
        for df in (calls, puts):
            df["timestamp"] = int(now.timestamp())
            data.append(df)

    # consolidate all data into a single DataFrame and filter columns
    df = pd.concat(data, ignore_index=True)
    interested_cols = ["timestamp", "contractSymbol", "bid", "ask",
                       "lastPrice", "impliedVolatility", "volume"]
    df = df[interested_cols]
    df['volume'] = df['volume'].fillna(0)

    # save to CSV
    path = f"data/{symbol}-options.csv"
    file_exists = os.path.exists(path)
    df.to_csv(path, mode='a', header=not file_exists, index=False)
    print(f"Appended {len(df)} rows to {path}")


def save_realtime_data():
    for symbol in SYMBOLS:
        save_realtime_data_1symbol(symbol)


print("Starting 15-minute polling between 08:30 and 15:15 CT...")
save_realtime_data()
while True:
    now = datetime.now(ZoneInfo("America/Chicago"))
    if now.weekday() < 5:
        if time(8, 30) <= now.time() <= time(15, 15):
            save_realtime_data()
        else:
            print(f"Outside active hours: {now.time()}")
    else:
        print(f"Weekend: {now.strftime('%A')}, sleeping...")

    next_run = (now + timedelta(minutes=15)).replace(second=0, microsecond=0)
    sleep_time = (
        next_run - datetime.now(ZoneInfo("America/Chicago"))).total_seconds()
    sleep(max(sleep_time, 0))
