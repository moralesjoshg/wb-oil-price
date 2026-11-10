#!/usr/bin/env python3
"""Record the lowest credit card heating oil price for Woodbridge, CT (06525).

Run on a schedule. Keeps one row per day in oil_prices.csv: date, lowest
credit card price per gallon seen that day, and how many suppliers were
listed. Emails an alert when the price drops below the previously recorded one.

Standard library only; needs Python 3.8+.
"""
import csv
import html
import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

URL = "https://www.cashheatingoil.com/woodbridge_ct_oil_prices/06525"
CSV_PATH = Path(__file__).with_name("oil_prices.csv")
FIELDS = ["date", "lowest_credit_card_price", "suppliers_listed"]


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (oil-price-tracker script)"}
    )
    # Some Python installs (notably python.org builds on macOS) ship without root
    # certificates. Use certifi's bundle when present; verification stays on.
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="replace")


def to_text(raw_html: str) -> str:
    raw_html = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw_html)
    text = re.sub(r"(?s)<[^>]+>", " ", raw_html)
    return re.sub(r"\s+", " ", html.unescape(text))


def credit_card_prices(text: str):
    """Return (list of every credit card price, number of supplier listings)."""
    prices = []
    sections = re.split(r"Credit Card Prices\s*:", text, flags=re.I)[1:]
    for chunk in sections:
        # Stop at the end of this supplier's block.
        chunk = re.split(r"You will be contacted|Delivery Date\s*:", chunk, maxsplit=1,
                         flags=re.I)[0]
        prices += [float(p) for p in re.findall(r"\$\s*(\d+\.\d{2,3})", chunk)]
    return prices, len(sections)


def today() -> str:
    # Use Eastern time so the date is right even when run on a UTC server.
    return datetime.now(ZoneInfo("America/New_York")).date().isoformat()


def save(row: dict):
    """Write today's row, keeping the lowest price seen across the day's runs.

    Returns the previously recorded price (today's earlier value, else the
    most recent earlier day), or None if the CSV had no data yet.
    """
    rows = []
    previous = None
    if CSV_PATH.exists():
        with CSV_PATH.open(newline="") as f:
            for r in csv.DictReader(f):
                if r["date"] == row["date"]:
                    previous = float(r["lowest_credit_card_price"])
                    if float(r["lowest_credit_card_price"]) < float(row["lowest_credit_card_price"]):
                        row["lowest_credit_card_price"] = r["lowest_credit_card_price"]
                else:
                    rows.append(r)
                    if previous is None or r["date"] < row["date"]:
                        previous = float(r["lowest_credit_card_price"])
    rows.append(row)
    with CSV_PATH.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    return previous


def send_email(subject: str, text: str, html_body: str = None, images: dict = None) -> bool:
    """Send an email via Gmail SMTP using EMAIL_USER, EMAIL_APP_PASSWORD, EMAIL_TO.

    images maps a Content-ID to PNG bytes, referenced in html_body as
    <img src="cid:NAME">. Returns False (without raising) if email isn't configured.
    """
    user = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_APP_PASSWORD")
    to = os.environ.get("EMAIL_TO") or user
    if not (user and password and to):
        print("Email isn't configured (EMAIL_* variables unset); not sending.")
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.set_content(text)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
        for cid, data in (images or {}).items():
            msg.get_payload()[1].add_related(data, "image", "png", cid=f"<{cid}>")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465,
                          context=ssl.create_default_context()) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
    return True


def send_alert(old: float, new: float) -> None:
    send_email(
        f"Heating oil price drop: ${new:.2f}/gal",
        f"Lowest credit card price in Woodbridge, CT (06525) fell from "
        f"${old:.2f} to ${new:.2f} per gallon.\n\n{URL}\n",
    )


def main() -> int:
    try:
        text = to_text(fetch(URL))
    except Exception as e:
        print(f"Fetch failed: {e}", file=sys.stderr)
        return 1

    prices, n = credit_card_prices(text)
    if not prices:
        print("No credit card prices found - the page layout may have changed.",
              file=sys.stderr)
        return 2

    low = min(prices)
    previous = save({"date": today(),
                     "lowest_credit_card_price": f"{low:.2f}",
                     "suppliers_listed": n})
    print(f"{today()}: lowest credit card price ${low:.2f}/gal ({n} suppliers)")

    if previous is not None and low < previous:
        try:
            send_alert(previous, low)
            print(f"Alert sent: ${previous:.2f} -> ${low:.2f}")
        except Exception as e:
            print(f"Email failed: {e}", file=sys.stderr)
            return 3  # non-zero so the Action shows as failed (CSV is still saved)
    return 0


if __name__ == "__main__":
    sys.exit(main())
