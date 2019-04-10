from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from urllib.parse import quote
from pyquery import PyQuery as pq
from multiprocessing import Pool
import pymongo

# browser = webdriver.Chrome()
browser = webdriver.PhantomJS("D:/Anaconda3/phantomjs-2.1.1-windows/bin/phantomjs.exe")
wait = WebDriverWait(browser, 10)
KEYWORD = 'ipad'
MONGO_URL = 'localhost'
MONGO_DB = 'TAOBAO'
MONGO_COLLECTION = 'products'
client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]


def index_page(page):  # 定义一个获取索引页信息的函数
    print('正在爬取第', page, '页')
    try:
        url = 'https://s.taobao.com/search?q=' + quote(KEYWORD)
        browser.get(url)
        if page > 1:
            input = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, '#mainsrp-pager > div > div > div > div.form > input')))
            submit = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '#mainsrp-pager > div > div > div > div.form > span.btn.J_Submit')))
            input.clear()
            input.send_keys(page)
            submit.click()
        wait.until(EC.text_to_be_present_in_element(
            (By.CSS_SELECTOR, '#mainsrp-pager > div > div > div > ul > li.item.active > span'), str(page)))
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.m-itemlist .items .item')))
        get_products()
    except TimeoutException:
        index_page(page)


def get_products():  # 解析获取到的索引页的信息，将商品的信息从中提取出来
    html = browser.page_source
    doc = pq(html)
    items = doc('#mainsrp-itemlist .items .item').items()
    for item in items:
        product = {
            'image': item.find('.pic .img').attr('data-src'),
            'price': item.find('.price').text(),
            'deal': item.find('.deal-cnt').text(),
            'title': item.find('.title').text(),
            'shop': item.find('.shop').text(),
            'location': item.find('.location').text()
        }
        print(product)
        # save_to_mongo(product)


def save_to_mongo(result):  # 定义一个存储到MONGODB数据库的方法
    try:
        if db[MONGO_COLLECTION].insert(result):
            print('存储到Mongodb成功！')
    except Exception:
        print('存储到Mongodb失败！')


MAX_PAGE = 100


def main():  # 实现页码的遍历
    for i in range(1, MAX_PAGE + 1):
        index_page(i)


if __name__ == '__main__':
    main()
