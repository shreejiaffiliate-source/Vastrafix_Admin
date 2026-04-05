import os
from celery import Celery

# 1. Django settings ko Celery ke liye set karein
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vastrafix.settings')

# 2. Celery app create karein
app = Celery('vastrafix')

# 3. Settings file se configuration load karein (CELERY_ prefix wali settings)
app.config_from_object('django.conf:settings', namespace='CELERY')

# 4. Saare installed apps (jaise orders, accounts) se tasks.py ko scan karo
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')