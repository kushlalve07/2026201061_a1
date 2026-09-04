--Workflow 2: Window Functions, CTEs

WITH daily_revenue AS (
    -- Total Revenue per vehicle, per calendar day.
    SELECT
        vehicle_id,
        DATE(created_at) AS revenue_date,
        SUM(fare_amount) AS daily_total
    FROM trips
    WHERE status = 'COMPLETED'
    GROUP BY vehicle_id, DATE(created_at)
),
moving_avg AS (
    -- Calculating 7 day moving average (current day + 6 preceding), per vehicle.
    SELECT
        vehicle_id, 
        revenue_date, 
        daily_total,
        ROUND(
            AVG(daily_total) OVER (
                PARTITION BY vehicle_id
                ORDER BY revenue_date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ),
        2) AS moving_avg_7day
    FROM daily_revenue
),
vehicle_ranking AS (
    --Ranking the vehicles by total revenue across the whole period.
    SELECT
        vehicle_id,
        SUM(daily_total) as total_revenue,
        DENSE_RANK() OVER (ORDER BY SUM(daily_total) DESC) AS revenue_rank
    FROM daily_revenue
    GROUP BY vehicle_id
)
SELECT
    m.vehicle_id,
    v.license_plate,
    m.revenue_date,
    m.daily_total,
    m.moving_avg_7day,
    r.total_revenue,
    r.revenue_rank
FROM moving_avg m
JOIN vehicle_ranking r ON r.vehicle_id = m.vehicle_id
JOIN vehicles v ON v.id = m.vehicle_id
ORDER BY r.revenue_rank, m.vehicle_id, m.revenue_date;