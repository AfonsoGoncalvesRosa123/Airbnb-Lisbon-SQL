"""Makes the README charts from the CSVs written by run_queries.py.

Usage:  python make_charts.py            (reads sql_results/, writes figures/)
Needs:  pip install pandas matplotlib
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "sql_results")
OUT = Path("figures")
OUT.mkdir(exist_ok=True)

BLUE, GREY, RED = "#2a6fdb", "#b9bec7", "#d9534f"
plt.rcParams.update({
    "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "figure.dpi": 100,
})


def load(n):
    return pd.read_csv(SRC / f"query_{n}.csv")


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=150)
    plt.close(fig)
    print("saved", OUT / name)


# 1) Median nightly price by Lisbon neighbourhood
d = load(2).sort_values("median_price")
fig, ax = plt.subplots(figsize=(7, 7))
ax.barh(d["neighbourhood"], d["median_price"], color=BLUE)
for y, v in enumerate(d["median_price"]):
    ax.text(v + 2, y, f"{v:.0f}", va="center", fontsize=8)
ax.set_xlabel("Median price per night (EUR)")
ax.set_title("Median nightly price by Lisbon neighbourhood")
save(fig, "median_price_by_neighbourhood.png")

# 2) Seasonality: reviews per calendar month (proxy for stays)
d = load(7)
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
colors = [RED if m == d["reviews"].idxmax() + 1 else BLUE for m in d["month"]]
fig, ax = plt.subplots(figsize=(7, 4))
ax.bar([months[m - 1] for m in d["month"]], d["reviews"] / 1000, color=colors)
ax.set_ylabel("Reviews (thousands, all years)")
ratio = d["reviews"].max() / d["reviews"].min()
ax.set_title(f"Reviews peak in summer: the busiest month has {ratio:.1f}x the quietest")
save(fig, "seasonality.png")

# 3) Reviews per year, COVID year highlighted
d = load(8)
d = d[d["year"] >= 2014]
colors = [RED if y == 2020 else BLUE for y in d["year"]]
fig, ax = plt.subplots(figsize=(7, 4))
ax.bar(d["year"].astype(str), d["reviews"] / 1000, color=colors)
ax.set_ylabel("Reviews per year (thousands)")
ax.set_title("Reviews fell 68% in 2020 and passed 2019 levels by 2022")
ax.tick_params(axis="x", rotation=45)
save(fig, "reviews_per_year.png")

# 4) Room-type mix by neighbourhood
d = load(3).pivot_table(index="neighbourhood", columns="room_type",
                        values="pct_of_neighbourhood", fill_value=0)
order = [c for c in ["Entire home/apt", "Private room", "Hotel room", "Shared room"] if c in d.columns]
d = d[order].sort_values("Entire home/apt")
palette = {"Entire home/apt": BLUE, "Private room": "#f0a030", "Hotel room": "#7a5cc0", "Shared room": GREY}
fig, ax = plt.subplots(figsize=(7, 7))
left = pd.Series(0.0, index=d.index)
for col in order:
    ax.barh(d.index, d[col], left=left, color=palette[col], label=col)
    left += d[col]
ax.set_xlabel("% of listings")
ax.set_xlim(0, 100)
ax.set_title("Entire homes dominate the historic centre;\nresidential areas rent more private rooms")
ax.legend(ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.2), frameon=False, fontsize=8)
save(fig, "room_type_mix.png")

# 5) Rating by price quartile (axis does not start at zero: the differences are small)
d = load(9)
labels = [f"Q{int(q)}\n{lo:.0f}-{hi:.0f} EUR" for q, lo, hi in zip(d["price_quartile"], d["min_price"], d["max_price"])]
fig, ax = plt.subplots(figsize=(6, 4))
ax.plot(labels, d["avg_rating"], marker="o", color=BLUE)
for x, v in zip(labels, d["avg_rating"]):
    ax.text(x, v + 0.012, f"{v:.2f}", ha="center", fontsize=9)
ax.set_ylim(4.5, 4.85)
ax.set_ylabel("Average rating (axis starts at 4.5)")
ax.set_title("Pricier listings rate slightly higher")
save(fig, "rating_by_price_quartile.png")
