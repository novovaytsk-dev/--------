from django.core.management.base import BaseCommand
from crm.bot import run_bot

class Command(BaseCommand):
    help = 'Запускает Telegram-бота'

    def handle(self, *args, **options):
        self.stdout.write("Запуск Telegram-бота...")
        run_bot()