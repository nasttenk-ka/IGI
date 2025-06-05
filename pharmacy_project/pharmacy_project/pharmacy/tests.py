from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from datetime import date, timedelta
import logging
from io import StringIO

from .models import (
    CustomUser, PickupPoint, CustomerOrder, OrderItem, Department, Supplier,
    MedicationCategory, Medication, Employee, Sale, CompanyInfo, CompanyHistory,
    CompanyRequisite, Article, FAQ, Vacancy, Review, PromoCode, Category,
    Product, VacancyApplication
)

User = get_user_model()

class CustomUserModelTest(TestCase):
    def setUp(self):
        self.user_data = {
            'username': 'testuser',
            'password': 'testpass123',
            'email': 'test@example.com',
            'user_type': 'C',
            'phone': '+375 (29) 123-45-67',
            'date_of_birth': date(1990, 1, 1)
        }

    def test_create_user(self):
        user = CustomUser.objects.create_user(**self.user_data)
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.user_type, 'C')
        self.assertEqual(user.phone, '+375 (29) 123-45-67')
        self.assertFalse(user.is_staff)
        self.assertTrue(user.is_active)

    def test_create_superuser(self):
        admin_user = CustomUser.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='testpass123',
            phone='+375 (29) 987-65-43'
        )
        self.assertEqual(admin_user.username, 'admin')
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)

    def test_phone_validation(self):
        # Valid phone
        user = CustomUser(**self.user_data)
        user.full_clean()  # Should not raise ValidationError

        # Invalid phone
        user.phone = 'invalid-phone'
        with self.assertRaises(ValidationError):
            user.full_clean()

    def test_user_type_choices(self):
        user = CustomUser.objects.create_user(**self.user_data)
        self.assertIn(('C', 'Customer'), CustomUser.USER_TYPE_CHOICES)
        self.assertIn(('E', 'Employee'), CustomUser.USER_TYPE_CHOICES)
        self.assertEqual(user.get_user_type_display(), 'Customer')

class PickupPointModelTest(TestCase):
    def setUp(self):
        self.pickup_point = PickupPoint.objects.create(
            address='Test Address 123',
            working_hours='9:00-18:00',
            phone='+375 (29) 111-22-33',
            is_active=True
        )

    def test_pickup_point_creation(self):
        self.assertEqual(self.pickup_point.address, 'Test Address 123')
        self.assertEqual(self.pickup_point.working_hours, '9:00-18:00')
        self.assertTrue(self.pickup_point.is_active)

    def test_str_representation(self):
        self.assertEqual(str(self.pickup_point), 'Пункт выдачи: Test Address 123')

class CustomerOrderModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='customer',
            password='testpass123',
            email='customer@example.com',
            user_type='C',
            phone='+375 (29) 123-45-67'
        )
        
        self.pickup_point = PickupPoint.objects.create(
            address='Test Address',
            working_hours='9:00-18:00',
            phone='+375 (29) 111-22-33'
        )
        
        self.department = Department.objects.create(
            name='Test Department',
            location='Test Location',
            phone='+375 (29) 111-11-11'
        )
        
        self.supplier = Supplier.objects.create(
            name='Test Supplier',
            contact_person='Test Person',
            phone='+375 (29) 222-22-22',
            email='supplier@example.com',
            address='Test Supplier Address'
        )
        
        self.medication = Medication.objects.create(
            barcode='1234567890',
            name='Test Medication',
            description='Test Description',
            instruction='Test Instruction',
            department=self.department,
            supplier=self.supplier,
            price=10.99,
            stock=100,
            prescription_required=False
        )
        
        self.order = CustomerOrder.objects.create(
            customer=self.user,
            pickup_point=self.pickup_point,
            total_price=21.98,
            status='P'
        )
        
        self.order_item = OrderItem.objects.create(
            order=self.order,
            medication=self.medication,
            quantity=2,
            price=10.99
        )

    def test_order_creation(self):
        self.assertEqual(self.order.customer, self.user)
        self.assertEqual(self.order.pickup_point, self.pickup_point)
        self.assertEqual(self.order.status, 'P')
        self.assertEqual(self.order.total_price, 21.98)
        self.assertFalse(self.order.paid)

    def test_order_items(self):
        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order.orderitem_set.first().medication, self.medication)
        self.assertEqual(self.order.orderitem_set.first().quantity, 2)

    def test_mark_as_paid(self):
        initial_stock = self.medication.stock
        self.order.mark_as_paid()
        
        self.assertTrue(self.order.paid)
        self.medication.refresh_from_db()
        self.assertEqual(self.medication.stock, initial_stock - 2)
        
        # Check if sale record was created
        self.assertTrue(Sale.objects.filter(order=self.order).exists())

    def test_status_choices(self):
        self.assertEqual(self.order.get_status_display(), 'Оформлен')
        self.order.status = 'C'
        self.assertEqual(self.order.get_status_display(), 'Готов к выдаче')
        self.order.status = 'D'
        self.assertEqual(self.order.get_status_display(), 'Выдан')

class DepartmentModelTest(TestCase):
    def setUp(self):
        self.department = Department.objects.create(
            name='Test Department',
            location='Test Location',
            phone='+375 (29) 111-11-11'
        )

    def test_department_creation(self):
        self.assertEqual(self.department.name, 'Test Department')
        self.assertEqual(self.department.location, 'Test Location')
        self.assertEqual(self.department.phone, '+375 (29) 111-11-11')
        self.assertTrue(self.department.is_active)

    def test_str_representation(self):
        self.assertEqual(str(self.department), 'Test Department (Test Location)')

class SupplierModelTest(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            name='Test Supplier',
            contact_person='Test Person',
            phone='+375 (29) 222-22-22',
            email='supplier@example.com',
            address='Test Supplier Address',
            delivery_time=3
        )

    def test_supplier_creation(self):
        self.assertEqual(self.supplier.name, 'Test Supplier')
        self.assertEqual(self.supplier.contact_person, 'Test Person')
        self.assertEqual(self.supplier.phone, '+375 (29) 222-22-22')
        self.assertEqual(self.supplier.delivery_time, 3)
        self.assertTrue(self.supplier.is_active)

    def test_str_representation(self):
        self.assertEqual(str(self.supplier), 'Test Supplier')

class MedicationCategoryModelTest(TestCase):
    def setUp(self):
        self.category = MedicationCategory.objects.create(
            name='Test Category',
            description='Test Description'
        )

    def test_category_creation(self):
        self.assertEqual(self.category.name, 'Test Category')
        self.assertEqual(self.category.description, 'Test Description')
        self.assertTrue(self.category.is_active)

    def test_slug_auto_generation(self):
        self.assertEqual(self.category.slug, 'test-category')

    def test_str_representation(self):
        self.assertEqual(str(self.category), 'Test Category')

class MedicationModelTest(TestCase):
    def setUp(self):
        self.department = Department.objects.create(
            name='Test Department',
            location='Test Location',
            phone='+375 (29) 111-11-11'
        )
        
        self.supplier = Supplier.objects.create(
            name='Test Supplier',
            contact_person='Test Person',
            phone='+375 (29) 222-22-22',
            email='supplier@example.com',
            address='Test Supplier Address'
        )
        
        self.medication = Medication.objects.create(
            barcode='1234567890',
            name='Test Medication',
            description='Test Description',
            instruction='Test Instruction',
            department=self.department,
            supplier=self.supplier,
            price=10.99,
            stock=100,
            prescription_required=False
        )

    def test_medication_creation(self):
        self.assertEqual(self.medication.name, 'Test Medication')
        self.assertEqual(self.medication.barcode, '1234567890')
        self.assertEqual(self.medication.price, 10.99)
        self.assertEqual(self.medication.stock, 100)
        self.assertFalse(self.medication.prescription_required)
        self.assertEqual(self.medication.department, self.department)
        self.assertEqual(self.medication.supplier, self.supplier)

    def test_str_representation(self):
        self.assertEqual(str(self.medication), 'Test Medication')

class EmployeeModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='employee',
            password='testpass123',
            email='employee@example.com',
            user_type='E',
            phone='+375 (29) 123-45-67'
        )
        
        self.department = Department.objects.create(
            name='Test Department',
            location='Test Location',
            phone='+375 (29) 111-11-11'
        )
        
        self.employee = Employee.objects.create(
            user=self.user,
            department=self.department,
            position='PHARM',
            hire_date=date.today(),
            salary=1000.00,
            phone='+375 (29) 987-65-43',
            address='Test Address'
        )

    def test_employee_creation(self):
        self.assertEqual(self.employee.user, self.user)
        self.assertEqual(self.employee.department, self.department)
        self.assertEqual(self.employee.position, 'PHARM')
        self.assertEqual(self.employee.get_position_display(), 'Фармацевт')
        self.assertEqual(self.employee.salary, 1000.00)
        self.assertTrue(self.employee.is_active)

    def test_str_representation(self):
        self.assertEqual(str(self.employee), f"{self.user.get_full_name()} (Фармацевт)")

class SaleModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='customer',
            password='testpass123',
            email='customer@example.com',
            user_type='C',
            phone='+375 (29) 123-45-67'
        )
        
        self.pickup_point = PickupPoint.objects.create(
            address='Test Address',
            working_hours='9:00-18:00',
            phone='+375 (29) 111-22-33'
        )
        
        self.order = CustomerOrder.objects.create(
            customer=self.user,
            pickup_point=self.pickup_point,
            total_price=100.00,
            status='P',
            paid=True
        )
        
        self.sale = Sale.objects.create(
            order=self.order,
            total_amount=100.00
        )

    def test_sale_creation(self):
        self.assertEqual(self.sale.order, self.order)
        self.assertEqual(self.sale.total_amount, 100.00)
        self.assertIsNotNone(self.sale.sale_date)

    def test_str_representation(self):
        self.assertEqual(str(self.sale), f"Sale #{self.sale.id} - Order #{self.order.id}")

class CompanyInfoModelTest(TestCase):
    def setUp(self):
        self.company_info = CompanyInfo.objects.create(
            title='Test Title',
            content='Test Content'
        )

    def test_company_info_creation(self):
        self.assertEqual(self.company_info.title, 'Test Title')
        self.assertEqual(self.company_info.content, 'Test Content')
        self.assertTrue(self.company_info.is_active)

    def test_str_representation(self):
        self.assertEqual(str(self.company_info), 'Test Title')

class PromoCodeModelTest(TestCase):
    def setUp(self):
        self.promo_code = PromoCode.objects.create(
            code='TEST20',
            description='Test Promo Code',
            discount=20.00,
            valid_from=date.today(),
            valid_to=date.today() + timedelta(days=30)
        )

    def test_promo_code_creation(self):
        self.assertEqual(self.promo_code.code, 'TEST20')
        self.assertEqual(self.promo_code.discount, 20.00)
        self.assertFalse(self.promo_code.is_archived)
        self.assertTrue(self.promo_code.is_active)

    def test_str_representation(self):
        self.assertEqual(str(self.promo_code), 'TEST20 - 20.00%')

class ReviewModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='reviewer',
            password='testpass123',
            email='reviewer@example.com',
            user_type='C',
            phone='+375 (29) 123-45-67'
        )
        
        self.review = Review.objects.create(
            user=self.user,
            rating=5,
            text='Excellent service!'
        )

    def test_review_creation(self):
        self.assertEqual(self.review.user, self.user)
        self.assertEqual(self.review.rating, 5)
        self.assertEqual(self.review.text, 'Excellent service!')
        self.assertTrue(self.review.is_active)

    def test_rating_choices(self):
        self.assertEqual(self.review.get_rating_display(), '5 звезд')

    def test_str_representation(self):
        self.assertEqual(str(self.review), f'Отзыв от {self.user.get_full_name()} (5/5)')

    def test_unique_constraint(self):
        with self.assertRaises(Exception):
            Review.objects.create(
                user=self.user,
                rating=4,
                text='Another review'
            )

class BaseModelTest(TestCase):
    def setUp(self):
        # We'll test BaseModel using Department as it inherits from BaseModel
        self.department = Department.objects.create(
            name='Test Department',
            location='Test Location',
            phone='+375 (29) 111-11-11'
        )

    def test_created_at_auto_add(self):
        self.assertIsNotNone(self.department.created_at)

    def test_updated_at_auto_now(self):
        initial_updated = self.department.updated_at
        self.department.name = 'Updated Department'
        self.department.save()
        self.assertNotEqual(self.department.updated_at, initial_updated)

    def test_is_active_default(self):
        self.assertTrue(self.department.is_active)

    def test_logging_on_create(self):
        # Test logging by capturing log output
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger('pharmacy')
        logger.addHandler(handler)
        
        department = Department.objects.create(
            name='New Department',
            location='New Location',
            phone='+375 (29) 222-22-22'
        )
        
        log_contents = log_stream.getvalue()
        self.assertIn(f"Created new Department with ID: {department.id}", log_contents)
        
        logger.removeHandler(handler)

    def test_logging_on_delete(self):
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger('pharmacy')
        logger.addHandler(handler)
        
        department = Department.objects.create(
            name='Temp Department',
            location='Temp Location',
            phone='+375 (29) 333-33-33'
        )
        department_id = department.id
        department.delete()
        
        log_contents = log_stream.getvalue()
        self.assertIn(f"Deleted Department with ID: {department_id}", log_contents)
        
        logger.removeHandler(handler)