-- =====================================================================
-- Urban Pulse NYC: the 15 analyst investigations, in MySQL 8 SQL
-- Every query starts with "WITH base AS (SELECT * FROM service_requests)".
-- Run as-is in MySQL Workbench for the whole dataset. The Streamlit app
-- swaps that one line for a filtered version (date / borough / complaint
-- type) using parameterised values, so the same SQL powers the dashboard.
-- Medians and quartiles use the nearest-rank method with ROW_NUMBER(),
-- because MySQL has no MEDIAN() function.
-- =====================================================================

-- name: T01
-- title: Total distinct request volume
WITH base AS (SELECT * FROM service_requests)
SELECT COUNT(*)                   AS total_rows,
       COUNT(DISTINCT unique_key) AS distinct_requests,
       MIN(created_date)          AS first_created,
       MAX(created_date)          AS last_created,
       COUNT(DISTINCT created_month) AS months_covered
FROM base;

-- name: T02
-- title: Top 10 complaint categories by count
WITH base AS (SELECT * FROM service_requests)
SELECT complaint_type,
       COUNT(*) AS requests,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct
FROM base
GROUP BY complaint_type
ORDER BY requests DESC
LIMIT 10;

-- name: T03
-- title: Agency workload distribution
WITH base AS (SELECT * FROM service_requests)
SELECT agency,
       MAX(agency_name) AS agency_name,
       COUNT(*) AS requests,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct,
       COUNT(DISTINCT complaint_type) AS complaint_types_handled
FROM base
GROUP BY agency
ORDER BY requests DESC;

-- name: T04
-- title: Request volume by borough
WITH base AS (SELECT * FROM service_requests)
SELECT COALESCE(borough, 'MISSING') AS borough,
       COUNT(*) AS requests,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct
FROM base
GROUP BY COALESCE(borough, 'MISSING')
ORDER BY requests DESC;

-- name: T05
-- title: Monthly request trend
WITH base AS (SELECT * FROM service_requests)
SELECT created_month,
       COUNT(*) AS requests,
       ROUND(100 * AVG(is_closed), 2) AS closed_pct
FROM base
GROUP BY created_month
ORDER BY created_month;

-- name: T06
-- title: Demand by weekday and hour
WITH base AS (SELECT * FROM service_requests)
SELECT created_weekday_num,
       created_weekday,
       created_hour,
       COUNT(*) AS requests,
       SUM(flag_midnight_created = 0) AS requests_excl_midnight_stamps
FROM base
GROUP BY created_weekday_num, created_weekday, created_hour
ORDER BY created_weekday_num, created_hour;

-- name: T07
-- title: Distribution of recorded request statuses
WITH base AS (SELECT * FROM service_requests)
SELECT COALESCE(status, 'MISSING') AS status,
       COUNT(*) AS requests,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct,
       SUM(closed_date IS NOT NULL) AS with_closed_date
FROM base
GROUP BY COALESCE(status, 'MISSING')
ORDER BY requests DESC;

-- name: T08
-- title: Descriptive statistics for valid resolution durations (hours)
WITH base AS (SELECT * FROM service_requests),
r AS (
    SELECT resolution_hours AS h,
           ROW_NUMBER() OVER (ORDER BY resolution_hours) AS rn,
           COUNT(*) OVER () AS cnt
    FROM base
    WHERE resolution_hours IS NOT NULL
)
SELECT MAX(cnt)                    AS n_valid,
       ROUND(AVG(h), 2)            AS mean_h,
       MAX(CASE WHEN rn = CEIL(0.50 * cnt) THEN h END) AS median_h,
       MIN(h)                      AS min_h,
       MAX(CASE WHEN rn = CEIL(0.25 * cnt) THEN h END) AS q1_h,
       MAX(CASE WHEN rn = CEIL(0.75 * cnt) THEN h END) AS q3_h,
       MAX(h)                      AS max_h,
       ROUND(MAX(h) - MIN(h), 2)   AS range_h,
       ROUND(VAR_SAMP(h), 2)       AS variance_h2,
       ROUND(STDDEV_SAMP(h), 2)    AS std_h
FROM r;

-- name: T09
-- title: Median resolution duration by complaint category (min 50 closed)
WITH base AS (SELECT * FROM service_requests),
r AS (
    SELECT complaint_type, resolution_hours AS h,
           ROW_NUMBER() OVER (PARTITION BY complaint_type ORDER BY resolution_hours) AS rn,
           COUNT(*)     OVER (PARTITION BY complaint_type) AS cnt
    FROM base
    WHERE resolution_hours IS NOT NULL
)
SELECT complaint_type,
       MAX(cnt) AS n_valid,
       MAX(CASE WHEN rn = CEIL(0.5 * cnt) THEN h END) AS median_h,
       ROUND(AVG(h), 2) AS mean_h
FROM r
GROUP BY complaint_type
HAVING n_valid >= 50
ORDER BY median_h DESC;

-- name: T10
-- title: Median resolution duration by agency (min 50 closed)
WITH base AS (SELECT * FROM service_requests),
r AS (
    SELECT agency, resolution_hours AS h,
           ROW_NUMBER() OVER (PARTITION BY agency ORDER BY resolution_hours) AS rn,
           COUNT(*)     OVER (PARTITION BY agency) AS cnt
    FROM base
    WHERE resolution_hours IS NOT NULL
)
SELECT agency,
       MAX(cnt) AS n_valid,
       MAX(CASE WHEN rn = CEIL(0.5 * cnt) THEN h END) AS median_h,
       ROUND(AVG(h), 2) AS mean_h,
       ROUND(100 * AVG(h > 72), 2) AS over_72h_pct
FROM r
GROUP BY agency
HAVING n_valid >= 50
ORDER BY median_h DESC;

-- name: T11
-- title: IQR-based outlier investigation (by complaint category)
WITH base AS (SELECT * FROM service_requests),
r AS (
    SELECT resolution_hours AS h,
           ROW_NUMBER() OVER (ORDER BY resolution_hours) AS rn,
           COUNT(*) OVER () AS cnt
    FROM base WHERE resolution_hours IS NOT NULL
),
q AS (
    SELECT MAX(CASE WHEN rn = CEIL(0.25 * cnt) THEN h END) AS q1,
           MAX(CASE WHEN rn = CEIL(0.75 * cnt) THEN h END) AS q3
    FROM r
),
fences AS (SELECT q1, q3, q3 - q1 AS iqr,
                  q1 - 1.5 * (q3 - q1) AS lower_fence,
                  q3 + 1.5 * (q3 - q1) AS upper_fence FROM q)
SELECT b.complaint_type,
       COUNT(*) AS n_valid,
       SUM(b.resolution_hours > f.upper_fence OR b.resolution_hours < f.lower_fence) AS outliers,
       ROUND(100 * AVG(b.resolution_hours > f.upper_fence OR b.resolution_hours < f.lower_fence), 2) AS outlier_pct,
       ROUND(MAX(f.upper_fence), 2) AS upper_fence_h,
       ROUND(MAX(b.resolution_hours), 1) AS longest_h
FROM base b CROSS JOIN fences f
WHERE b.resolution_hours IS NOT NULL
GROUP BY b.complaint_type
HAVING outliers > 0
ORDER BY outliers DESC
LIMIT 15;

-- name: T12a
-- title: Resolution-time skewness (moment coefficient)
WITH base AS (SELECT * FROM service_requests),
s AS (SELECT AVG(resolution_hours) AS m, STDDEV_POP(resolution_hours) AS sd
      FROM base WHERE resolution_hours IS NOT NULL)
SELECT COUNT(*) AS n_valid,
       ROUND(MAX(s.m), 2)  AS mean_h,
       ROUND(MAX(s.sd), 2) AS std_h,
       ROUND(AVG(POW(b.resolution_hours - s.m, 3)) / POW(MAX(s.sd), 3), 2) AS skewness
FROM base b CROSS JOIN s
WHERE b.resolution_hours IS NOT NULL;

-- name: T12b
-- title: Resolution-time distribution (duration buckets)
WITH base AS (SELECT * FROM service_requests)
SELECT CASE
         WHEN resolution_hours < 1   THEN '1. under 1 hour'
         WHEN resolution_hours < 4   THEN '2. 1-4 hours'
         WHEN resolution_hours < 24  THEN '3. 4-24 hours'
         WHEN resolution_hours < 72  THEN '4. 1-3 days'
         WHEN resolution_hours < 168 THEN '5. 3-7 days'
         WHEN resolution_hours < 720 THEN '6. 7-30 days'
         ELSE '7. over 30 days' END AS duration_bucket,
       COUNT(*) AS requests,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct
FROM base
WHERE resolution_hours IS NOT NULL
GROUP BY duration_bucket
ORDER BY duration_bucket;

-- name: T13a
-- title: Geographic concentration: borough coverage and coordinate completeness
WITH base AS (SELECT * FROM service_requests)
SELECT COALESCE(borough, 'MISSING') AS borough,
       COUNT(*) AS requests,
       SUM(flag_missing_coords = 0 AND flag_coords_outside_nyc = 0) AS usable_coords,
       ROUND(100 * AVG(flag_missing_coords = 0 AND flag_coords_outside_nyc = 0), 2) AS usable_coords_pct
FROM base
GROUP BY COALESCE(borough, 'MISSING')
ORDER BY requests DESC;

-- name: T13b
-- title: Geographic concentration: top 15 hotspots (about 1 km grid cells)
WITH base AS (SELECT * FROM service_requests),
cells AS (
    SELECT ROUND(latitude, 2) AS lat_cell, ROUND(longitude, 2) AS lon_cell,
           borough, complaint_type
    FROM base
    WHERE flag_missing_coords = 0 AND flag_coords_outside_nyc = 0
),
top_type AS (
    SELECT lat_cell, lon_cell, complaint_type,
           ROW_NUMBER() OVER (PARTITION BY lat_cell, lon_cell ORDER BY COUNT(*) DESC) AS rk
    FROM cells GROUP BY lat_cell, lon_cell, complaint_type
)
SELECT c.lat_cell, c.lon_cell, MAX(c.borough) AS borough,
       COUNT(*) AS requests,
       MAX(t.complaint_type) AS top_complaint
FROM cells c
JOIN top_type t ON t.lat_cell = c.lat_cell AND t.lon_cell = c.lon_cell AND t.rk = 1
GROUP BY c.lat_cell, c.lon_cell
ORDER BY requests DESC
LIMIT 15;

-- name: T14
-- title: Recorded closure-rate comparison by agency (min 100 requests)
WITH base AS (SELECT * FROM service_requests)
SELECT agency,
       COUNT(*) AS requests,
       SUM(is_closed) AS closed,
       COUNT(*) - SUM(is_closed) AS still_open,
       ROUND(100 * AVG(is_closed), 2) AS closure_pct
FROM base
GROUP BY agency
HAVING requests >= 100
ORDER BY closure_pct;

-- name: T15
-- title: Categories with high volume AND long median resolution
WITH base AS (SELECT * FROM service_requests),
r AS (
    SELECT complaint_type, resolution_hours AS h,
           ROW_NUMBER() OVER (PARTITION BY complaint_type ORDER BY resolution_hours) AS rn,
           COUNT(*)     OVER (PARTITION BY complaint_type) AS cnt
    FROM base WHERE resolution_hours IS NOT NULL
),
cat AS (
    SELECT complaint_type, MAX(cnt) AS n_valid,
           MAX(CASE WHEN rn = CEIL(0.5 * cnt) THEN h END) AS median_h
    FROM r GROUP BY complaint_type
),
overall AS (
    SELECT MAX(CASE WHEN rn = CEIL(0.5 * cnt) THEN h END) AS overall_median_h
    FROM (SELECT resolution_hours AS h,
                 ROW_NUMBER() OVER (ORDER BY resolution_hours) AS rn,
                 COUNT(*) OVER () AS cnt
          FROM base WHERE resolution_hours IS NOT NULL) x
),
vol AS (SELECT complaint_type, COUNT(*) AS requests,
               RANK() OVER (ORDER BY COUNT(*) DESC) AS volume_rank
        FROM base GROUP BY complaint_type)
SELECT v.complaint_type, v.requests, v.volume_rank, c.n_valid, c.median_h,
       ROUND(o.overall_median_h, 2) AS overall_median_h,
       ROUND(c.median_h / NULLIF(o.overall_median_h, 0), 1) AS times_overall_median
FROM vol v
JOIN cat c ON c.complaint_type = v.complaint_type
CROSS JOIN overall o
WHERE v.volume_rank <= 20 AND c.median_h > o.overall_median_h
ORDER BY c.median_h DESC;

-- name: KPI
-- title: Five dashboard KPIs
WITH base AS (SELECT * FROM service_requests),
r AS (
    SELECT resolution_hours AS h,
           ROW_NUMBER() OVER (ORDER BY resolution_hours) AS rn,
           COUNT(*) OVER () AS cnt
    FROM base WHERE resolution_hours IS NOT NULL
),
med AS (SELECT MAX(CASE WHEN rn = CEIL(0.5 * cnt) THEN h END) AS median_h,
               ROUND(100 * AVG(h > 72), 2) AS over_72h_pct FROM r)
SELECT (SELECT COUNT(DISTINCT unique_key) FROM base)          AS total_requests,
       (SELECT ROUND(100 * AVG(is_closed), 2) FROM base)      AS closure_pct,
       (SELECT COUNT(*) - SUM(is_closed) FROM base)           AS open_requests,
       med.median_h                                            AS median_resolution_h,
       med.over_72h_pct                                        AS over_72h_pct
FROM med;
