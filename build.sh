#!/bin/bash
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py shell -c "
from apps.users.models import User
if not User.objects.filter(email='admin@visatrack.app').exists():
    User.objects.create_superuser(email='admin@visatrack.app', full_name='Admin', password='Admin@1234', role='superadmin')
"