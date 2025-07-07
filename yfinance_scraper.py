import os
import yfinance as yf
import pandas as pd
from time import sleep
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from log import logger

LOG_PATH = "tmp/yfinance_scraper.log"
SYMBOLS = ["SPY", "QQQ"]
DTE_RANGE = 7
TIME_OPEN = time(8, 30)
TIME_CLOSE = time(15, 15)


def save_realtime_data_1symbol(symbol: str):
    spy = yf.Ticker(symbol)
    now = datetime.now(ZoneInfo("America/Chicago"))

    # determine expirations within the DTE range
    expirations = [
        date for date in spy.options
        if 0 <= (datetime.strptime(date, "%Y-%m-%d").date() - now.date()).days <= DTE_RANGE
    ]
    logger.info(
        f"Fetching data for {len(expirations)} {symbol} expirations: {expirations}")

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
    logger.info(f"Appended {len(df)} rows to {path}")


def save_realtime_data():
    for symbol in SYMBOLS:
        save_realtime_data_1symbol(symbol)


if __name__ == "__main__":
    logger.open(LOG_PATH)
    print("Starting 15-minute polling between 08:30 and 15:15 CT...")
    while True:
        now = datetime.now(ZoneInfo("America/Chicago"))
        logger.settime(now)
        assert logger.file

        # check market hours
        if now.weekday() < 5 and TIME_OPEN <= now.time() <= TIME_CLOSE:
            save_realtime_data()

        # sleep until the next 15-minute moment (.00, .15, .30, .45)
        now = datetime.now(ZoneInfo("America/Chicago"))
        minute = (now.minute // 15 + 1) * 15
        if minute == 60:
            # next hour
            next_run = now.replace(
                minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            next_run = now.replace(minute=minute, second=0, microsecond=0)
        logger.info(
            f"Sleeping till next invocation at {next_run.astimezone(ZoneInfo('America/Chicago'))}")
        sleep_time = (
            next_run - datetime.now(ZoneInfo("America/Chicago"))).total_seconds()
        logger.file.flush()  # flush log before sleeping
        sleep(max(sleep_time, 0))
