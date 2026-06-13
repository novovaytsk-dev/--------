import pytest
from crm.forms import OrderForm, SignUpForm
from crm.models import Customer

@pytest.mark.django_db
def test_order_form_date_in_past():
    customer = Customer.objects.create(name="Т")
    form = OrderForm(data={
        'customer': customer.id,
        'pickup_address': 'А',
        'delivery_address': 'Б',
        'weight_ton': 5,
        'requested_date': '2020-01-01',
        'status': 'new'
    })
    assert not form.is_valid()
    assert 'requested_date' in form.errors

@pytest.mark.django_db
def test_signup_form():
    form = SignUpForm(data={
        'username': 'newuser',
        'email': 'new@example.com',
        'password1': 'complexpass123',
        'password2': 'complexpass123',
        'role': 'customer'
    })
    assert form.is_valid()