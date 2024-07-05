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

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)

# 设置日志记录
logging.basicConfig(level=logging.INFO)

# 创建忽略 SSL 验证的上下文
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

# 设置全局的 SSL 上下文
urllib.request.install_opener(urllib.request.build_opener(urllib.request.HTTPSHandler(context=context)))

# 自动安装或更新 chromedriver
chromedriver_autoinstaller.install()

# 设置 Chrome WebDriver 的选项
options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--ignore-certificate-errors")
options.add_argument("--test-type")

# 初始化 Chrome WebDriver
driver = webdriver.Chrome(options=options)

# 访问目标网页
url = 'https://stockcharts.com/freecharts/sctr.html'
driver.get(url)

# 等待页面加载完成，最大等待时间为 120 秒
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

# 获取页面内容
soup = BeautifulSoup(driver.page_source, 'html.parser')

# 关闭浏览器
driver.quit()

# 找到包含数据的表格
table = soup.find('table', {'class': 'table table-striped table-bordered table-hover nowrap dataTable no-footer'})
if table:
    # 解析表格中的数据
    headers = [header.text for header in table.find_all('th')]
    logging.info(f"Headers found: {headers}")

    rows = table.find_all('tr')[1:]  # 提取所有行数据
    data = []
    for row in rows:
        cells = row.find_all('td')
        if len(cells) > 5:  # 确保行中有足够的列
            symbol = cells[1].text.strip()
            sctr = cells[5].text.strip()
            #logging.info(f"Processing row - SYMBOL: {symbol}, SCTR: {sctr}")
            try:
                sctr_value = float(sctr)
                if sctr_value >= 60:  # 只选择 SCTR 大于等于 60 的记录
                    data.append([symbol, sctr_value])
            except ValueError:
                logging.warning(f"Skipping row with invalid SCTR value: {sctr}")

    # 创建 DataFrame
    df = pd.DataFrame(data, columns=['SYMBOL', 'SCTR'])

    # 检查是否有数据被提取出来
    if not df.empty:
        logging.info("Data extracted successfully")

        # 使用yfinance获取数据并计算AO、RSI和MACD
        logging.info("Fetching AO, RSI, and MACD data for selected symbols...")
        ao_rsi_macd_data = []
        for symbol in df['SYMBOL']:
            try:
                # 计算日期范围：当前日期前60天
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
                
                # 下载股票历史数据
                stock_data = yf.download(symbol, start=start_date, end=end_date)
                
                # 计算AO（Accumulation/Distribution Oscillator）
                ao = stock_data['Close'].rolling(window=5).mean() - stock_data['Close'].rolling(window=34).mean()
                
                # 计算30日RSI
                delta = stock_data['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=30).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=30).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                
                # 计算MACD及其信号线
                exp1 = stock_data['Close'].ewm(span=12, adjust=False).mean()
                exp2 = stock_data['Close'].ewm(span=26, adjust=False).mean()
                macd = exp1 - exp2
                signal = macd.ewm(span=9, adjust=False).mean()
                
                # 计算MACD的柱状图
                macd_histogram = macd - signal
                
                # 获取最新的AO、RSI和MACD值
                latest_ao = ao.iloc[-1]
                latest_rsi = rsi.iloc[-1]
                latest_macd = macd.iloc[-1]
                latest_signal = signal.iloc[-1]
                
                # 筛选条件：AO最新一日大于昨日，昨日大于前日；RSI小于60；MACD金叉；MACD柱状图递增
                if (ao.iloc[-1] > ao.iloc[-2]) and (ao.iloc[-2] > ao.iloc[-3]) \
                   and (latest_rsi < 60) and (latest_macd > latest_signal) \
                   and (macd_histogram.iloc[-1] > macd_histogram.iloc[-2]):
                    ao_rsi_macd_data.append([symbol, latest_ao, latest_rsi, latest_macd, latest_signal])
            except Exception as e:
                logging.warning(f"Failed to fetch AO, RSI, and MACD for {symbol}: {e}")

        # 创建AO、RSI和MACD数据的DataFrame
        ao_rsi_macd_df = pd.DataFrame(ao_rsi_macd_data, columns=['SYMBOL', 'AO', 'RSI', 'MACD', 'Signal'])
        
        # 合并符合条件的数据
        final_data = pd.merge(df, ao_rsi_macd_df, on='SYMBOL')
        
        # 输出最终符合条件的数据
        print(final_data)

    else:
        logging.warning("No data extracted that meets the SCTR criteria")
else:
    logging.error("Table not found")
