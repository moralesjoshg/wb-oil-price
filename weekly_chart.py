#!/usr/bin/env python3
"""Generate a 30-day price history chart (price_history.png) from oil_prices.csv.

Needs matplotlib (pip install matplotlib).
"""
import csv
import sys
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

import oil_price_tracker as t

OUT_PATH = t.CSV_PATH.with_name("price_history.png")


def load():
    with t.CSV_PATH.open(newline="") as f:
        return sorted(
            (date.fromisoformat(r["date"]), float(r["lowest_credit_card_price"]))
            for r in csv.DictReader(f)
        )


def make_chart(rows, out_path) -> None:
    xs = [d for d, _ in rows]
    ys = [p for _, p in rows]
    fig, ax = plt.subplots(figsize=(8, 3.8), dpi=150)
    ax.plot(xs, ys, color="#1f6feb", marker="o", markersize=4, linewidth=2)
    lo = min(ys)
    ax.annotate(f"low ${lo:.2f}", (xs[ys.index(lo)], lo), textcoords="offset points",
                xytext=(0, -16), ha="center", fontsize=9, color="#1a7f37")
    ax.set_title("Lowest credit card price per gallon - last 30 days (Woodbridge, CT)",
                 fontsize=11)
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:.2f}")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    # Evenly spaced weekly ticks counting back from the latest date.
    ax.set_xticks([xs[-1] - timedelta(days=7 * k) for k in range(5)
                   if xs[-1] - timedelta(days=7 * k) >= xs[0]] or [xs[-1]])
    if len(xs) == 1:
        ax.set_xlim(xs[0] - timedelta(days=3), xs[0] + timedelta(days=3))
    pad = max(0.02, (max(ys) - lo) * 0.2)
    ax.set_ylim(lo - pad, max(ys) + pad)
    ax.grid(alpha=0.3)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, format="png", facecolor="white")
    plt.close(fig)


def main() -> int:
    if not t.CSV_PATH.exists():
        print("No oil_prices.csv yet; nothing to chart.")
        return 0
    rows = load()
    if not rows:
        print("oil_prices.csv is empty; nothing to chart.")
        return 0
    today = date.fromisoformat(t.today())
    month = [r for r in rows if r[0] > today - timedelta(days=30)] or rows[-1:]
    make_chart(month, OUT_PATH)
    print(f"Wrote {OUT_PATH.name} ({len(month)} days of data).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
