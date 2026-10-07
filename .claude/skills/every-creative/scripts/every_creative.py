#!/usr/bin/env python3
"""every-creative: read the fatigue curve of every single Meta ad and flag kills.

Compares each ad's first 7 active days to its last 7 (CTR, CPA, frequency) and
builds a weekly CTR curve. Ads that stopped spending before the last 3 days
of the file are skipped as already paused.
"""
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep_common import (apply_overrides, base_parser, div, find_col, load_table, num,
                          parse_date, print_summary, write_csv)


def agg(days):
    t = defaultdict(float)
    for d in days:
        for k, v in d.items():
            t[k] += v
    t["ctr"] = div(t["clicks"] * 100, t["impr"], 0.0)
    t["cpa"] = div(t["spend"], t["purch"], math.inf)
    t["freq"] = div(t["freq_w"], t["impr"], 0.0)
    return t


def main():
    p = base_parser(__doc__)
    p.add_argument("export", help="Meta export at Ad level, broken down by Day")
    p.add_argument("--target-cpa", type=float, help="Default: account CPA in the file")
    p.add_argument("--min-days", type=int, default=10, help="Active days needed to read a curve")
    a = p.parse_args()
    apply_overrides(a)

    h, rows = load_table(a.export)
    c = {k: find_col(h, k) for k in ("date", "ad", "spend", "impressions", "clicks", "purchases")}
    c["adset"] = find_col(h, "adset", required=False)
    c["ad_id"] = find_col(h, "ad_id", required=False)
    c["frequency"] = find_col(h, "frequency", required=False)

    ads = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    names = {}
    for r in rows:
        d = parse_date(r[c["date"]])
        if not d:
            continue
        key = r[c["ad_id"]] if c["ad_id"] else (r.get(c["adset"], "") if c["adset"] else "", r[c["ad"]])
        names[key] = (r[c["ad"]], r.get(c["adset"], "") if c["adset"] else "")
        day = ads[key][d]
        impr = num(r[c["impressions"]])
        day["impr"] += impr
        day["clicks"] += num(r[c["clicks"]])
        day["spend"] += num(r[c["spend"]])
        day["purch"] += num(r[c["purchases"]])
        if c["frequency"]:
            day["freq_w"] += num(r[c["frequency"]]) * impr
    if not ads:
        sys.exit("No dated rows. Export at Ad level with Breakdown > By Time > Day.")

    last_date = max(d for a_ in ads.values() for d in a_)
    tot_spend = sum(v["spend"] for a_ in ads.values() for v in a_.values())
    tot_purch = sum(v["purch"] for a_ in ads.values() for v in a_.values())
    cpa = a.target_cpa or div(tot_spend, tot_purch)
    if not cpa:
        sys.exit("No purchases in file and no --target-cpa given.")

    out = []
    for key, daymap in ads.items():
        active = sorted(d for d, v in daymap.items() if v["impr"] > 0)
        if not active:
            continue
        ad_name, adset = names[key]
        life = agg(daymap[d] for d in active)
        r = {"ad": ad_name, "ad_set": adset, "active_days": len(active), "last_active": active[-1].isoformat(),
             "spend": life["spend"], "purchases": life["purch"], "cpa": life["cpa"], "ctr": life["ctr"]}
        if (last_date - active[-1]).days > 3:
            r["action"] = "INACTIVE"
            out.append(r)
            continue
        early, recent = agg(daymap[d] for d in active[:7]), agg(daymap[d] for d in active[-7:])
        weeks = [agg(daymap[d] for d in active[i:i + 7])["ctr"] for i in range(0, len(active), 7)]
        decline = 1 - recent["ctr"] / early["ctr"] if early["ctr"] else 0.0
        r.update({"ctr_first7": early["ctr"], "ctr_last7": recent["ctr"], "ctr_decline_pct": decline * 100,
                  "cpa_first7": early["cpa"], "cpa_last7": recent["cpa"], "freq_last7": recent["freq"],
                  "spend_last7": recent["spend"], "purch_last7": recent["purch"],
                  "weekly_ctr_curve": " > ".join(f"{w:.2f}" for w in weeks)})
        if life["purch"] == 0 and life["spend"] >= 3 * cpa:
            act = f"KILL (never converted: spent {life['spend'] / cpa:.1f}x CPA)"
        elif len(active) < a.min_days:
            act = "TOO NEW"
        elif recent["purch"] == 0 and recent["spend"] >= 2 * cpa:
            act = "KILL (no purchases in last 7 active days)"
        elif decline >= 0.35 and recent["cpa"] >= 1.5 * cpa:
            act = "KILL (fatigued: CTR down, CPA up)"
        elif decline >= 0.25 and recent["cpa"] >= 1.2 * min(early["cpa"], cpa * 1.2):
            act = "REFRESH (new hook / iteration of this concept)"
        elif life["cpa"] <= 0.7 * cpa and life["purch"] >= 10 and decline < 0.2:
            act = "SCALE (winner, not fatigued)"
        elif decline >= 0.2:
            act = "WATCH (CTR slipping)"
        elif recent["freq"] >= 3:
            act = "WATCH (high frequency, CTR still holding)"
        else:
            act = "KEEP"
        r["action"] = act
        out.append(r)

    order = {"KILL": 0, "REFRESH": 1, "SCALE": 2, "WATCH": 3}
    flagged = [r for r in out if r["action"].split(" ")[0] in order]
    flagged.sort(key=lambda r: (order[r["action"].split(" ")[0]], -r["spend"]))
    fields = ["action", "ad", "ad_set", "spend", "purchases", "cpa", "ctr", "active_days", "last_active",
              "ctr_first7", "ctr_last7", "ctr_decline_pct", "cpa_first7", "cpa_last7", "freq_last7",
              "spend_last7", "purch_last7", "weekly_ctr_curve"]
    f1 = write_csv(os.path.join(a.out, "every-creative-flags.csv"), flagged, fields)
    f2 = write_csv(os.path.join(a.out, "every-creative-all.csv"),
                   sorted(out, key=lambda r: -r["spend"]), fields)
    print(f"Account CPA used: {cpa:,.2f}   Ads: {len(out)}   File ends: {last_date}")
    print_summary("every-creative", out, flagged, money_field="spend",
                  show=["action", "ad", "spend", "cpa_last7", "weekly_ctr_curve"], files=[f1, f2])


if __name__ == "__main__":
    main()
