import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from crm.models import UserProfile, Customer, Order

@pytest.mark.django_db
class TestRoleAccess:
    def setup_method(self):
        self.dispatcher_user = User.objects.create_user(username='disp', password='pass')
        UserProfile.objects.create(user=self.dispatcher_user, role='dispatcher')
        self.driver_user = User.objects.create_user(username='driver1', password='pass')
        UserProfile.objects.create(user=self.driver_user, role='driver')
        self.customer_user = User.objects.create_user(username='cust', password='pass')
        UserProfile.objects.create(user=self.customer_user, role='customer')
        self.customer_record = Customer.objects.create(user=self.customer_user, name="Тест клиент")
        self.order = Order.objects.create(
            customer=self.customer_record,
            pickup_address="А",
            delivery_address="Б",
            requested_date="2026-06-01"
        )

    def test_order_list_only_dispatcher(self, client):
        response = client.get(reverse('order_list'))
        assert response.status_code == 302
        client.login(username='disp', password='pass')
        response = client.get(reverse('order_list'))
        assert response.status_code == 200
        client.login(username='driver1', password='pass')
        response = client.get(reverse('order_list'))
        assert response.status_code == 403

    def test_customer_dashboard_own_orders(self, client):
        client.login(username='cust', password='pass')
        response = client.get(reverse('customer_dashboard'))
        assert response.status_code == 200
        assert 'А' in response.content.decode()

    def test_customer_pay_order(self, client):
        client.login(username='cust', password='pass')
        # Заказ ещё не выполнен → редирект
        response = client.get(reverse('customer_pay_order', args=[self.order.id]))
        assert response.status_code == 302
        self.order.status = 'completed'
        self.order.save()
        response = client.get(reverse('customer_pay_order', args=[self.order.id]), follow=True)
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Спасибо' in content or 'Оплачен' in content