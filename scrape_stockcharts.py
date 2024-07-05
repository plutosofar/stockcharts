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

        # 使用yfinance获取RSI数据
        logging.info("Fetching RSI data for selected symbols...")
        rsi_data = []
        for symbol in df['SYMBOL']:
            try:
                # 计算日期范围：当前日期前60天
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
                
                # 下载股票历史数据
                stock_data = yf.download(symbol, start=start_date, end=end_date)
                
                # 计算30日RSI
                delta = stock_data['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=30).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=30).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                
                # 获取最新的RSI值
                latest_rsi = rsi.iloc[-1]
                
                # 筛选条件：RSI小于60
                if latest_rsi < 60:
                    rsi_data.append([symbol, latest_rsi])
            except Exception as e:
                logging.warning(f"Failed to fetch RSI for {symbol}: {e}")

        # 创建RSI数据的DataFrame
        rsi_df = pd.DataFrame(rsi_data, columns=['SYMBOL', 'RSI'])
        
        # 合并符合条件的数据
        final_data = pd.merge(df, rsi_df, on='SYMBOL')
        
        # 输出最终符合条件的数据
        print(final_data)

    else:
        logging.warning("No data extracted that meets the SCTR criteria")
else:
    logging.error("Table not found")
