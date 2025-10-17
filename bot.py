import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import json
from datetime import datetime
import math
from openpyxl import load_workbook

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
prices_data = None

def load_prices():
    """Загрузка цен из Excel файла без pandas"""
    global prices_data
    
    try:
        # Загружаем Excel файл
        wb = load_workbook('data.xlsx', data_only=True)
        sheet = wb.active
        
        prices = []
        
        # Читаем данные начиная с 4 строки (пропускаем заголовки)
        for row_num in range(4, sheet.max_row + 1):
            article = sheet.cell(row=row_num, column=1).value
            name = sheet.cell(row=row_num, column=2).value
            stair_type = sheet.cell(row=row_num, column=3).value
            sizes = sheet.cell(row=row_num, column=4).value
            unit = sheet.cell(row=row_num, column=5).value
            price = sheet.cell(row=row_num, column=6).value
            
            # Пропускаем пустые строки
            if article and name and price:
                item = {
                    'article': str(article).split('.')[0] if '.' in str(article) else str(article),
                    'name': str(name),
                    'stair_type': str(stair_type) if stair_type else '',
                    'sizes': str(sizes) if sizes else '',
                    'unit': str(unit) if unit else 'шт.',
                    'price': float(price) if price else 0
                }
                prices.append(item)
        
        prices_data = prices
        logger.info(f"Успешно загружено {len(prices)} позиций из Excel")
        
    except Exception as e:
        logger.error(f"Ошибка загрузки прайса: {e}")
        prices_data = get_test_data()

def get_test_data():
    """Тестовые данные если файл не загружается"""
    test_data = [
        {'article': '15762294', 'name': 'Верхний и нижний элемент сталь ЛЭ-01-01', 'stair_type': 'металлическая', 'price': 7590, 'unit': 'штука'},
        {'article': '15762307', 'name': 'Промежуточный элемент сталь ЛЭ-01-02', 'stair_type': 'металлическая', 'price': 4076, 'unit': 'штука'},
        {'article': '15762374', 'name': 'Опора лестницы 1000мм сталь ЛЭ-01-09', 'stair_type': 'металлическая', 'price': 3647, 'unit': 'штука'},
        {'article': '15762382', 'name': 'Опора лестницы 2000 сталь ЛЭ-01-10', 'stair_type': 'металлическая', 'price': 5490, 'unit': 'штука'},
        {'article': '15762391', 'name': 'Угловой элемент сталь ЛЭ-01-14', 'stair_type': 'металлическая', 'price': 12411, 'unit': 'штука'},
        {'article': '83850952', 'name': 'СТУПЕНЬ ПРЯМАЯ 900x300', 'stair_type': 'деревянная', 'price': 1504, 'unit': 'штука'},
        {'article': '83850953', 'name': 'СТУПЕНЬ ПРЯМАЯ 1000x300', 'stair_type': 'деревянная', 'price': 1282, 'unit': 'штука'},
        {'article': '83850954', 'name': 'СТУПЕНЬ ПРЯМАЯ 1200x300', 'stair_type': 'деревянная', 'price': 1358, 'unit': 'штука'},
        {'article': '83850961', 'name': 'Тетива 3000x300x60', 'stair_type': 'деревянная', 'price': 9518, 'unit': 'штука'},
        {'article': '83850962', 'name': 'Тетива 4000x300x60', 'stair_type': 'деревянная', 'price': 10215, 'unit': 'штука'},
        {'article': '83850939', 'name': 'Поручень 3000мм', 'stair_type': 'деревянная', 'price': 2108, 'unit': 'штука'},
        {'article': '89426866', 'name': 'Столб Хюгге', 'stair_type': 'деревянная', 'price': 1931, 'unit': 'штука'},
        {'article': '89426868', 'name': 'Балясина Хюгге', 'stair_type': 'деревянная', 'price': 400, 'unit': 'штука'},
    ]
    logger.info("Используются тестовые данные")
    return test_data

def get_material_price(material_type, name_pattern, default_price):
    """Получение цены с фильтрацией по типу лестницы"""
    if not prices_data:
        return default_price
    
    try:
        for item in prices_data:
            if (item['stair_type'] == material_type and 
                name_pattern.lower() in item['name'].lower()):
                return item['price']
        return default_price
    except Exception as e:
        logger.error(f"Ошибка поиска цены: {e}")
        return default_price

def get_material_by_article(article):
    """Получение материала по артикулу"""
    if not prices_data:
        return None
    
    try:
        clean_article = str(article).split('.')[0] if '.' in str(article) else str(article)
        for item in prices_data:
            if item['article'] == clean_article:
                return item
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

# ОСТАВЬТЕ ВСЕ ФУНКЦИИ РАСЧЕТА БЕЗ ИЗМЕНЕНИЙ:
# calculate_wood_stairs, calculate_modular_stairs и т.д.
# Они используют get_material_price и get_material_by_article которые мы обновили

def calculate_wood_stairs(height, steps_count, config, material_type, actual_step_height, step_width):
    """Расчет деревянной лестницы"""
    materials = []
    total_cost = 0
    
    # Расчет длины тетивы с учетом оптимального угла 30-40 градусов
    step_depth = 300
    stair_length = (steps_count - 1) * step_depth
    stringer_length = math.sqrt(height**2 + stair_length**2)
    
    # Определяем количество и длину тетив
    stringer_qty = 2
    
    if stringer_length <= 3000:
        stringer_size = "3000"
        stringer_price = get_material_price(material_type, 'Тетива 3000', 9518)
    else:
        stringer_size = "4000" 
        stringer_price = get_material_price(material_type, 'Тетива 4000', 10215)
    
    stringer_cost = stringer_price * stringer_qty
    
    materials.append({
        'name': f'Тетива {stringer_size}мм',
        'qty': stringer_qty,
        'unit': 'шт.',
        'price': stringer_price,
        'total': stringer_cost
    })
    total_cost += stringer_cost
    
    # Ступени
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
    
    # Столбы
    post_price = get_material_price(material_type, 'Столб', 1931)
    if config == 'straight':
        posts_qty = 2
    elif config == 'l_shape':
        posts_qty = 3
    else:
        posts_qty = 4
    
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
    
    # Крепеж
    fixing_kit_price = 1500
    fixing_kit_qty = max(1, steps_count // 10)
    materials.append({
        'name': 'Крепежный комплект',
        'qty': fixing_kit_qty,
        'unit': 'компл.',
        'price': fixing_kit_price,
        'total': fixing_kit_price * fixing_kit_qty
    })
    total_cost += fixing_kit_price * fixing_kit_qty
    
    screws_price = 5
    screws_qty = steps_count * 12
    materials.append({
        'name': 'Саморезы',
        'qty': screws_qty,
        'unit': 'шт.',
        'price': screws_price,
        'total': screws_price * screws_qty
    })
    total_cost += screws_price * screws_qty
    
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
    """Расчет модульной лестницы"""
    materials = []
    total_cost = 0
    
    # Корректировка количества ступеней с учетом площадок
    platforms_count = 0
    if config == 'l_shape':
        platforms_count = 1
        steps_count = max(1, steps_count - 1)
    elif config == 'u_shape':
        platforms_count = 2
        steps_count = max(1, steps_count - 2)
    
    # Элементы каркаса
    support_1000 = get_material_by_article('15762374')
    support_2000 = get_material_by_article('15762382')
    
    if support_1000:
        materials.append({
            'name': support_1000['name'],
            'qty': 1,
            'unit': 'шт.',
            'price': support_1000['price'],
            'total': support_1000['price']
        })
        total_cost += support_1000['price']
    
    if support_2000:
        materials.append({
            'name': support_2000['name'],
            'qty': 1,
            'unit': 'шт.',
            'price': support_2000['price'],
            'total': support_2000['price']
        })
        total_cost += support_2000['price']
    
    # Модули
    module_price = get_material_price(material_type, 'Промежуточный элемент', 4076)
    modules_qty = steps_count - 1
    modules_cost = modules_qty * module_price
    
    materials.append({
        'name': 'Промежуточный элемент',
        'qty': modules_qty,
        'unit': 'шт.',
        'price': module_price,
        'total': modules_cost
    })
    total_cost += modules_cost
    
    # Верхний/нижний элемент
    end_module_price = get_material_price(material_type, 'Верхний и нижний элемент', 7590)
    materials.append({
        'name': 'Верхний и нижний элемент',
        'qty': 1,
        'unit': 'шт.',
        'price': end_module_price,
        'total': end_module_price
    })
    total_cost += end_module_price
    
    # Угловые элементы
    corner_element = get_material_by_article('15762391')
    if corner_element:
        if config == 'l_shape':
            materials.append({
                'name': corner_element['name'],
                'qty': 1,
                'unit': 'шт.',
                'price': corner_element['price'],
                'total': corner_element['price']
            })
            total_cost += corner_element['price']
        elif config == 'u_shape':
            materials.append({
                'name': corner_element['name'],
                'qty': 2,
                'unit': 'шт.',
                'price': corner_element['price'],
                'total': corner_element['price'] * 2
            })
            total_cost += corner_element['price'] * 2
    
    # Площадки
    if platforms_count > 0:
        platform_price = get_material_price(material_type, 'Площадка', 8000)
        materials.append({
            'name': f'Площадка {step_width}x{step_width}',
            'qty': platforms_count,
            'unit': 'шт.',
            'price': platform_price,
            'total': platform_price * platforms_count
        })
        total_cost += platform_price * platforms_count
    
    # Ступени
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
    
    # Ограждение
    railing_price = get_material_price(material_type, 'Опора под поручень', 900)
    railing_qty = steps_count + platforms_count
    railing_cost = railing_qty * railing_price
    
    materials.append({
        'name': 'Опора под поручень',
        'qty': railing_qty,
        'unit': 'шт.',
        'price': railing_price,
        'total': railing_cost
    })
    total_cost += railing_cost
    
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

# ОСТАВЬТЕ ВСЕ ФУНКЦИИ БОТА БЕЗ ИЗМЕНЕНИЙ:
# start, restart_bot, button_handler, select_type, select_config, input_height, select_step_size, send_calculation_result

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    if prices_data is None:
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
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перезапуск бота"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
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
    
    await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "calculate_stairs":
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
    
    reply_keyboard = [["🔄 Перезапустить"]]
    
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
    
    optimal_step_height = 180
    steps_count = round(height / optimal_step_height)
    
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
    
    await update.message.reply_text(message_text, parse_mode='Markdown')
    
    keyboard = [
        [InlineKeyboardButton("🔄 Новый расчет", callback_data="calculate_stairs")],
        [InlineKeyboardButton("🔄 Перезапустить", callback_data="restart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("Хотите выполнить новый расчет?", reply_markup=reply_markup)

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
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена диалога"""
    await update.message.reply_text("Расчет отменен.")
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)
    if update and update.effective_message:
        await update.effective_message.reply_text("❌ Произошла ошибка. Используйте /start для перезапуска.")

def main():
    """Основная функция запуска бота"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN не найден!")
        return
    
    load_prices()
    application = Application.builder().token(token).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler, pattern="^calculate_stairs$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, select_type)
        ],
        states={
            SELECTING_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_type)],
            SELECTING_CONFIG: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_config)],
            INPUT_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_height)],
            SELECTING_STEP_SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_step_size)],
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
