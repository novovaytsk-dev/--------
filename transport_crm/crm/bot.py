import requests
from django.conf import settings

TOKEN = '8611685364:AAGkf8eFYKvy-8DhxuEqtU4k1JbPYrxBSFs'

def send_telegram_message(telegram_id, text):
    """Отправляет текстовое сообщение в Telegram."""
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