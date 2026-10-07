#!/usr/bin/env python3
"""every-event: find the days your Meta Pixel / CAPI quietly stopped counting purchases.

With --orders: compares Pixel purchases to real store orders day by day.
Without it: compares each day's purchases-per-spend to the trailing 14 days.
Flags are only raised when the gap is statistically unlikely to be noise (Poisson test).
"""
import os
import sys
from collections import defaultdict
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep_common import (apply_overrides, base_parser, div, find_col, load_table, median,
                          num, parse_date, pois_cdf, pois_sf, print_summary, write_csv)


def load_orders(path):
    h, rows = load_table(path)
    dcol = find_col(h, "order_date", ["Created at", "Processed at", "Order date", "Day", "Date"])
    ccol = find_col(h, "order_count", required=False)
    idcol = None if ccol else find_col(h, "order_id", required=False)
    orders, seen = defaultdict(float), set()
    for r in rows:
        d = parse_date(r[dcol])
        if not d:
            continue
        if ccol:
            orders[d] += num(r[ccol])
        else:
            oid = r.get(idcol) if idcol else None
            if oid:  # Shopify exports one row per line item; count each order once
                if oid in seen:
                    continue
                seen.add(oid)
            orders[d] += 1
    return orders


def main():
    p = base_parser(__doc__)
    p.add_argument("meta", help="Meta Ads export broken down by Day (any level; rows are summed per day)")
    p.add_argument("--orders", help="Store orders export: one row per order, or Day + order count")
    p.add_argument("--min-orders", type=float, default=3, help="Ignore days with fewer real orders than this")
    p.add_argument("--alpha", type=float, default=0.02, help="How unlikely a gap must be to flag it")
    a = p.parse_args()
    apply_overrides(a)

    h, rows = load_table(a.meta)
    dcol, pcol = find_col(h, "date"), find_col(h, "purchases")
    scol = find_col(h, "spend", required=False)
    pixel, spend = defaultdict(float), defaultdict(float)
    for r in rows:
        d = parse_date(r[dcol])
        if d:
            pixel[d] += num(r[pcol])
            if scol:
                spend[d] += num(r[scol])
    if not pixel:
        sys.exit("No dated rows found. Export with Breakdown > By Time > Day.")
    start, end = min(pixel), max(pixel)
    days = [start + timedelta(i) for i in range((end - start).days + 1)]

    out = []
    if a.orders:
        orders = load_orders(a.orders)
        ratios = [pixel[d] / orders[d] for d in days if orders.get(d, 0) >= a.min_orders]
        base = median(ratios)
        if base is None:
            sys.exit("No overlapping days with enough orders. Check both files cover the same dates.")
        mode = f"Pixel vs store orders (Pixel normally records {base:.0%} of orders)"
        for d in days:
            o, px = orders.get(d, 0), pixel[d]
            exp = o * base
            r = {"date": d.isoformat(), "spend": spend.get(d, 0.0), "pixel_purchases": px,
                 "store_orders": o, "expected_pixel": exp, "missing_events": max(0.0, exp - px),
                 "action": ""}
            if o >= a.min_orders:
                lo, hi = pois_cdf(px, exp), pois_sf(px, exp)
                r["p_value"] = min(lo, hi)
                if px == 0 and lo < a.alpha:
                    r["action"] = "OUTAGE (Pixel recorded zero purchases)"
                elif px < 0.6 * exp and lo < a.alpha:
                    r["action"] = "UNDER-TRACKING"
                elif px > 1.5 * exp and hi < a.alpha:
                    r["action"] = "OVER-COUNTING (duplicate events?)"
            out.append(r)
    else:
        mode = "Purchases per spend vs trailing 14 days (no orders file given)"
        flagged_days = set()
        for i, d in enumerate(days):
            prior = [x for x in days[max(0, i - 14):i] if x not in flagged_days and spend.get(x, 0) > 0]
            rate = div(sum(pixel[x] for x in prior), sum(spend[x] for x in prior))
            exp = spend.get(d, 0) * rate if rate and len(prior) >= 7 else None
            px = pixel[d]
            r = {"date": d.isoformat(), "spend": spend.get(d, 0.0), "pixel_purchases": px,
                 "store_orders": "", "expected_pixel": exp,
                 "missing_events": max(0.0, exp - px) if exp else 0.0, "action": ""}
            if exp and exp >= 3:
                lo = pois_cdf(px, exp)
                r["p_value"] = lo
                if px == 0 and lo < a.alpha:
                    r["action"] = "LIKELY OUTAGE (spend ran, zero purchases)"
                elif px < 0.5 * exp and lo < a.alpha:
                    r["action"] = "DROP (purchases far below spend level)"
                if r["action"]:
                    flagged_days.add(d)
            out.append(r)

    # Group consecutive flagged days into incidents
    inc, last, incidents = 0, None, []
    for r in out:
        if not r["action"]:
            continue
        d = parse_date(r["date"])
        if last is None or (d - last).days > 1:
            inc += 1
            incidents.append({"incident": inc, "start": r["date"], "end": r["date"], "days": 0,
                              "missing_events": 0.0, "spend": 0.0})
        r["incident"] = inc
        cur = incidents[-1]
        cur["end"], cur["days"] = r["date"], cur["days"] + 1
        cur["missing_events"] += r["missing_events"]
        cur["spend"] += r["spend"] or 0
        last = d

    fields = ["date", "incident", "action", "spend", "pixel_purchases", "store_orders",
              "expected_pixel", "missing_events", "p_value"]
    flagged = [r for r in out if r["action"]]
    f1 = write_csv(os.path.join(a.out, "every-event-daily.csv"), out, fields)
    f2 = write_csv(os.path.join(a.out, "every-event-flags.csv"), flagged, fields)
    f3 = write_csv(os.path.join(a.out, "every-event-incidents.csv"), incidents,
                   ["incident", "start", "end", "days", "missing_events", "spend"])
    print(f"Mode: {mode}\nRange: {start} to {end} ({len(days)} days)")
    print_summary("every-event", out, flagged, money_field="spend",
                  show=["date", "action", "pixel_purchases", "store_orders", "expected_pixel"],
                  files=[f2, f3, f1])


if __name__ == "__main__":
    main()
