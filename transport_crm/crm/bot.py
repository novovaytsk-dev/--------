import asyncio
import nest_asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Bot

# Разрешаем вложенный event loop для работы внутри синхронного кода Django
nest_asyncio.apply()

# Токен бота (получить у @BotFather)
TOKEN = 'ВАШ_ТОКЕН_БОТА'  # ← ЗАМЕНИТЬ НА СВОЙ

async def send_telegram_message(telegram_id: int, text: str):
    """Отправляет текстовое сообщение в Telegram."""
    bot = Bot(token=TOKEN)
    try:
        await bot.send_message(chat_id=telegram_id, text=text)
        print(f"Сообщение отправлено пользователю {telegram_id}")
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Регистрация водителя: выводит его Telegram ID для привязки диспетчером."""
    telegram_id = update.effective_user.id
    await update.message.reply_text(
        f"Добро пожаловать! Ваш Telegram ID: {telegram_id}\n"
        "Передайте его диспетчеру для привязки к вашему профилю."
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Заглушка для проверки статуса рейсов."""
    await update.message.reply_text("Здесь будет список ваших рейсов и кнопки для смены статуса.")

def run_bot():
    """Запускает бота в режиме polling."""
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    print("Telegram bot started...")
    application.run_polling()