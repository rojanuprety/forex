import smtplib
import ssl
from email.message import EmailMessage
import pandas as pd
import time
import yfinance as yf
from scipy.signal import find_peaks
import numpy as np
import os
import json
from datetime import datetime

# List of all major Forex pairs
FOREX_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD",  # Major pairs
    "EURGBP", "EURJPY", "EURAUD", "EURCAD", "EURNZD",           # EUR crosses
    "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",           # GBP crosses
    "AUDJPY", "CADJPY", "NZDJPY",                               # JPY crosses
    "AUDCAD"                                                    # Other crosses
]

def fetch_forex_data(pair):
    try:
        forex_data = yf.download(tickers=f"{pair}=X", period="1d", interval="1h")
        if forex_data.empty:
            print(f"No data found for {pair}")
            return None
        forex_data = forex_data.reset_index()
        forex_data = forex_data.rename(columns={
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Date': 'Datetime'  # Ensure consistent column name for time
        })
        return forex_data
    except Exception as e:
        print(f"Error fetching data for {pair}: {e}")
        return None

def calculate_ema(data, period=200):
    return data['close'].ewm(span=period, adjust=False).mean()

def detect_m_pattern(data, ema, pair):
    high_prices = np.array(data['high'].dropna().values, dtype=np.float64).flatten()
    peaks, _ = find_peaks(high_prices, distance=5)
    
    valid_peaks = [p for p in peaks if abs(high_prices[p] - ema.iloc[p].item()) <= 0.0005]
    
    if len(valid_peaks) >= 2:
        first_peak, second_peak = valid_peaks[-2], valid_peaks[-1]
        first_low = data['low'].iloc[first_peak].item()
        second_low = data['low'].iloc[second_peak].item()
        if first_low > second_low:
            # Convert to timezone-naive timestamp
            pattern_time = data['Datetime'].iloc[second_peak].to_pydatetime().replace(tzinfo=None)
            print(f"M pattern detected for {pair} at {pattern_time}.")
            return True, pattern_time
    print(f"No M pattern detected for {pair}.")
    return False, None

def send_email_alert(pair, pattern_time):
    sender_email = os.getenv("EMAIL_ADDRESS")
    receiver_emails = ["rojan.uprety@gmail.com", "upramod9@gmail.com"]
    app_password = os.getenv("EMAIL_PASSWORD")

    formatted_time = pattern_time.strftime("%y/%m/%d %H.%M.%S")

    subject = f"ALERT M/W Pattern Alert: {pair}"
    body = (f"An M/W pattern has formed on {pair} 1hr timeframe with both peaks touching the 200 EMA.\n\n"
            f"Pattern detected at: {formatted_time}")

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = ", ".join(receiver_emails)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, app_password)
            server.send_message(msg)
        print(f"Email sent for {pair}")
    except Exception as e:
        print(f"Error sending email: {e}")

def load_alert_log():
    try:
        with open('alerts_log.json', 'r') as f:
            log_str = json.load(f)
            log = {}
            for pair, time_str in log_str.items():
                log[pair] = datetime.fromisoformat(time_str)
            return log
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        print("Warning: alerts_log.json is corrupted. Starting with empty log.")
        return {}

def save_alert_log(log):
    log_str = {pair: time.isoformat() for pair, time in log.items()}
    with open('alerts_log.json', 'w') as f:
        json.dump(log_str, f)

def main():
    alert_log = load_alert_log()
    updated = False

    print("\nStarting new monitoring cycle...")
    for pair in FOREX_PAIRS:
        print(f"Checking {pair}...")
        data = fetch_forex_data(pair)
        if data is not None and not data.empty:
            data['Datetime'] = pd.to_datetime(data['Datetime']).dt.tz_localize(None)
            ema_200 = calculate_ema(data)
            pattern_detected, pattern_time = detect_m_pattern(data, ema_200, pair)
            
            if pattern_detected:
                last_alert_time = alert_log.get(pair)
                if last_alert_time is None or pattern_time > last_alert_time:
                    send_email_alert(pair, pattern_time)
                    alert_log[pair] = pattern_time
                    updated = True
        else:
            print(f"No data fetched for {pair}.")
    
    if updated:
        save_alert_log(alert_log)
    print("Cycle complete")

if __name__ == "__main__":
    main()