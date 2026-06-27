from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Order, Tariff, Assignment, UserProfile, Vehicle, Driver, Customer, Payment


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['customer', 'pickup_address', 'delivery_address',
                  'cargo_description', 'weight_ton', 'distance_km', 'tariff', 'requested_date', 'status']
        widgets = {
            'requested_date': forms.DateInput(attrs={'type': 'date', 'required': True}),
            'pickup_address': forms.Textarea(attrs={'required': True, 'rows': 2}),
            'delivery_address': forms.Textarea(attrs={'required': True, 'rows': 2}),
            'weight_ton': forms.NumberInput(attrs={'required': True, 'min': '0.01', 'step': '0.01'}),
            'distance_km': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
            'cargo_description': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_requested_date(self):
        requested_date = self.cleaned_data['requested_date']
        if requested_date < timezone.now().date():
            raise ValidationError("Дата перевозки не может быть в прошлом.")
        return requested_date

    def clean_weight_ton(self):
        weight = self.cleaned_data['weight_ton']
        if weight <= 0:
            raise ValidationError("Вес груза должен быть положительным числом.")
        return weight

    def clean_distance_km(self):
        distance = self.cleaned_data.get('distance_km')
        if distance is not None and distance < 0:
            raise ValidationError("Расстояние не может быть отрицательным.")
        return distance


class SignUpForm(UserCreationForm):
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, label="Роль")
    email = forms.EmailField(required=True, help_text="Обязательное поле. Введите действующий email.")

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'role')

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if len(password) < 8:
            raise ValidationError("Пароль должен содержать не менее 8 символов.")
        return password


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['driver', 'vehicle']
        widgets = {
            'driver': forms.Select(attrs={'required': True}),
            'vehicle': forms.Select(attrs={'required': True}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['driver'].queryset = Driver.objects.filter(
            user__profile__role='driver'
        )
        self.fields['vehicle'].queryset = Vehicle.objects.filter(is_active=True)


class DriverForm(forms.ModelForm):
    class Meta:
        model = Driver
        fields = ['first_name', 'last_name', 'phone', 'license_number', 'telegram_id', 'hire_date']
        widgets = {
            'first_name': forms.TextInput(attrs={'required': True}),
            'last_name': forms.TextInput(attrs={'required': True}),
            'phone': forms.TextInput(attrs={
                'required': True,
                'pattern': r'\+7\d{10}',
                'title': 'Формат: +7XXXXXXXXXX (11 цифр, начиная с +7)',
            }),
            'license_number': forms.TextInput(attrs={
                'required': True,
                'pattern': r'[A-Za-z0-9]+',
                'title': 'Только латинские буквы и цифры',
            }),
            'hire_date': forms.DateInput(attrs={'type': 'date', 'required': True}),
            'telegram_id': forms.NumberInput(attrs={'placeholder': '123456789'}),
        }


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'phone', 'email', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'required': True}),
            'phone': forms.TextInput(attrs={
                'required': True,
                'pattern': r'\+7\d{10}',
                'title': 'Формат: +7XXXXXXXXXX (11 цифр, начиная с +7)',
            }),
            'email': forms.EmailInput(attrs={'required': True}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['plate_number', 'brand', 'model', 'capacity_ton', 'is_active']
        widgets = {
            'plate_number': forms.TextInput(attrs={
                'required': True,
                'pattern': r'[A-Z]\d{3}[A-Z]{2}\d{2,3}',
                'title': 'Формат: A111AA77 (латиница, как в СТС)',
            }),
            'brand': forms.TextInput(attrs={'required': True}),
            'model': forms.TextInput(attrs={'required': True}),
            'capacity_ton': forms.NumberInput(attrs={'required': True, 'min': '0.1', 'step': '0.1'}),
        }

    def clean_capacity_ton(self):
        capacity = self.cleaned_data['capacity_ton']
        if capacity <= 0:
            raise ValidationError("Грузоподъёмность должна быть положительным числом.")
        return capacity


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['order', 'amount', 'paid_at', 'method']
        widgets = {
            'order': forms.Select(attrs={'required': True}),
            'amount': forms.NumberInput(attrs={'required': True, 'min': '0.01', 'step': '0.01'}),
            'paid_at': forms.DateInput(attrs={'type': 'date', 'required': True}),
            'method': forms.Select(attrs={'required': True}),
        }

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise ValidationError("Сумма платежа должна быть положительной.")
        return amount

    def clean_paid_at(self):
        paid_at = self.cleaned_data['paid_at']
        if paid_at > timezone.now().date():
            raise ValidationError("Дата оплаты не может быть в будущем.")
        return paid_at