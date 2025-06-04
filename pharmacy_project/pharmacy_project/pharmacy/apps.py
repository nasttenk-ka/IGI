from django.apps import AppConfig

class PharmacyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pharmacy'  # Это должно соответствовать имени вашего приложения
    verbose_name = "Аптека"