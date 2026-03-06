web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
worker: celery -A app.workers.celery_worker worker --loglevel=info --concurrency=${CELERY_CONCURRENCY:-2}
flower: celery --broker=${CELERY_BROKER_URL:-redis://localhost:6379/0} flower --port=${FLOWER_PORT:-5555}
