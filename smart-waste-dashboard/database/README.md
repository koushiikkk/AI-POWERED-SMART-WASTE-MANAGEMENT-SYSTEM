# Database — Smart Waste Management Dashboard

## Database

MySQL — `smart_waste_db`

## Tables

| Table | Purpose |
|---|---|
| `locations` | Physical waste collection points with capacity and current fill level |
| `waste_records` | Historical time-series log of waste level readings per location |
| `collection_records` | Tracks waste collection operations through their lifecycle |

## Relationships

```
locations 1 ──── N waste_records      (location_id → locations.id)
locations 1 ──── N collection_records  (location_id → locations.id)
```

## Status Bands (Derived)

| Band | Fill % |
|---|---|
| LOW | 0–50% |
| MEDIUM | 51–75% |
| HIGH | 76–90% |
| CRITICAL | 91–100% |

Status is stored in `locations.status` but derived/updated by backend business logic.

## Collection Lifecycle

`pending` → `assigned` → `in_progress` → `completed`

## Users Table

Deferred — authentication is P2/optional.

## Setup

```sql
mysql -u root -p < database/schema.sql
mysql -u root -p smart_waste_db < database/seed.sql
```

## API Contract (for future backend modules)

These tables will be consumed by FastAPI endpoints:

- `GET/POST /api/locations` — CRUD on locations
- `GET/POST/PATCH /api/collections` — collection lifecycle
- `GET /api/dashboard/summary` — aggregate stats
- `GET /api/analytics/trend` — waste level trends
- `GET /api/smart/recommendations` — priority-ranked collection list
