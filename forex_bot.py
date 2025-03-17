import smtplib
import ssl
from email.message import EmailMessage
import pandas as pd
import time
import yfinance as yf
from scipy.signal import find_peaks
import numpy as np

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
    sender_email = "rojan.uprety@gmail.com"
    receiver_emails = ["rojan.uprety@gmail.com"]
    app_password = "mxpfasjkofzmioev"

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

def main():
    last_alert_times = {}  # Track last alert time for each pair
    
    while True:
        print("\nStarting new monitoring cycle...")
        for pair in FOREX_PAIRS:
            print(f"Checking {pair}...")
            data = fetch_forex_data(pair)
            if data is not None and not data.empty:
                data['Datetime'] = pd.to_datetime(data['Datetime']).dt.tz_localize(None)
                ema_200 = calculate_ema(data)
                pattern_detected, pattern_time = detect_m_pattern(data, ema_200, pair)
                
                if pattern_detected:
                    last_time = last_alert_times.get(pair, pd.Timestamp.min)
                    if pattern_time > last_time:
                        print(f"New M pattern detected for {pair}. Sending email...")
                        send_email_alert(pair, pattern_time)
                        last_alert_times[pair] = pattern_time
                    else:
                        print(f"Already alerted for {pair} at {last_alert_times[pair]}. Skipping.")
            else:
                print(f"No data fetched for {pair}.")
        
        print("Waiting for the next cycle...")
        time.sleep(3600)  # 5 minutes between checks

if __name__ == "__main__":
    main()