import io
import urllib.parse
import matplotlib
matplotlib.use('Agg')  # Бэкенд без GUI
import matplotlib.pyplot as plt
import pandas as pd
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta
from .models import Customer, Driver, Vehicle, Order, Assignment, Payment, UserProfile, OrderStatusHistory
from .forms import OrderForm, SignUpForm, AssignmentForm

# ---------- Вспомогательные функции проверки ролей ----------
def is_dispatcher(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        return user.profile.role == 'dispatcher'
    except UserProfile.DoesNotExist:
        return False

def is_driver(user):
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == 'driver'
    except UserProfile.DoesNotExist:
        return False

def is_customer(user):
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == 'customer'
    except UserProfile.DoesNotExist:
        return False

# ---------- Примесь для доступа только диспетчеру и админу ----------
class DispatcherRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return is_dispatcher(self.request.user)

# ---------- Заказы ----------
class OrderListView(LoginRequiredMixin, DispatcherRequiredMixin, ListView):
    model = Order
    template_name = 'crm/order_list.html'
    context_object_name = 'orders'
    paginate_by = 10

    def get_queryset(self):
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuses'] = Order.STATUS_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        context['query'] = self.request.GET.get('q', '')
        return context

class OrderDetailView(LoginRequiredMixin, DispatcherRequiredMixin, DetailView):
    model = Order
    template_name = 'crm/order_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['assignment'] = Assignment.objects.filter(order=self.object).first()
        context['status_history'] = self.object.status_history.all()
        context['YANDEX_MAPS_KEY'] = settings.YANDEX_STATIC_API_KEY
        return context

class OrderCreateView(LoginRequiredMixin, DispatcherRequiredMixin, CreateView):
    model = Order
    form_class = OrderForm
    template_name = 'crm/order_form.html'
    success_url = reverse_lazy('order_list')

    def form_valid(self, form):
        messages.success(self.request, "Заказ успешно создан.")
        return super().form_valid(form)

class OrderUpdateView(LoginRequiredMixin, DispatcherRequiredMixin, UpdateView):
    model = Order
    form_class = OrderForm
    template_name = 'crm/order_form.html'
    success_url = reverse_lazy('order_list')

    def form_valid(self, form):
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
        messages.success(self.request, "Заказ обновлён.")
        return response

class OrderDeleteView(LoginRequiredMixin, DispatcherRequiredMixin, DeleteView):
    model = Order
    template_name = 'crm/order_confirm_delete.html'
    success_url = reverse_lazy('order_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Заказ удалён.")
        return super().delete(request, *args, **kwargs)

# ---------- Назначение рейса ----------
@login_required
@user_passes_test(is_dispatcher)
def assign_order(request, order_id):
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
                messages.success(request, "Рейс успешно назначен.")
                return redirect('order_detail', pk=order.id)
            except ValidationError as e:
                messages.error(request, f"Ошибка назначения: {e}")
    else:
        form = AssignmentForm()

    return render(request, 'crm/assign_form.html', {'form': form, 'order': order})

# ---------- Изменение статуса водителем ----------
@login_required
@user_passes_test(is_driver)
def change_order_status(request, assignment_id):
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
            messages.success(request, "Статус обновлён.")
        else:
            messages.error(request, "Недопустимый статус.")
    return redirect('driver_dashboard')

# ---------- Клиенты ----------
class CustomerListView(LoginRequiredMixin, DispatcherRequiredMixin, ListView):
    model = Customer
    template_name = 'crm/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 10

class CustomerDetailView(LoginRequiredMixin, DispatcherRequiredMixin, DetailView):
    model = Customer
    template_name = 'crm/customer_detail.html'

class CustomerCreateView(LoginRequiredMixin, DispatcherRequiredMixin, CreateView):
    model = Customer
    fields = ['name', 'phone', 'email', 'address']
    template_name = 'crm/customer_form.html'
    success_url = reverse_lazy('customer_list')

class CustomerUpdateView(LoginRequiredMixin, DispatcherRequiredMixin, UpdateView):
    model = Customer
    fields = ['name', 'phone', 'email', 'address']
    template_name = 'crm/customer_form.html'
    success_url = reverse_lazy('customer_list')

class CustomerDeleteView(LoginRequiredMixin, DispatcherRequiredMixin, DeleteView):
    model = Customer
    template_name = 'crm/customer_confirm_delete.html'
    success_url = reverse_lazy('customer_list')

# ---------- Водители ----------
class DriverListView(LoginRequiredMixin, DispatcherRequiredMixin, ListView):
    model = Driver
    template_name = 'crm/driver_list.html'
    context_object_name = 'drivers'
    paginate_by = 10

class DriverDetailView(LoginRequiredMixin, DispatcherRequiredMixin, DetailView):
    model = Driver
    template_name = 'crm/driver_detail.html'

class DriverCreateView(LoginRequiredMixin, DispatcherRequiredMixin, CreateView):
    model = Driver
    fields = ['first_name', 'last_name', 'phone', 'license_number', 'hire_date']
    template_name = 'crm/driver_form.html'
    success_url = reverse_lazy('driver_list')

class DriverUpdateView(LoginRequiredMixin, DispatcherRequiredMixin, UpdateView):
    model = Driver
    fields = ['first_name', 'last_name', 'phone', 'license_number', 'hire_date']
    template_name = 'crm/driver_form.html'
    success_url = reverse_lazy('driver_list')

class DriverDeleteView(LoginRequiredMixin, DispatcherRequiredMixin, DeleteView):
    model = Driver
    template_name = 'crm/driver_confirm_delete.html'
    success_url = reverse_lazy('driver_list')

# ---------- Автомобили ----------
class VehicleListView(LoginRequiredMixin, DispatcherRequiredMixin, ListView):
    model = Vehicle
    template_name = 'crm/vehicle_list.html'
    context_object_name = 'vehicles'
    paginate_by = 10

class VehicleDetailView(LoginRequiredMixin, DispatcherRequiredMixin, DetailView):
    model = Vehicle
    template_name = 'crm/vehicle_detail.html'

class VehicleCreateView(LoginRequiredMixin, DispatcherRequiredMixin, CreateView):
    model = Vehicle
    fields = ['plate_number', 'brand', 'model', 'capacity_ton', 'is_active']
    template_name = 'crm/vehicle_form.html'
    success_url = reverse_lazy('vehicle_list')

class VehicleUpdateView(LoginRequiredMixin, DispatcherRequiredMixin, UpdateView):
    model = Vehicle
    fields = ['plate_number', 'brand', 'model', 'capacity_ton', 'is_active']
    template_name = 'crm/vehicle_form.html'
    success_url = reverse_lazy('vehicle_list')

class VehicleDeleteView(LoginRequiredMixin, DispatcherRequiredMixin, DeleteView):
    model = Vehicle
    template_name = 'crm/vehicle_confirm_delete.html'
    success_url = reverse_lazy('vehicle_list')

# ---------- Назначения ----------
class AssignmentListView(LoginRequiredMixin, DispatcherRequiredMixin, ListView):
    model = Assignment
    template_name = 'crm/assignment_list.html'
    context_object_name = 'assignments'
    paginate_by = 10

# ---------- Платежи ----------
class PaymentListView(LoginRequiredMixin, DispatcherRequiredMixin, ListView):
    model = Payment
    template_name = 'crm/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 10

# ---------- Аутентификация ----------
def signup_view(request):
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

def logout_view(request):
    logout(request)
    return redirect('login')

# ---------- Личный кабинет ----------
@login_required
def dashboard(request):
    if is_dispatcher(request.user):
        return redirect('dispatcher_dashboard')
    elif is_driver(request.user):
        return redirect('driver_dashboard')
    else:
        return redirect('customer_dashboard')

@login_required
@user_passes_test(is_dispatcher)
def dispatcher_dashboard(request):
    orders = Order.objects.all().order_by('-created_at')[:10]
    return render(request, 'crm/dispatcher_dashboard.html', {'orders': orders})

@login_required
@user_passes_test(is_driver)
def driver_dashboard(request):
    assignments = Assignment.objects.filter(driver__user=request.user).select_related('order').order_by('-assigned_at')
    return render(request, 'crm/driver_dashboard.html', {'assignments': assignments})

@login_required
@user_passes_test(is_customer)
def customer_dashboard(request):
    orders = Order.objects.filter(customer__user=request.user).order_by('-created_at')
    return render(request, 'crm/customer_dashboard.html', {'orders': orders})

# ---------- Аналитика и отчёты ----------
@login_required
@user_passes_test(is_dispatcher)
def analytics_dashboard(request):
    """Главная страница аналитики с отчётами."""
    context = {
        'revenue_chart': _generate_revenue_chart(),
        'top_clients_chart': _generate_top_clients_chart(),
        'drivers_load_chart': _generate_drivers_load_chart(),
        'status_distribution_chart': _generate_status_distribution_chart(),
    }
    return render(request, 'crm/analytics_dashboard.html', context)

def _generate_revenue_chart():
    """Выручка по месяцам (линейный график)."""
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

def _generate_top_clients_chart():
    """Топ-5 клиентов по количеству заказов (горизонтальная столбчатая диаграмма)."""
    top_clients = Order.objects.values('customer__name').annotate(total=Count('id')).order_by('-total')[:5]
    df = pd.DataFrame(list(top_clients))
    if df.empty or df['total'].sum() == 0:
        return None
    plt.figure(figsize=(8, 4))
    plt.barh(df['customer__name'], df['total'], color='orange')
    plt.title('Топ-5 клиентов по числу заказов')
    plt.xlabel('Количество заказов')
    plt.tight_layout()
    return _fig_to_base64()

def _generate_drivers_load_chart():
    """Загрузка водителей (круговая диаграмма)."""
    drivers_load = Assignment.objects.filter(order__status__in=['completed', 'in_transit']) \
                                     .values('driver__last_name', 'driver__first_name') \
                                     .annotate(total=Count('id')).order_by('-total')
    df = pd.DataFrame(list(drivers_load))
    if df.empty or df['total'].sum() == 0:
        return None
    df['label'] = df['driver__last_name'] + ' ' + df['driver__first_name']
    plt.figure(figsize=(6, 6))
    plt.pie(df['total'], labels=df['label'], autopct='%1.1f%%', startangle=90)
    plt.title('Загрузка водителей')
    plt.tight_layout()
    return _fig_to_base64()

def _generate_status_distribution_chart():
    """Распределение заказов по статусам (круговая диаграмма)."""
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

def _fig_to_base64():
    """Сохраняет текущую фигуру matplotlib в base64 строку."""
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    buf.seek(0)
    image_base64 = urllib.parse.quote(buf.getvalue().hex(), safe='')
    return f'data:image/png;base64,{image_base64}'

@login_required
@user_passes_test(is_dispatcher)
def download_report(request, report_type):
    """Генерация и скачивание отчёта в Excel."""
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
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

    # Преобразуем все datetime-столбцы, удаляя информацию о часовом поясе
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)

    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=report_type)

    return response