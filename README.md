# Expense Tracker API

Django 3.2 + Django REST Framework JSON API for the expense tracker. The Angular frontend (`../expense-web`) calls it at `http://localhost:8000/api/`.

## Run with Docker

```bash
cp .env.example .env              # then set DJANGO_SECRET_KEY and POSTGRES_PASSWORD
docker compose up -d --build      # migrations run automatically on start
docker compose exec web python manage.py createsuperuser
```

- API: http://localhost:8000/api/
- Admin: http://localhost:8000/admin/
- Logs: `docker compose logs -f web`
- Stop: `docker compose down`. This keeps the data. `docker compose down -v` also **deletes the database**.

There are two services:

- `web` runs Django under gunicorn.
- `db` runs PostgreSQL 17 and keeps its data in the `pgdata17` volume.

The database publishes no port. To open a SQL shell:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

The `POSTGRES_*` values in `.env` only take effect the first time the database starts on an empty volume. Changing them later does not change the existing database.

### Development mode

This mounts the source into the container and runs `runserver` with `DEBUG` on, so code edits reload without a rebuild:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Rebuild after changing `requirements.txt`.

### Tests

The tests use in-memory SQLite, so the `db` service is not needed:

```bash
docker compose run --rm --no-deps web python manage.py test --settings=expense_tracker.test_settings
```

This runs the code baked into the image. To test your working tree, run `docker compose build` first, or add the two `-f` flags from development mode.

### Import data from the host Postgres

The database container starts empty. To bring over the data from the local Postgres this project used before:

```bash
# 1. Dump the host database. The host Postgres must be running.
pg_dump --no-owner --no-privileges -h 127.0.0.1 -U piseth expense_tracker_db > expense_backup.sql

# 2. Start only the database, before the API has migrated it.
docker compose up -d --wait db

# 3. Load the dump.
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < expense_backup.sql

# 4. Start the API. Migrate applies anything newer than the dump.
docker compose up -d --build
```

Step 3 needs an empty database. If the API has already started once, run `docker compose down -v` first. That deletes the container's database, not the host one.

## Run on the host (without Docker)

With no env vars set, the settings fall back to the local Postgres (`expense_tracker_db` on `127.0.0.1:5432`):

```bash
python manage.py runserver
python manage.py test --settings=expense_tracker.test_settings
```

## Configuration

| Variable | Default (host run) | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | the old dev key | Django secret key |
| `DJANGO_DEBUG` | `True` | `True`/`False` |
| `DJANGO_ALLOWED_HOSTS` | `*` | comma-separated host names |
| `POSTGRES_DB` | `expense_tracker_db` | database name |
| `POSTGRES_USER` | `piseth` | database user |
| `POSTGRES_PASSWORD` | the old dev password | database password |
| `POSTGRES_HOST` | `127.0.0.1` | compose sets this to `db` |
| `POSTGRES_PORT` | `5432` | database port |
| `DJANGO_STATIC_ROOT` | `./staticfiles` | the image sets this to `/srv/static` |
