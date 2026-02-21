#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram бот для перевірки наявності особи в базі розшукуваних осіб
"""

import requests
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

try:
    from config import BOT_TOKEN
except ImportError:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    if not BOT_TOKEN:
        raise ValueError("⚠️ Токен бота не знайдено! Створіть файл config.py або встановіть змінну оточення BOT_TOKEN")

JSON_URL = "https://data.gov.ua/dataset/59ecf2ab-47a1-4fae-a63c-fe5007d68130/resource/9694e34c-92a5-4839-91df-c32850db7ba9/download/mvswantedperson_1.json"

FIRST_NAME, LAST_NAME, PATRONYMIC, BIRTH_DATE, SAVE_CHOICE = range(5)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник команди /start"""
    
    saved_data = context.user_data.get('saved_params')
    
    if saved_data:
        keyboard = [
            [InlineKeyboardButton("🔍 Пошук за збереженими даними", callback_data='search_saved')],
            [InlineKeyboardButton("✏️ Змінити параметри пошуку", callback_data='start_check')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            '👋 Вітаю!\n\n'
            '💾 <b>У вас є збережені параметри:</b>\n\n'
            f'• Ім\'я: {saved_data["first_name"]}\n'
            f'• Прізвище: {saved_data["last_name"]}\n'
            f'• По-батькові: {saved_data["patronymic"]}\n'
            f'• Дата народження: {saved_data["birth_date"]}\n\n'
            'Виберіть дію:',
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        
        keyboard = [
            [InlineKeyboardButton("🔍 Почати перевірку", callback_data='start_check')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            '👋 Вітаю!\n\n'
            'Цей бот перевіряє наявність особи в базі розшукуваних осіб МВС України.\n\n'
            '📝 Для перевірки вам потрібно буде ввести:\n'
            '• Ім\'я\n'
            '• Прізвище\n'
            '• По-батькові\n'
            '• Дату народження (формат: ДД.ММ.РРРР)\n\n'
            'Натисніть кнопку для початку:',
            reply_markup=reply_markup
        )
    
    return ConversationHandler.END


async def start_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок процесу перевірки"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📝 Введіть <b>прізвище</b> особи для перевірки:\n\n"
        "Приклад: Осауленко\n\n"
        "Або /cancel для скасування",
        parse_mode='HTML'
    )
    
    return LAST_NAME  # Починаємо з прізвища


async def search_saved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пошук за збереженими даними"""
    query = update.callback_query
    await query.answer()
    
    saved_data = context.user_data.get('saved_params')
    
    if not saved_data:
        await query.edit_message_text(
            "❌ Немає збережених даних.\n\n"
            "Натисніть /start для введення нових параметрів."
        )
        return ConversationHandler.END
    
   
    context.user_data['first_name'] = saved_data['first_name']
    context.user_data['last_name'] = saved_data['last_name']
    context.user_data['patronymic'] = saved_data['patronymic']
    context.user_data['birth_date'] = saved_data['birth_date']
    
    await query.edit_message_text(
        f"📋 Пошук за збереженими параметрами:\n\n"
        f"✅ Прізвище: {saved_data['last_name']}\n"
        f"✅ Ім'я: {saved_data['first_name']}\n"
        f"✅ По-батькові: {saved_data['patronymic']}\n"
        f"✅ Дата народження: {saved_data['birth_date']}\n\n"
        f"⏳ Починаю перевірку...",
        parse_mode='HTML'
    )
    
 
    class FakeMessage:
        async def reply_text(self, text, **kwargs):
            return await query.message.reply_text(text, **kwargs)
    
    fake_update = type('obj', (object,), {
        'message': FakeMessage(),
        'callback_query': query
    })()
    
    await perform_search(fake_update, context, use_saved=True)
    
    return ConversationHandler.END


async def get_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання імені"""
    context.user_data['first_name'] = update.message.text.strip()
    
    await update.message.reply_text(
        f"✅ Прізвище: {context.user_data['last_name']}\n"
        f"✅ Ім'я: {context.user_data['first_name']}\n\n"
        "📝 Тепер введіть <b>по-батькові</b>:\n\n"
        "Приклад: Петрович\n\n"
        "Або /cancel для скасування",
        parse_mode='HTML'
    )
    
    return PATRONYMIC


async def get_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання прізвища"""
    context.user_data['last_name'] = update.message.text.strip()
    
    await update.message.reply_text(
        f"✅ Прізвище: {context.user_data['last_name']}\n\n"
        "📝 Тепер введіть <b>ім'я</b>:\n\n"
        "Приклад: Микита\n\n"
        "Або /cancel для скасування",
        parse_mode='HTML'
    )
    
    return FIRST_NAME


async def get_patronymic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання по-батькові"""
    context.user_data['patronymic'] = update.message.text.strip()
    
    await update.message.reply_text(
        f"✅ Прізвище: {context.user_data['last_name']}\n"
        f"✅ Ім'я: {context.user_data['first_name']}\n"
        f"✅ По-батькові: {context.user_data['patronymic']}\n\n"
        "📝 Тепер введіть <b>дату народження</b>:\n\n"
        "Формат: ДД.ММ.РРРР\n"
        "Приклад: 01.02.1990\n\n"
        "Або /cancel для скасування",
        parse_mode='HTML'
    )
    
    return BIRTH_DATE


async def get_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання дати народження та запит про збереження"""
    context.user_data['birth_date'] = update.message.text.strip()
    
    
    keyboard = [
        [InlineKeyboardButton("💾 Так, зберегти", callback_data='save_yes')],
        [InlineKeyboardButton("❌ Ні, не зберігати", callback_data='save_no')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📋 Дані для перевірки:\n\n"
        f"✅ Прізвище: {context.user_data['last_name']}\n"
        f"✅ Ім'я: {context.user_data['first_name']}\n"
        f"✅ По-батькові: {context.user_data['patronymic']}\n"
        f"✅ Дата народження: {context.user_data['birth_date']}\n\n"
        f"💾 <b>Зберегти ці дані для майбутніх пошуків?</b>\n\n"
        f"Якщо збережете, зможете швидко перевіряти цю особу знову, не вводячи дані кожен раз.",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    return SAVE_CHOICE


async def save_choice_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Зберігаємо дані та виконуємо пошук"""
    query = update.callback_query
    await query.answer("✅ Дані збережено!")
    
    # Зберігаємо параметри
    context.user_data['saved_params'] = {
        'first_name': context.user_data['first_name'],
        'last_name': context.user_data['last_name'],
        'patronymic': context.user_data['patronymic'],
        'birth_date': context.user_data['birth_date']
    }
    
    await query.edit_message_text(
        f"💾 <b>Дані збережено!</b>\n\n"
        f"⏳ Починаю перевірку...",
        parse_mode='HTML'
    )
    
    # Виконуємо пошук
    class FakeMessage:
        async def reply_text(self, text, **kwargs):
            return await query.message.reply_text(text, **kwargs)
    
    fake_update = type('obj', (object,), {
        'message': FakeMessage(),
        'callback_query': query
    })()
    
    await perform_search(fake_update, context, use_saved=False)
    
    return ConversationHandler.END


async def save_choice_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Не зберігаємо дані, тільки виконуємо пошук"""
    query = update.callback_query
    await query.answer("Дані не будуть збережені")
    
    await query.edit_message_text(
        f"⏳ Починаю перевірку...\n\n"
        f"(Дані не збережено)",
        parse_mode='HTML'
    )
    
    # Виконуємо пошук
    class FakeMessage:
        async def reply_text(self, text, **kwargs):
            return await query.message.reply_text(text, **kwargs)
    
    fake_update = type('obj', (object,), {
        'message': FakeMessage(),
        'callback_query': query
    })()
    
    await perform_search(fake_update, context, use_saved=False)
    
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скасування перевірки"""
    await update.message.reply_text(
        '❌ Перевірку скасовано.\n\n'
        'Натисніть /start для нової перевірки.',
        reply_markup=ReplyKeyboardRemove()
    )
    
    return ConversationHandler.END


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повернення до головного меню"""
    query = update.callback_query
    await query.answer()
    
    # Перевіряємо чи є збережені дані
    saved_data = context.user_data.get('saved_params')
    
    if saved_data:
        keyboard = [
            [InlineKeyboardButton("🔍 Пошук за збереженими даними", callback_data='search_saved')],
            [InlineKeyboardButton("✏️ Змінити параметри пошуку", callback_data='start_check')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            '🏠 <b>Головне меню</b>\n\n'
            '💾 <b>Збережені параметри:</b>\n\n'
            f'• Ім\'я: {saved_data["first_name"]}\n'
            f'• Прізвище: {saved_data["last_name"]}\n'
            f'• По-батькові: {saved_data["patronymic"]}\n'
            f'• Дата народження: {saved_data["birth_date"]}\n\n'
            'Виберіть дію:',
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        keyboard = [
            [InlineKeyboardButton("🔍 Почати перевірку", callback_data='start_check')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            '🏠 <b>Головне меню</b>\n\n'
            'Цей бот перевіряє наявність особи в базі розшукуваних осіб МВС України.\n\n'
            'Натисніть кнопку для початку:',
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    return ConversationHandler.END


async def perform_search(update: Update, context: ContextTypes.DEFAULT_TYPE, use_saved: bool = False):
    """Виконання пошуку особи в JSON"""
    
    # Отримуємо параметри пошуку з контексту користувача
    search_params = {
        "first_name": context.user_data.get('first_name', ''),
        "last_name": context.user_data.get('last_name', ''),
        "patronymic": context.user_data.get('patronymic', ''),
        "birth_date": context.user_data.get('birth_date', '')
    }
    
    try:
        # Завантаження JSON
        loading_msg = await update.message.reply_text("⏳ Завантажую дані з бази МВС...\nЗачекайте, це може зайняти деякий час")
        
        response = requests.get(JSON_URL, timeout=120)
        response.raise_for_status()
        
        # Парсинг JSON
        await loading_msg.edit_text("⏳ Обробляю дані... Це може зайняти до 1 хвилини.")
        data = response.json()
        
        # Пошук збігу
        found = False
        matching_record = None
        
        # Перевіряємо чи це масив чи об'єкт
        records = data if isinstance(data, list) else data.get('persons', [])
        
        for record in records:
            # Отримуємо поля (перевіряємо різні варіанти назв)
            # Українська версія полів (з підкресленням _U)
            first_name = record.get('FIRST_NAME_U') or record.get('FIRST_NAME') or record.get('OVD') or ''
            last_name = record.get('LAST_NAME_U') or record.get('LAST_NAME') or record.get('OVDSURNAME') or ''
            patronymic = record.get('MIDDLE_NAME_U') or record.get('PATRONYMIC') or record.get('OVDPATRONYMIC') or ''
            birth_date_raw = record.get('BIRTH_DATE') or record.get('BIRTHDAY') or ''
            
            # Обробка дати народження
            # Формат у JSON: "1991-04-30T00:00:00" або "1978-12-26T00:00:00"
            # Формат вводу користувача: "30.04.1991"
            birth_date_normalized = ""
            if birth_date_raw:
                # Витягуємо тільки дату (без часу)
                if 'T' in birth_date_raw:
                    birth_date_parts = birth_date_raw.split('T')[0]  # "1991-04-30"
                    # Конвертуємо в формат ДД.ММ.РРРР
                    try:
                        year, month, day = birth_date_parts.split('-')
                        birth_date_normalized = f"{day}.{month}.{year}"  # "30.04.1991"
                    except:
                        birth_date_normalized = birth_date_raw
                else:
                    birth_date_normalized = birth_date_raw
            
            # Нормалізація пошукових даних
            search_date_normalized = search_params["birth_date"].strip()
            
            # Нормалізація тексту (прибираємо зайві пробіли, нормалізуємо апострофи)
            def normalize_text(text):
                """Нормалізує текст: прибирає пробіли, приводить до lower case, нормалізує апострофи"""
                if not text:
                    return ""
                # Замінюємо різні види апострофів на стандартний
                text = text.replace("'", "'").replace("`", "'").replace("ʼ", "'")
                return text.strip().lower()
            
            # Перевірка повного збігу всіх 4 параметрів
            if (normalize_text(first_name) == normalize_text(search_params["first_name"]) and
                normalize_text(last_name) == normalize_text(search_params["last_name"]) and
                normalize_text(patronymic) == normalize_text(search_params["patronymic"]) and
                birth_date_normalized == search_date_normalized):
                
                found = True
                matching_record = record
                break
        
        # Формування відповіді
        if found:
            result_message = (
                f"🚨 <b>ОПА! ОСОБУ ЗНАЙДЕНО В БАЗІ РОЗШУКУВАНИХ!</b>\n\n"
                f"📋 Дані:\n"
                f"• Прізвище: {matching_record.get('LAST_NAME_U') or matching_record.get('OVDSURNAME', 'N/A')}\n"
                f"• Ім'я: {matching_record.get('FIRST_NAME_U') or matching_record.get('OVD', 'N/A')}\n"
                f"• По-батькові: {matching_record.get('MIDDLE_NAME_U') or matching_record.get('OVDPATRONYMIC', 'N/A')}\n"
                f"• Дата народження: {birth_date_normalized}\n"
            )
            
            # Додаткова інформація, якщо є
            if matching_record.get('CATEGORY'):
                result_message += f"• Категорія: {matching_record.get('CATEGORY')}\n"
            if matching_record.get('RESTRAINT'):
                result_message += f"• Запобіжний захід: {matching_record.get('RESTRAINT')}\n"
            if matching_record.get('ARTICLE_CRIM'):
                result_message += f"• Стаття: {matching_record.get('ARTICLE_CRIM')}\n"
            if matching_record.get('OVD'):
                result_message += f"• Орган: {matching_record.get('OVD')}\n"
                
        else:
            result_message = (
                f"✅ <b>ВСЕ ДОБРЕ, ЖИВЕМО ДАЛІ</b>\n\n"
                f"Перевірено за параметрами:\n"
                f"• Прізвище: {search_params['last_name']}\n"
                f"• Ім'я: {search_params['first_name']}\n"
                f"• По-батькові: {search_params['patronymic']}\n"
                f"• Дата народження: {search_params['birth_date']}\n"
            )
        
       
        saved_data = context.user_data.get('saved_params')
        
        if saved_data:
           
            keyboard = [
                [InlineKeyboardButton("🔄 Пошук знову", callback_data='search_saved')],
                [InlineKeyboardButton("✏️ Змінити параметри", callback_data='start_check')],
                [InlineKeyboardButton("🏠 Головне меню", callback_data='main_menu')]
            ]
        else:
            # Якщо немає збережених даних - тільки нова перевірка
            keyboard = [
                [InlineKeyboardButton("🔄 Нова перевірка", callback_data='start_check')],
                [InlineKeyboardButton("🏠 Головне меню", callback_data='main_menu')]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await loading_msg.edit_text(
            result_message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
    except requests.RequestException as e:
        await update.message.reply_text(
            f"❌ Помилка при завантаженні даних:\n{str(e)}\n\n"
            f"Спробуйте пізніше або перевірте з'єднання з інтернетом.\n\n"
            f"Натисніть /start для нової перевірки."
        )
    except json.JSONDecodeError as e:
        await update.message.reply_text(
            f"❌ Помилка при обробці JSON:\n{str(e)}\n\n"
            f"Можливо, формат даних на сервері змінився.\n\n"
            f"Натисніть /start для нової перевірки."
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Несподівана помилка:\n{str(e)}\n\n"
            f"Натисніть /start для нової перевірки."
        )



def main():
    """Запуск бота"""
    print("🤖 Запуск Telegram бота...")
    print("📝 Бот готовий приймати дані від користувачів")
    print("💾 Підтримка збереження параметрів активована")
    
    # Створення додатку
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ConversationHandler для послідовного введення даних
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_check, pattern='start_check')
        ],
        states={
            FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_first_name)],
            LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_last_name)],
            PATRONYMIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_patronymic)],
            BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_date)],
            SAVE_CHOICE: [
                CallbackQueryHandler(save_choice_yes, pattern='save_yes'),
                CallbackQueryHandler(save_choice_no, pattern='save_no')
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        # Видалено per_message=True для усунення warning
    )
    
    # Додавання обробників
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(search_saved, pattern='search_saved'))
    application.add_handler(CallbackQueryHandler(main_menu, pattern='main_menu'))
    application.add_handler(conv_handler)
    
    # HTTP сервер для Render (щоб не було timeout)
    import os
    from threading import Thread
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    class HealthCheckHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Bot is running')
        
        def do_HEAD(self):
            # Підтримка HEAD запитів для UptimeRobot
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.send_header('Content-Length', '14')
            self.end_headers()
        
        def log_message(self, format, *args):
            pass  # Не логувати HTTP запити
    
    def run_health_server():
        port = int(os.environ.get('PORT', 10000))
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f"🌐 HTTP сервер запущено на порту {port}")
        server.serve_forever()
    
    # Запуск HTTP сервера у фоновому потоці
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # Запуск бота з drop_pending_updates для уникнення конфліктів
    print("✅ Бот запущено! Натисніть Ctrl+C для зупинки.")
    print("💬 Відкрийте бота в Telegram та відправте /start")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True  # Скидає старі оновлення при запуску
    )


if __name__ == '__main__':
    main()