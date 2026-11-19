"""Runs every query in queries.sql against the airbnb_lisbon database.

Usage:  python run_queries.py queries.sql
Writes one CSV per query into sql_results/ and a single sql_results.txt with all the tables
(send me that .txt, or open the CSVs in Excel / Power BI).
"""
import getpass
import re
import sys
from pathlib import Path

import pandas as pd

DB_NAME = "airbnb_lisbon"


def parse(sql_text):
    """Returns [(query_number, statement)], using the '-- N.' comments as names. USE is skipped."""
    out, buf, number = [], [], None
    for line in sql_text.splitlines():
        m = re.match(r"\s*--\s*(\d+)\.", line)
        if m:
            number = int(m.group(1))
        if line.strip().startswith("--") or not line.strip():
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(buf).rstrip().rstrip(";")
            buf = []
            if not stmt.upper().startswith("USE "):
                out.append((number, stmt))
    return out


def main(sql_file, host="localhost", port=3306, user="root"):
    import mysql.connector

    queries = parse(Path(sql_file).read_text(encoding="utf-8"))
    password = getpass.getpass(f"MySQL password for {user}: ")
    conn = mysql.connector.connect(host=host, port=port, user=user, password=password, database=DB_NAME)
    cur = conn.cursor()
    out_dir = Path("sql_results")
    out_dir.mkdir(exist_ok=True)
    report = []
    for number, stmt in queries:
        label = f"query_{number}"
        try:
            cur.execute(stmt)
            df = pd.DataFrame(cur.fetchall(), columns=cur.column_names)
            df.to_csv(out_dir / f"{label}.csv", index=False, encoding="utf-8-sig")
            text = df.to_string(index=False, max_rows=60)
            print(f"{label}: {len(df)} rows")
        except Exception as e:  # keep going so one broken query does not hide the others
            text = f"ERROR: {e}"
            print(f"{label}: ERROR {e}")
        report.append(f"=== {label} ===\n{text}\n")
    Path("sql_results.txt").write_text("\n".join(report), encoding="utf-8")
    conn.close()
    print("Done. Files: sql_results.txt and the sql_results folder.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python run_queries.py queries.sql")
    main(sys.argv[1])
