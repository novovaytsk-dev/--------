import io
import base64
import urllib.parse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q, Count, Sum, QuerySet
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.http import HttpResponse, HttpRequest
from django.utils import timezone
from datetime import timedelta
from django.core.mail import EmailMessage
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from .models import (
    Customer, Driver, Vehicle, Order, Assignment, Payment,
    UserProfile, OrderStatusHistory
)
from .forms import (
    OrderForm, SignUpForm, AssignmentForm, DriverForm,
    CustomerForm, VehicleForm, PaymentForm
)
from . import documents
from crm.bot import send_telegram_message


#  Вспомогательные функции проверки ролей 
def is_dispatcher(user: User) -> bool:
    """
    Проверяет, обладает ли пользователь правами диспетчера или администратора.

    Args:
        user: Объект пользователя Django.

    Returns:
        True, если пользователь аутентифицирован и является суперпользователем
        или имеет профиль с ролью 'dispatcher'.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        return user.profile.role == 'dispatcher'
    except UserProfile.DoesNotExist:
        return False


def is_driver(user: User) -> bool:
    """
    Проверяет, что пользователь имеет роль 'driver'.

    Args:
        user: Объект пользователя.

    Returns:
        True, если у пользователя есть профиль с ролью 'driver'.
    """
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == 'driver'
    except UserProfile.DoesNotExist:
        return False


def is_customer(user: User) -> bool:
    """
    Проверяет, что пользователь имеет роль 'customer'.

    Args:
        user: Объект пользователя.

    Returns:
        True, если у пользователя есть профиль с ролью 'customer'.
    """
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == 'customer'
    except UserProfile.DoesNotExist:
        return False


#  Примесь для доступа только диспетчеру и админу 
class DispatcherRequiredMixin(UserPassesTestMixin):
    """
    Миксин, ограничивающий доступ только диспетчерам и суперпользователям.
    Возвращает 403 при невыполнении условия.
    """

    def test_func(self) -> bool:
        return is_dispatcher(self.request.user)


#  Email-уведомления 
def send_status_email(order: Order, old_status: str, new_status: str) -> None:
    """
    Отправляет клиенту письмо об изменении статуса заказа.

    Письмо формируется только если у клиента заполнен email.
    Использует EmailMessage с кодировкой UTF-8.

    Args:
        order: Заказ, статус которого изменился.
        old_status: Предыдущий статус (код).
        new_status: Новый статус (код).
    """
    customer = order.customer
    if not customer.email:
        return
    subject = f"Статус заказа №{order.id} изменён"
    message = (
        f"Здравствуйте, {customer.name}!\n\n"
        f"Статус вашего заказа №{order.id} изменён:\n"
        f"Маршрут: {order.pickup_address} → {order.delivery_address}\n"
        f"Дата перевозки: {order.requested_date}\n"
        f"Предыдущий статус: {dict(Order.STATUS_CHOICES).get(old_status, old_status)}\n"
        f"Новый статус: {order.get_status_display()}\n\n"
        f"С уважением, Транспортная CRM"
    )
    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[customer.email],
    )
    email.encoding = 'utf-8'
    email.send(fail_silently=True)


#  Заказы 
class OrderListView(LoginRequiredMixin, DispatcherRequiredMixin, ListView):
    """Список заказов с поддержкой поиска и фильтрации по статусу."""

    model = Order
    template_name = 'crm/order_list.html'
    context_object_name = 'orders'
    paginate_by = 10

    def get_queryset(self) -> QuerySet:
        """Возвращает отфильтрованный QuerySet заказов."""
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(customer__name__icontains=query) |
                Q(pickup_address__icontains=query) |
                Q(delivery_address__icontains=query) |
                Q(cargo_description__icontains=query)
            )
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs) -> dict:
        """Добавляет в контекст перечень статусов и текущие параметры поиска."""
        context = super().get_context_data(**kwargs)
        context['statuses'] = Order.STATUS_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        context['query'] = self.request.GET.get('q', '')
        return context


class OrderDetailView(LoginRequiredMixin, DispatcherRequiredMixin, DetailView):
    """Детальный просмотр заказа с информацией о назначении и истории статусов."""

    model = Order
    template_name = 'crm/order_detail.html'

    def get_context_data(self, **kwargs) -> dict:
        """Добавляет в контекст назначение, историю статусов и ключ Яндекс.Карт."""
        context = super().get_context_data(**kwargs)
        context['assignment'] = Assignment.objects.filter(order=self.object).first()
        context['status_history'] = self.object.status_history.all()
        context['YANDEX_MAPS_KEY'] = settings.YANDEX_STATIC_API_KEY
        return context


class OrderCreateView(LoginRequiredMixin, DispatcherRequiredMixin, CreateView):
    """Создание нового заказа (доступно только диспетчеру)."""

    model = Order
    form_class = OrderForm
    template_name = 'crm/order_form.html'
    success_url = reverse_lazy('order_list')

    def form_valid(self, form: OrderForm) -> HttpResponse:
        messages.success(self.request, "Заказ успешно создан.")
        return super().form_valid(form)


class OrderUpdateView(LoginRequiredMixin, DispatcherRequiredMixin, UpdateView):
    """Редактирование заказа с фиксацией изменения статуса и отправкой уведомлений."""

    model = Order
    form_class = OrderForm
    template_name = 'crm/order_form.html'
    success_url = reverse_lazy('order_list')

    def form_valid(self, form: OrderForm) -> HttpResponse:
        old_status = self.model.objects.get(pk=self.object.pk).status
        new_status = form.cleaned_data['status']
        response = super().form_valid(form)
        if old_status != new_status:
            OrderStatusHistory.objects.create(
                order=self.object,
                old_status=old_status,
                new_status=new_status,
                changed_by=self.request.user
            )
            send_status_email(self.object, old_status, new_status)
        messages.success(self.request, "Заказ обновлён.")
        return response


class OrderDeleteView(LoginRequiredMixin, DispatcherRequiredMixin, DeleteView):
    """Удаление заказа."""

    model = Order
    template_name = 'crm/order_confirm_delete.html'
    success_url = reverse_lazy('order_list')

    def delete(self, request, *args, **kwargs) -> HttpResponse:
        messages.success(request, "Заказ удалён.")
        return super().delete(request, *args, **kwargs)


#  Назначение рейса
@login_required
@user_passes_test(is_dispatcher)
def assign_order(request: HttpRequest, order_id: int) -> HttpResponse:
    """
    Назначает водителя и автомобиль на заказ.

    При успешном назначении:
    - меняет статус заказа на 'assigned',
    - записывает изменение в историю,
    - отправляет email-уведомление клиенту,
    - при наличии telegram_id у водителя отправляет ему сообщение.

    Args:
        request: Объект запроса.
        order_id: Первичный ключ заказа.

    Returns:
        Редирект на страницу заказа или форму назначения при ошибке.
    """
    order = get_object_or_404(Order, pk=order_id)
    if Assignment.objects.filter(order=order).exists():
        messages.error(request, "Назначение для этого заказа уже существует.")
        return redirect('order_detail', pk=order.id)

    if request.method == 'POST':
        form = AssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.order = order
            try:
                assignment.save()
                order.status = 'assigned'
                order.save()
                OrderStatusHistory.objects.create(
                    order=order,
                    old_status='new',
                    new_status='assigned',
                    changed_by=request.user
                )
                send_status_email(order, 'new', 'assigned')

                # Telegram-уведомление
                if assignment.driver.telegram_id:
                    send_telegram_message(
                        assignment.driver.telegram_id,
                        f"Вам назначен рейс №{order.id}\n"
                        f"Маршрут: {order.pickup_address} → {order.delivery_address}\n"
                        f"Дата: {order.requested_date}"
                    )

                messages.success(request, "Рейс успешно назначен.")
                return redirect('order_detail', pk=order.id)
            except ValidationError as e:
                messages.error(request, f"Ошибка назначения: {e}")
    else:
        form = AssignmentForm()

    return render(request, 'crm/assign_form.html', {'form': form, 'order': order})


#  Изменение статуса водителем 
@login_required
@user_passes_test(is_driver)
def change_order_status(request: HttpRequest, assignment_id: int) -> HttpResponse:
    """
    Позволяет водителю изменить статус назначенного заказа.

    Допустимые переходы:
    - 'assigned' → 'in_transit'
    - 'in_transit' → 'completed'

    При изменении обновляется история статусов и отправляется email клиенту.

    Args:
        request: Объект запроса.
        assignment_id: Первичный ключ назначения.

    Returns:
        Редирект на дашборд водителя.
    """
    assignment = get_object_or_404(Assignment, pk=assignment_id, driver__user=request.user)
    order = assignment.order
    if request.method == 'POST':
        new_status = request.POST.get('new_status')
        if new_status in dict(Order.STATUS_CHOICES):
            old_status = order.status
            order.status = new_status
            order.save()
            OrderStatusHistory.objects.create(
                order=order,
                old_status=old_status,
                new_status=new_status,
                changed_by=request.user
            )
            send_status_email(order, old_status, new_status)
            messages.success(request, "Статус обновлён.")
        else:
            messages.error(request, "Недопустимый статус.")
    return redirect('driver_dashboard')


# Клиенты 
class CustomerListView(LoginRequiredMixin, DispatcherRequiredMixin, ListView):
    """Список всех клиентов (для диспетчера)."""
    model = Customer
    template_name = 'crm/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 10


class CustomerDetailView(LoginRequiredMixin, DispatcherRequiredMixin, DetailView):
    """Детальная информация о клиенте."""
    model = Customer
    template_name = 'crm/customer_detail.html'


class CustomerCreateView(LoginRequiredMixin, DispatcherRequiredMixin, CreateView):
    """Добавление нового клиента."""
    model = Customer
    form_class = CustomerForm          # ← заменили fields на form_class
    template_name = 'crm/customer_form.html'
    success_url = reverse_lazy('customer_list')


class CustomerUpdateView(LoginRequiredMixin, DispatcherRequiredMixin, UpdateView):
    """Редактирование данных клиента."""
    model = Customer
    form_class = CustomerForm          # ← заменили fields на form_class
    template_name = 'crm/customer_form.html'
    success_url = reverse_lazy('customer_list')


class CustomerDeleteView(LoginRequiredMixin, DispatcherRequiredMixin, DeleteView):
    """Удаление клиента."""
    model = Customer
    template_name = 'crm/customer_confirm_delete.html'
    success_url = reverse_lazy('customer_list')


#  Водители 
class DriverListView(LoginRequiredMixin, DispatcherRequiredMixin, ListView):
    """Список водителей."""
    model = Driver
    template_name = 'crm/driver_list.html'
    context_object_name = 'drivers'
    paginate_by = 10


class DriverDetailView(LoginRequiredMixin, DispatcherRequiredMixin, DetailView):
    """Детальная информация о водителе."""
    model = Driver
    template_name = 'crm/driver_detail.html'


class DriverCreateView(LoginRequiredMixin, DispatcherRequiredMixin, CreateView):
    """Добавление нового водителя."""
    model = Driver
    form_class = DriverForm
    template_name = 'crm/driver_form.html'
    success_url = reverse_lazy('driver_list')


class DriverUpdateView(LoginRequiredMixin, DispatcherRequiredMixin, UpdateView):
    """Редактирование профиля водителя."""
    model = Driver
    form_class = DriverForm
    template_name = 'crm/driver_form.html'
    success_url = reverse_lazy('driver_list')


class DriverDeleteView(LoginRequiredMixin, DispatcherRequiredMixin, DeleteView):
    """Удаление водителя."""
    model = Driver
    template_name = 'crm/driver_confirm_delete.html'
    success_url = reverse_lazy('driver_list')


#  Автомобили 
class VehicleListView(LoginRequiredMixin, DispatcherRequiredMixin, ListView):
    """Список автомобилей."""
    model = Vehicle
    template_name = 'crm/vehicle_list.html'
    context_object_name = 'vehicles'
    paginate_by = 10


class VehicleDetailView(LoginRequiredMixin, DispatcherRequiredMixin, DetailView):
    """Детальная информация об автомобиле."""
    model = Vehicle
    template_name = 'crm/vehicle_detail.html'


class VehicleCreateView(LoginRequiredMixin, DispatcherRequiredMixin, CreateView):
    """Добавление нового автомобиля."""
    model = Vehicle
    form_class = VehicleForm          # ← заменили fields на form_class
    template_name = 'crm/vehicle_form.html'
    success_url = reverse_lazy('vehicle_list')


class VehicleUpdateView(LoginRequiredMixin, DispatcherRequiredMixin, UpdateView):
    """Редактирование автомобиля."""
    model = Vehicle
    form_class = VehicleForm          # ← заменили fields на form_class
    template_name = 'crm/vehicle_form.html'
    success_url = reverse_lazy('vehicle_list')


class VehicleDeleteView(LoginRequiredMixin, DispatcherRequiredMixin, DeleteView):
    """Удаление автомобиля."""
    model = Vehicle
    template_name = 'crm/vehicle_confirm_delete.html'
    success_url = reverse_lazy('vehicle_list')


#  Назначения 
class AssignmentListView(LoginRequiredMixin, DispatcherRequiredMixin, ListView):
    """Список всех назначений (рейсов)."""
    model = Assignment
    template_name = 'crm/assignment_list.html'
    context_object_name = 'assignments'
    paginate_by = 10


# Платежи
class PaymentListView(LoginRequiredMixin, DispatcherRequiredMixin, ListView):
    """Список всех платежей."""
    model = Payment
    template_name = 'crm/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 10


class PaymentDetailView(LoginRequiredMixin, DispatcherRequiredMixin, DetailView):
    """Детали конкретного платежа."""
    model = Payment
    template_name = 'crm/payment_detail.html'
    context_object_name = 'payment'


class PaymentCreateView(LoginRequiredMixin, DispatcherRequiredMixin, CreateView):
    """Добавление нового платежа (диспетчером)."""
    model = Payment
    form_class = PaymentForm          # ← заменили fields на form_class
    template_name = 'crm/payment_form.html'
    success_url = reverse_lazy('payment_list')

    def form_valid(self, form):
        messages.success(self.request, "Платёж добавлен.")
        return super().form_valid(form)


class PaymentUpdateView(LoginRequiredMixin, DispatcherRequiredMixin, UpdateView):
    """Редактирование платежа."""
    model = Payment
    form_class = PaymentForm          # ← заменили fields на form_class
    template_name = 'crm/payment_form.html'
    success_url = reverse_lazy('payment_list')

    def form_valid(self, form):
        messages.success(self.request, "Платёж обновлён.")
        return super().form_valid(form)


class PaymentDeleteView(LoginRequiredMixin, DispatcherRequiredMixin, DeleteView):
    """Удаление платежа."""
    model = Payment
    template_name = 'crm/payment_confirm_delete.html'
    success_url = reverse_lazy('payment_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Платёж удалён.")
        return super().delete(request, *args, **kwargs)


#  Аутентификация
def signup_view(request: HttpRequest) -> HttpResponse:
    """
    Регистрация нового пользователя с выбором роли.

    При успешной регистрации автоматически создаётся UserProfile,
    а также связанная запись Customer или Driver в зависимости от выбранной роли.
    """
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            role = form.cleaned_data['role']
            UserProfile.objects.create(user=user, role=role)
            if role == 'customer':
                Customer.objects.create(user=user, name=user.username, phone='')
            elif role == 'driver':
                Driver.objects.create(user=user, first_name='', last_name='', phone='', license_number='')
            login(request, user)
            return redirect('dashboard')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})


def logout_view(request: HttpRequest) -> HttpResponse:
    """Завершает сессию пользователя и перенаправляет на страницу входа."""
    logout(request)
    return redirect('login')


# Личный кабинет
@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """
    Центральный маршрутизатор: перенаправляет пользователя в кабинет,
    соответствующий его роли.
    """
    if is_dispatcher(request.user):
        return redirect('dispatcher_dashboard')
    elif is_driver(request.user):
        return redirect('driver_dashboard')
    else:
        return redirect('customer_dashboard')


@login_required
@user_passes_test(is_dispatcher)
def dispatcher_dashboard(request: HttpRequest) -> HttpResponse:
    """
    Панель диспетчера: показывает последние 10 заказов
    и предоставляет быстрый доступ к основным разделам.
    """
    orders = Order.objects.all().order_by('-created_at')[:10]
    return render(request, 'crm/dispatcher_dashboard.html', {'orders': orders})


@login_required
@user_passes_test(is_driver)
def driver_dashboard(request: HttpRequest) -> HttpResponse:
    """
    Кабинет водителя: список назначенных рейсов
    с возможностью изменить статус заказа.
    """
    assignments = Assignment.objects.filter(
        driver__user=request.user
    ).select_related('order').order_by('-assigned_at')
    return render(request, 'crm/driver_dashboard.html', {'assignments': assignments})


@login_required
@user_passes_test(is_customer)
def customer_dashboard(request: HttpRequest) -> HttpResponse:
    """
    Кабинет клиента: список своих заказов с возможностью просмотра деталей
    и оплаты выполненных заказов.
    """
    orders = Order.objects.filter(customer__user=request.user).order_by('-created_at')
    return render(request, 'crm/customer_dashboard.html', {'orders': orders})


# Оплата заказа клиентом
@login_required
@user_passes_test(is_customer)
def customer_pay_order(request: HttpRequest, order_id: int) -> HttpResponse:
    """
    Отмечает заказ как оплаченный: создаёт запись Payment на сумму заказа.
    Доступно только для выполненных заказов.
    """
    order = get_object_or_404(Order, pk=order_id, customer__user=request.user)
    if order.status != 'completed':
        messages.error(request, "Заказ ещё не выполнен, оплата невозможна.")
        return redirect('customer_dashboard')
    if Payment.objects.filter(order=order).exists():
        messages.warning(request, "Заказ уже оплачен.")
        return redirect('customer_dashboard')

    Payment.objects.create(
        order=order,
        amount=order.price or 0,
        paid_at=timezone.now().date(),
        method='transfer'
    )
    messages.success(request, f"Заказ №{order.id} оплачен. Спасибо!")
    return redirect('customer_dashboard')


# Детали заказа для клиента
@login_required
@user_passes_test(is_customer)
def customer_order_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Показывает клиенту детали его собственного заказа.
    Не требует прав диспетчера.
    """
    order = get_object_or_404(Order, pk=pk, customer__user=request.user)
    return render(request, 'crm/customer_order_detail.html', {'order': order})


# Аналитика и отчёты 
@login_required
@user_passes_test(is_dispatcher)
def analytics_dashboard(request: HttpRequest) -> HttpResponse:
    """
    Дашборд аналитики с четырьмя графиками:
    - Выручка по месяцам
    - Топ-5 клиентов
    - Загрузка водителей
    - Распределение статусов заказов
    """
    context = {
        'revenue_chart': _generate_revenue_chart(),
        'top_clients_chart': _generate_top_clients_chart(),
        'drivers_load_chart': _generate_drivers_load_chart(),
        'status_distribution_chart': _generate_status_distribution_chart(),
    }
    return render(request, 'crm/analytics_dashboard.html', context)


def _generate_revenue_chart() -> str | None:
    """
    Строит линейный график выручки по месяцам на основе выполненных заказов.

    Returns:
        data:image/png;base64-строка или None, если данных недостаточно.
    """
    orders = Order.objects.filter(status='completed')
    df = pd.DataFrame(list(orders.values('created_at', 'price')))
    if df.empty:
        return None
    df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0)
    df['month'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m')
    monthly = df.groupby('month')['price'].sum()
    if monthly.empty or monthly.sum() == 0:
        return None
    plt.figure(figsize=(8, 4))
    monthly.plot(kind='line', marker='o', color='green')
    plt.title('Выручка по месяцам')
    plt.ylabel('Сумма, руб.')
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    return _fig_to_base64()


def _generate_top_clients_chart() -> str | None:
    """
    Строит горизонтальную столбчатую диаграмму топ-5 клиентов по числу заказов.

    Returns:
        data:image/png;base64-строка или None.
    """
    top_clients = Order.objects.values('customer__name').annotate(
        total=Count('id')
    ).order_by('-total')[:5]
    df = pd.DataFrame(list(top_clients))
    if df.empty or df['total'].sum() == 0:
        return None
    plt.figure(figsize=(8, 4))
    plt.barh(df['customer__name'], df['total'], color='orange')
    plt.title('Топ-5 клиентов по числу заказов')
    plt.xlabel('Количество заказов')
    plt.tight_layout()
    return _fig_to_base64()


def _generate_drivers_load_chart() -> str | None:
    """
    Круговая диаграмма загрузки водителей (по выполненным и активным рейсам).

    Returns:
        data:image/png;base64-строка или None.
    """
    drivers_load = Assignment.objects.filter(
        order__status__in=['completed', 'in_transit']
    ).values('driver__last_name', 'driver__first_name').annotate(
        total=Count('id')
    ).order_by('-total')
    df = pd.DataFrame(list(drivers_load))
    if df.empty or df['total'].sum() == 0:
        return None
    df['label'] = df['driver__last_name'] + ' ' + df['driver__first_name']
    plt.figure(figsize=(6, 6))
    plt.pie(df['total'], labels=df['label'], autopct='%1.1f%%', startangle=90)
    plt.title('Загрузка водителей')
    plt.tight_layout()
    return _fig_to_base64()


def _generate_status_distribution_chart() -> str | None:
    """
    Круговая диаграмма распределения заказов по статусам.

    Returns:
        data:image/png;base64-строка или None.
    """
    statuses = Order.objects.values('status').annotate(total=Count('id'))
    df = pd.DataFrame(list(statuses))
    if df.empty or df['total'].sum() == 0:
        return None
    status_map = dict(Order.STATUS_CHOICES)
    df['status_name'] = df['status'].map(status_map)
    plt.figure(figsize=(6, 6))
    plt.pie(df['total'], labels=df['status_name'], autopct='%1.1f%%', startangle=90)
    plt.title('Распределение заказов по статусам')
    plt.tight_layout()
    return _fig_to_base64()


def _fig_to_base64() -> str:
    """
    Сохраняет текущую фигуру matplotlib в байтовый буфер и возвращает
    data-URL изображения PNG в кодировке base64.
    """
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    buf.seek(0)
    image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return f'data:image/png;base64,{image_base64}'


@login_required
@user_passes_test(is_dispatcher)
def download_report(request: HttpRequest, report_type: str) -> HttpResponse:
    """
    Генерирует Excel-отчёт по заказам, клиентам или водителям.

    Args:
        request: Объект запроса.
        report_type: Тип отчёта ('orders', 'customers', 'drivers').

    Returns:
        HttpResponse с файлом Excel, либо ошибку 400 при неверном типе.
    """
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report.xlsx"'

    if report_type == 'orders':
        data = Order.objects.all().values()
    elif report_type == 'customers':
        data = Customer.objects.all().values()
    elif report_type == 'drivers':
        data = Driver.objects.all().values()
    else:
        return HttpResponse('Неверный тип отчёта', status=400)

    df = pd.DataFrame(list(data))
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)

    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=report_type)

    return response


# Экспорт документов
@login_required
@user_passes_test(is_dispatcher)
def download_document(request: HttpRequest, pk: int, doc_type: str) -> HttpResponse:
    """
    Скачивание первичного документа (путевой лист, счёт, акт) для заказа.

    Args:
        request: Объект запроса.
        pk: Первичный ключ заказа.
        doc_type: Тип документа ('waybill', 'invoice', 'act').

    Returns:
        HttpResponse с файлом Excel или ошибку 400 при неверном типе.
    """
    order = get_object_or_404(Order, pk=pk)
    if doc_type == 'waybill':
        return documents.generate_waybill(order)
    elif doc_type == 'invoice':
        return documents.generate_invoice(order)
    elif doc_type == 'act':
        return documents.generate_act(order)
    else:
        return HttpResponse('Неверный тип документа', status=400)