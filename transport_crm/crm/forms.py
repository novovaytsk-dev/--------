from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Order, Tariff, Assignment, UserProfile, Vehicle, Driver

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['customer', 'pickup_address', 'delivery_address',
                  'cargo_description', 'weight_ton', 'distance_km', 'tariff', 'requested_date', 'status']

    def clean_requested_date(self):
        requested_date = self.cleaned_data['requested_date']
        from django.utils import timezone
        if requested_date < timezone.now().date():
            raise forms.ValidationError("Дата перевозки не может быть в прошлом.")
        return requested_date


class SignUpForm(UserCreationForm):
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, label="Роль")

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'role')


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['driver', 'vehicle']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['driver'].queryset = Driver.objects.all()
        self.fields['vehicle'].queryset = Vehicle.objects.filter(is_active=True)


class DriverForm(forms.ModelForm):
    """Форма для создания/редактирования водителя с HTML5-валидацией."""
    class Meta:
        model = Driver
        fields = ['first_name', 'last_name', 'phone', 'license_number', 'telegram_id', 'hire_date']
        widgets = {
            'phone': forms.TextInput(attrs={
                'pattern': r'\+7\d{10}',
                'title': 'Формат: +7XXXXXXXXXX (11 цифр)',
                'required': True,
                'placeholder': '+79991234567'
            }),
            'license_number': forms.TextInput(attrs={
                'pattern': r'[A-Za-z0-9]+',
                'title': 'Только латинские буквы и цифры',
                'required': True,
                'placeholder': 'A1B2C3'
            }),
        }