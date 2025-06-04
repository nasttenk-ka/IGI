from django.contrib import admin
from django.db.models import Sum
from django.urls import path
from django.shortcuts import render
from django.contrib.auth.admin import UserAdmin
from .models import (
    Medication, Department, Employee, Supplier, 
    Sale, CustomUser, VacancyApplication, CustomerOrder,
    PromoCode, PickupPoint, OrderItem
)
from .models import *
from django.utils.html import format_html

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'user_type', 'is_staff', 'date_of_birth')
    fieldsets = UserAdmin.fieldsets + (
        ('Доп. информация', {'fields': ('user_type', 'phone', 'date_of_birth', 'photo')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(PickupPoint)

class DepartmentFilter(admin.SimpleListFilter):
    title = 'Отдел'
    parameter_name = 'department'

    def lookups(self, request, model_admin):
        return [(d.id, d.name) for d in Department.objects.all()]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(department__id=self.value())

class SupplierFilter(admin.SimpleListFilter):
    title = 'Поставщик'
    parameter_name = 'supplier'

    def lookups(self, request, model_admin):
        return [(s.id, s.name) for s in Supplier.objects.all()]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(supplier__id=self.value())

@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ['name', 'barcode', 'price', 'stock', 'department_name', 'supplier_name', 'prescription_status']
    list_filter = [DepartmentFilter, SupplierFilter, 'prescription_required']
    search_fields = ['name', 'barcode', 'description']
    readonly_fields = ['barcode']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'barcode', 'description', 'instruction', 'photo')
        }),
        ('Детали', {
            'fields': ('department', 'supplier', 'price', 'stock', 'prescription_required')
        }),
    )

    def department_name(self, obj):
        return obj.department.name
    department_name.short_description = 'Отдел'
    department_name.admin_order_field = 'department__name'

    def supplier_name(self, obj):
        return obj.supplier.name
    supplier_name.short_description = 'Поставщик'
    supplier_name.admin_order_field = 'supplier__name'

    def prescription_status(self, obj):
        return "Да" if obj.prescription_required else "Нет"
    prescription_status.short_description = 'Требуется рецепт'

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'phone']
    search_fields = ['name', 'location']

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['employee_photo', 'name', 'position', 'department', 'specialization', 'phone', 'email', 'is_active']
    list_filter = ['department', 'position', 'is_active']
    search_fields = ['name', 'position', 'department', 'specialization', 'description', 'phone', 'email']
    ordering = ['order', 'name']
    list_editable = ['position', 'department', 'is_active']
    list_per_page = 20
    
    fieldsets = (
        ('Основная информация', {
            'fields': (
                'name', 
                'position', 
                'department', 
                'specialization',
                'photo',
            ),
            'classes': ('wide',)
        }),
        ('Контактная информация', {
            'fields': (
                'phone',
                'email',
            ),
            'classes': ('wide',)
        }),
        ('Описание и настройки', {
            'fields': (
                'description',
                'order',
                'is_active',
            ),
            'classes': ('wide',)
        }),
    )
    
    def employee_photo(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 50%;" />',
                obj.photo.url
            )
        return format_html(
            '<img src="/static/images/default-avatar.png" width="50" height="50" style="border-radius: 50%;" />'
        )
    employee_photo.short_description = 'Фото'
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # при редактировании
            return []
        return []  # при создании
    
    def save_model(self, request, obj, form, change):
        if not change:  # если создается новый объект
            # Устанавливаем порядок отображения как максимальный + 1
            max_order = Employee.objects.aggregate(models.Max('order'))['order__max']
            obj.order = (max_order or 0) + 1
        super().save_model(request, obj, form, change)
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_person', 'phone', 'email']
    search_fields = ['name', 'contact_person']

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'sale_date', 'total_amount']
    list_filter = ['sale_date']
    search_fields = ['order__id']

# Кастомные представления для отчетов
'''def sales_report_view(request):
    total_revenue = Sale.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    by_department = Sale.objects.values(
        'employee__department__name'
    ).annotate(
        total=Sum('total_amount')
    ).order_by('-total')
    
    return render(request, 'admin/pharmacy/sales_report.html', {
        'total_revenue': total_revenue,
        'by_department': by_department,
    })

def medication_report_view(request, med_id):
    medication = Medication.objects.get(pk=med_id)
    sales = SaleItem.objects.filter(medication=medication)
    total_sold = sales.aggregate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('price')
    )
    
    return render(request, 'admin/pharmacy/medication_report.html', {
        'medication': medication,
        'sales': sales,
        'total_sold': total_sold,
    })

# Добавляем кастомные URL в админ-панель
def get_admin_urls(urls):
    def get_urls():
        my_urls = [
            path('sales-report/', admin.site.admin_view(sales_report_view)), 
            path('medication-report/<int:med_id>/', admin.site.admin_view(medication_report_view)),
        ]
        return my_urls + urls
    return get_urls

admin.site.get_urls = get_admin_urls(admin.site.get_urls())

# Настройки админ-панели
admin.site.site_header = 'Управление аптекой'
admin.site.site_title = 'Администрирование аптеки'
admin.site.index_title = 'Панель управления'
'''
@admin.register(CompanyInfo)
class CompanyInfoAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_active']

@admin.register(CompanyHistory)
class CompanyHistoryAdmin(admin.ModelAdmin):
    list_display = ['year', 'event']

@admin.register(CompanyRequisite)
class CompanyRequisiteAdmin(admin.ModelAdmin):
    list_display = ['name', 'value']

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'published_date', 'is_active']
    prepopulated_fields = {'slug': ('title',)}

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'is_active']

@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_active']

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'rating', 'created_at', 'is_active']
    list_filter = ['rating', 'created_at', 'is_active']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'text']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount', 'valid_from', 'valid_to', 'is_archived']
    list_filter = ['is_archived']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'category', 'price', 'stock', 'available']
    list_filter = ['available', 'category']
    list_editable = ['price', 'stock', 'available']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(VacancyApplication)
class VacancyApplicationAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'created_at']
    list_filter = ['created_at']
    search_fields = ['first_name', 'last_name', 'email']

@admin.register(CustomerOrder)
class CustomerOrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'order_date', 'status', 'total_price', 'paid']
    list_filter = ['status', 'paid', 'order_date']
    search_fields = ['id', 'customer__username']