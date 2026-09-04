# RideSync — Assignment 1 (Project 2)

PostgreSQL + MongoDB persistence for a global ride-hailing network. No application frontend; all work is schema, indexes, procedures, aggregations, seeders, and query plans.

- **Course:** CS6.302 Software System Development
- **Project:** 2 — RideSync
- **Team number:** 1
- **GitHub:** https://github.com/kushlalve07/2026201061_a1
- **Final commit hash:** `b5843a6`

## Repository layout

```
README.md
docs/relational_erd.png
docs/mongo_schema_map.json
sql/01_schema_ddl.sql
sql/02_indexes.sql
sql/03_triggers_and_audit.sql
sql/04_stored_procedures.sql
sql/05_materialized_views.sql
sql/06_window_analytics.sql
mongo/01_collections_and_indexes.js
mongo/02_workflow3_geonear.js
mongo/03_workflow4_facet.js
data_generation/postgres_seeder.py
data_generation/mongo_seeder.py
data_generation/requirements.txt
performance/postgres_explain_analyzes.txt
performance/mongo_execution_stats.json
```

## Assumptions

- Primary keys are UUID via `gen_random_uuid()` (PostgreSQL 13+). No `uuid-ossp`.
- Trip status `IN_TRANSIT` uses an underscore (SQL token). The brief writes “IN TRANSIT”.
- Workflow 1 escrow is a debit of `riders.wallet_balance` by `fare_amount`. There is no extra escrow column. The audit trigger records the DEBIT.
- `wallet_audit_logs` is append-only (trigger blocks UPDATE/DELETE). Rows are produced by `AFTER UPDATE OF wallet_balance` on `riders`, not by bulk INSERT into the log table.
- Materialized view `vehicle_lifetime_stats` counts **COMPLETED** trips only for trip count and earnings.
- Partial unique index `idx_active_rider_trip` uses `REQUESTED` / `IN_TRANSIT` so a rider has at most one active trip.
- Mongo GeoJSON is `[longitude, latitude]`. Telemetry pings are clustered around San Francisco `[-122.4194, 37.7749]` so Workflow 3’s 5 km `$geoNear` hits.
- TTL on `TelemetryPings.created_at` is 7200 seconds (2 hours). Seed `created_at` is within the last 90 minutes so pings survive long enough to capture `explain`. Re-seed before a viva if TTL has expired.
- Workflow 4 `$match` is `rating >= 1` so the pipeline uses index `rating_1` (same pipeline as `performance/mongo_execution_stats.json`).
- No Docker. Local PostgreSQL 13+ and MongoDB 7 + `mongosh`.
- Python dependencies: `data_generation/requirements.txt`.

## Setup

### PostgreSQL

Install PostgreSQL and add `psql` to PATH. As superuser `postgres`:

```sql
CREATE USER ridesync WITH PASSWORD 'ridesync';
CREATE DATABASE ridesync OWNER ridesync;
```

Connect as `ridesync` to database `ridesync` (so that user owns the objects), then:

```sql
\i sql/01_schema_ddl.sql
\i sql/02_indexes.sql
\i sql/03_triggers_and_audit.sql
\i sql/04_stored_procedures.sql
\i sql/05_materialized_views.sql
```

From PowerShell (project root), if `psql` is on PATH:

```powershell
$env:PGPASSWORD = "ridesync"
psql -h localhost -p 5432 -U ridesync -d ridesync -f sql/01_schema_ddl.sql
psql -h localhost -p 5432 -U ridesync -d ridesync -f sql/02_indexes.sql
psql -h localhost -p 5432 -U ridesync -d ridesync -f sql/03_triggers_and_audit.sql
psql -h localhost -p 5432 -U ridesync -d ridesync -f sql/04_stored_procedures.sql
psql -h localhost -p 5432 -U ridesync -d ridesync -f sql/05_materialized_views.sql
```

ERD: [docs/relational_erd.png](docs/relational_erd.png)

### MongoDB

```powershell
mongosh ridesync mongo/01_collections_and_indexes.js
```

Creates `VehicleMetadata`, `TripReviews`, `TelemetryPings`; `2dsphere` on `location`; TTL 7200s on `created_at`; `rating` index on reviews.

Schema map: [docs/mongo_schema_map.json](docs/mongo_schema_map.json)

### Seed (Step 4)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r data_generation/requirements.txt

python data_generation/postgres_seeder.py --reset
python data_generation/mongo_seeder.py --reset
```

`--reset` truncates / deletes existing seed rows first. Expected:

| Store | Minimum |
| --- | --- |
| `trips` | ≥ 50,000 |
| `wallet_audit_logs` | ≥ 100,000 (via wallet UPDATE trigger) |
| `TelemetryPings` | ≥ 500,000 |

Then:

```sql
SELECT refresh_vehicle_lifetime_stats();
```

`sql/06_window_analytics.sql` is a **query**, not DDL. Run it only after seed.

## Workflows

### Workflow 1 — atomic booking (`sql/04_stored_procedures.sql`)

`sp_atomic_booking`: `REPEATABLE READ`, debit wallet (escrow), insert `REQUESTED` trip, commit. CHECK / unique / missing rider-or-vehicle failures roll back (`p_status` explains why).

```sql
CALL sp_atomic_booking('<rider_uuid>', '<vehicle_uuid>', 10.00, NULL, NULL);
```

Pick a rider with no `REQUESTED`/`IN_TRANSIT` trip. Oversize fare should set `ROLLED_BACK: insufficient wallet balance` and leave no trip.

### Workflow 2 — window analytics (`sql/06_window_analytics.sql`)

CTEs: daily completed fare per vehicle, 7-day moving average (`RANGE BETWEEN INTERVAL '6 days'`), `DENSE_RANK()` on lifetime revenue.

```sql
\i sql/06_window_analytics.sql
```

### Workflow 3 — nearest vehicle (`mongo/02_workflow3_geonear.js`)

`$geoNear` within 5 km of `[-122.4194, 37.7749]`, `is_available: true`, then `$project` and `$limit: 1`.

```powershell
mongosh ridesync mongo/02_workflow3_geonear.js
```

### Workflow 4 — review `$facet` (`mongo/03_workflow4_facet.js`)

`$match rating >= 1`, then `$facet`: rating histogram, `$unwind` tags, overall average.

```powershell
mongosh ridesync mongo/03_workflow4_facet.js
```

## Performance proofs (Workflows 2, 3, 4)

Raw logs: [performance/postgres_explain_analyzes.txt](performance/postgres_explain_analyzes.txt), [performance/mongo_execution_stats.json](performance/mongo_execution_stats.json).

### Workflow 2 — `EXPLAIN (ANALYZE, BUFFERS)`

Completed trips are read with **Index Only Scan** on partial covering index `idx_trips_completed_vehicle_date` (`WHERE status = 'COMPLETED'`). Not a sequential scan of `trips`. `Seq Scan on vehicles` is the 500-row fleet table.

```
QUERY PLAN
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 Sort  (cost=16401.15..16523.14 rows=48797 width=132) (actual time=100.475..101.366 rows=29980 loops=1)
   Sort Key: r.revenue_rank, daily_revenue.vehicle_id, daily_revenue.revenue_date
   Sort Method: quicksort  Memory: 3110kB
   Buffers: shared hit=401
   CTE daily_revenue
     ->  GroupAggregate  (cost=8.56..5797.02 rows=48797 width=52) (actual time=0.200..31.547 rows=29980 loops=1)
           Group Key: trips.vehicle_id, (date(trips.created_at))
           Buffers: shared hit=397
           ->  Incremental Sort  (cost=8.56..4697.51 rows=49007 width=26) (actual time=0.191..17.291 rows=49001 loops=1)
                 Sort Key: trips.vehicle_id, (date(trips.created_at))
                 Presorted Key: trips.vehicle_id
                 Full-sort Groups: 500  Sort Method: quicksort  Average Memory: 28kB  Peak Memory: 28kB
                 Pre-sorted Groups: 500  Sort Method: quicksort  Average Memory: 30kB  Peak Memory: 30kB
                 Buffers: shared hit=397
                 ->  Index Only Scan using idx_trips_completed_vehicle_date on trips  (cost=0.41..2454.04 rows=49007 width=26) (actual time=0.112..8.386 rows=49001 loops=1)
                       Heap Fetches: 0
                       Buffers: shared hit=397
   ->  Hash Join  (cost=1253.36..3465.19 rows=48797 width=132) (actual time=41.432..85.162 rows=29980 loops=1)
         Hash Cond: (r.vehicle_id = v.id)
         Buffers: shared hit=401
         ->  Hash Join  (cost=1238.11..3320.76 rows=48797 width=140) (actual time=41.262..80.342 rows=29980 loops=1)
               Hash Cond: (daily_revenue.vehicle_id = r.vehicle_id)
               Buffers: shared hit=397
               ->  WindowAgg  (cost=0.04..1951.88 rows=48797 width=84) (actual time=0.222..33.580 rows=29980 loops=1)
                     Buffers: shared hit=5
                     ->  CTE Scan on daily_revenue  (cost=0.00..975.94 rows=48797 width=52) (actual time=0.202..1.751 rows=29980 loops=1)
                           Buffers: shared hit=5
               ->  Hash  (cost=1235.57..1235.57 rows=200 width=56) (actual time=41.029..41.032 rows=500 loops=1)
                     Buckets: 1024  Batches: 1  Memory Usage: 44kB
                     Buffers: shared hit=392
                     ->  Subquery Scan on r  (cost=1230.09..1235.57 rows=200 width=56) (actual time=40.753..40.972 rows=500 loops=1)
                           Buffers: shared hit=392
                           ->  WindowAgg  (cost=1230.09..1233.57 rows=200 width=56) (actual time=40.753..40.936 rows=500 loops=1)
                                 Buffers: shared hit=392
                                 ->  Sort  (cost=1230.07..1230.57 rows=200 width=48) (actual time=40.746..40.769 rows=500 loops=1)
                                       Sort Key: (sum(daily_revenue_1.daily_total)) DESC
                                       Sort Method: quicksort  Memory: 48kB
                                       Buffers: shared hit=392
                                       ->  GroupAggregate  (cost=0.00..1222.43 rows=200 width=48) (actual time=0.137..40.610 rows=500 loops=1)
                                             Group Key: daily_revenue_1.vehicle_id
                                             Buffers: shared hit=392
                                             ->  CTE Scan on daily_revenue daily_revenue_1  (cost=0.00..975.94 rows=48797 width=48) (actual time=0.000..36.733 rows=29980 loops=1)
                                                   Buffers: shared hit=392
         ->  Hash  (cost=9.00..9.00 rows=500 width=24) (actual time=0.160..0.160 rows=500 loops=1)
               Buckets: 1024  Batches: 1  Memory Usage: 36kB
               Buffers: shared hit=4
               ->  Seq Scan on vehicles v  (cost=0.00..9.00 rows=500 width=24) (actual time=0.017..0.076 rows=500 loops=1)
                     Buffers: shared hit=4
 Planning:
   Buffers: shared hit=61
 Planning Time: 4.899 ms
 Execution Time: 102.829 ms
```

~49,001 completed trips from the index; ~103 ms.

### Workflow 3 — `explain("executionStats")`

Full JSON: `performance/mongo_execution_stats.json` → `Workflow_3_GeoNear`.

- Namespace: `ridesync.TelemetryPings`
- Winning plan: **`GEO_NEAR_2DSPHERE`** on `location_2dsphere`, child **`IXSCAN`** (not `COLLSCAN`)
- `query`: `is_available: true`, `maxDistance: 5000`, near `[-122.4194, 37.7749]`
- `nReturned`: 6251 geo candidates; pipeline ends with `$limit: 1`
- `totalDocsExamined`: 18778
- `executionTimeMillis`: 90

```json
"winningPlan": {
  "stage": "FETCH",
  "filter": { "is_available": { "$eq": true } },
  "inputStage": {
    "stage": "GEO_NEAR_2DSPHERE",
    "keyPattern": { "location": "2dsphere" },
    "indexName": "location_2dsphere",
    "inputStages": [
      {
        "stage": "FETCH",
        "inputStage": {
          "stage": "IXSCAN",
          "keyPattern": { "location": "2dsphere" },
          "indexName": "location_2dsphere"
        }
      }
    ]
  }
}
```

```json
"executionStats": {
  "executionSuccess": true,
  "nReturned": 6251,
  "executionTimeMillis": 90,
  "totalKeysExamined": 10937,
  "totalDocsExamined": 18778
}
```

### Workflow 4 — `explain("executionStats")`

Full JSON: same file → `Workflow_4_Facet`. Matches `mongo/03_workflow4_facet.js`.

- Namespace: `ridesync.TripReviews`
- `$match`: `rating >= 1`
- Winning plan: **`IXSCAN`** on `rating_1` (not `COLLSCAN`)
- `$facet`: `rating_distribution`, `driver_feedback_tags` (`$unwind`), `overall_average`
- `nReturned`: 25000
- `executionTimeMillis`: 136

```json
"parsedQuery": { "rating": { "$gte": 1 } },
"winningPlan": {
  "stage": "PROJECTION_SIMPLE",
  "inputStage": {
    "stage": "FETCH",
    "inputStage": {
      "stage": "IXSCAN",
      "keyPattern": { "rating": 1 },
      "indexName": "rating_1",
      "indexBounds": { "rating": ["[1, inf.0]"] }
    }
  }
}
```

```json
"executionStats": {
  "executionSuccess": true,
  "nReturned": 25000,
  "executionTimeMillis": 136,
  "totalKeysExamined": 25000,
  "totalDocsExamined": 25000
}
```
