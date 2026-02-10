import requests
import json
import os
import asyncio
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
            [InlineKeyboardButton("🔍 Пошук за збереженими даними", callback_data='search_saved')],
            [InlineKeyboardButton("✏️ Змінити параметри пошуку", callback_data='start_check')]
        ]
        text = (f'👋 Вітаю!\n\n💾 <b>У вас є збережені параметри:</b>\n\n'
                f'• Ім\'я: {saved_data["first_name"]}\n'
                f'• Прізвище: {saved_data["last_name"]}\n'
                f'• По-батькові: {saved_data["patronymic"]}\n'
                f'• Дата народження: {saved_data["birth_date"]}\n\n'
                'Виберіть дію:')
        await target.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        keyboard = [[InlineKeyboardButton("🔍 Почати перевірку", callback_data='start_check')]]
        await target.reply_text('👋 Вітаю!\n\nЦей бот перевіряє розшук МВС.\nНатисніть кнопку:', 
                                reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def start_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📝 Введіть <b>ім'я</b> особи:", parse_mode='HTML')
    return FIRST_NAME

async def get_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['first_name'] = update.message.text.strip()
    await update.message.reply_text("✅ Введіть <b>прізвище</b>:", parse_mode='HTML')
    return LAST_NAME

async def get_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['last_name'] = update.message.text.strip()
    await update.message.reply_text("✅ Введіть <b>по-батькові</b>:", parse_mode='HTML')
    return PATRONYMIC

async def get_patronymic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['patronymic'] = update.message.text.strip()
    await update.message.reply_text("✅ Введіть <b>дату народження</b> (ДД.ММ.РРРР):", parse_mode='HTML')
    return BIRTH_DATE

async def get_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['birth_date'] = update.message.text.strip()
    keyboard = [[InlineKeyboardButton("💾 Так", callback_data='save_yes'), 
                 InlineKeyboardButton("❌ Ні", callback_data='save_no')]]
    await update.message.reply_text("💾 Зберегти дані для майбутніх пошуків?", 
                                    reply_markup=InlineKeyboardMarkup(keyboard))
    return SAVE_CHOICE

async def perform_search_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.callback_query.message
    search_params = {
        "f": context.user_data.get('first_name', ''),
        "l": context.user_data.get('last_name', ''),
        "p": context.user_data.get('patronymic', ''),
        "b": context.user_data.get('birth_date', '')
    }
    
    status_msg = await msg.reply_text("⏳ Завантаження та пошук (це може зайняти до хвилини)...")
    
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: requests.get(JSON_URL, timeout=60))
        data = response.json()
        records = data if isinstance(data, list) else data.get('persons', [])
        
        found = None
        norm = lambda t: str(t).strip().lower().replace("ʼ", "'") if t else ""
        
        target_f, target_l, target_p, target_b = norm(search_params["f"]), norm(search_params["l"]), norm(search_params["p"]), search_params["b"]

        for r in records:
            rf = norm(r.get('FIRST_NAME_U') or r.get('FIRST_NAME'))
            rl = norm(r.get('LAST_NAME_U') or r.get('LAST_NAME'))
            rp = norm(r.get('MIDDLE_NAME_U') or r.get('PATRONYMIC'))
            rb_raw = r.get('BIRTH_DATE') or r.get('BIRTHDAY') or ''
            rb = ""
            if rb_raw and 'T' in rb_raw:
                p = rb_raw.split('T')[0].split('-')
                if len(p) == 3: rb = f"{p[2]}.{p[1]}.{p[0]}"

            if rf == target_f and rl == target_l and rp == target_p and rb == target_b:
                found = r
                break

        res = f"🚨 <b>Знайдено!</b>\nСтаття: {found.get('ARTICLE_CRIM')}" if found else "✅ <b>Не знайдено.</b>"
        await status_msg.edit_text(res, parse_mode='HTML', 
                                   reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data='main_menu')]]))
    except Exception as e:
        await status_msg.edit_text(f"❌ Помилка: {str(e)}")

async def save_choice_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data['saved_params'] = {
        'first_name': context.user_data['first_name'], 'last_name': context.user_data['last_name'],
        'patronymic': context.user_data['patronymic'], 'birth_date': context.user_data['birth_date']
    }
    await update.callback_query.edit_message_text("💾 Збережено!")
    await perform_search_logic(update, context)
    return ConversationHandler.END

async def save_choice_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("⏳ Пошук без збереження...")
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
    await update.message.reply_text('❌ Скасовано.', reply_markup=ReplyKeyboardRemove())
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
        fallbacks=[CommandHandler('cancel', cancel)],
        per_chat=True,
        per_user=True,
        per_message=False
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(search_saved, pattern='search_saved'))
    app.add_handler(CallbackQueryHandler(start, pattern='main_menu'))
    app.add_handler(conv)
    
    print("✅ Бот запущено!")
    app.run_polling()

if __name__ == '__main__':
    main()
