from django.apps import AppConfig

class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"

    def ready(self):
        import os
        # Ye check zaroori hai taaki Django reloader do baar thread na chalu karde
        if os.environ.get('RUN_MAIN'):
            from .utils import start_deadline_checker
            start_deadline_checker()