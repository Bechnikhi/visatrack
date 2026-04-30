FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN mkdir -p logs media staticfiles

RUN python manage.py collectstatic --noinput 2>/dev/null || true

RUN python manage.py migrate --noinput

RUN python manage.py shell -c "from apps.users.models import User; User.objects.create_superuser(email='admin@visatrack.app', full_name='Admin', password='Admin@1234', role='superadmin') if not User.objects.filter(email='admin@visatrack.app').exists() else print('ok')"

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]