#!/usr/bin/env bash

# Start Celery worker in the background
celery -A silleconfig worker --loglevel=info --concurrency=2 &

# Start Gunicorn server
gunicorn silleconfig.wsgi:application
