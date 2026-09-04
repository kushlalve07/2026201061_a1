# RideSync — Assignment 1 (Project 2)

PostgreSQL + MongoDB design for a global ride-hailing network.

- **Project:** 2 — RideSync
- **Team number:** 1
- **GitHub:** https://github.com/kushlalve07/2026201061_a1
- **Final commit hash:** _paste after last push_

## PostgreSQL setup (Step 1)

No Docker. Install [PostgreSQL 13+](https://www.postgresql.org/download/windows/) and add `psql` to PATH.

Create the role and database (connect as the `postgres` superuser):

```sql
CREATE USER ridesync WITH PASSWORD 'ridesync';
CREATE DATABASE ridesync OWNER ridesync;
```

Apply scripts in this order (skip any you already ran):

```powershell
$env:PGPASSWORD = "ridesync"
psql -U ridesync -d ridesync -f sql/01_schema_ddl.sql
psql -U ridesync -d ridesync -f sql/02_indexes.sql
psql -U ridesync -d ridesync -f sql/03_triggers_and_audit.sql
psql -U ridesync -d ridesync -f sql/04_stored_procedures.sql
psql -U ridesync -d ridesync -f sql/05_materialized_views.sql
```

In SQL Shell, after `ridesync=>`:

```sql
\i 'C:/Users/Nehal/Desktop/SSD Group Project/sql/04_stored_procedures.sql'
```

You should see `CREATE PROCEDURE`.

### Workflow 1 — atomic booking

Escrow is a **wallet debit** of `fare_amount` (no extra escrow column). The audit trigger logs the DEBIT. The trip is inserted as `REQUESTED`. If the wallet CHECK fails, both the debit and the trip are rolled back.

```sql
BEGIN ISOLATION LEVEL REPEATABLE READ;
CALL sp_atomic_booking('<rider_uuid>', '<vehicle_uuid>', 250.00, NULL);
COMMIT;
```

Replace the UUIDs with rows from `SELECT id, name, wallet_balance FROM riders;` and `SELECT id, license_plate FROM vehicles;`.

Quick check:

```sql
\dt
\di idx_active_rider_trip
SELECT * FROM vehicle_lifetime_stats;
SELECT refresh_vehicle_lifetime_stats();
```

ERD: [docs/relational_erd.png](docs/relational_erd.png)

## Assumptions (PostgreSQL)

- UUID primary keys via `gen_random_uuid()` (PostgreSQL 13+, no `uuid-ossp`).
- Trip status `IN_TRANSIT` uses an underscore so it is a single SQL token. The assignment text writes “IN TRANSIT”.
- `action_type` is constrained to `DEBIT` and `CREDIT`.
- `fare_amount` cannot be negative.
- `license_plate` is unique.
- `wallet_audit_logs` is filled by trigger `rider_wallet_audit` (`sql/03_triggers_and_audit.sql`).
- Workflow 1 escrow = debit `riders.wallet_balance` by the fare. There is no separate escrow column.
- Lifetime trip count and total earnings on `vehicle_lifetime_stats` count **COMPLETED** trips only. Requested / in-transit rides are not earnings yet.
- Partial unique index `idx_active_rider_trip` uses `IN_TRANSIT` to match the CHECK on `trips.status`.

## MongoDB

Collections, `2dsphere` + TTL indexes, and workflows 3–4 live under `mongo/`. Schema map: [docs/mongo_schema_map.json](docs/mongo_schema_map.json).

```powershell
mongosh ridesync mongo/01_collections_and_indexes.js
```

Run seeders **before** the geoNear / `$facet` scripts so those pipelines have data.

## Step 4 — data generation

Install Python deps, then seed. Postgres first (Mongo reviews reuse completed trip ids when they exist).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python data_generation/postgres_seeder.py --reset
python data_generation/mongo_seeder.py --reset
```

Omit `--reset` if the tables/collections are already empty. Expected counts:

- PostgreSQL: ≥ 50,000 `trips`, ≥ 100,000 `wallet_audit_logs`
- MongoDB: ≥ 500,000 `TelemetryPings`

After Postgres seed, refresh the view:

```sql
SELECT refresh_vehicle_lifetime_stats();
```

Then run analytics:

```sql
\i 'C:/Users/Nehal/Desktop/SSD Group Project/sql/06_window_analytics.sql'
```

```powershell
mongosh ridesync mongo/02_workflow3_geonear.js
mongosh ridesync mongo/03_workflow4_facet.js
```

500k Mongo inserts take several minutes. Telemetry `created_at` is within the last 90 minutes so the 2-hour TTL index does not wipe the pings before you capture `explain`.
