#!/usr/bin/env python3
"""Email a weekly summary of heating oil prices with a 30-day chart.

Reads oil_prices.csv (written by oil_price_tracker.py) and sends the email
through the same EMAIL_* settings. Needs matplotlib (pip install matplotlib).
"""
import csv
import io
import sys
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

import oil_price_tracker as t


def load():
    with t.CSV_PATH.open(newline="") as f:
        return sorted(
            (date.fromisoformat(r["date"]), float(r["lowest_credit_card_price"]))
            for r in csv.DictReader(f)
        )


def make_chart(rows) -> bytes:
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
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    return buf.getvalue()


def main() -> int:
    if not t.CSV_PATH.exists():
        print("No oil_prices.csv yet; nothing to summarize.")
        return 0
    rows = load()
    if not rows:
        print("oil_prices.csv is empty; nothing to summarize.")
        return 0

    today = date.fromisoformat(t.today())
    month = [r for r in rows if r[0] > today - timedelta(days=30)] or rows[-1:]
    week = [r for r in rows if r[0] > today - timedelta(days=7)] or rows[-1:]
    prior = [r for r in rows if r[0] <= today - timedelta(days=7)]

    now = rows[-1][1]
    wk_lo = min(p for _, p in week)
    wk_hi = max(p for _, p in week)
    mo_lo = min(p for _, p in month)
    mo_hi = max(p for _, p in month)
    if prior:
        chg = now - prior[-1][1]
        change = f"{'up' if chg > 0 else 'down' if chg < 0 else 'unchanged'}" + \
                 (f" ${abs(chg):.2f}" if chg else "") + f" vs {prior[-1][0]:%b %d}"
    else:
        change = "not enough history yet to compare"

    lines = [
        ("Latest lowest credit card price", f"${now:.2f}/gal"),
        ("Change over the past week", change),
        ("This week's range", f"${wk_lo:.2f} - ${wk_hi:.2f}"),
        ("30-day range", f"${mo_lo:.2f} - ${mo_hi:.2f}"),
        ("Days of data in the last 30", str(len(month))),
    ]
    text = "Weekly heating oil summary - Woodbridge, CT (06525)\n\n" + \
        "\n".join(f"{k}: {v}" for k, v in lines) + f"\n\n{t.URL}\n"
    rows_html = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#555'>{k}</td>"
        f"<td style='padding:4px 0'><b>{v}</b></td></tr>" for k, v in lines)
    html_body = (
        "<div style='font-family:Arial,sans-serif;max-width:640px'>"
        "<h2 style='margin:0 0 8px'>Weekly heating oil summary</h2>"
        "<div style='color:#555;margin-bottom:12px'>Woodbridge, CT (06525)</div>"
        f"<table style='border-collapse:collapse;margin-bottom:16px'>{rows_html}</table>"
        "<img src='cid:chart' style='width:100%;max-width:640px' alt='30-day price chart'>"
        f"<p><a href='{t.URL}'>View current prices</a></p></div>"
    )
    chart = make_chart(month)
    try:
        sent = t.send_email(f"Weekly heating oil summary: ${now:.2f}/gal", text,
                            html_body, {"chart": chart})
    except Exception as e:
        print(f"Email failed: {e}", file=sys.stderr)
        return 3
    print("Summary sent." if sent else "Summary not sent (email not configured).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
