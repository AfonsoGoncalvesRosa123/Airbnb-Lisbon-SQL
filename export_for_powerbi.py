"""Exports the Lisbon-city data from MySQL to two small CSV files for Power BI.

Usage:  python export_for_powerbi.py
Writes: powerbi_data/listings_lisboa.csv  and  powerbi_data/reviews_monthly.csv
"""
import getpass
from pathlib import Path

import mysql.connector
import pandas as pd

LISTINGS_SQL = """
SELECT l.id, l.neighbourhood, l.room_type, l.price, l.review_scores_rating, l.accommodates,
       l.bedrooms, l.number_of_reviews, l.availability_365, l.latitude, l.longitude,
       h.host_is_superhost, h.host_listings_count
FROM listings l
LEFT JOIN hosts h ON h.host_id = l.host_id
WHERE l.municipality = 'Lisboa' AND l.price BETWEEN 10 AND 1000
"""

REVIEWS_SQL = """
SELECT l.neighbourhood, DATE_FORMAT(r.review_date, '%Y-%m-01') AS month, COUNT(*) AS reviews
FROM reviews r
JOIN listings l ON l.id = r.listing_id
WHERE l.municipality = 'Lisboa' AND r.review_date IS NOT NULL AND r.review_date < '2026-01-01'
GROUP BY 1, 2
"""


def run(conn, sql):
    cur = conn.cursor()
    cur.execute(sql)
    df = pd.DataFrame(cur.fetchall(), columns=cur.column_names)
    cur.close()
    return df


password = getpass.getpass("MySQL password for root: ")
conn = mysql.connector.connect(host="localhost", user="root", password=password, database="airbnb_lisbon")

listings = run(conn, LISTINGS_SQL)
for c in ["price", "review_scores_rating", "latitude", "longitude"]:
    listings[c] = pd.to_numeric(listings[c])
listings["host_type"] = pd.cut(listings["host_listings_count"], [-1, 1, 4, float("inf")],
                               labels=["1 listing", "2-4 listings", "5+ listings"])
reviews = run(conn, REVIEWS_SQL)
conn.close()

out = Path("powerbi_data")
out.mkdir(exist_ok=True)
listings.to_csv(out / "listings_lisboa.csv", index=False, encoding="utf-8-sig")
reviews.to_csv(out / "reviews_monthly.csv", index=False, encoding="utf-8-sig")
print(f"listings_lisboa.csv: {len(listings)} rows | reviews_monthly.csv: {len(reviews)} rows")
