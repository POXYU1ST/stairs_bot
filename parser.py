import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging

logger = logging.getLogger(__name__)

class LemanaproParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_price_by_article(self, article):
        """Получение цены по артикулу с сайта lemanapro.ru"""
        try:
            url = f"https://surgut.lemanapro.ru/search/?q={article}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Поиск цены на странице (нужно адаптировать под структуру сайта)
                price_selectors = [
                    '.price',
                    '.product-price',
                    '[class*="price"]',
                    '[data-price]'
                ]
                
                for selector in price_selectors:
                    price_elements = soup.select(selector)
                    for element in price_elements:
                        price_text = element.get_text(strip=True)
                        # Извлекаем числа из текста
                        price = ''.join(filter(str.isdigit, price_text))
                        if price:
                            return int(price)
            
            logger.warning(f"Цена для артикула {article} не найдена")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка парсинга артикула {article}: {e}")
            return None
    
    def update_prices(self, df):
        """Обновление цен в DataFrame"""
        try:
            updated_count = 0
            
            for index, row in df.iterrows():
                article = str(row['Артикул']).strip()
                if article and article != 'nan' and article != 'None' and article != '':
                    # Ждем между запросами чтобы не заблокировали
                    time.sleep(1)
                    
                    new_price = self.get_price_by_article(article)
                    if new_price and new_price != row['Продажная цена магазина']:
                        df.at[index, 'Продажная цена магазина'] = new_price
                        updated_count += 1
                        logger.info(f"Обновлена цена для {article}: {new_price}")
            
            logger.info(f"Обновлено {updated_count} цен")
            return df
                
        except Exception as e:
            logger.error(f"Ошибка обновления цен: {e}")
            return df
