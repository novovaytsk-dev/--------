from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Order, Tariff, Assignment, UserProfile, Vehicle, Driver

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['customer', 'pickup_address', 'delivery_address',
                  'cargo_description', 'weight_ton', 'tariff', 'requested_date', 'status']

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
        # Показываем всех водителей (без фильтрации по пользователю)
        self.fields['driver'].queryset = Driver.objects.all()
        # Показываем только активные автомобили
        self.fields['vehicle'].queryset = Vehicle.objects.filter(is_active=True)