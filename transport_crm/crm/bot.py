import requests
from django.conf import settings

"""
Модуль для отправки уведомлений в Telegram через HTTP-запросы.
Использует токен бота, полученный от BotFather.
"""


TOKEN: str = '8611685364:AAGkf8eFYKvy-8DhxuEqtU4k1JbPYrxBSFs'

def send_telegram_message(telegram_id: int, text: str) -> None:
    """
    Отправляет текстовое сообщение пользователю Telegram.

    Args:
        telegram_id (int): ID чата получателя.
        text (str): Текст сообщения.

    Returns:
        None: В случае ошибки выводит сообщение в консоль.
    """
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        'chat_id': telegram_id,
        'text': text,
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print(f"Сообщение отправлено пользователю {telegram_id}")
        else:
            print(f"Ошибка отправки: {response.text}")
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")