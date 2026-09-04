--   psql -U ridesync -d ridesync -f sql/05_materialized_views.sql
--   SELECT refresh_vehicle_lifetime_stats();

CREATE MATERIALIZED VIEW vehicle_lifetime_stats AS
SELECT
    v.id            AS vehicle_id,
    v.license_plate,
    v.class,
    v.is_active,
    COUNT(t.id) FILTER (WHERE t.status = 'COMPLETED')     AS lifetime_trip_count,
    COALESCE(
        SUM(t.fare_amount) FILTER (WHERE t.status = 'COMPLETED'),
        0
    )                                                     AS total_earnings
FROM vehicles v
LEFT JOIN trips t ON t.vehicle_id = v.id
GROUP BY v.id, v.license_plate, v.class, v.is_active;

CREATE UNIQUE INDEX idx_vehicle_lifetime_stats_vehicle_id
    ON vehicle_lifetime_stats (vehicle_id);

CREATE OR REPLACE FUNCTION refresh_vehicle_lifetime_stats()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY vehicle_lifetime_stats;
END;
$$;
