-- Inside Airbnb Lisbon: business questions in SQL (MySQL 8)
-- Run in MySQL Workbench after load_airbnb_mysql.py. Prices below 10 or above 1000 per night are
-- treated as data errors/outliers in the price questions; say so in the README.
-- The file covers the whole Lisbon region, so neighbourhood questions filter municipality = 'Lisboa'
-- (the city itself). Check query 11 for the exact municipality names.
USE airbnb_lisbon;

-- 0. Sanity check: rows per table
SELECT 'listings' AS tbl, COUNT(*) AS n FROM listings
UNION ALL SELECT 'hosts', COUNT(*) FROM hosts
UNION ALL SELECT 'reviews', COUNT(*) FROM reviews;

-- 1. How many listings per neighbourhood (Lisbon city) and what is the average price? (top 15)
SELECT neighbourhood,
       COUNT(*)              AS listings,
       ROUND(AVG(price), 1)  AS avg_price
FROM listings
WHERE price BETWEEN 10 AND 1000 AND municipality = 'Lisboa'
GROUP BY neighbourhood
ORDER BY listings DESC
LIMIT 15;

-- 2. Median price per neighbourhood (MySQL has no MEDIAN: use ROW_NUMBER)
WITH ranked AS (
    SELECT neighbourhood, price,
           ROW_NUMBER() OVER (PARTITION BY neighbourhood ORDER BY price) AS rn,
           COUNT(*)     OVER (PARTITION BY neighbourhood)                AS cnt
    FROM listings
    WHERE price BETWEEN 10 AND 1000 AND municipality = 'Lisboa'
)
SELECT neighbourhood, ROUND(AVG(price), 1) AS median_price, MAX(cnt) AS listings
FROM ranked
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2))
GROUP BY neighbourhood
HAVING listings >= 30
ORDER BY median_price DESC;

-- 3. Share of each room type in each Lisbon neighbourhood (neighbourhoods with 100+ listings)
WITH counts AS (
    SELECT neighbourhood, room_type, COUNT(*) AS listings
    FROM listings
    WHERE municipality = 'Lisboa'
    GROUP BY neighbourhood, room_type
),
totals AS (
    SELECT neighbourhood, room_type, listings,
           SUM(listings) OVER (PARTITION BY neighbourhood) AS total
    FROM counts
)
SELECT neighbourhood, room_type, listings,
       ROUND(100 * listings / total, 1) AS pct_of_neighbourhood
FROM totals
WHERE total >= 100
ORDER BY neighbourhood, listings DESC;

-- 4. Do hosts with several listings behave differently? (needs host_listings_count)
SELECT CASE WHEN h.host_listings_count >= 5 THEN '5+ listings'
            WHEN h.host_listings_count >= 2 THEN '2-4 listings'
            ELSE '1 listing' END AS host_type,
       COUNT(*)                  AS listings,
       ROUND(AVG(l.price), 1)    AS avg_price
FROM listings l
JOIN hosts h ON h.host_id = l.host_id
WHERE l.price BETWEEN 10 AND 1000
GROUP BY host_type
ORDER BY avg_price DESC;

-- 5. Top 10 hosts by number of listings
SELECT h.host_id, h.host_name, COUNT(*) AS listings, ROUND(AVG(l.price), 1) AS avg_price
FROM hosts h
JOIN listings l ON l.host_id = h.host_id
GROUP BY h.host_id, h.host_name
ORDER BY listings DESC
LIMIT 10;

-- 6. Superhosts vs the rest: price and rating (needs the detailed listings file)
SELECT h.host_is_superhost,
       COUNT(*)                          AS listings,
       ROUND(AVG(l.price), 1)            AS avg_price,
       ROUND(AVG(l.review_scores_rating), 2) AS avg_rating
FROM listings l
JOIN hosts h ON h.host_id = l.host_id
WHERE l.price BETWEEN 10 AND 1000 AND h.host_is_superhost IS NOT NULL
GROUP BY h.host_is_superhost;

-- 7. Seasonality: reviews per calendar month, summed over all years (reviews are a proxy for stays)
SELECT MONTH(review_date) AS month, COUNT(*) AS reviews
FROM reviews
WHERE review_date IS NOT NULL
GROUP BY MONTH(review_date)
ORDER BY month;

-- 8. Growth: reviews per year and the change from the previous year (2026 is excluded: the year is incomplete)
WITH yearly AS (
    SELECT YEAR(review_date) AS year, COUNT(*) AS reviews
    FROM reviews
    WHERE review_date IS NOT NULL AND YEAR(review_date) < 2026
    GROUP BY YEAR(review_date)
)
SELECT year, reviews,
       ROUND(100 * (reviews - LAG(reviews) OVER (ORDER BY year)) / LAG(reviews) OVER (ORDER BY year), 1) AS pct_change
FROM yearly
ORDER BY year;

-- 9. Does a higher price mean a better rating? Average rating by price quartile
WITH q AS (
    SELECT price, review_scores_rating,
           NTILE(4) OVER (ORDER BY price) AS price_quartile
    FROM listings
    WHERE price BETWEEN 10 AND 1000 AND review_scores_rating IS NOT NULL
)
SELECT price_quartile,
       MIN(price) AS min_price, MAX(price) AS max_price,
       ROUND(AVG(review_scores_rating), 2) AS avg_rating,
       COUNT(*) AS listings
FROM q
GROUP BY price_quartile
ORDER BY price_quartile;

-- 10. Which Lisbon neighbourhoods get the most reviews per listing? (min 50 listings)
SELECT l.neighbourhood,
       COUNT(DISTINCT l.id)                         AS listings,
       COUNT(r.review_id)                           AS reviews,
       ROUND(COUNT(r.review_id) / COUNT(DISTINCT l.id), 1) AS reviews_per_listing
FROM listings l
LEFT JOIN reviews r ON r.listing_id = l.id
WHERE l.municipality = 'Lisboa'
GROUP BY l.neighbourhood
HAVING listings >= 50
ORDER BY reviews_per_listing DESC
LIMIT 10;

-- 11. Which municipalities does the file cover? Listings and average price for each
SELECT municipality,
       COUNT(*)             AS listings,
       ROUND(AVG(CASE WHEN price BETWEEN 10 AND 1000 THEN price END), 1) AS avg_price
FROM listings
GROUP BY municipality
ORDER BY listings DESC;
