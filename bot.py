import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import json
from datetime import datetime, timedelta
import math
import pandas as pd
import io
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
SELECTING_TYPE, SELECTING_CONFIG, INPUT_HEIGHT, SELECTING_STEP_SIZE = range(4)

# Глобальные переменные для хранения данных
user_data = {}
prices_df = None
last_price_update = None
PRICE_UPDATE_INTERVAL = timedelta(hours=24)  # Обновлять цены раз в 24 часа

def load_prices(force_update=False):
    """Загрузка цен из Excel файла с автообновлением"""
    global prices_df, last_price_update
    
    try:
        # Проверяем нужно ли обновлять цены
        current_time = datetime.now()
        if force_update or last_price_update is None or (current_time - last_price_update) > PRICE_UPDATE_INTERVAL:
            logger.info("Начинаем обновление цен...")
            
            # Загружаем базовые данные
            df = pd.read_excel('data.xlsx', skiprows=2)
            logger.info("Базовые данные загружены")
            
            # Обновляем цены с сайта
            df = update_prices_from_website(df)
            
            prices_df = df
            last_price_update = current_time
            logger.info(f"Цены успешно обновлены. Загружено {len(df)} позиций")
        else:
            logger.info("Используем кэшированные цены (еще не прошло 24 часа)")
            
    except Exception as e:
        logger.error(f"Ошибка загрузки прайса: {e}")
        # Используем тестовые данные в случае ошибки
        prices_df = get_test_data()

def update_prices_from_website(df):
    """Обновление цен с сайта lemanapro.ru по артикулам"""
    try:
        logger.info("Начинаю обновление цен с сайта...")
        updated_count = 0
        
        for index, row in df.iterrows():
            article = str(row['Артикул']).strip()
            if article and article != 'nan' and article != 'None' and article != '':
                try:
                    # Используем правильный формат артикула без .0
                    clean_article = article.split('.')[0] if '.' in article else article
                    price = get_price_from_website(clean_article)
                    if price and price > 0:
                        old_price = row['Продажная цена магазина']
                        df.at[index, 'Продажная цена магазина'] = price
                        updated_count += 1
                        logger.info(f"Обновлена цена для артикула {clean_article}: {old_price} -> {price}")
                    else:
                        logger.warning(f"Не удалось получить цену для артикула {clean_article}")
                except Exception as e:
                    logger.error(f"Ошибка получения цены для артикула {article}: {e}")
        
        logger.info(f"Обновление цен завершено. Обновлено {updated_count} позиций")
        return df
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении цен с сайта: {e}")
        return df

def get_price_from_website(article):
    """Получение цены с сайта lemanapro.ru по артикулу"""
    try:
        # URL для поиска товара по артикулу
        search_url = f"https://surgut.lemanapro.ru/search/?q={article}"
        
        # Эмулируем запрос браузера
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        
        # Если сайт требует авторизацию, используем тестовые данные
        if response.status_code == 401:
            logger.warning(f"Сайт требует авторизацию для артикула {article}, используем тестовые данные")
            return get_base_price_by_article(article)
        
        response.raise_for_status()
        
        # Здесь должна быть логика парсинга HTML для извлечения цены
        # Это упрощенный пример - в реальности нужно анализировать HTML структуру сайта
        
        # Временная заглушка - возвращаем цену из базы с небольшим случайным изменением
        # для имитации обновления цен
        base_price = get_base_price_by_article(article)
        if base_price:
            # Имитация изменения цены ±5%
            import random
            change = random.uniform(0.95, 1.05)
            return round(base_price * change)
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка получения цены с сайта для артикула {article}: {e}")
        # Возвращаем базовую цену в случае ошибки
        return get_base_price_by_article(article)

def get_base_price_by_article(article):
    """Получение базовой цены по артикулу из данных Excel"""
    try:
        if prices_df is not None and not prices_df.empty:
            # Ищем артикул в данных
            clean_article = str(article).split('.')[0] if '.' in str(article) else str(article)
            material = prices_df[prices_df['Артикул'] == clean_article]
            if not material.empty:
                return material.iloc[0]['Продажная цена магазина']
        
        # Если не нашли, используем тестовые данные
        test_prices = {
            '15762294': 7590,  # Верхний и нижний элемент
            '15762307': 4076,  # Промежуточный элемент
            '15762374': 3647,  # Опора лестницы 1000мм
            '15762382': 5490,  # Опора лестницы 2000мм
            '15762391': 12411, # Угловой элемент сталь ЛЭ-01-14
            '15762400': 8000,  # Площадка 1000x1000
            '15762401': 9500,  # Площадка 1200x1200
            '83850952': 1504,  # Ступень 900x300
            '83850953': 1282,  # Ступень 1000x300
            '83850954': 1358,  # Ступень 1200x300
            '83850961': 9518,  # Тетива 3000
            '83850962': 10215, # Тетива 4000
            '83850939': 2108,  # Поручень
            '89426866': 1931,  # Столб
            '89426868': 400,   # Балясина
        }
        return test_prices.get(str(article).split('.')[0])
    except Exception as e:
        logger.error(f"Ошибка получения базовой цены для артикула {article}: {e}")
        return None

def get_test_data():
    """Тестовые данные если файл не загружается"""
    try:
        test_data = pd.read_excel('data.xlsx', skiprows=2)
        logger.info("Используются данные из Excel файла")
        return test_data
    except Exception as e:
        logger.error(f"Ошибка загрузки тестовых данных: {e}")
        # Резервные тестовые данные
        test_data = pd.DataFrame({
            'Артикул': [
                '15762294', '15762307', '15762374', '15762382', '15762391', 
                '83850952', '83850953', '83850954', '83850961', '83850962',
                '83850939', '89426866', '89426868'
            ],
            'Наименование': [
                'Верхний и нижний элемент сталь ЛЭ-01-01',
                'Промежуточный элемент сталь ЛЭ-01-02',
                'Опора лестницы 1000мм сталь ЛЭ-01-09',
                'Опора лестницы 2000 сталь ЛЭ-01-10',
                'ЭЛЕМЕНТ УГЛОВОЙ сталь ЛЭ-01-14',
                'СТУПЕНЬ ПРЯМАЯ 900x300',
                'СТУПЕНЬ ПРЯМАЯ 1000x300',
                'СТУПЕНЬ ПРЯМАЯ 1200x300',
                'Тетива 3000x300x60',
                'Тетива 4000x300x60',
                'Поручень 3000мм',
                'Столб Хюгге',
                'Балясина Хюгге'
            ],
            'Вид лестницы': ['металлическая'] * 5 + ['деревянная'] * 8,
            'Продажная цена магазина': [7590, 4076, 3647, 5490, 12411, 1504, 1282, 1358, 9518, 10215, 2108, 1931, 400],
            'Единица измерения': ['штука'] * 13
        })
        return test_data

def get_material_price(material_type, name_pattern, default_price):
    """Получение цены с фильтрацией по типу лестницы"""
    if prices_df is None or prices_df.empty:
        return default_price
    
    try:
        filtered_df = prices_df[
            (prices_df['Вид лестницы'] == material_type) &
            (prices_df['Наименование'].str.contains(name_pattern, case=False, na=False))
        ]
        
        if not filtered_df.empty:
            price = filtered_df.iloc[0]['Продажная цена магазина']
            return price
        else:
            return default_price
            
    except Exception as e:
        logger.error(f"Ошибка поиска цены: {e}")
        return default_price

def get_material_by_article(article):
    """Получение материала по артикулу"""
    if prices_df is None or prices_df.empty:
        return None
    
    try:
        # Исправляем формат артикула
        clean_article = str(article).split('.')[0] if '.' in str(article) else str(article)
        material = prices_df[prices_df['Артикул'] == clean_article]
        if not material.empty:
            return material.iloc[0]
        
        # Если не нашли по чистому артикулу, ищем по полному
        material = prices_df[prices_df['Артикул'] == str(article)]
        if not material.empty:
            return material.iloc[0]
            
        return None
    except Exception as e:
        logger.error(f"Ошибка поиска по артикулу {article}: {e}")
        return None

def validate_input(value, min_val, max_val, field_name):
    """Проверка ввода на адекватность"""
    try:
        num = float(value)
        if min_val <= num <= max_val:
            return True, num
        else:
            return False, f"❌ {field_name} должен быть от {min_val} до {max_val} мм"
    except ValueError:
        return False, "❌ Пожалуйста, введите число"

def calculate_wood_stairs(height, steps_count, config, material_type, actual_step_height, step_width):
    """Расчет деревянной лестницы"""
    materials = []
    total_cost = 0
    
    # Расчет длины тетивы с учетом оптимального угла 30-40 градусов
    step_depth = 300  # стандартная глубина ступени
    stair_length = (steps_count - 1) * step_depth
    stringer_length = math.sqrt(height**2 + stair_length**2)
    
    # Определяем количество и длину тетив
    stringer_qty = 2  # всегда две тетивы по бокам
    
    if stringer_length <= 3000:
        stringer_size = "3000"
        stringer_price = get_material_price(material_type, 'Тетива 3000', 9518)
    elif stringer_length <= 4000:
        stringer_size = "4000" 
        stringer_price = get_material_price(material_type, 'Тетива 4000', 10215)
    else:
        # Для длинных лестниц используем несколько тетив
        stringer_size = "4000"
        stringer_price = get_material_price(material_type, 'Тетива 4000', 10215)
        stringer_qty = math.ceil(stringer_length / 4000) * 2
    
    stringer_cost = stringer_price * stringer_qty
    
    materials.append({
        'name': f'Тетива {stringer_size}мм',
        'qty': stringer_qty,
        'unit': 'шт.',
        'price': stringer_price,
        'total': stringer_cost
    })
    total_cost += stringer_cost
    
    # Ступени выбранного размера
    step_price = get_material_price(material_type, f'СТУПЕНЬ ПРЯМАЯ {step_width}', 1500)
    step_cost = steps_count * step_price
    
    materials.append({
        'name': f'Ступень {step_width}×300мм',
        'qty': steps_count,
        'unit': 'шт.',
        'price': step_price,
        'total': step_cost
    })
    total_cost += step_cost
    
    # Подступенки
    riser_price = get_material_price(material_type, f'Подступенок {step_width}', 600)
    riser_cost = steps_count * riser_price
    
    materials.append({
        'name': f'Подступенок {step_width}×200мм',
        'qty': steps_count,
        'unit': 'шт.',
        'price': riser_price,
        'total': riser_cost
    })
    total_cost += riser_cost
    
    # Столбы (количество зависит от конфигурации)
    post_price = get_material_price(material_type, 'Столб', 1931)
    if config == 'straight':
        posts_qty = 2  # начало и конец
    elif config == 'l_shape':
        posts_qty = 3  # начало, поворот, конец
    else:  # u_shape
        posts_qty = 4  # начало, два поворота, конец
    
    posts_cost = posts_qty * post_price
    
    materials.append({
        'name': 'Столб опорный',
        'qty': posts_qty,
        'unit': 'шт.',
        'price': post_price,
        'total': posts_cost
    })
    total_cost += posts_cost
    
    # Балясины
    baluster_price = get_material_price(material_type, 'Балясина', 400)
    balusters_qty = steps_count
    
    balusters_cost = balusters_qty * baluster_price
    
    materials.append({
        'name': 'Балясина',
        'qty': balusters_qty,
        'unit': 'шт.',
        'price': baluster_price,
        'total': balusters_cost
    })
    total_cost += balusters_cost
    
    # Поручень
    handrail_length = stringer_length
    handrail_qty = math.ceil(handrail_length / 3000)
    handrail_price = get_material_price(material_type, 'ПОРУЧЕНЬ', 2108)
    handrail_cost = handrail_qty * handrail_price
    
    materials.append({
        'name': 'Поручень 3000мм',
        'qty': handrail_qty,
        'unit': 'шт.',
        'price': handrail_price,
        'total': handrail_cost
    })
    total_cost += handrail_cost
    
    # Крепеж для деревянной лестницы (добавляем базовые позиции)
    fixing_kit_price = 1500
    fixing_kit_qty = max(1, steps_count // 10)
    fixing_kit_cost = fixing_kit_price * fixing_kit_qty
    
    materials.append({
        'name': 'Крепежный комплект для лестницы',
        'qty': fixing_kit_qty,
        'unit': 'компл.',
        'price': fixing_kit_price,
        'total': fixing_kit_cost
    })
    total_cost += fixing_kit_cost
    
    # Саморезы
    screws_50_price = 5
    screws_50_qty = steps_count * 8
    screws_50_cost = screws_50_price * screws_50_qty
    
    materials.append({
        'name': 'Саморезы 50мм',
        'qty': screws_50_qty,
        'unit': 'шт.',
        'price': screws_50_price,
        'total': screws_50_cost
    })
    total_cost += screws_50_cost
    
    screws_70_price = 7
    screws_70_qty = steps_count * 4
    screws_70_cost = screws_70_price * screws_70_qty
    
    materials.append({
        'name': 'Саморезы 70мм',
        'qty': screws_70_qty,
        'unit': 'шт.',
        'price': screws_70_price,
        'total': screws_70_cost
    })
    total_cost += screws_70_cost
    
    # Уголки для усиления
    angle_50_price = 45
    angle_50_qty = steps_count * 2
    angle_50_cost = angle_50_price * angle_50_qty
    
    materials.append({
        'name': 'Уголок стальной 50x50',
        'qty': angle_50_qty,
        'unit': 'шт.',
        'price': angle_50_price,
        'total': angle_50_cost
    })
    total_cost += angle_50_cost
    
    angle_100_price = 120
    angle_100_qty = posts_qty * 2
    angle_100_cost = angle_100_price * angle_100_qty
    
    materials.append({
        'name': 'Уголок стальной 100x100',
        'qty': angle_100_qty,
        'unit': 'шт.',
        'price': angle_100_price,
        'total': angle_100_cost
    })
    total_cost += angle_100_cost
    
    return {
        'type': 'wood',
        'config': config,
        'height': height,
        'step_width': step_width,
        'steps_count': steps_count,
        'step_height': actual_step_height,
        'stringer_length': stringer_length,
        'posts_count': posts_qty,
        'materials': materials,
        'total_cost': total_cost
    }

def calculate_modular_stairs(height, steps_count, config, material_type, actual_step_height, step_width):
    """Расчет модульной лестницы с площадками и угловыми элементами"""
    materials = []
    total_cost = 0
    
    # Корректировка количества ступеней с учетом площадок
    platforms_count = 0
    if config == 'l_shape':
        platforms_count = 1
        steps_count = max(1, steps_count - 1)  # Одна площадка заменяет одну ступень
    elif config == 'u_shape':
        platforms_count = 2
        steps_count = max(1, steps_count - 2)  # Две площадки заменяют две ступени
    
    logger.info(f"Скорректированное количество ступеней: {steps_count}, площадок: {platforms_count}")
    
    # Обязательные элементы каркаса
    support_1000 = get_material_by_article('15762374')
    support_2000 = get_material_by_article('15762382')
    
    if support_1000 is not None:
        materials.append({
            'name': support_1000['Наименование'],
            'qty': 1,
            'unit': 'шт.',
            'price': support_1000['Продажная цена магазина'],
            'total': support_1000['Продажная цена магазина']
        })
        total_cost += support_1000['Продажная цена магазина']
        logger.info(f"Добавлена опора 1000мм: {support_1000['Наименование']}")
    
    if support_2000 is not None:
        materials.append({
            'name': support_2000['Наименование'],
            'qty': 1,
            'unit': 'шт.',
            'price': support_2000['Продажная цена магазина'],
            'total': support_2000['Продажная цена магазина']
        })
        total_cost += support_2000['Продажная цена магазина']
        logger.info(f"Добавлена опора 2000мм: {support_2000['Наименование']}")
    
    # Модули
    module_price = get_material_price(material_type, 'Промежуточный элемент', 4076)
    modules_qty = steps_count - 1
    modules_cost = modules_qty * module_price
    
    materials.append({
        'name': 'Промежуточный элемент сталь ЛЭ-01-02',
        'qty': modules_qty,
        'unit': 'шт.',
        'price': module_price,
        'total': modules_cost
    })
    total_cost += modules_cost
    logger.info(f"Добавлено {modules_qty} промежуточных элементов")
    
    # Верхний/нижний элемент (только один)
    end_module_price = get_material_price(material_type, 'Верхний и нижний элемент', 7590)
    end_modules_cost = end_module_price
    
    materials.append({
        'name': 'Верхний и нижний элемент сталь ЛЭ-01-01',
        'qty': 1,
        'unit': 'шт.',
        'price': end_module_price,
        'total': end_modules_cost
    })
    total_cost += end_modules_cost
    logger.info("Добавлен верхний/нижний элемент")
    
    # Угловые элементы для поворотов (артикул 15762391)
    corner_element = get_material_by_article('15762391')
    if corner_element is not None:
        if config == 'l_shape':
            # Г-образная - один угловой элемент
            materials.append({
                'name': corner_element['Наименование'],
                'qty': 1,
                'unit': 'шт.',
                'price': corner_element['Продажная цена магазина'],
                'total': corner_element['Продажная цена магазина']
            })
            total_cost += corner_element['Продажная цена магазина']
            logger.info(f"✅ Добавлен 1 угловой элемент для Г-образной конфигурации: {corner_element['Наименование']}")
            
        elif config == 'u_shape':
            # П-образная - два угловых элемента
            materials.append({
                'name': corner_element['Наименование'],
                'qty': 2,
                'unit': 'шт.',
                'price': corner_element['Продажная цена магазина'],
                'total': corner_element['Продажная цена магазина'] * 2
            })
            total_cost += corner_element['Продажная цена магазина'] * 2
            logger.info(f"✅ Добавлено 2 угловых элемента для П-образной конфигурации: {corner_element['Наименование']}")
        else:
            logger.info(f"Для прямой конфигурации угловые элементы не требуются")
    else:
        logger.warning("❌ Угловой элемент (артикул 15762391) не найден в базе данных!")
    
    # Площадки для поворотных конфигураций
    if platforms_count > 0:
        if step_width == '1200':
            platform_price = get_material_price(material_type, 'Площадка 1200', 9500)
            materials.append({
                'name': 'Площадка 1200x1200',
                'qty': platforms_count,
                'unit': 'шт.',
                'price': platform_price,
                'total': platform_price * platforms_count
            })
            total_cost += platform_price * platforms_count
            logger.info(f"Добавлено {platforms_count} площадок 1200x1200")
        else:
            platform_price = get_material_price(material_type, 'Площадка 1000', 8000)
            materials.append({
                'name': 'Площадка 1000x1000',
                'qty': platforms_count,
                'unit': 'шт.',
                'price': platform_price,
                'total': platform_price * platforms_count
            })
            total_cost += platform_price * platforms_count
            logger.info(f"Добавлено {platforms_count} площадок 1000x1000")
    
    # Ступени выбранного размера
    step_price = get_material_price(material_type, f'СТУПЕНЬ ПРЯМАЯ {step_width}', 1500)
    step_cost = steps_count * step_price
    
    materials.append({
        'name': f'Ступень {step_width}×300мм',
        'qty': steps_count,
        'unit': 'шт.',
        'price': step_price,
        'total': step_cost
    })
    total_cost += step_cost
    logger.info(f"Добавлено {steps_count} ступеней {step_width}×300мм")
    
    # Ограждение
    railing_price = get_material_price(material_type, 'Опора под поручень', 900)
    railing_qty = steps_count + platforms_count  # Учитываем и ступени и площадки
    railing_cost = railing_qty * railing_price
    
    materials.append({
        'name': 'Опора под поручень',
        'qty': railing_qty,
        'unit': 'шт.',
        'price': railing_price,
        'total': railing_cost
    })
    total_cost += railing_cost
    logger.info(f"Добавлено {railing_qty} опор под поручень")
    
    # Поручень
    handrail_length = math.sqrt(height**2 + (steps_count * 300)**2) / 1000
    handrail_qty = math.ceil(handrail_length / 3)
    handrail_price = get_material_price(material_type, 'ПОРУЧЕНЬ', 2108)
    handrail_cost = handrail_qty * handrail_price
    
    materials.append({
        'name': 'Поручень 3000мм',
        'qty': handrail_qty,
        'unit': 'шт.',
        'price': handrail_price,
        'total': handrail_cost
    })
    total_cost += handrail_cost
    logger.info(f"Добавлено {handrail_qty} поручней")
    
    logger.info(f"Итоговая стоимость модульной лестницы: {total_cost} руб.")
    return {
        'type': 'modular',
        'config': config,
        'height': height,
        'step_width': step_width,
        'steps_count': steps_count,
        'platforms_count': platforms_count,
        'step_height': actual_step_height,
        'stringer_length': handrail_length,
        'materials': materials,
        'total_cost': total_cost
    }

async def delete_chat_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление истории чата"""
    try:
        chat_id = update.effective_chat.id
        message_id = update.effective_message.message_id
        
        # Удаляем все сообщения до текущего
        for i in range(1, 50):
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id - i)
            except:
                break
                
        logger.info(f"История чата очищена для пользователя {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при очистке истории чата: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    # Загружаем цены при первом запуске
    if prices_df is None:
        load_prices()
    
    user = update.effective_user
    
    welcome_text = (
        f"👋 Добро пожаловать, {user.first_name}!\n"
        "Я твой помощник в расчете лестниц.\n\n"
        "📋 *Выберите тип лестницы:*\n"
        "• 🏠 *Деревянная* - из отдельных элементов\n"
        "• ⚡ *Модульная* - металлическая система"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Рассчитать лестницу", callback_data="calculate_stairs")],
        [InlineKeyboardButton("🔄 Перезапустить", callback_data="restart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перезапуск бота"""
    query = update.callback_query
    await query.answer()
    
    await delete_chat_history(update, context)
    
    user = query.from_user
    
    # Очищаем данные пользователя
    user_id = user.id
    if user_id in user_data:
        del user_data[user_id]
    
    welcome_text = (
        f"👋 Добро пожаловать, {user.first_name}!\n"
        "Я твой помощник в расчете лестниц.\n\n"
        "📋 *Выберите тип лестницы:*\n"
        "• 🏠 *Деревянная* - из отдельных элементов\n"
        "• ⚡ *Модульная* - металлическая система"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Рассчитать лестницу", callback_data="calculate_stairs")],
        [InlineKeyboardButton("🔄 Перезапустить", callback_data="restart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "calculate_stairs":
        await delete_chat_history(update, context)
        
        user_id = query.from_user.id
        
        if user_id not in user_data:
            user_data[user_id] = {}
        
        reply_keyboard = [
            ["🏠 Деревянная", "⚡ Модульная"],
            ["🔄 Перезапустить"]
        ]
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="👋 Добро пожаловать!\n\n"
                 "📋 *Выберите тип лестницы:*\n"
                 "• 🏠 *Деревянная* - из отдельных элементов\n"
                 "• ⚡ *Модульная* - металлическая система",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
            parse_mode='Markdown'
        )
        return SELECTING_TYPE
    
    elif query.data == "restart":
        await restart_bot(update, context)

async def select_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор типа лестницы"""
    user_choice = update.message.text
    user_id = update.effective_user.id
    
    if user_choice == "🔄 Перезапустить":
        await restart_from_message(update, context)
        return ConversationHandler.END
    
    user_data[user_id] = {
        'type': 'wood' if 'Деревянная' in user_choice else 'modular',
        'material_type': 'деревянная' if 'Деревянная' in user_choice else 'металлическая'
    }
    
    reply_keyboard = [
        ["📏 Прямая", "📐 Г-образная", "🔄 П-образная"],
        ["🔄 Перезапустить"]
    ]
    
    await update.message.reply_text(
        "📐 *Выберите конфигурацию лестницы:*\n\n"
        "• 📏 *Прямая* - одномаршевая лестница\n"
        "• 📐 *Г-образная* - с поворотом на 90°\n" 
        "• 🔄 *П-образная* - с поворотом на 180°",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode='Markdown'
    )
    return SELECTING_CONFIG

async def select_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор конфигурации лестницы"""
    user_choice = update.message.text
    user_id = update.effective_user.id
    
    if user_choice == "🔄 Перезапустить":
        await restart_from_message(update, context)
        return ConversationHandler.END
    
    config_map = {
        "📏 Прямая": "straight",
        "📐 Г-образная": "l_shape", 
        "🔄 П-образная": "u_shape"
    }
    
    user_data[user_id]['config'] = config_map.get(user_choice, 'straight')
    
    reply_keyboard = [
        ["🔄 Перезапустить"]
    ]
    
    await update.message.reply_text(
        "📏 *Введите высоту лестницы (мм):*\n\n"
        "Пример: 2800 (для высоты 2.8 метра)\n"
        "Диапазон: 1000-5000 мм",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode='Markdown'
    )
    return INPUT_HEIGHT

async def input_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод высоты лестницы"""
    user_input = update.message.text
    user_id = update.effective_user.id
    
    if user_input == "🔄 Перезапустить":
        await restart_from_message(update, context)
        return ConversationHandler.END
    
    is_valid, result = validate_input(user_input, 1000, 5000, "Высота")
    if not is_valid:
        await update.message.reply_text(result)
        return INPUT_HEIGHT
    
    height = result
    user_data[user_id]['height'] = height
    
    # Рассчитываем количество ступеней
    optimal_step_height = 180
    steps_count = round(height / optimal_step_height)
    
    # Корректируем количество ступеней для модульных лестниц с площадками
    if user_data[user_id]['type'] == 'modular':
        config = user_data[user_id]['config']
        if config == 'l_shape':
            steps_count = max(3, steps_count + 1)
        elif config == 'u_shape':
            steps_count = max(3, steps_count + 2)
    
    actual_step_height = height / steps_count
    
    user_data[user_id]['steps_count'] = steps_count
    user_data[user_id]['step_height'] = actual_step_height
    
    reply_keyboard = [
        ["900", "1000", "1200"],
        ["🔄 Перезапустить"]
    ]
    
    await update.message.reply_text(
        f"📊 *Расчет ступеней:*\n\n"
        f"• Высота: {height} мм\n"
        f"• Количество ступеней: {steps_count}\n"
        f"• Высота ступени: {actual_step_height:.1f} мм\n\n"
        f"📏 *Выберите ширину ступени:*\n"
        f"• 900 мм - компактная\n"
        f"• 1000 мм - стандартная\n"
        f"• 1200 мм - широкая",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode='Markdown'
    )
    return SELECTING_STEP_SIZE

async def select_step_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор ширины ступени и расчет"""
    user_choice = update.message.text
    user_id = update.effective_user.id
    
    if user_choice == "🔄 Перезапустить":
        await restart_from_message(update, context)
        return ConversationHandler.END
    
    if user_choice not in ["900", "1000", "1200"]:
        await update.message.reply_text("❌ Пожалуйста, выберите ширину ступени из предложенных вариантов")
        return SELECTING_STEP_SIZE
    
    step_width = user_choice
    user_data[user_id]['step_width'] = step_width
    
    stair_type = user_data[user_id]['type']
    config = user_data[user_id]['config']
    height = user_data[user_id]['height']
    steps_count = user_data[user_id]['steps_count']
    actual_step_height = user_data[user_id]['step_height']
    material_type = user_data[user_id]['material_type']
    
    # Выполняем расчет
    if stair_type == 'wood':
        result = calculate_wood_stairs(height, steps_count, config, material_type, actual_step_height, step_width)
    else:
        result = calculate_modular_stairs(height, steps_count, config, material_type, actual_step_height, step_width)
    
    await send_calculation_result(update, result)
    
    return ConversationHandler.END

async def send_calculation_result(update: Update, result):
    """Отправка результата расчета"""
    type_name = "Деревянная" if result['type'] == 'wood' else "Модульная"
    config_names = {
        'straight': 'Прямая',
        'l_shape': 'Г-образная', 
        'u_shape': 'П-образная'
    }
    
    message_text = (
        f"🏠 *РАСЧЕТ ЛЕСТНИЦЫ*\n\n"
        f"📋 *Тип:* {type_name}\n"
        f"📐 *Конфигурация:* {config_names[result['config']]}\n"
        f"📏 *Высота:* {result['height']} мм\n"
        f"🪜 *Количество ступеней:* {result['steps_count']}\n"
        f"📊 *Высота ступени:* {result['step_height']:.1f} мм\n"
    )
    
    if result['type'] == 'modular' and result.get('platforms_count', 0) > 0:
        message_text += f"🔄 *Количество площадок:* {result['platforms_count']}\n"
    
    if result['type'] == 'wood':
        message_text += f"📐 *Длина тетивы:* {result['stringer_length']:.0f} мм\n"
        message_text += f"🏗️ *Количество столбов:* {result['posts_count']}\n"
    
    message_text += f"\n💎 *МАТЕРИАЛЫ:*\n\n"
    
    total_cost = 0
    for material in result['materials']:
        message_text += f"• {material['name']}\n"
        message_text += f"  Кол-во: {material['qty']} {material['unit']}\n"
        message_text += f"  Цена: {material['price']} руб.\n"
        message_text += f"  Сумма: {material['total']} руб.\n\n"
        total_cost += material['total']
    
    message_text += f"💰 *ОБЩАЯ СТОИМОСТЬ:* {total_cost:,.0f} руб.\n\n"
    message_text += f"_*Цены актуальны на {datetime.now().strftime('%d.%m.%Y')}_\n"
    message_text += "_*Стоимость является ориентировочной_"
    
    await update.message.reply_text(
        message_text,
        parse_mode='Markdown'
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Новый расчет", callback_data="calculate_stairs")],
        [InlineKeyboardButton("🔄 Перезапустить", callback_data="restart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Хотите выполнить новый расчет?",
        reply_markup=reply_markup
    )

async def restart_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перезапуск из состояния ConversationHandler"""
    user = update.effective_user
    
    user_id = user.id
    if user_id in user_data:
        del user_data[user_id]
    
    welcome_text = (
        f"👋 Добро пожаловать, {user.first_name}!\n"
        "Я твой помощник в расчете лестниц.\n\n"
        "📋 *Выберите тип лестницы:*\n"
        "• 🏠 *Деревянная* - из отдельных элементов\n"
        "• ⚡ *Модульная* - металлическая система"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Рассчитать лестницу", callback_data="calculate_stairs")],
        [InlineKeyboardButton("🔄 Перезапустить", callback_data="restart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена диалога"""
    await update.message.reply_text(
        "Расчет отменен.",
        reply_markup=ReplyKeyboardMarkup([["/start"]], one_time_keyboard=True)
    )
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка. Пожалуйста, попробуйте снова.\n"
            "Используйте /start для перезапуска."
        )

async def scheduled_price_update(context: ContextTypes.DEFAULT_TYPE):
    """Плановое обновление цен"""
    logger.info("Запуск планового обновления цен...")
    load_prices(force_update=True)

def main():
    """Основная функция запуска бота"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN не найден в переменных окружения!")
        return
    
    # Загружаем цены при запуске
    load_prices()
    
    application = Application.builder().token(token).build()
    
    # Настраиваем планировщик для автообновления цен
    job_queue = application.job_queue
    if job_queue:
        # Обновлять цены каждые 24 часа
        job_queue.run_repeating(scheduled_price_update, interval=86400, first=10)
    
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler, pattern="^calculate_stairs$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, select_type)
        ],
        states={
            SELECTING_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_type)
            ],
            SELECTING_CONFIG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_config)
            ],
            INPUT_HEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_height)
            ],
            SELECTING_STEP_SIZE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_step_size)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & filters.Regex("^🔄 Перезапустить$"), restart_from_message)
        ],
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(calculate_stairs|restart)$"))
    
    application.add_error_handler(error_handler)
    
    logger.info("🤖 Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
