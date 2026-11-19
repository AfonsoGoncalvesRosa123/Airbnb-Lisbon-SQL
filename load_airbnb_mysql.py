"""Loads the Inside Airbnb Lisbon files into a MySQL database.

Usage (PowerShell, inside the project folder):
    pip install pandas mysql-connector-python
    python load_airbnb_mysql.py data

"data" is the folder with listings.csv.gz and reviews.csv.gz (the .csv versions work too).
It asks for your MySQL password, creates the database "airbnb_lisbon" and rebuilds
four tables: neighbourhoods, hosts, listings, reviews.
"""
import argparse
import getpass
import sys
from pathlib import Path

import pandas as pd

DB_NAME = "airbnb_lisbon"

DDL = [
    """CREATE TABLE neighbourhoods (
        neighbourhood VARCHAR(100) PRIMARY KEY
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE hosts (
        host_id BIGINT PRIMARY KEY,
        host_name VARCHAR(200),
        host_since DATE,
        host_is_superhost TINYINT(1),
        host_listings_count INT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE listings (
        id BIGINT PRIMARY KEY,
        host_id BIGINT,
        name VARCHAR(500),
        neighbourhood VARCHAR(100),
        municipality VARCHAR(100),
        room_type VARCHAR(50),
        property_type VARCHAR(100),
        accommodates INT,
        bedrooms INT,
        beds INT,
        price DECIMAL(10,2),
        minimum_nights INT,
        number_of_reviews INT,
        review_scores_rating DECIMAL(4,2),
        availability_365 INT,
        latitude DECIMAL(9,6),
        longitude DECIMAL(9,6),
        FOREIGN KEY (host_id) REFERENCES hosts(host_id),
        FOREIGN KEY (neighbourhood) REFERENCES neighbourhoods(neighbourhood),
        INDEX idx_listings_neighbourhood (neighbourhood),
        INDEX idx_listings_municipality (municipality),
        INDEX idx_listings_price (price)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE reviews (
        review_id BIGINT PRIMARY KEY,
        listing_id BIGINT NOT NULL,
        review_date DATE,
        FOREIGN KEY (listing_id) REFERENCES listings(id),
        INDEX idx_reviews_date (review_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]
DROP_ORDER = ["reviews", "listings", "hosts", "neighbourhoods"]


# In the Lisbon files some accented characters are missing from the neighbourhood names
# ("Santo Antnio"). Restore the 24 Lisbon parishes used in the analysis.
NAME_FIXES = {
    "Alcntara": "Alcântara",
    "Belm": "Belém",
    "Misericrdia": "Misericórdia",
    "Parque das Naes": "Parque das Nações",
    "Penha de Frana": "Penha de França",
    "Santo Antnio": "Santo António",
    "So Domingos de Benfica": "São Domingos de Benfica",
    "So Vicente": "São Vicente",
}


def find_file(folder, names):
    for n in names:
        p = Path(folder) / n
        if p.exists():
            return p
    sys.exit(f"None of {names} found in {folder}")


def first_col(df, options):
    """Returns the first of the given column names that exists (detailed vs summary files differ)."""
    for c in options:
        if c in df.columns:
            return df[c]
    return pd.Series([None] * len(df), index=df.index)


def clean_price(s):
    return pd.to_numeric(s.astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce")


def build_tables(listings_raw, reviews_raw):
    raw = listings_raw
    listings = pd.DataFrame({
        "id": raw["id"],
        "host_id": raw["host_id"],
        "name": first_col(raw, ["name"]),
        "neighbourhood": first_col(raw, ["neighbourhood_cleansed", "neighbourhood"]).replace(NAME_FIXES),
        "municipality": first_col(raw, ["neighbourhood_group_cleansed", "neighbourhood_group"]),
        "room_type": first_col(raw, ["room_type"]),
        "property_type": first_col(raw, ["property_type"]),
        "accommodates": first_col(raw, ["accommodates"]),
        "bedrooms": first_col(raw, ["bedrooms"]),
        "beds": first_col(raw, ["beds"]),
        "price": clean_price(first_col(raw, ["price"])),
        "minimum_nights": first_col(raw, ["minimum_nights"]),
        "number_of_reviews": first_col(raw, ["number_of_reviews"]),
        "review_scores_rating": first_col(raw, ["review_scores_rating"]),
        "availability_365": first_col(raw, ["availability_365"]),
        "latitude": first_col(raw, ["latitude"]),
        "longitude": first_col(raw, ["longitude"]),
    }).drop_duplicates("id")

    superhost = first_col(raw, ["host_is_superhost"]).map({"t": 1, "f": 0})
    hosts = pd.DataFrame({
        "host_id": raw["host_id"],
        "host_name": first_col(raw, ["host_name"]),
        "host_since": pd.to_datetime(first_col(raw, ["host_since"]), errors="coerce").dt.strftime("%Y-%m-%d"),
        "host_is_superhost": superhost,
        "host_listings_count": first_col(raw, ["host_listings_count", "calculated_host_listings_count"]),
    }).drop_duplicates("host_id")

    neighbourhoods = (listings[["neighbourhood"]].dropna().drop_duplicates())

    rv = reviews_raw
    review_id = rv["id"] if "id" in rv.columns else pd.Series(range(1, len(rv) + 1), index=rv.index)
    reviews = pd.DataFrame({
        "review_id": review_id,
        "listing_id": rv["listing_id"],
        "review_date": pd.to_datetime(rv["date"], errors="coerce").dt.strftime("%Y-%m-%d"),
    }).drop_duplicates("review_id")
    reviews = reviews[reviews["listing_id"].isin(listings["id"])]  # keep only reviews of known listings
    return neighbourhoods, hosts, listings, reviews


def rows(df):
    """DataFrame -> list of tuples, with NaN/NaT turned into None (NULL)."""
    return list(df.astype(object).where(df.notna(), None).itertuples(index=False, name=None))


def insert(cur, table, df, batch=10000):
    cols = ", ".join(df.columns)
    marks = ", ".join(["%s"] * len(df.columns))
    sql = f"INSERT INTO {table} ({cols}) VALUES ({marks})"
    data = rows(df)
    for i in range(0, len(data), batch):
        cur.executemany(sql, data[i:i + batch])
    print(f"  {table}: {len(data)} rows")


def main(folder, host, port, user):
    import mysql.connector  # imported here so the cleaning code can be tested without MySQL

    lpath = find_file(folder, ["listings.csv.gz", "listings.csv"])
    rpath = find_file(folder, ["reviews.csv.gz", "reviews.csv"])
    print(f"Reading {lpath.name} and {rpath.name} ...")
    # reviews.csv is huge (comments); read only the columns we use
    reviews_raw = pd.read_csv(rpath, usecols=lambda c: c in {"listing_id", "id", "date"})
    tables = build_tables(pd.read_csv(lpath), reviews_raw)

    password = getpass.getpass(f"MySQL password for {user}: ")
    conn = mysql.connector.connect(host=host, port=port, user=user, password=password)
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4")
    cur.execute(f"USE {DB_NAME}")
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for t in DROP_ORDER:
        cur.execute(f"DROP TABLE IF EXISTS {t}")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    for stmt in DDL:
        cur.execute(stmt)

    print("Loading ...")
    for name, df in zip(["neighbourhoods", "hosts", "listings", "reviews"], tables):
        insert(cur, name, df)
    conn.commit()
    cur.close()
    conn.close()
    print(f"Done. Open MySQL Workbench and run: USE {DB_NAME};")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="folder with listings.csv.gz and reviews.csv.gz")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=3306)
    ap.add_argument("--user", default="root")
    a = ap.parse_args()
    main(a.folder, a.host, a.port, a.user)
