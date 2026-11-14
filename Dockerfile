FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# DejaVu fonts: Vietnamese glyphs for the credit memo PDF. gettext: compiles the translations.
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core gettext \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip

COPY requirements.txt requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files with hashed, compressed names for WhiteNoise. Settings
# need a secret and a database password to load; these values are only for this step.
ENV DJANGO_STATIC_MANIFEST=true
RUN DJANGO_SECRET_KEY=compilemessages POSTGRES_PASSWORD=compilemessages python manage.py compilemessages --ignore '.venv/*'
RUN DJANGO_SECRET_KEY=collectstatic POSTGRES_PASSWORD=collectstatic python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 app && mkdir -p /app/media && chown -R app /app/media
USER app

EXPOSE 8000
# WEB_CONCURRENCY sets the number of workers (gunicorn reads it).
CMD ["gunicorn", "lws.wsgi:application", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--timeout", "60"]
