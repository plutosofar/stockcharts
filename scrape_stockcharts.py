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

# 設置日誌紀錄
logging.basicConfig(level=logging.INFO)

# 創建忽略 SSL 驗證的上下文
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

# 設置全局的 SSL 上下文
urllib.request.install_opener(urllib.request.build_opener(urllib.request.HTTPSHandler(context=context)))

# 自動安裝或更新 chromedriver
#chromedriver_autoinstaller.install()

# 設置 Chrome WebDriver 的選項
options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--ignore-certificate-errors")
options.add_argument("--test-type")

# 初始化 Chrome WebDriver
driver = webdriver.Chrome(options=options)

# 訪問目標網頁
url = 'https://stockcharts.com/freecharts/sctr.html'
driver.get(url)

# 等待頁面加載完成，最大等待時間為 120 秒
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

# 獲取頁面內容
soup = BeautifulSoup(driver.page_source, 'html.parser')

# 關閉瀏覽器
driver.quit()

# 找到包含數據的表格
table = soup.find('table', {'class': 'table table-striped table-bordered table-hover nowrap dataTable no-footer'})
if table:
    # 解析表格中的前10行數據
    headers = [header.text for header in table.find_all('th')]
    rows = table.find_all('tr')[1:500]  # 只提取前10行數據
    data = []
    for row in rows:
        cells = row.find_all('td')
        # 提取 SYMBOL 和 SCTR 列的數據
        symbol = cells[1].text.strip()
        sctr = cells[5].text.strip()
        data.append([symbol, sctr])

    # 創建 DataFrame
    df = pd.DataFrame(data, columns=['SYMBOL', 'SCTR'])

    # 將數據打印到終端
    print(df)
else:
    logging.error("Table not found")
