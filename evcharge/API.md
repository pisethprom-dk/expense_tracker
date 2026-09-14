# EV Charge Report API — v1.0.0

All endpoints require `Authorization: Token <key>` and are scoped to the
authenticated user. Money and kWh values are returned as **strings** to avoid
float drift, matching the existing expense API convention.

## Vehicles

`GET|POST /api/ev/vehicles/`
`GET|PUT|PATCH|DELETE /api/ev/vehicles/{id}/`

Query: `?active=true|false`

| Field | Type | Required |
|---|---|---|
| `brand` | string(100) | yes |
| `plate_number` | string(20) | no |
| `color` | string(50) | no |
| `battery_capacity_kwh` | decimal, > 0 | yes |
| `is_active` | bool | no (default true) |
| `display_name` | string | read-only — `"Tesla (1AA-1234)"` |

A vehicle with charging history cannot be deleted (`PROTECT`). Set
`is_active=false` to retire it instead.

## Charging records

`GET|POST /api/ev/charges/`
`GET|PUT|PATCH|DELETE /api/ev/charges/{id}/`

Query: `?vehicle=<id>`, `?charger_type=AC|DC`, `?month=YYYY-MM`,
`?from=YYYY-MM-DD`, `?to=YYYY-MM-DD`. Malformed dates return **400**.

| Field | Type | Notes |
|---|---|---|
| `vehicle` | int | must belong to the caller |
| `charger_type` | `"AC"` \| `"DC"` | |
| `charge_date` | date | optional; defaults to today |
| `location` | string(255) | optional |
| `start_percent` | decimal 0–100 | |
| `end_percent` | decimal 0–100 | must be **>** `start_percent` |
| `price_per_kwh` | decimal, > 0 | 4 dp; zero is rejected |
| `battery_capacity_kwh` | decimal | **read-only** — snapshot from the vehicle |
| `total_kwh` | decimal (3 dp) | **read-only** — computed |
| `total_price` | decimal (2 dp) | **read-only** — computed |
| `expense_record_id` | int \| null | **read-only** — the linked expense row |

```
total_kwh   = (end_percent - start_percent) / 100 * battery_capacity_kwh
total_price = total_kwh * price_per_kwh
```

`battery_capacity_kwh` is copied onto the record when it is saved, so editing a
vehicle's capacity later never re-prices past sessions.

## Reports

`GET /api/ev/summary/monthly/?month=YYYY-MM` (default: current month)

```json
{
  "month": "2026-03",
  "session_count": 2,
  "total_kwh": "75.000",
  "total_price": "20.25",
  "vehicles": [
    {"vehicle_id": 1, "brand": "Tesla", "plate_number": "1AA-1234",
     "session_count": 1, "total_kwh": "45.000", "total_price": "11.25"}
  ]
}
```

`GET /api/ev/summary/yearly/?year=YYYY` (default: current year)

Same totals plus a `months[]` array (only months with activity) and the same
`vehicles[]` breakdown for the whole year.

## Expense tracker link

Every charging session creates a mirrored `ExpenseRecord` under the
auto-created **"EV Charging"** item, so charging shows up in the normal
monthly spend figures. Create, update and delete stay in sync inside one
transaction.

Because the session owns that row, `/api/records/{id}/` returns **409 Conflict**
on `PUT`/`PATCH`/`DELETE` for linked rows. The expense serializer now exposes a
read-only **`is_linked`** boolean so the UI can disable the edit control and
route the user to `/api/ev/charges/` instead.
