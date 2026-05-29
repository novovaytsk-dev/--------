from django.urls import path
from django.contrib.auth.views import LoginView
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    # Редирект стандартного /accounts/profile/ на дашборд
    path('accounts/profile/', RedirectView.as_view(url='/dashboard/', permanent=False)),

    # Заказы
    path('', views.OrderListView.as_view(), name='order_list'),
    path('order/<int:pk>/', views.OrderDetailView.as_view(), name='order_detail'),
    path('order/create/', views.OrderCreateView.as_view(), name='order_create'),
    path('order/<int:pk>/update/', views.OrderUpdateView.as_view(), name='order_update'),
    path('order/<int:pk>/delete/', views.OrderDeleteView.as_view(), name='order_delete'),
    path('order/<int:order_id>/assign/', views.assign_order, name='assign_order'),

    # Клиенты
    path('customers/', views.CustomerListView.as_view(), name='customer_list'),
    path('customer/<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    path('customer/create/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('customer/<int:pk>/update/', views.CustomerUpdateView.as_view(), name='customer_update'),
    path('customer/<int:pk>/delete/', views.CustomerDeleteView.as_view(), name='customer_delete'),

    # Водители
    path('drivers/', views.DriverListView.as_view(), name='driver_list'),
    path('driver/<int:pk>/', views.DriverDetailView.as_view(), name='driver_detail'),
    path('driver/create/', views.DriverCreateView.as_view(), name='driver_create'),
    path('driver/<int:pk>/update/', views.DriverUpdateView.as_view(), name='driver_update'),
    path('driver/<int:pk>/delete/', views.DriverDeleteView.as_view(), name='driver_delete'),

    # Автомобили
    path('vehicles/', views.VehicleListView.as_view(), name='vehicle_list'),
    path('vehicle/<int:pk>/', views.VehicleDetailView.as_view(), name='vehicle_detail'),
    path('vehicle/create/', views.VehicleCreateView.as_view(), name='vehicle_create'),
    path('vehicle/<int:pk>/update/', views.VehicleUpdateView.as_view(), name='vehicle_update'),
    path('vehicle/<int:pk>/delete/', views.VehicleDeleteView.as_view(), name='vehicle_delete'),

    # Назначения и смена статуса водителем
    path('assignments/', views.AssignmentListView.as_view(), name='assignment_list'),
    path('assignment/<int:assignment_id>/change_status/', views.change_order_status, name='change_order_status'),

    # Платежи (полный CRUD)
    path('payments/', views.PaymentListView.as_view(), name='payment_list'),
    path('payment/create/', views.PaymentCreateView.as_view(), name='payment_create'),
    path('payment/<int:pk>/', views.PaymentDetailView.as_view(), name='payment_detail'),
    path('payment/<int:pk>/update/', views.PaymentUpdateView.as_view(), name='payment_update'),
    path('payment/<int:pk>/delete/', views.PaymentDeleteView.as_view(), name='payment_delete'),

    # Аутентификация и дашборды
    path('customer/order/<int:pk>/', views.customer_order_detail, name='customer_order_detail'),
    path('accounts/login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', views.logout_view, name='logout'),
    path('accounts/signup/', views.signup_view, name='signup'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/dispatcher/', views.dispatcher_dashboard, name='dispatcher_dashboard'),
    path('dashboard/driver/', views.driver_dashboard, name='driver_dashboard'),
    path('dashboard/customer/', views.customer_dashboard, name='customer_dashboard'),

    # Оплата заказа клиентом
    path('customer/pay/<int:order_id>/', views.customer_pay_order, name='customer_pay_order'),

    # Аналитика и отчёты
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('analytics/download/<str:report_type>/', views.download_report, name='download_report'),

    # Экспорт документов
    path('order/<int:pk>/document/<str:doc_type>/', views.download_document, name='download_document'),
]