# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Django 3.2 + Django REST Framework JSON API (no templates/UI) for a personal expense tracker. The Angular 17 frontend lives in a sibling directory, `../expense-web`, and consumes this API. That is why `settings.py` whitelists CORS for `localhost:4200`. This project runs directly on the host against a local Postgres, not in Docker. That is why the DB settings are hardcoded. `../expense_tracker-docker` is a separate, older copy that is not used. It has no `evcharge` app, and edits made here do not reach it.

## Commands

The test suite needs no database server. `expense_tracker/test_settings.py` switches to in-memory SQLite:

```bash
python manage.py test --settings=expense_tracker.test_settings                    # all tests
python manage.py test expense.tests.test_services --settings=expense_tracker.test_settings
python manage.py test expense.tests.test_serializers.AmountValidationTests.test_saving_amount_zero_rejected --settings=expense_tracker.test_settings
```

Without `--settings`, Django uses the main `settings.py`. Its Postgres credentials are hardcoded: `expense_tracker_db` on `127.0.0.1:5432`. So `runserver`, `migrate` and plain `manage.py test` all require that local Postgres.

```bash
python manage.py runserver
python manage.py makemigrations expense evcharge
python manage.py migrate
```

Coverage needs a `pip install -r requirements-dev.txt` first. The config file is named `coveragerc` with no leading dot, so pass it explicitly:

```bash
coverage run --rcfile=coveragerc manage.py test --settings=expense_tracker.test_settings
coverage report --rcfile=coveragerc
```

No linter or formatter is configured. Django must stay `<4.0` (see `requirements-dev.txt`).

## Architecture

There are two apps. URLs are mounted in `expense_tracker/urls.py`:
- `expense` at `/api/`: expense records and items, income, savings, monthly balance, weekly tasks, monthly tasks, task templates, and token auth (`auth_views.py`).
- `evcharge` at `/api/ev/`: vehicles and EV charging sessions. Its endpoints are documented in `evcharge/API.md`. Keep that file in sync when the EV API changes.

Some view docstrings mention `/api/expense/...` paths. These are stale. The real prefix is `/api/`.

**Views are thin; logic lives in `services.py`.** Each summary endpoint parses its query params with `services.parse_date` / `services.parse_month`. It returns 400 on `ValueError` and delegates to a `get_*_summary(..., user=...)` function that returns a plain dict. `evcharge` reuses `expense.services` helpers and does not define its own.

**Money is serialized as strings.** Summary dicts format amounts with `services.money()` (2 dp) and `evcharge.services.kwh()` (3 dp). This avoids float drift, and the frontend relies on these string values. Use the same helpers in any new summary.

**Per-user scoping is manual.** Every record model has a `user` FK. In the `expense` app this FK is nullable. Each ViewSet filters `get_queryset()` by `request.user` and sets the user in `perform_create`. `ExpenseItem` is the exception: it is global master data shared by all users. Auth is DRF `TokenAuthentication` only. `POST /api/auth/login/` returns the token.

**URL ordering matters in `expense/urls.py`.** Explicit `path()` routes such as `savings/summary/` and `tasks/summary/` must come before the router include. Otherwise the router's `<pk>` routes shadow them.

**Grouped aggregations must clear `Meta.ordering`.** Models define default ordering. If you call `.values().annotate()` without first calling `.order_by()`, the default ordering leaks into GROUP BY and splits the groups. See `get_income_summary` and `get_yearly_ev_summary` for the pattern.

### Cross-app coupling: EV charging → expenses

Every `ChargingRecord` owns a mirrored `ExpenseRecord` under the auto-created "EV Charging" `ExpenseItem`. This lets charging costs show up in normal spending totals. `evcharge.services.save_charging_record` / `delete_charging_record` keep the two in sync inside one transaction:
- They compute `total_kwh` and `total_price` server-side.
- They snapshot `battery_capacity_kwh` from the vehicle.

On the expense side, `ExpenseRecordViewSet` returns **409** on update or delete of a linked row. `ExpenseRecordSerializer.is_linked` tells the UI to send the user to `/api/ev/charges/` instead.

### Financial semantics

- Monthly and range summaries compute `balance = income_total - (expense_total + saving_total)`.
- `SavingRecord.amount` is signed: positive is a deposit, negative is a withdrawal. Zero is rejected. Expense and income amounts must be greater than 0.
- `MonthlyBalance` is a separate user-entered figure per month. `get_balance_overview` uses it as `remaining = entered balance - expenses`.
- The `IncomeRecord` docstring says income is "NOT included in any expense calculation". That is stale: income feeds the balance above.

### Task planner

- `WeeklyTask` is per day. A week runs Monday to Sunday (`services.week_bounds`).
- `MonthlyTask` is per year and month.
- Both use `status` (`pending`/`success`/`failed`), and achievement % is success / total. They also keep a separate legacy `is_done` boolean.
- New tasks are appended at the end of their day or month (`order = max + 1`). A `reorder` action takes `{"ids": [...]}`.
- `TaskTemplate.apply` copies active templates onto dates. It skips any (date, title) pair that already exists.

## Conventions

- Most modules start with a `# vX.Y.Z` header comment. It is bumped to the current release version when the file changes.
- Every model sets an explicit snake_case `db_table`.
- Migrations are committed.
- Tests live in `<app>/tests/`. Shared object builders are in `factories.py` (`make_user`, `make_expense`, `make_saving`, ...). API tests use `APITestCase` with `force_authenticate`. Week tests use the fixed dates `WEEK_MON`/`WEEK_WED`/`WEEK_SUN`.
