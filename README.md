# RideSync — Assignment 1 (Project 2)

PostgreSQL + MongoDB design for a global ride-hailing network.

- **Project:** 2 — RideSync
- **Team number:** _TBD_
- **GitHub:** _paste repo URL_
- **Final commit hash:** _paste after last push_

## PostgreSQL setup (Step 1)

No Docker. Install [PostgreSQL 13+](https://www.postgresql.org/download/windows/) and add `psql` to PATH.

Create the role and database (connect as the `postgres` superuser):

```sql
CREATE USER ridesync WITH PASSWORD 'ridesync';
CREATE DATABASE ridesync OWNER ridesync;
```

Apply the schema, then Step 2 index + materialized view (trigger is not in yet):

```powershell
$env:PGPASSWORD = "ridesync"
psql -U ridesync -d ridesync -f sql/01_schema_ddl.sql
psql -U ridesync -d ridesync -f sql/02_indexes.sql
psql -U ridesync -d ridesync -f sql/05_materialized_views.sql
```

Quick check:

```powershell
psql -U ridesync -d ridesync -c "\dt"
psql -U ridesync -d ridesync -c "\di idx_active_rider_trip"
psql -U ridesync -d ridesync -c "SELECT * FROM vehicle_lifetime_stats;"
```

You should see `riders`, `vehicles`, `trips`, and `wallet_audit_logs`. After trips exist, refresh stats with `SELECT refresh_vehicle_lifetime_stats();`.

ERD: [docs/relational_erd.png](docs/relational_erd.png)

## Assumptions (PostgreSQL)

- UUID primary keys via `gen_random_uuid()` (PostgreSQL 13+, no `uuid-ossp`).
- Trip status `IN_TRANSIT` uses an underscore so it is a single SQL token. The assignment text writes “IN TRANSIT”.
- `action_type` is constrained to `DEBIT` and `CREDIT`.
- `fare_amount` cannot be negative.
- `license_plate` is unique.
- `wallet_audit_logs` is created in Step 1; the audit trigger is still pending (Step 2 task 1).
- Lifetime trip count and total earnings on `vehicle_lifetime_stats` count **COMPLETED** trips only. Requested / in-transit rides are not earnings yet.
- Partial unique index `idx_active_rider_trip` uses `IN_TRANSIT` to match the CHECK on `trips.status`.

## MongoDB

Not changed in this Step 1 pass. See `mongo/`.
