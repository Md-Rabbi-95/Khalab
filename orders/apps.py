# orders/apps.py (or a small core app's AppConfig.ready)
from django.apps import AppConfig
from django.db.backends.signals import connection_created

class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orders'

    def ready(self):
        def _set_sqlite_pragmas(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                cursor = connection.cursor()
                cursor.execute('PRAGMA journal_mode=WAL;')     
                cursor.execute('PRAGMA busy_timeout=30000;')    
        connection_created.connect(_set_sqlite_pragmas)
