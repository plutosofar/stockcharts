import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz

# List of ETF and crypto symbols
symbols = [
    'XLE', 'XLF', 'XLU', 'XLI', 'GDX', 'XLK', 'XLV', 'XLY', 'XLP', 'XLB', 'XOP', 'IYR',
    'XHB', 'ITB', 'VNQ', 'GDXJ', 'IYE', 'OIH', 'XME', 'XRT', 'SMH', 'IBB', 'KBE', 'KRE',
    'XTL', 'ARKK', 'BTC-USD', 'ETH-USD'
]

# Define the US Eastern Time (ET) timezone
us_eastern = pytz.timezone('US/Eastern')

# Define the date ranges for changes
today = datetime.now(us_eastern).date()
one_week_ago = today - timedelta(days=7)
one_month_ago = today - timedelta(days=30)
one_year_ago = today - timedelta(days=365)

# Function to calculate percentage change
def calculate_change(current, previous):
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100

# Function to find the closest available date
def get_closest_date(hist, target_date):
    dates = hist.index
    closest_date = min(dates, key=lambda x: abs(x - target_date))
    return closest_date

# DataFrame to store the data
data = []

for symbol in symbols:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y")
        
        if hist.empty:
            raise ValueError("No historical data available")
        
        # Convert index to date format
        hist.index = hist.index.date
        
        # Full name
        full_name = ticker.info.get('longName', ticker.info.get('name', 'N/A'))
        
        # Current price
        current_price = hist['Close'].iloc[-1]
        
        # Volume
        volume = hist['Volume'].iloc[-1]
        
        # Today's change
        today_change = calculate_change(hist['Close'].iloc[-1], hist['Close'].iloc[-2])
        
        # Week change
        week_date = get_closest_date(hist, one_week_ago)
        week_change = calculate_change(hist['Close'].iloc[-1], hist.loc[week_date]['Close'])
        
        # Month change
        month_date = get_closest_date(hist, one_month_ago)
        month_change = calculate_change(hist['Close'].iloc[-1], hist.loc[month_date]['Close'])
        
        # Year change
        year_date = get_closest_date(hist, one_year_ago)
        year_change = calculate_change(hist['Close'].iloc[-1], hist.loc[year_date]['Close'])
        
        data.append([symbol, full_name, current_price, volume, today_change, week_change, month_change, year_change])
    
    except Exception as e:
        print(f"Could not fetch data for {symbol}: {e}")
        data.append([symbol, 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A'])

# Create DataFrame
columns = ['Symbol', 'Full Name', 'Current Price (USD)', 'Volume', "Today's Change (%)", "Week's Change (%)", "Month's Change (%)", "Year's Change (%)"]
df = pd.DataFrame(data, columns=columns)

# Display the DataFrame
print(df)
