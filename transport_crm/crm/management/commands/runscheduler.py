import schedule
import time
import asyncio
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from crm.models import Order
from crm.bot import send_telegram_message

def remind_drivers():
    """
    Проверяет заказы со статусом 'assigned' и датой подачи сегодня,
    и если время подачи через 1 час (+- 5 минут), отправляет напоминание водителю.
    """
    now = timezone.now()
    today = now.date()
    orders = Order.objects.filter(
        status='assigned',
        requested_date=today
    ).select_related('assignment__driver')

    for order in orders:
        assignment = order.assignment
        if not assignment or not assignment.driver:
            continue
        driver = assignment.driver
        if not driver.telegram_id:
            continue

        # Здесь упрощённая логика: предполагаемое время подачи – 8:00 утра.
        # Если сейчас между 7:00 и 7:05, отправляем напоминание.
        target_hour = 8
        if now.hour == target_hour - 1 and 0 <= now.minute <= 5:
            message = (
                f"🚛 Напоминание о рейсе!\n"
                f"Заказ №{order.id}\n"
                f"Маршрут: {order.pickup_address} → {order.delivery_address}\n"
                f"Дата: {order.requested_date}\n"
                f"Предполагаемое время подачи: {target_hour}:00\n"
                f"Пожалуйста, будьте готовы."
            )
            # Асинхронная отправка через бота
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(send_telegram_message(driver.telegram_id, message))
            loop.close()
            print(f"Напоминание отправлено водителю {driver.last_name} по заказу №{order.id}")

class Command(BaseCommand):
    help = 'Запускает планировщик задач (напоминания водителям)'

    def handle(self, *args, **options):
        schedule.every(5).minutes.do(remind_drivers)  # <-- вот где schedule

        self.stdout.write(self.style.SUCCESS("Планировщик запущен. Нажмите Ctrl+C для остановки."))
        while True:
            schedule.run_pending()
            time.sleep(1)