from django.apps import AppConfig

class CategoryConfig(AppConfig):    # Match app name
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'category'   # Must be the folder name (lowercase)
