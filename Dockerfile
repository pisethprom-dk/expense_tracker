# Expense Tracker API image.
# Django 3.2 supports Python up to 3.10, so the image stays on 3.10.
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_STATIC_ROOT=/srv/static

WORKDIR /app

# psycopg2-binary bundles libpq, so no system packages are needed.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# COPY keeps host file modes, and some source files are 0600 on the host, so
# make the tree readable for the unprivileged user (the code stays root-owned).
# Then collect the admin's static files; WhiteNoise serves them.
RUN chmod -R a+rX /app \
 && python manage.py collectstatic --noinput \
 && useradd --create-home --uid 1000 app
USER app

EXPOSE 8003

# Apply pending migrations, then hand PID 1 to gunicorn.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn expense_tracker.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]
