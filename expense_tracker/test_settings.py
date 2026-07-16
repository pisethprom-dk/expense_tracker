# test_settings.py
# Run the suite anywhere (no Postgres required):
#     python manage.py test --settings=expense_tracker.test_settings
#
# Inherits everything from the normal settings and only swaps the database
# for an in-memory SQLite instance. money() in services.py is already
# SQLite-safe, so summary math behaves identically.
from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Faster password hashing during tests.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
