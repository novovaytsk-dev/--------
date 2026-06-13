import pytest
from decimal import Decimal
from crm.models import Customer, Driver, Vehicle, Tariff, Order, Assignment

@pytest.mark.django_db
class TestCustomerModel:
    def test_create_customer(self):
        customer = Customer.objects.create(name="ООО Ромашка", phone="+79991234567")
        assert customer.name == "ООО Ромашка"
        assert str(customer) == "ООО Ромашка"

@pytest.mark.django_db
class TestDriverModel:
    def test_create_driver(self):
        driver = Driver.objects.create(first_name="Иван", last_name="Петров", phone="123", license_number="AB123")
        assert str(driver) == "Иван Петров"

@pytest.mark.django_db
class TestTariffAndPriceCalculation:
    def test_calculate_price_formula(self):
        """
        Проверяет, что метод calculate_price возвращает корректную сумму
        для заданного тарифа, веса и расстояния.
        """
        tariff = Tariff.objects.create(
            name="Стандарт",
            base_price=500,
            price_per_km=20,
            price_per_ton=100,
            urgency_coefficient=1.0
        )
        customer = Customer.objects.create(name="Тест")
        order = Order(
            customer=customer,
            pickup_address="Киров",
            delivery_address="Москва",
            weight_ton=10,
            distance_km=200,
            tariff=tariff,
            requested_date="2026-06-01"
        )
        order.save()
        order.distance_km = Decimal('200')
        calculated = order.calculate_price()
        expected = Decimal('5500.00')
        assert calculated == expected

    def test_save_assigns_price(self):
        """
        При сохранении заказа с тарифом и расстоянием автоматически заполняется цена.
        """
        tariff = Tariff.objects.create(name="Эконом", base_price=100, price_per_km=10, price_per_ton=50, urgency_coefficient=1.5)
        customer = Customer.objects.create(name="Тест2")
        order = Order(
            customer=customer,
            pickup_address="А",
            delivery_address="Б",
            weight_ton=5,
            distance_km=100,
            tariff=tariff,
            requested_date="2026-06-02"
        )
        order.save()
        assert order.price is not None
        assert order.price > 0

@pytest.mark.django_db
class TestAssignmentConflict:
    def test_driver_double_booking_raises(self):
        driver = Driver.objects.create(first_name="A", last_name="B", phone="1", license_number="L1")
        vehicle = Vehicle.objects.create(plate_number="A111AA", brand="X", model="Y", capacity_ton=20)
        customer = Customer.objects.create(name="C")
        order1 = Order.objects.create(
            customer=customer, pickup_address="A", delivery_address="B",
            requested_date="2026-06-01"
        )
        order2 = Order.objects.create(
            customer=customer, pickup_address="C", delivery_address="D",
            requested_date="2026-06-01"
        )
        Assignment.objects.create(order=order1, driver=driver, vehicle=vehicle)
        assign2 = Assignment(order=order2, driver=driver, vehicle=vehicle)
        with pytest.raises(Exception):
            assign2.save()