import logging
import ssl
import urllib.request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import pandas as pd
import chromedriver_autoinstaller
import yfinance as yf
from datetime import datetime, timedelta
import requests
# Set display options
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)

# Setup logging
logging.basicConfig(level=logging.INFO)

# Create an SSL context that ignores SSL certificate errors
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

# Install the SSL context globally
urllib.request.install_opener(urllib.request.build_opener(urllib.request.HTTPSHandler(context=context)))

# Automatically install or update chromedriver
chromedriver_autoinstaller.install()

# Set Chrome WebDriver options
options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--ignore-certificate-errors")
options.add_argument("--test-type")

# Initialize Chrome WebDriver
driver = webdriver.Chrome(options=options)

# Access the target webpage
url = 'https://stockcharts.com/freecharts/sctr.html'
driver.get(url)

# Wait for the page to load completely
try:
    logging.info("Waiting for element 'table-responsive' to be visible...")
    element = WebDriverWait(driver, 120).until(
        EC.visibility_of_element_located((By.CLASS_NAME, 'table-responsive'))
    )
except TimeoutException as e:
    logging.error("Timeout waiting for element: %s", e)
    driver.quit()
    exit()

logging.info("Element 'table-responsive' is now visible. Proceeding with data extraction.")

# Get the page content
soup = BeautifulSoup(driver.page_source, 'html.parser')

# Close the browser
driver.quit()

# Find the table containing the data
table = soup.find('table', {'class': 'table table-striped table-bordered table-hover nowrap dataTable no-footer'})
if table:
    # Parse the table data
    headers = [header.text for header in table.find_all('th')]
    logging.info(f"Headers found: {headers}")

    rows = table.find_all('tr')[1:]  # Extract all row data
    data = []
    for row in rows:
        cells = row.find_all('td')
        if len(cells) > 5:  # Ensure the row has enough columns
            symbol = cells[1].text.strip().replace('/', '.')  # Replace '/' with '.' for yfinance compatibility
            sctr = cells[5].text.strip()
            try:
                sctr_value = float(sctr)
                if sctr_value >= 60:  # Filter records where SCTR >= 60
                    data.append([symbol, sctr_value])
            except ValueError:
                logging.warning(f"Skipping row with invalid SCTR value: {sctr}")

    # Create a DataFrame
    df = pd.DataFrame(data, columns=['SYMBOL', 'SCTR'])

    # Check if any data was extracted
    if not df.empty:
        logging.info("Data extracted successfully")

        # Fetch data from yfinance and calculate AO, RSI, MACD, VWAP, and timestamp
        logging.info("Fetching AO, RSI, MACD, VWAP, and timestamp data for selected symbols...")
        ao_rsi_macd_data = []
        for symbol in df['SYMBOL']:
            try:
                # Calculate date range: last 60 days
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')

                # Download historical stock data
                stock_data = yf.download(symbol, start=start_date, end=end_date)

                # Check if data is available
                if stock_data.empty:
                    logging.warning(f"No data returned for {symbol}. Skipping.")
                    continue

                # Calculate AO (Awesome Oscillator)
                ao = stock_data['Close'].rolling(window=5).mean() - stock_data['Close'].rolling(window=34).mean()

                # Calculate 30-day RSI
                delta = stock_data['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))

                # Calculate MACD and its signal line
                exp1 = stock_data['Close'].ewm(span=12, adjust=False).mean()
                exp2 = stock_data['Close'].ewm(span=26, adjust=False).mean()
                macd = exp1 - exp2
                signal = macd.ewm(span=9, adjust=False).mean()

                # Calculate MACD histogram
                macd_histogram = macd - signal

                # Calculate VWAP using EMA
                volume = stock_data['Volume']
                vwap = (stock_data['Close'] * volume).cumsum() / volume.cumsum()
                vwap_ema = vwap.ewm(span=5, adjust=False).mean()  # EMA of VWAP

                # Get the latest AO, RSI, MACD, VWAP, and signal values
                latest_ao = ao.iloc[-1]
                latest_rsi = rsi.iloc[-1]
                latest_macd = macd.iloc[-1]
                latest_signal = signal.iloc[-1]
                latest_vwap = vwap_ema.iloc[-1]

                # Get the timestamp of the latest data
                latest_timestamp = stock_data.index[-1].strftime('%Y-%m-%d %H:%M:%S')

                # Filter conditions (including the MACD golden cross under the basic line)
                if (ao.iloc[-1] > ao.iloc[-2]) and (ao.iloc[-2] > ao.iloc[-3]) \
                   and (latest_rsi < 70) and (latest_macd > latest_signal) \
                   and (macd.iloc[-2] < signal.iloc[-2]) and (macd.iloc[-1] > signal.iloc[-1]) \
                   and (latest_macd < 0) and (latest_signal < 0) \
                   and (macd_histogram.iloc[-1] > macd_histogram.iloc[-2]):
                    ao_rsi_macd_data.append([symbol, latest_ao, latest_rsi, latest_macd, latest_signal, latest_vwap, latest_timestamp])
            except Exception as e:
                logging.warning(f"Failed to fetch AO, RSI, MACD, VWAP, and timestamp for {symbol}: {e}")

        # Create DataFrame with AO, RSI, MACD, VWAP, and timestamp data
        ao_rsi_macd_df = pd.DataFrame(ao_rsi_macd_data, columns=['SYMBOL', 'AO', 'RSI', 'MACD', 'Signal', 'VWAP', 'Timestamp'])

        # Merge the filtered data
        final_data = pd.merge(df, ao_rsi_macd_df, on='SYMBOL')

        # Output the final filtered data
        if not final_data.empty:
            logging.info("Final data that meets the criteria:")
            print(final_data)

            # Export the final data to a text file with timestamp
            output_file = f"/Users/leesiufung/Documents/python_stock_env/filtered_stock_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            final_data.to_csv(output_file, index=False, sep='\t')
            logging.info(f"Data exported to {output_file}")

            #send the line message to me

            url = 'https://notify-api.line.me/api/notify'
            token = '剛剛複製的權杖'
            headers = {
                    'Authorization': 'Bearer ' + ''    # 設定權杖
            }
            data = {
            'message':f"Stock list for {datetime.now().strftime('%Y%m%d_%H%M%S')}\n {final_data}"     # 設定要發送的訊息
            }
            data = requests.post(url, headers=headers, data=data)   # 使用 POST 方法
        else:
            logging.warning("No data meets the final filtering criteria")
    else:
        logging.warning("No data extracted that meets the SCTR criteria")
else:
    logging.error("Table not found")
