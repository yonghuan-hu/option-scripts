import yfinance as yf
import pandas as pd
from time import sleep
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo


def save_realtime_data():
    spy = yf.Ticker("SPY")
    today = datetime.now().date()

    expirations = [
        date for date in spy.options
        if 0 <= (datetime.strptime(date, "%Y-%m-%d").date() - today).days <= 3
    ]
    print("Fetching data for expirations (0-3 DTE):", expirations)

    data = []
    for expiry in expirations:
        opt_chain = spy.option_chain(expiry)
        calls = opt_chain.calls.copy()
        data.append(calls)
        puts = opt_chain.puts.copy()
        data.append(puts)

    # Combine all and save to CSV
    df = pd.concat(data, ignore_index=True)
    current_time_str = datetime.now().strftime("%Y%m%d-%H%M")
    filepath = f"data/SPY-options-{current_time_str}.csv"
    df.to_csv(filepath, index=False)
    print(f"CSV files saved: {filepath}")


print("Starting 15-minute polling between 08:30 and 15:15 CT...")
save_realtime_data()
while True:
    now = datetime.now(ZoneInfo("America/Chicago"))
    if now.weekday() < 5:  # Weekdays only
        if time(8, 30) <= now.time() <= time(15, 15):
            save_realtime_data()
        else:
            print(f"Outside active hours: {now.time()}")
    else:
        print(f"Weekend: {now.strftime('%A')}, sleeping...")

    # Sleep until the next 15-minute mark
    next_run = (now + timedelta(minutes=15)).replace(second=0, microsecond=0)
    sleep_time = (
        next_run - datetime.now(ZoneInfo("America/Chicago"))).total_seconds()
    sleep(max(sleep_time, 0))
