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
TIME_OPEN = time(9, 00, 00)  # yfinance does not show quotes until 9:00 AM CT
TIME_CLOSE = time(15, 15, 59)  # market closes at 3:15 PM CT
PERIOD = 15  # scrape every PERIOD minutes


# cache last seen trade ts to avoid duplicates
lastTimestamp = {}


def has_new_trade(row):
    instrument = row["contractSymbol"]
    last = lastTimestamp.get(instrument)
    return pd.isna(last) or row["timestamp"] > last


def quote_price_valid(row):
    if pd.isna(row["bid"]) or pd.isna(row["ask"]):
        return False
    bid = float(row["bid"])
    ask = float(row["ask"])
    return bid < ask and bid >= 0


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
    cutoff = now - timedelta(hours=8)
    for expiry in expirations:
        opt_chain = spy.option_chain(expiry)
        calls = opt_chain.calls.copy()
        puts = opt_chain.puts.copy()
        for df in (calls, puts):
            df.rename(columns={
                "lastTradeDate": "timestamp",
            }, inplace=True)
            # only keep rows that satisfy ALL of the following:
            # 1. timestamp is within 8h
            # 2. timestamp is newer than cache
            # 3. bid and ask are not both 0
            df = df[df["timestamp"] >= cutoff]
            df = df[df.apply(has_new_trade, axis=1)]
            df = df[df.apply(quote_price_valid, axis=1)]
            data.append(df)
            # update cache
            for _, row in df.iterrows():
                lastTimestamp[row["contractSymbol"]] = row["timestamp"]

    # consolidate put/call data into a single DataFrame
    df = pd.concat(data, ignore_index=True)
    # filter columns
    interested_cols = ["timestamp", "contractSymbol", "bid", "ask",
                       "lastPrice", "impliedVolatility", "volume"]
    df = df[interested_cols]
    df["timestamp"] = df["timestamp"].astype(int) // 10**9
    df['impliedVolatility'] = df['impliedVolatility'].round(5)
    df['volume'] = df['volume'].fillna(0).astype(int)

    # save to CSV
    path = f"data/{symbol}-options.csv"
    file_exists = os.path.exists(path)
    df.to_csv(path, mode='a', header=not file_exists, index=False)
    logger.info(f"Appended {len(df)} rows to {path}")


def save_realtime_data():
    for symbol in SYMBOLS:
        # retry 3 times in case of failure
        for _ in range(3):
            try:
                save_realtime_data_1symbol(symbol)
                break  # success, exit retry loop
            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {e}")
                sleep(5)  # wait before retrying


if __name__ == "__main__":
    logger.open(LOG_PATH)
    print(
        f"Polling every {PERIOD} minute between {TIME_OPEN} and {TIME_CLOSE} CT...")
    while True:
        now = datetime.now(ZoneInfo("America/Chicago"))
        logger.settime(now)
        assert logger.file

        # check market hours
        if now.weekday() < 5 and TIME_OPEN <= now.time() <= TIME_CLOSE:
            save_realtime_data()

        # sleep until the next PERIOD-minute moment (e.g. 00, 15, 30, 45)
        now = datetime.now(ZoneInfo("America/Chicago"))
        minute = (now.minute // PERIOD + 1) * PERIOD
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
