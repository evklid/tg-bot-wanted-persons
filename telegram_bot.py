import requests
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

try:
    from config import BOT_TOKEN
except ImportError:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    if not BOT_TOKEN:
        raise ValueError("⚠️ Токен бота не знайдено!")

JSON_URL = "https://data.gov.ua/dataset/59ecf2ab-47a1-4fae-a63c-fe5007d68130/resource/9694e34c-92a5-4839-91df-c32850db7ba9/download/mvswantedperson_1.json"

FIRST_NAME, LAST_NAME, PATRONYMIC, BIRTH_DATE, SAVE_CHOICE = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message if update.message else update.callback_query.message
    saved_data = context.user_data.get('saved_params')
    
    if saved_data:
        keyboard = [
            [InlineKeyboardButton("🔍 Пошук за збереженими", callback_data='search_saved')],
            [InlineKeyboardButton("✏️ Змінити дані", callback_data='start_check')]
        ]
        text = f"💾 Збережено: {saved_data['last_name']} {saved_data['first_name']}"
        await target.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        keyboard = [[InlineKeyboardButton("🔍 Почати", callback_data='start_check')]]
        await target.reply_text('👋 Вітаю! Натисніть кнопку для пошуку:', reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def start_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("📝 Введіть ім'я:")
    return FIRST_NAME

async def get_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['first_name'] = update.message.text.strip()
    await update.message.reply_text("✅ Введіть прізвище:")
    return LAST_NAME

async def get_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['last_name'] = update.message.text.strip()
    await update.message.reply_text("✅ Введіть по-батькові:")
    return PATRONYMIC

async def get_patronymic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['patronymic'] = update.message.text.strip()
    await update.message.reply_text("✅ Введіть дату народження (ДД.ММ.РРРР):")
    return BIRTH_DATE

async def get_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['birth_date'] = update.message.text.strip()
    keyboard = [[InlineKeyboardButton("💾 Так", callback_data='save_yes'), InlineKeyboardButton("❌ Ні", callback_data='save_no')]]
    await update.message.reply_text("💾 Зберегти дані?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SAVE_CHOICE

async def perform_search_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    msg = await query.message.reply_text("⏳ Пошук у базі МВС (зачекайте)...")
    
    try:
        # Виконуємо запит синхронно для стабільності на Render
        response = requests.get(JSON_URL, timeout=60)
        data = response.json()
        records = data if isinstance(data, list) else data.get('persons', [])
        
        target_f = context.user_data.get('first_name', '').lower()
        target_l = context.user_data.get('last_name', '').lower()
        target_b = context.user_data.get('birth_date', '')

        found = None
        for r in records:
            rf = (r.get('FIRST_NAME_U') or r.get('FIRST_NAME') or '').lower()
            rl = (r.get('LAST_NAME_U') or r.get('LAST_NAME') or '').lower()
            
            rb_raw = r.get('BIRTH_DATE') or r.get('BIRTHDAY') or ''
            rb = ""
            if 'T' in rb_raw:
                p = rb_raw.split('T')[0].split('-')
                if len(p) == 3: rb = f"{p[2]}.{p[1]}.{p[0]}"

            if rf == target_f and rl == target_l and rb == target_b:
                found = r
                break

        res = f"🚨 Знайдено! Стаття: {found.get('ARTICLE_CRIM')}" if found else "✅ Не знайдено."
        await msg.edit_text(res, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data='main_menu')]]))
    except Exception as e:
        await msg.edit_text(f"❌ Помилка: {str(e)}")

async def save_choice_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data['saved_params'] = {
        'first_name': context.user_data['first_name'], 'last_name': context.user_data['last_name'],
        'patronymic': context.user_data['patronymic'], 'birth_date': context.user_data['birth_date']
    }
    await update.callback_query.edit_message_text("✅ Збережено!")
    await perform_search_logic(update, context)
    return ConversationHandler.END

async def save_choice_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("⏳ Пошук...")
    await perform_search_logic(update, context)
    return ConversationHandler.END

async def search_saved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = context.user_data.get('saved_params')
    context.user_data.update(data)
    await update.callback_query.edit_message_text(f"🔍 Перевірка {data['last_name']}...")
    await perform_search_logic(update, context)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('❌ Скасовано.')
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_check, pattern='start_check')],
        states={
            FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_first_name)],
            LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_last_name)],
            PATRONYMIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_patronymic)],
            BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_date)],
            SAVE_CHOICE: [CallbackQueryHandler(save_choice_yes, pattern='save_yes'),
                          CallbackQueryHandler(save_choice_no, pattern='save_no')],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(search_saved, pattern='search_saved'))
    app.add_handler(CallbackQueryHandler(start, pattern='main_menu'))
    app.add_handler(conv)
    
    print("✅ Бот запущено!")
    app.run_polling()

if __name__ == '__main__':
    main()
