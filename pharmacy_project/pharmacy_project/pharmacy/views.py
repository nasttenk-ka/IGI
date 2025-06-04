from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import ExtractMonth
from django.http import JsonResponse
from statistics import mean, median, mode
from collections import Counter
from .models import *
from .forms import *
from django.contrib import messages
from .utils.api_utils import NewsAPI
import logging
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use Agg backend
import io
import base64
from datetime import date
import numpy as np

# Configure loggers
logger = logging.getLogger('pharmacy')
auth_logger = logging.getLogger('pharmacy.auth')
security_logger = logging.getLogger('pharmacy.security')
orders_logger = logging.getLogger('pharmacy.orders')

def is_customer(user):
    return user.user_type == 'C'

def is_employee(user):
    return user.user_type == 'E'

def home(request):
    medications = Medication.objects.all()
    
    # Search functionality
    search_query = request.GET.get('search', '')
    search_field = request.GET.get('search_field', 'name')
    
    if search_query:
        if search_field == 'name':
            medications = medications.filter(name__icontains=search_query)
        elif search_field == 'description':
            medications = medications.filter(description__icontains=search_query)
        elif search_field == 'price_min':
            try:
                medications = medications.filter(price__gte=float(search_query))
            except ValueError:
                pass
        elif search_field == 'price_max':
            try:
                medications = medications.filter(price__lte=float(search_query))
            except ValueError:
                pass
        elif search_field == 'department':
            medications = medications.filter(department__name__icontains=search_query)
        elif search_field == 'supplier':
            medications = medications.filter(supplier__name__icontains=search_query)
    
    # Sorting functionality
    sort_by = request.GET.get('sort_by', 'name')
    sort_order = request.GET.get('sort_order', 'asc')
    
    if sort_by in ['name', 'price', 'stock']:
        sort_field = sort_by
        if sort_order == 'desc':
            sort_field = f'-{sort_field}'
        medications = medications.order_by(sort_field)
    elif sort_by == 'department':
        sort_field = 'department__name'
        if sort_order == 'desc':
            sort_field = f'-{sort_field}'
        medications = medications.order_by(sort_field)
    elif sort_by == 'supplier':
        sort_field = 'supplier__name'
        if sort_order == 'desc':
            sort_field = f'-{sort_field}'
        medications = medications.order_by(sort_field)

    # Get unique departments and suppliers for search filters
    departments = Department.objects.values_list('name', flat=True).distinct()
    suppliers = Supplier.objects.values_list('name', flat=True).distinct()

    context = {
        'medications': medications,
        'search_query': search_query,
        'search_field': search_field,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'departments': departments,
        'suppliers': suppliers,
    }
    
    return render(request, 'pharmacy/home.html', context)

@login_required
def profile(request):
    if request.user.user_type == 'C':
        orders = CustomerOrder.objects.filter(customer=request.user)
        # Получаем активные промокоды
        active_promos = PromoCode.objects.filter(is_active=True, is_archived=False)
        # Получаем статистику заказов пользователя
        total_orders = orders.count()
        total_spent = orders.filter(paid=True).aggregate(total=Sum('total_price'))['total'] or 0
        avg_order = total_spent / total_orders if total_orders > 0 else 0
        
        context = {
            'orders': orders,
            'active_promos': active_promos,
            'user_info': {
                'full_name': f"{request.user.last_name} {request.user.first_name}",
                'email': request.user.email,
                'phone': request.user.phone,
                'date_of_birth': request.user.date_of_birth,
                'registration_date': request.user.date_joined
            },
            'stats': {
                'total_orders': total_orders,
                'total_spent': total_spent,
                'avg_order': avg_order
            }
        }
        return render(request, 'pharmacy/customer_profile.html', context)
    else:
        # Для сотрудника
        sales = Sale.objects.all()
        # Получаем статистику продаж сотрудника
        total_sales = sales.count()
        total_revenue = sales.aggregate(total=Sum('total_amount'))['total'] or 0
        avg_sale = total_revenue / total_sales if total_sales > 0 else 0
        
        # Получаем последние продажи
        recent_sales = sales.order_by('-sale_date')[:10]
        
        # Получаем список поставщиков
        suppliers = Supplier.objects.filter(is_active=True)
        
        context = {
            'sales': recent_sales,
            'suppliers': suppliers,
            'user_info': {
                'full_name': f"{request.user.last_name} {request.user.first_name}",
                'email': request.user.email,
                'phone': request.user.phone,
                'position': request.user.get_position_display() if hasattr(request.user, 'position') else 'Сотрудник',
                'department': request.user.department.name if hasattr(request.user, 'department') else 'Общий',
                'date_joined': request.user.date_joined
            },
            'stats': {
                'total_sales': total_sales,
                'total_revenue': total_revenue,
                'avg_sale': avg_sale
            }
        }
        return render(request, 'pharmacy/employee_profile.html', context)

@login_required
@user_passes_test(is_customer)
def create_order(request):
    initial = {}
    pickup_point_id = request.GET.get('pickup_point')
    if pickup_point_id:
        try:
            pickup_point = PickupPoint.objects.get(id=pickup_point_id, is_active=True)
            initial['pickup_point'] = pickup_point
        except PickupPoint.DoesNotExist:
            pass

    if request.method == 'POST':
        form = OrderForm(request.POST, user=request.user)
        if form.is_valid():
            order = form.save()
            return redirect('pharmacy:order_detail', pk=order.pk)
    else:
        form = OrderForm(user=request.user, initial=initial)
    return render(request, 'pharmacy/create_order.html', {'form': form})

def about(request):
    company_info = CompanyInfo.objects.filter(is_active=True).first()
    history = CompanyHistory.objects.filter(is_active=True).order_by('year')
    requisites = CompanyRequisite.objects.filter(is_active=True)
    return render(request, 'pharmacy/about.html', {
        'company_info': company_info,
        'history': history,
        'requisites': requisites
    })

def news(request):
    """Display pharmacy and healthcare news"""
    news_data = NewsAPI.get_pharmacy_news()
    
    context = {
        'title': 'Новости',
        'articles': news_data.get('articles', [])
    }
    return render(request, 'pharmacy/news.html', context)

def faq(request):
    questions = FAQ.objects.filter(is_active=True)
    return render(request, 'pharmacy/faq.html', {'questions': questions})

def contacts(request):
    employees = Employee.objects.filter(is_active=True).order_by('order', 'name')
    
    # Группируем сотрудников по отделам для удобного отображения
    departments = {}
    for employee in employees:
        if employee.department not in departments:
            departments[employee.department] = []
        departments[employee.department].append(employee)
    
    return render(request, 'pharmacy/contacts.html', {
        'employees': employees,
        'departments': departments
    })

def privacy_policy(request):
    return render(request, 'pharmacy/privacy_policy.html')

def vacancies(request):
    vacancies_list = Vacancy.objects.filter(is_active=True)
    
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, 'Для отклика на вакансию необходимо авторизоваться')
            return redirect('pharmacy:login')
        
        form = VacancyApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                vacancy_id = request.POST.get('vacancy_id')
                vacancy = get_object_or_404(Vacancy, id=vacancy_id, is_active=True)
                
                # Проверяем, не откликался ли пользователь уже на эту вакансию
                if VacancyApplication.objects.filter(user=request.user, vacancy=vacancy).exists():
                    messages.error(request, 'Вы уже откликнулись на эту вакансию')
                    return redirect('pharmacy:vacancies')
                
                application = form.save(commit=False)
                application.user = request.user
                application.vacancy = vacancy
                application.save()
                
                messages.success(request, 'Ваш отклик успешно отправлен!')
                return redirect('pharmacy:vacancies')
            except Vacancy.DoesNotExist:
                messages.error(request, 'Вакансия не найдена')
                return redirect('pharmacy:vacancies')
    else:
        form = VacancyApplicationForm()
        if request.user.is_authenticated:
            # Предзаполняем форму данными пользователя
            form = VacancyApplicationForm(initial={
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
                'phone': request.user.phone,
            })
    
    # Получаем список вакансий, на которые пользователь уже откликнулся
    user_applications = []
    if request.user.is_authenticated:
        user_applications = VacancyApplication.objects.filter(
            user=request.user
        ).values_list('vacancy_id', flat=True)
    
    context = {
        'vacancies': vacancies_list,
        'form': form,
        'user_applications': user_applications,
    }
    
    return render(request, 'pharmacy/vacancies.html', context)

@login_required
def edit_review(request):
    try:
        review = Review.objects.get(user=request.user)
        if request.method == 'POST':
            form = ReviewForm(request.POST, instance=review)
            if form.is_valid():
                form.save()
                messages.success(request, 'Ваш отзыв успешно обновлен!')
                return redirect('pharmacy:reviews')
        else:
            form = ReviewForm(instance=review)
        return render(request, 'pharmacy/edit_review.html', {'form': form})
    except Review.DoesNotExist:
        messages.error(request, 'У вас нет отзыва для редактирования')
        return redirect('pharmacy:reviews')

def reviews(request):
    reviews_list = Review.objects.filter(is_active=True,  user__isnull=False).select_related('user').order_by('-created_at')
    
    # Проверяем, является ли пользователь клиентом
    is_customer = request.user.is_authenticated and request.user.user_type == 'C'
    user_has_review = request.user.is_authenticated and Review.objects.filter(user=request.user).exists()
    
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, 'Для добавления отзыва необходимо авторизоваться')
            return redirect('pharmacy:login')
        
        if not is_customer:
            messages.error(request, 'Только клиенты могут оставлять отзывы')
            return redirect('pharmacy:reviews')
        
        if user_has_review:
            messages.error(request, 'Вы уже оставили отзыв. Вы можете отредактировать существующий отзыв.')
            return redirect('pharmacy:reviews')
        
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.save()
            messages.success(request, 'Спасибо за ваш отзыв!')
            return redirect('pharmacy:reviews')
    else:
        form = ReviewForm()
    
    # Calculate average rating
    avg_rating = reviews_list.aggregate(Avg('rating'))['rating__avg'] or 0
    
    # Group reviews by rating for statistics
    rating_stats = reviews_list.values('rating').annotate(
        count=Count('rating')
    ).order_by('-rating')
    
    # Calculate total reviews count
    total_reviews = reviews_list.count()
    
    # Calculate percentage for each rating
    for stat in rating_stats:
        stat['percentage'] = (stat['count'] / total_reviews * 100) if total_reviews > 0 else 0
    
    context = {
        'reviews': reviews_list,
        'form': form if is_customer and not user_has_review else None,
        'user_has_review': user_has_review,
        'avg_rating': round(avg_rating, 1),
        'rating_stats': rating_stats,
        'total_reviews': total_reviews,
        'is_customer': is_customer,
    }
    
    return render(request, 'pharmacy/reviews.html', context)

def promocodes(request):
    active_promocodes = PromoCode.objects.filter(is_active=True, is_archived=False)
    archived_promocodes = PromoCode.objects.filter(is_active=True, is_archived=True)
    return render(request, 'pharmacy/promocodes.html', {
        'active_promocodes': active_promocodes,
        'archived_promocodes': archived_promocodes
    })

# Ваши предыдущие представления для продуктов

def product_list(request, category_slug=None):
    category = None
    categories = Category.objects.all()
    products = Product.objects.filter(available=True)
    
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
    
    return render(request, 'pharmacy/product/list.html',
                 {'category': category,
                  'categories': categories,
                  'products': products})

def product_detail(request, id, slug):
    product = get_object_or_404(Product, id=id, slug=slug, available=True)
    return render(request, 'pharmacy/product/detail.html', {'product': product})

from .forms import RegistrationForm  # Импортируем вашу форму


def login_view(request):
    auth_logger.info(f"Login attempt from IP: {request.META.get('REMOTE_ADDR')}")
    
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            auth_logger.info(f"User {username} logged in successfully")
            return redirect('pharmacy:profile')
        else:
            auth_logger.warning(f"Failed login attempt for username: {username}")
            security_logger.warning(f"Failed login attempt from IP: {request.META.get('REMOTE_ADDR')} for user: {username}")
            return render(request, 'pharmacy/login.html', {'error': 'Invalid credentials'})
    
    return render(request, 'pharmacy/login.html')

def logout_view(request):
    logout(request)
    return redirect('pharmacy:home')

@login_required
def order_detail(request, pk):
    order = get_object_or_404(CustomerOrder, pk=pk)
    # Check if the user is the owner of the order or an employee
    if request.user.user_type == 'C' and order.customer != request.user:
        return redirect('pharmacy:profile')
    
    # Handle payment
    if request.method == 'POST' and 'pay_order' in request.POST:
        if not order.paid:
            order.mark_as_paid()
            messages.success(request, 'Заказ успешно оплачен!')
            return redirect('pharmacy:order_detail', pk=order.pk)
    
    return render(request, 'pharmacy/order_detail.html', {'order': order})

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        auth_logger.info(f"Registration attempt from IP: {request.META.get('REMOTE_ADDR')}")
        
        if form.is_valid():
            try:
                user = form.save()
                auth_logger.info(f"User registered successfully: {user.username}")
                login(request, user)
                return redirect('pharmacy:profile')
            except Exception as e:
                auth_logger.error(f"Registration error for user: {form.cleaned_data.get('username')}. Error: {str(e)}")
                security_logger.error(f"Registration failed with exception: {str(e)}")
                return render(request, 'pharmacy/register.html', {'form': form, 'error': 'Ошибка при регистрации'})
        else:
            auth_logger.warning(f"Invalid registration form submitted. Errors: {form.errors}")
    else:
        form = RegistrationForm()
        logger.debug("Registration form displayed")
    
    return render(request, 'pharmacy/register.html', {'form': form})

@login_required
@user_passes_test(is_customer)
def my_orders(request):
    orders = CustomerOrder.objects.filter(customer=request.user).order_by('-order_date')
    return render(request, 'pharmacy/my_orders.html', {'orders': orders})

def pickup_points(request):
    pickup_points = PickupPoint.objects.filter(is_active=True)
    return render(request, 'pharmacy/pickup_points.html', {'pickup_points': pickup_points})

@login_required
@user_passes_test(is_employee)
def sales(request):
    sales_list = Sale.objects.all().order_by('-sale_date')
    total_revenue = sales_list.aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Получаем все суммы продаж для статистических расчетов
    sale_amounts = list(sales_list.values_list('total_amount', flat=True))
    
    # Статистические показатели
    stats = {
        'mean': round(mean(sale_amounts), 2) if sale_amounts else 0,
        'median': round(median(sale_amounts), 2) if sale_amounts else 0,
        'mode': round(mode(sale_amounts), 2) if sale_amounts else 0,
    }
    
    # Самый популярный товар
    most_popular_item = OrderItem.objects.values(
        'medication__name'
    ).annotate(
        total_quantity=Sum('quantity')
    ).order_by('-total_quantity').first()
    
    # Самый прибыльный товар
    most_profitable_item = OrderItem.objects.values(
        'medication__name'
    ).annotate(
        total_revenue=Sum(F('price') * F('quantity'))
    ).order_by('-total_revenue').first()
    
    # Анализ продаж по месяцам
    monthly_sales = Sale.objects.annotate(
        month=ExtractMonth('sale_date')
    ).values('month').annotate(
        total=Sum('total_amount')
    ).order_by('month')

    # Генерация графиков с помощью matplotlib

    # 1. График распределения сумм заказов
    plt.figure(figsize=(10, 6))
    order_amounts = CustomerOrder.objects.filter(paid=True).values_list('total_price', flat=True)
    ranges = [(0, 25), (26, 50), (51, 75), (76, 100), (101, 150), (151, 200), (201, 300), (301, 400), (401, 500), (501, float('inf'))]
    labels = ['0-25', '26-50', '51-75', '76-100', '101-150', '151-200', '201-300', '301-400', '401-500', '501+']
    amounts_hist = [sum(1 for x in order_amounts if r[1] != float('inf') and r[0] <= x <= r[1] or r[1] == float('inf') and x >= r[0]) for r in ranges]
    
    plt.figure(figsize=(12, 6))
    plt.bar(labels, amounts_hist)
    plt.title('Распределение сумм заказов')
    plt.xlabel('Диапазон сумм (руб.)')
    plt.ylabel('Количество заказов')
    plt.xticks(rotation=45)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    orders_chart = base64.b64encode(buffer.getvalue()).decode()
    plt.close()

    # 2. График возрастного распределения (теперь столбчатая диаграмма)
    plt.figure(figsize=(10, 6))
    customers = CustomUser.objects.filter(user_type='C', date_of_birth__isnull=False)
    ages = [(date.today() - customer.date_of_birth).days // 365 for customer in customers]
    age_ranges = [(18, 25), (26, 35), (36, 45), (46, 55), (56, 65), (66, float('inf'))]
    age_labels = ['18-25', '26-35', '36-45', '46-55', '56-65', '66+']
    age_hist = [sum(1 for age in ages if r[1] != float('inf') and r[0] <= age <= r[1] or r[1] == float('inf') and age >= r[0]) for r in age_ranges]
    
    plt.bar(age_labels, age_hist, color='skyblue')
    plt.title('Распределение возрастов клиентов')
    plt.xlabel('Возрастные группы')
    plt.ylabel('Количество клиентов')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    ages_chart = base64.b64encode(buffer.getvalue()).decode()
    plt.close()

    # 3. График топ-5 популярных товаров
    plt.figure(figsize=(12, 6))
    top_products = OrderItem.objects.values(
        'medication__name'
    ).annotate(
        total_quantity=Sum('quantity')
    ).order_by('-total_quantity')[:5]
    
    product_names = [item['medication__name'] for item in top_products]
    quantities = [item['total_quantity'] for item in top_products]
    
    y_pos = np.arange(len(product_names))
    plt.barh(y_pos, quantities)
    plt.yticks(y_pos, product_names)
    plt.xlabel('Количество проданных единиц')
    plt.title('Топ-5 популярных товаров')
    
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    products_chart = base64.b64encode(buffer.getvalue()).decode()
    plt.close()

    context = {
        'sales': sales_list,
        'total_revenue': total_revenue,
        'stats': stats,
        'most_popular_item': most_popular_item,
        'most_profitable_item': most_profitable_item,
        'monthly_sales': monthly_sales,
        'orders_chart': orders_chart,
        'ages_chart': ages_chart,
        'products_chart': products_chart,
    }
    return render(request, 'pharmacy/sales.html', context)

@login_required
def medication_list(request):
    medications = Medication.objects.all().select_related('department', 'supplier')
    return render(request, 'pharmacy/medication/list.html', {
        'medications': medications
    })

def medication_detail(request, pk):
    medication = get_object_or_404(Medication, pk=pk)
    return render(request, 'pharmacy/medication/detail.html', {'medication': medication})

# Medication CRUD
@login_required
@user_passes_test(is_employee)
def medication_create(request):
    if request.method == 'POST':
        form = MedicationForm(request.POST, request.FILES)
        if form.is_valid():
            medication = form.save()
            messages.success(request, 'Медикамент успешно добавлен.')
            return redirect('pharmacy:medication_detail', pk=medication.pk)
    else:
        form = MedicationForm()
    return render(request, 'pharmacy/medication/form.html', {
        'form': form,
        'title': 'Добавить медикамент'
    })

@login_required
@user_passes_test(is_employee)
def medication_update(request, pk):
    medication = get_object_or_404(Medication, pk=pk)
    if request.method == 'POST':
        form = MedicationForm(request.POST, request.FILES, instance=medication)
        if form.is_valid():
            medication = form.save()
            messages.success(request, 'Медикамент успешно обновлен.')
            return redirect('pharmacy:medication_detail', pk=medication.pk)
    else:
        form = MedicationForm(instance=medication)
    return render(request, 'pharmacy/medication/form.html', {
        'form': form,
        'title': 'Редактировать медикамент',
        'medication': medication
    })

@login_required
@user_passes_test(is_employee)
def medication_delete(request, pk):
    medication = get_object_or_404(Medication, pk=pk)
    if request.method == 'POST':
        medication.delete()
        messages.success(request, 'Медикамент успешно удален.')
        return redirect('pharmacy:medication_list')
    return render(request, 'pharmacy/medication/delete.html', {'medication': medication})

# Supplier CRUD
@login_required
@user_passes_test(is_employee)
def supplier_list(request):
    suppliers_list = Supplier.objects.filter(is_active=True)
    return render(request, 'pharmacy/supplier/list.html', {'suppliers': suppliers_list})

@login_required
@user_passes_test(is_employee)
def supplier_detail(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    medications = Medication.objects.filter(supplier=supplier)
    return render(request, 'pharmacy/supplier/detail.html', {
        'supplier': supplier,
        'medications': medications
    })

@login_required
@user_passes_test(is_employee)
def supplier_create(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, 'Поставщик успешно добавлен.')
            return redirect('pharmacy:supplier_detail', pk=supplier.pk)
    else:
        form = SupplierForm()
    return render(request, 'pharmacy/supplier/form.html', {
        'form': form,
        'title': 'Добавить поставщика'
    })

@login_required
@user_passes_test(is_employee)
def supplier_update(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, 'Поставщик успешно обновлен.')
            return redirect('pharmacy:supplier_detail', pk=supplier.pk)
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'pharmacy/supplier/form.html', {
        'form': form,
        'title': 'Редактировать поставщика',
        'supplier': supplier
    })

@login_required
@user_passes_test(is_employee)
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        supplier.is_active = False
        supplier.save()
        messages.success(request, 'Поставщик успешно удален.')
        return redirect('pharmacy:supplier_list')
    return render(request, 'pharmacy/supplier/delete.html', {'supplier': supplier})

def mark_order_as_paid(request, order_id):
    try:
        order = CustomerOrder.objects.get(id=order_id)
        if not order.paid:
            order.mark_as_paid()
            orders_logger.info(f"Order #{order_id} marked as paid by user {request.user.username}")
            return JsonResponse({'status': 'success'})
        else:
            orders_logger.warning(f"Attempt to mark already paid order #{order_id} as paid")
            return JsonResponse({'status': 'error', 'message': 'Order is already paid'})
    except CustomerOrder.DoesNotExist:
        orders_logger.error(f"Attempt to mark non-existent order #{order_id} as paid")
        return JsonResponse({'status': 'error', 'message': 'Order not found'})
    except Exception as e:
        orders_logger.error(f"Error marking order #{order_id} as paid: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
@user_passes_test(is_customer)
def edit_customer_profile(request):
    if request.method == 'POST':
        form = CustomerProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен')
            return redirect('pharmacy:profile')
    else:
        form = CustomerProfileForm(instance=request.user)
    return render(request, 'pharmacy/edit_customer_profile.html', {'form': form})

@login_required
@user_passes_test(is_employee)
def edit_employee_profile(request):
    if request.method == 'POST':
        form = EmployeeProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен')
            return redirect('pharmacy:profile')
    else:
        form = EmployeeProfileForm(instance=request.user)
    return render(request, 'pharmacy/edit_employee_profile.html', {'form': form})
