from django.db import models
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, RegexValidator
from django.conf import settings
import logging
from django.core.exceptions import ValidationError
from django.utils import timezone
import calendar

# Configure logger
logger = logging.getLogger('pharmacy')
orders_logger = logging.getLogger('pharmacy.orders')

# Phone number validator
phone_regex = RegexValidator(
    regex=r'^\+375 \((17|29|33|44)\) [0-9]{3}-[0-9]{2}-[0-9]{2}$',
    message="Номер телефона должен быть в формате: '+375 (29) XXX-XX-XX'"
)

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            logger.info(f"Created new {self.__class__.__name__} with ID: {self.id}")
        else:
            logger.info(f"Updated {self.__class__.__name__} with ID: {self.id}")

    def delete(self, *args, **kwargs):
        logger.info(f"Deleted {self.__class__.__name__} with ID: {self.id}")
        super().delete(*args, **kwargs)

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = [
        ('C', 'Customer'),
        ('E', 'Employee'),
    ]
    
    user_type = models.CharField(max_length=1, choices=USER_TYPE_CHOICES)
    phone = models.CharField(max_length=19, validators=[phone_regex])
    date_of_birth = models.DateField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    photo = models.ImageField(upload_to='user_photos/', null=True, blank=True, verbose_name='Фотография')
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        db_table = 'pharmacy_user'

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            logger.info(f"New user created: {self.username} (Type: {self.get_user_type_display()})")
        else:
            logger.info(f"User updated: {self.username}")
            
    def get_text_calendar(self):
        """Календарь в текстовом виде для текущего месяца пользователя"""
        now = timezone.now()
        return calendar.month(now.year, now.month)

class PickupPoint(models.Model):
    address = models.TextField()
    working_hours = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Пункт выдачи: {self.address}"
    
    class Meta:
        verbose_name = 'Пункт выдачи'
        verbose_name_plural = 'Пункты выдачи'

class CustomerOrder(models.Model):
    STATUS_CHOICES = (
        ('P', 'Оформлен'),
        ('C', 'Готов к выдаче'),
        ('D', 'Выдан')
    )
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'user_type': 'C'})
    items = models.ManyToManyField('Medication', through='OrderItem')
    pickup_point = models.ForeignKey(PickupPoint, on_delete=models.PROTECT)
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='P')
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    promo_code = models.ForeignKey('PromoCode', on_delete=models.SET_NULL, null=True, blank=True)
    paid = models.BooleanField(default=False)

    def __str__(self):
        return f"Order #{self.id}"

    def mark_as_paid(self):
        if not self.paid:
            try:
                # Уменьшаем количество медикаментов в наличии
                for order_item in self.orderitem_set.all():
                    medication = order_item.medication
                    old_stock = medication.stock
                    medication.stock -= order_item.quantity
                    medication.save()
                    orders_logger.info(
                        f"Stock updated for medication {medication.name} (ID: {medication.id}): "
                        f"{old_stock} -> {medication.stock}"
                    )
                
                # Помечаем заказ как оплаченный
                self.paid = True
                self.save()
                orders_logger.info(f"Order #{self.id} marked as paid. Total amount: {self.total_price}")
                
                # Создаем запись о продаже
                sale = Sale.objects.create(
                    order=self,
                    total_amount=self.total_price
                )
                orders_logger.info(f"Sale record created for Order #{self.id}: Sale #{sale.id}")
                
            except Exception as e:
                orders_logger.error(f"Error processing payment for Order #{self.id}: {str(e)}")
                raise

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            orders_logger.info(
                f"New order created: #{self.id} by {self.customer.username}. "
                f"Total: {self.total_price}"
            )
        else:
            orders_logger.info(
                f"Order #{self.id} updated. Status: {self.get_status_display()}, "
                f"Paid: {self.paid}"
            )

class OrderItem(models.Model):
    order = models.ForeignKey(CustomerOrder, on_delete=models.CASCADE)
    medication = models.ForeignKey('Medication', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)


class Department(BaseModel):
    """Отделы аптеки"""
    name = models.CharField(max_length=100, verbose_name="Название отдела")
    location = models.CharField(max_length=100, verbose_name="Расположение")
    phone = models.CharField(max_length=20, verbose_name="Телефон")

    def __str__(self):
        return f"{self.name} ({self.location})"

class Supplier(BaseModel):
    """Поставщики медикаментов"""
    name = models.CharField(max_length=200, verbose_name="Название компании")
    contact_person = models.CharField(max_length=100, verbose_name="Контактное лицо")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    email = models.EmailField(verbose_name="Email")
    address = models.TextField(verbose_name="Адрес")
    delivery_time = models.PositiveIntegerField(
        verbose_name="Срок поставки (дни)",
        default=3
    )

    def __str__(self):
        return self.name

class MedicationCategory(BaseModel):
    """Категории медикаментов"""
    name = models.CharField(max_length=100, verbose_name="Название категории")
    description = models.TextField(verbose_name="Описание", blank=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Medication(models.Model):
    barcode = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField()
    instruction = models.TextField()
    photo = models.ImageField(upload_to='medications/', blank=True, null=True)
    department = models.ForeignKey(
        'Department', 
        on_delete=models.PROTECT,
        verbose_name="Отдел"
    )
    supplier = models.ForeignKey(
        'Supplier',
        on_delete=models.PROTECT,
        verbose_name="Поставщик"
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()
    prescription_required = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Медикамент'
        verbose_name_plural = 'Медикаменты'
        

class Employee(BaseModel):
    """Сотрудники аптеки"""
    name = models.CharField(max_length=200, verbose_name="ФИО", default="Сотрудник")
    position = models.CharField(max_length=100, verbose_name="Должность", default="Специалист")
    department = models.CharField(max_length=100, verbose_name="Отдел", default="Общий")
    specialization = models.CharField(max_length=200, verbose_name="Специализация", blank=True)
    description = models.TextField(verbose_name="Описание обязанностей", blank=True, default="")
    phone = models.CharField(max_length=20, verbose_name="Телефон", default="+375 (29) 123-45-67")
    email = models.EmailField(verbose_name="Email", default="info@pharmacy.by")
    photo = models.ImageField(upload_to='employee_photos/', blank=True, null=True, verbose_name="Фото")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок отображения")

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"

    def __str__(self):
        return f"{self.name} - {self.position}"

class Sale(models.Model):
    order = models.OneToOneField('CustomerOrder', on_delete=models.CASCADE, null=True)
    sale_date = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"Sale #{self.id} - Order #{self.order.id if self.order else 'N/A'}"

    class Meta:
        ordering = ['-sale_date']
        verbose_name = 'Продажа'
        verbose_name_plural = 'Продажи'

class CompanyInfo(BaseModel):
    title = models.CharField(max_length=200)
    content = models.TextField()
    video_url = models.URLField(blank=True, null=True)
    logo = models.ImageField(upload_to='company/', blank=True, null=True)

    def __str__(self):
        return self.title

class CompanyHistory(BaseModel):
    year = models.PositiveIntegerField()
    event = models.CharField(max_length=255)
    description = models.TextField()

    class Meta:
        ordering = ['-year']

    def __str__(self):
        return f"{self.year}: {self.event}"

class CompanyRequisite(BaseModel):
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class Article(BaseModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    short_content = models.CharField(max_length=255)
    full_content = models.TextField()
    image = models.ImageField(upload_to='articles/')
    published_date = models.DateField()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class FAQ(BaseModel):
    question = models.CharField(max_length=255)
    answer = models.TextField()

    def __str__(self):
        return self.question

'''class Employee(BaseModel):
    name = models.CharField(max_length=100)
    position = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='employees/')
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    description = models.TextField('

    def __str__(self):
        return f"{self.name} - {self.position}"'''

class Vacancy(BaseModel):
    title = models.CharField(max_length=200)
    description = models.TextField()
    requirements = models.TextField()
    salary = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.title

class Review(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        limit_choices_to={'user_type': 'C'},  # Ограничиваем выбор только клиентами
        null=True,  # Temporarily allow null
        blank=True  # Temporarily allow blank
    )
    rating = models.PositiveSmallIntegerField(
        choices=[(i, f'{i} звезд{"а" if i == 1 else "ы" if 1 < i < 5 else ""}') for i in range(1, 6)],
        verbose_name='Оценка'
    )
    text = models.TextField(verbose_name='Текст отзыва')

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                name='unique_user_review',
                condition=models.Q(user__isnull=False)  # Only apply constraint when user is not null
            )
        ]

    def clean(self):
        if self.user and self.user.user_type != 'C':
            raise ValidationError('Только клиенты могут оставлять отзывы.')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.user:
            return f'Отзыв от {self.user.get_full_name()} ({self.rating}/5)'
        return f'Анонимный отзыв ({self.rating}/5)' 

class PromoCode(BaseModel):
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    discount = models.DecimalField(max_digits=5, decimal_places=2)
    valid_from = models.DateField()
    valid_to = models.DateField()
    is_archived = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.code} - {self.discount}%"

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название категории")
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название препарата")
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name="Категория")
    description = models.TextField(verbose_name="Описание")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    stock = models.PositiveIntegerField(verbose_name="Количество на складе")
    available = models.BooleanField(default=True, verbose_name="Доступен")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Препарат"
        verbose_name_plural = "Препараты"
        ordering = ['name']

class VacancyApplication(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vacancy_applications',
        verbose_name='Пользователь',
        null=True,  # Временно разрешаем null значения
        blank=True  # Временно разрешаем пустые значения
    )
    first_name = models.CharField(max_length=100, verbose_name='Имя')
    last_name = models.CharField(max_length=100, verbose_name='Фамилия')
    email = models.EmailField(verbose_name='Email')
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    resume = models.FileField(upload_to='resumes/', verbose_name='Резюме')
    cover_letter = models.TextField(blank=True, verbose_name='Сопроводительное письмо')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    vacancy = models.ForeignKey(
        'Vacancy',
        on_delete=models.CASCADE,
        related_name='applications',
        verbose_name='Вакансия',
        null=True,  # Временно разрешаем null значения
        blank=True  # Временно разрешаем пустые значения
    )
    
    class Meta:
        verbose_name = 'Отклик на вакансию'
        verbose_name_plural = 'Отклики на вакансии'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'vacancy'],
                name='unique_user_vacancy_application',
                condition=models.Q(user__isnull=False, vacancy__isnull=False)  # Применяем ограничение только для существующих значений
            )
        ]
    
    def __str__(self):
        vacancy_name = self.vacancy.title if self.vacancy else 'Неизвестная вакансия'
        return f"{self.first_name} {self.last_name} - {vacancy_name}"

    def save(self, *args, **kwargs):
        if self.user:
            if not self.first_name:
                self.first_name = self.user.first_name
            if not self.last_name:
                self.last_name = self.user.last_name
            if not self.email:
                self.email = self.user.email
            if not self.phone:
                self.phone = self.user.phone
        super().save(*args, **kwargs)

class Contact(BaseModel):
    name = models.CharField(max_length=100, verbose_name='Имя')
    position = models.CharField(max_length=100, verbose_name='Должность')
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    email = models.EmailField(verbose_name='Email')
    order = models.IntegerField(default=0, verbose_name='Порядок отображения')

    def __str__(self):
        return f"{self.name} - {self.position}"

    class Meta:
        verbose_name = 'Контакт'
        verbose_name_plural = 'Контакты'
        ordering = ['order', 'name']