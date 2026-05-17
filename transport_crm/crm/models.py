import time
from decimal import Decimal
import requests
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
from django.contrib.auth.models import User

class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Пользователь")
    name = models.CharField(max_length=200, verbose_name="Название компании / ФИО")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    email = models.EmailField(blank=True, verbose_name="Email")
    address = models.TextField(blank=True, verbose_name="Адрес")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"


class Driver(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Пользователь")
    first_name = models.CharField(max_length=100, verbose_name="Имя")
    last_name = models.CharField(max_length=100, verbose_name="Фамилия")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    license_number = models.CharField(max_length=50, verbose_name="Номер прав")
    hire_date = models.DateField(default=date.today, verbose_name="Дата найма")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        verbose_name = "Водитель"
        verbose_name_plural = "Водители"


class Vehicle(models.Model):
    plate_number = models.CharField(max_length=20, unique=True, verbose_name="Госномер")
    brand = models.CharField(max_length=100, verbose_name="Марка")
    model = models.CharField(max_length=100, verbose_name="Модель")
    capacity_ton = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Грузоподъемность, т")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    def __str__(self):
        return f"{self.plate_number} ({self.brand} {self.model})"

    class Meta:
        verbose_name = "Автомобиль"
        verbose_name_plural = "Автомобили"


class Tariff(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название тарифа")
    base_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Базовая ставка, руб.")
    price_per_km = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Цена за 1 км, руб.")
    price_per_ton = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Цена за 1 тонну, руб.")
    urgency_coefficient = models.DecimalField(max_digits=3, decimal_places=2, default=1.0, verbose_name="Коэффициент срочности")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Тариф"
        verbose_name_plural = "Тарифы"


class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('assigned', 'Назначен'),
        ('in_transit', 'В пути'),
        ('completed', 'Выполнен'),
        ('cancelled', 'Отменён'),
    ]
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="Клиент")
    pickup_address = models.TextField(verbose_name="Адрес подачи")
    delivery_address = models.TextField(verbose_name="Адрес доставки")
    cargo_description = models.TextField(blank=True, verbose_name="Описание груза")
    weight_ton = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name="Вес, т")
    distance_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Расстояние, км")
    tariff = models.ForeignKey(Tariff, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Тариф")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Стоимость, руб.")
    requested_date = models.DateField(verbose_name="Желаемая дата перевозки")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name="Статус")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлён")

    pickup_lat = models.FloatField(null=True, blank=True, verbose_name="Широта подачи")
    pickup_lon = models.FloatField(null=True, blank=True, verbose_name="Долгота подачи")
    delivery_lat = models.FloatField(null=True, blank=True, verbose_name="Широта доставки")
    delivery_lon = models.FloatField(null=True, blank=True, verbose_name="Долгота доставки")

    def _geocode_with_yandex(self, address):
        """Геокодирование через старый ключ (Геокодер). Возвращает (lat, lon) или None."""
        base_url = "https://geocode-maps.yandex.ru/1.x/"
        params = {
            "geocode": address,
            "format": "json",
            "results": 1,
            "apikey": settings.YANDEX_GEOCODER_API_KEY,
            "lang": "ru_RU",
        }
        try:
            time.sleep(1)
            resp = requests.get(base_url, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                geo_objects = data['response']['GeoObjectCollection']['featureMember']
                if geo_objects:
                    coords = geo_objects[0]['GeoObject']['Point']['pos']
                    lon, lat = map(float, coords.split())
                    return lat, lon
        except Exception as e:
            print(f"Ошибка геокодирования адреса '{address}':", e)
        return None, None

    def get_route_distance(self, lat1, lon1, lat2, lon2):
        """
        Возвращает расстояние в км по автодорогам.
        Сначала пробует Яндекс.Маршрутизацию с новым ключом.
        При неудаче – OSRM.
        Если оба недоступны – возвращает None.
        """
        # Попытка 1: Яндекс Маршрутизация
        try:
            url = "https://api.routing.yandex.net/v2/route"
            params = {
                "apikey": settings.YANDEX_ROUTING_API_KEY,
                "mode": "driving",
                "lang": "ru",
                "waypoints": f"{lat1},{lon1}|{lat2},{lon2}",
            }
            resp = requests.get(url, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if 'route' in data and data['route']:
                    distance_m = data['route']['distance']
                    return round(distance_m / 1000, 2)
        except Exception:
            pass

        try:
            osrm_url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
            resp = requests.get(osrm_url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if 'routes' in data and len(data['routes']) > 0:
                    distance_m = data['routes'][0]['distance']
                    return round(distance_m / 1000, 2)
        except Exception:
            pass

        return None

    def geocode_and_set_coordinates(self):
        """Геокодирует адреса и вычисляет дорожное расстояние (без прямой)."""
        if self.pickup_address and self.delivery_address:
            self.pickup_lat, self.pickup_lon = self._geocode_with_yandex(self.pickup_address)
            self.delivery_lat, self.delivery_lon = self._geocode_with_yandex(self.delivery_address)

            if self.pickup_lat and self.delivery_lat:
                road_km = self.get_route_distance(
                    self.pickup_lat, self.pickup_lon,
                    self.delivery_lat, self.delivery_lon
                )
                if road_km is not None:
                    self.distance_km = Decimal(str(road_km))
                else:
                    # Оставляем distance_km = None (стоимость не рассчитается)
                    self.distance_km = None

    def save(self, *args, **kwargs):
        if not self.pk or self._pickup_changed() or self._delivery_changed():
            self.geocode_and_set_coordinates()
        if self.tariff and self.distance_km is not None:
            self.price = self.calculate_price()
        else:
            self.price = None
        super().save(*args, **kwargs)

    def _pickup_changed(self):
        if not self.pk:
            return True
        old = Order.objects.get(pk=self.pk)
        return old.pickup_address != self.pickup_address

    def _delivery_changed(self):
        if not self.pk:
            return True
        old = Order.objects.get(pk=self.pk)
        return old.delivery_address != self.delivery_address

    def calculate_price(self):
        if self.tariff and self.distance_km is not None:
            base = self.tariff.base_price
            km_cost = self.tariff.price_per_km * self.distance_km
            ton_cost = self.tariff.price_per_ton * Decimal(str(self.weight_ton))
            total = base + km_cost + ton_cost
            total = total * self.tariff.urgency_coefficient
            return total.quantize(Decimal('0.01'))
        return None

    def __str__(self):
        return f"Заказ №{self.id} от {self.customer.name} ({self.get_status_display()})"

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-created_at']


class Assignment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='assignment', verbose_name="Заказ")
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, verbose_name="Водитель")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, verbose_name="Автомобиль")
    assigned_at = models.DateTimeField(auto_now_add=True, verbose_name="Назначено")

    def clean(self):
        if self.order_id and self.driver_id:
            conflicts = Assignment.objects.filter(
                driver=self.driver,
                order__requested_date=self.order.requested_date
            ).exclude(order__status__in=['completed', 'cancelled'])
            if self.pk:
                conflicts = conflicts.exclude(pk=self.pk)
            if conflicts.exists():
                raise ValidationError("Водитель уже занят в этот день другим заказом.")
        if self.order_id and self.vehicle_id:
            conflicts = Assignment.objects.filter(
                vehicle=self.vehicle,
                order__requested_date=self.order.requested_date
            ).exclude(order__status__in=['completed', 'cancelled'])
            if self.pk:
                conflicts = conflicts.exclude(pk=self.pk)
            if conflicts.exists():
                raise ValidationError("Автомобиль уже занят в этот день другим заказом.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Назначение: {self.order} → {self.driver} / {self.vehicle}"

    class Meta:
        verbose_name = "Назначение"
        verbose_name_plural = "Назначения"


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES, null=True, blank=True)
    new_status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Заказ №{self.order.id}: {self.old_status or '—'} → {self.new_status}"

    class Meta:
        verbose_name = "История статуса"
        verbose_name_plural = "Истории статусов"
        ordering = ['-changed_at']


class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments', verbose_name="Заказ")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Сумма")
    paid_at = models.DateField(verbose_name="Дата оплаты")
    method = models.CharField(max_length=50, choices=[('cash', 'Наличные'), ('card', 'Карта'), ('transfer', 'Безнал')], verbose_name="Способ оплаты")

    def __str__(self):
        return f"Оплата {self.amount} руб. по {self.order}"

    class Meta:
        verbose_name = "Платёж"
        verbose_name_plural = "Платежи"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('dispatcher', 'Диспетчер'),
        ('driver', 'Водитель'),
        ('customer', 'Клиент'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer', verbose_name="Роль")

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"