from django.db import migrations

def delete_reviews_without_users(apps, schema_editor):
    Review = apps.get_model('pharmacy', 'Review')
    Review.objects.filter(user__isnull=True).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('pharmacy', '0012_alter_review_user'),
    ]

    operations = [
        migrations.RunPython(delete_reviews_without_users, reverse_code=migrations.RunPython.noop),
    ] 