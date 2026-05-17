from django.contrib import admin
from .models import (
    Customer, Driver, Vehicle, Tariff, Order,
    Assignment, Payment, UserProfile, OrderStatusHistory
)

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email')
    search_fields = ('name', 'phone')


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'phone', 'hire_date')
    search_fields = ('last_name', 'first_name')


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('plate_number', 'brand', 'model', 'capacity_ton', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('plate_number', 'brand')


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_price', 'price_per_km', 'price_per_ton', 'urgency_coefficient')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'pickup_address', 'delivery_address',
                    'weight_ton', 'distance_km', 'tariff', 'price',
                    'pickup_lat', 'pickup_lon', 'delivery_lat', 'delivery_lon',
                    'requested_date', 'status', 'created_at')
    list_filter = ('status', 'requested_date', 'tariff')
    search_fields = ('customer__name', 'pickup_address', 'delivery_address')
    date_hierarchy = 'created_at'
    fieldsets = (
        ('Основная информация', {
            'fields': ('customer', 'pickup_address', 'delivery_address',
                       'cargo_description', 'weight_ton', 'requested_date')
        }),
        ('Расчёт стоимости', {
            'fields': ('tariff', 'distance_km', 'price')
        }),
        ('Координаты (автозаполнение)', {
            'fields': ('pickup_lat', 'pickup_lon', 'delivery_lat', 'delivery_lon')
        }),
        ('Статус', {
            'fields': ('status',)
        }),
    )


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('order', 'driver', 'vehicle', 'assigned_at')
    raw_id_fields = ('order', 'driver', 'vehicle')


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('order', 'old_status', 'new_status', 'changed_by', 'changed_at')
    list_filter = ('new_status', 'changed_at')
    readonly_fields = ('changed_at',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'amount', 'paid_at', 'method')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)