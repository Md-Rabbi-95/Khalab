# core/apps.py
'''
from django.apps import AppConfig
from django.db.backends.signals import connection_created

def _set_sqlite_pragmas(sender, connection, **kwargs):
    """
    Apply SQLite PRAGMAs on each new DB connection.
    This avoids touching the DB during app initialization, silencing the warning.
    """
    if connection.vendor != 'sqlite':
        return
    with connection.cursor() as cursor:
        # Better concurrent writes with WAL; reasonable durability for dev
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA synchronous=NORMAL;')

class CoreConfig(AppConfig):
    name = 'core'
    verbose_name = 'Core'

    def ready(self):
        # Hook once; Django will call _set_sqlite_pragmas every time a connection is created
        connection_created.connect(_set_sqlite_pragmas, dispatch_uid="core.sqlite.pragmas")'''

#D:\Django\khalab\core\apps.py
from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.admin  