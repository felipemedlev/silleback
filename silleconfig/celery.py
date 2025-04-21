import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
# Make sure 'silleconfig.settings' matches your actual settings file path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'silleconfig.settings')

# Create the Celery application instance
# The first argument is the name of the current module, used for naming tasks etc.
# It's conventional to name it after the project package.
app = Celery('silleconfig')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix in settings.py.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
# This will automatically discover tasks in files named 'tasks.py' within your apps.
app.autodiscover_tasks()


# Optional: Example debug task (can be removed later)
@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')