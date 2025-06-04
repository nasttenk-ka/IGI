from django.urls import path, re_path
from . import views, views_api

app_name = 'pharmacy'

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/customer/', views.edit_customer_profile, name='edit_customer_profile'),
    path('profile/edit/employee/', views.edit_employee_profile, name='edit_employee_profile'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('pickup-points/', views.pickup_points, name='pickup_points'),
    path('sales/', views.sales, name='sales'),
    
    # Supplier CRUD
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/create/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:pk>/', views.supplier_detail, name='supplier_detail'),
    path('suppliers/<int:pk>/update/', views.supplier_update, name='supplier_update'),
    path('suppliers/<int:pk>/delete/', views.supplier_delete, name='supplier_delete'),
    
    # Medication CRUD
    path('medications/', views.medication_list, name='medication_list'),
    path('medications/create/', views.medication_create, name='medication_create'),
    path('medications/<int:pk>/', views.medication_detail, name='medication_detail'),
    path('medications/<int:pk>/update/', views.medication_update, name='medication_update'),
    path('medications/<int:pk>/delete/', views.medication_delete, name='medication_delete'),
    
    path('order/create/', views.create_order, name='create_order'),
    path('order/<int:pk>/', views.order_detail, name='order_detail'),
    path('about/', views.about, name='about'),
    path('news/', views.news, name='news'),
    path('faq/', views.faq, name='faq'),
    path('contacts/', views.contacts, name='contacts'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('vacancies/', views.vacancies, name='vacancies'),
    path('reviews/', views.reviews, name='reviews'),
    path('reviews/edit/', views.edit_review, name='edit_review'),
    path('promocodes/', views.promocodes, name='promocodes'),
    path('products/', views.product_list, name='product_list'),
    path('products/<slug:category_slug>/', views.product_list, name='product_list_by_category'),
    re_path(r'^products/(?P<id>\d+)/(?P<slug>[-\w]+)/$', views.product_detail, name='product_detail'),

    # API endpoints
    path('api/weather/minsk/', views_api.get_minsk_weather, name='api_weather_minsk'),
]