from django import forms
from .models import CustomUser, CustomerOrder, PickupPoint, PromoCode, OrderItem, Medication, Review, VacancyApplication, Supplier
from django.utils import timezone
from datetime import date
import re

class RegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'minlength': '8',
            'required': True,
            'pattern': '^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$',
            'title': 'Пароль должен содержать минимум 8 символов, включая буквы и цифры'
        })
    )
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'required': True,
            'max': date.today().isoformat()
        }),
        required=True,
        label='Дата рождения'
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        label='Номер телефона',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+375 (29) XXX-XX-XX',
            'pattern': '\\+375 \\(29\\) \\d{3}-\\d{2}-\\d{2}',
            'title': 'Введите номер в формате: +375 (29) XXX-XX-XX',
            'required': True
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'required': True,
            'title': 'Введите корректный email адрес'
        })
    )
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'required': True,
            'pattern': '^[А-Яа-яЁё\\s-]+$',
            'title': 'Используйте только русские буквы'
        })
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'required': True,
            'pattern': '^[А-Яа-яЁё\\s-]+$',
            'title': 'Используйте только русские буквы'
        })
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'required': True,
            'minlength': '3',
            'pattern': '^[a-zA-Z0-9_]+$',
            'title': 'Используйте только латинские буквы, цифры и знак подчеркивания'
        })
    )
    photo = forms.ImageField(
        required=False,
        label='Фотография профиля',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )
    
    class Meta:
        model = CustomUser
        fields = ['username', 'password', 'first_name', 'last_name', 'email', 'phone', 'user_type', 'date_of_birth', 'photo']

    def clean_date_of_birth(self):
        birth_date = self.cleaned_data['date_of_birth']
        today = date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        if age < 18:
            raise forms.ValidationError('Вы должны быть старше 18 лет для регистрации.')
        return birth_date

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        pattern = r'^\+375 \(29\) \d{3}-\d{2}-\d{2}$'
        if not re.match(pattern, phone):
            raise forms.ValidationError('Номер телефона должен быть в формате: +375 (29) XXX-XX-XX')
        return phone

class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ['medication', 'quantity']
        widgets = {
            'quantity': forms.NumberInput(attrs={'min': 1})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medication'].queryset = Medication.objects.filter(stock__gt=0)

class OrderForm(forms.ModelForm):
    medications = forms.ModelMultipleChoiceField(
        queryset=Medication.objects.filter(stock__gt=0),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Выберите медикаменты"
    )
    quantities = forms.CharField(
        widget=forms.HiddenInput,
        required=False
    )

    class Meta:
        model = CustomerOrder
        fields = ['pickup_point', 'promo_code', 'medications']
        widgets = {
            'promo_code': forms.Select(attrs={'class': 'form-select'}),
            'pickup_point': forms.Select(attrs={'class': 'form-select'})
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['pickup_point'].queryset = PickupPoint.objects.filter(is_active=True)
        self.fields['promo_code'].queryset = PromoCode.objects.filter(is_active=True, is_archived=False)
        self.fields['promo_code'].required = False

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.customer = self.user
        instance.total_price = 0  # Will be calculated when adding items
        
        if commit:
            instance.save()
            # Process medications and quantities
            quantities = self.cleaned_data.get('quantities', '').split(',')
            medications = self.cleaned_data['medications']
            
            for medication, quantity_str in zip(medications, quantities):
                if quantity_str:
                    quantity = int(quantity_str)
                    if quantity > 0:
                        OrderItem.objects.create(
                            order=instance,
                            medication=medication,
                            quantity=quantity,
                            price=medication.price
                        )
            
            # Update total price
            total = sum(item.price * item.quantity for item in instance.orderitem_set.all())
            if instance.promo_code:
                total = total * (1 - instance.promo_code.discount / 100)
            instance.total_price = total
            instance.save()
            
        return instance

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'text']
        widgets = {
            'rating': forms.RadioSelect(attrs={'class': 'star-rating'}),
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Поделитесь своим мнением...'
            }),
        }
        labels = {
            'rating': 'Оценка',
            'text': 'Ваш отзыв'
        }
        help_texts = {
            'rating': 'Выберите оценку от 1 до 5 звезд',
            'text': 'Минимум 10 символов'
        }

    def clean_text(self):
        text = self.cleaned_data['text']
        if len(text.strip()) < 10:
            raise forms.ValidationError('Отзыв должен содержать минимум 10 символов')
        return text

class VacancyApplicationForm(forms.ModelForm):
    class Meta:
        model = VacancyApplication
        fields = ['first_name', 'last_name', 'email', 'phone', 'resume', 'cover_letter']
        widgets = {
            'cover_letter': forms.Textarea(attrs={'rows': 4}),
        }

class MedicationForm(forms.ModelForm):
    class Meta:
        model = Medication
        fields = ['barcode', 'name', 'description', 'instruction', 'photo', 
                 'department', 'supplier', 'price', 'stock', 'prescription_required']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'instruction': forms.Textarea(attrs={'rows': 3}),
            'price': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'stock': forms.NumberInput(attrs={'min': 0}),
        }

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'phone', 'email', 'address', 'delivery_time']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'delivery_time': forms.NumberInput(attrs={'min': 1}),
        }

class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone', 'date_of_birth', 'photo']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

class EmployeeProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone', 'photo']