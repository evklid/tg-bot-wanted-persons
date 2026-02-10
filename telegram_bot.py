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
    saved_data = context.user_data.get('saved_params')
    if saved_data:
        keyboard = [
            [InlineKeyboardButton("🔍 Пошук за збереженими даними", callback_data='search_saved')],
            [InlineKeyboardButton("✏️ Змінити параметри пошуку", callback_data='start_check')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f'👋 Вітаю!\n\n💾 <b>У вас є збережені параметри:</b>\n\n'
            f'• Ім\'я: {saved_data["first_name"]}\n'
            f'• Прізвище: {saved_data["last_name"]}\n'
            f'• По-батькові: {saved_data["patronymic"]}\n'
            f'• Дата народження: {saved_data["birth_date"]}\n\n'
            'Виберіть дію:',
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        keyboard = [[InlineKeyboardButton("🔍 Почати перевірку", callback_data='start_check')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            '👋 Вітаю!\n\nЦей бот перевіряє наявність особи в базі розшукуваних осіб МВС України.\n\n'
            'Натисніть кнопку для початку:',
            reply_markup=reply_markup
        )
    return ConversationHandler.END

async def start_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📝 Введіть <b>ім'я</b> особи для перевірки:\n\nПриклад: Павло",
        parse_mode='HTML'
    )
    return FIRST_NAME

async def search_saved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    saved_data = context.user_data.get('saved_params')
    if not saved_data:
        await query.edit_message_text("❌ Немає збережених даних.")
        return ConversationHandler.END
    
    context.user_data.update(saved_data)
    await query.edit_message_text(f"⏳ Починаю перевірку для: {saved_data['last_name']} {saved_data['first_name']}...")
    await perform_search(query.message, context)
    return ConversationHandler.END

async def get_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['first_name'] = update.message.text.strip()
    await update.message.reply_text("✅ Ім'я прийнято. Введіть <b>прізвище</b>:", parse_mode='HTML')
    return LAST_NAME

async def get_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['last_name'] = update.message.text.strip()
    await update.message.reply_text("✅ Прізвище прийнято. Введіть <b>по-батькові</b>:", parse_mode='HTML')
    return PATRONYMIC

async def get_patronymic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['patronymic'] = update.message.text.strip()
    await update.message.reply_text("✅ По-батькові прийнято. Введіть <b>дату народження</b> (ДД.ММ.РРРР):", parse_mode='HTML')
    return BIRTH_DATE

async def get_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['birth_date'] = update.message.text.strip()
    keyboard = [
        [InlineKeyboardButton("💾 Так, зберегти", callback_data='save_yes')],
        [InlineKeyboardButton("❌ Ні, не зберігати", callback_data='save_no')]
    ]
    await update.message.reply_text(
        f"📋 Дані: {context.user_data['last_name']} {context.user_data['first_name']} {context.user_data['birth_date']}\n"
        "💾 Зберегти дані для майбутніх пошуків?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return SAVE_CHOICE

async def save_choice_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['saved_params'] = {
        'first_name': context.user_data['first_name'],
        'last_name': context.user_data['last_name'],
        'patronymic': context.user_data['patronymic'],
        'birth_date': context.user_data['birth_date']
    }
    await query.edit_message_text("💾 Дані збережено! ⏳ Починаю пошук...")
    await perform_search(query.message, context)
    return ConversationHandler.END

async def save_choice_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⏳ Починаю пошук без збереження...")
    await perform_search(query.message, context)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('❌ Скасовано.', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(query, context)
    return ConversationHandler.END

async def perform_search(message_obj, context: ContextTypes.DEFAULT_TYPE):
    search_params = {
        "first_name": context.user_data.get('first_name', ''),
        "last_name": context.user_data.get('last_name', ''),
        "patronymic": context.user_data.get('patronymic', ''),
        "birth_date": context.user_data.get('birth_date', '')
    }
    
    try:
        loading_msg = await message_obj.reply_text("⏳ Завантаження бази МВС...")
        response = requests.get(JSON_URL, timeout=120)
        response.raise_for_status()
        data = response.json()
        
        records = data if isinstance(data, list) else data.get('persons', [])
        found_record = None
        
        def normalize(text):
            return str(text).strip().lower().replace("'", "'").replace("`", "'").replace("ʼ", "'") if text else ""

        for record in records:
            f_name = normalize(record.get('FIRST_NAME_U') or record.get('FIRST_NAME'))
            l_name = normalize(record.get('LAST_NAME_U') or record.get('LAST_NAME'))
            p_name = normalize(record.get('MIDDLE_NAME_U') or record.get('PATRONYMIC'))
            
            b_date_raw = record.get('BIRTH_DATE') or record.get('BIRTHDAY') or ''
            b_date_norm = ""
            if b_date_raw and 'T' in b_date_raw:
                parts = b_date_raw.split('T')[0].split('-')
                if len(parts) == 3: b_date_norm = f"{parts[2]}.{parts[1]}.{parts[0]}"

            if (f_name == normalize(search_params["first_name"]) and
                l_name == normalize(search_params["last_name"]) and
                p_name == normalize(search_params["patronymic"]) and
                b_date_norm == search_params["birth_date"]):
                found_record = record
                found_record['b_date'] = b_date_norm
                break

        if found_record:
            res = (f"🚨 <b>Особу знайдено в розшуку!</b>\n\n"
                   f"• Прізвище: {found_record.get('LAST_NAME_U', 'N/A')}\n"
                   f"• Стаття: {found_record.get('ARTICLE_CRIM', 'Не вказано')}\n")
        else:
            res = "✅ <b>Особу не знайдено в базі розшуку.</b>"
        
        keyboard = [[InlineKeyboardButton("🏠 Меню", callback_data='main_menu')]]
        await loading_msg.edit_text(res, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        
    except Exception as e:
        await message_obj.reply_text(f"❌ Помилка: {str(e)}")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_check, pattern='start_check')],
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
        per_message=False
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(search_saved, pattern='search_saved'))
    application.add_handler(CallbackQueryHandler(main_menu, pattern='main_menu'))
    application.add_handler(conv_handler)
    
    print("✅ Бот запущено!")
    application.run_polling()

if __name__ == '__main__':
    main()
