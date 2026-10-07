#!/usr/bin/env python3
"""every-adset: 90 days per ad set; flags decay, dead ad sets, and merge candidates.

Decay  = last 14 days CPA vs the ad set's own earlier CPA (Poisson-tested).
Merge  = ad sets averaging fewer optimisation events per week than Meta needs to
         exit learning (default 50); grouped by campaign so you can consolidate.
"""
import math
import os
import sys
from collections import defaultdict
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep_common import (apply_overrides, base_parser, div, find_col, load_table, num,
                          parse_date, pois_cdf, print_summary, write_csv)


def main():
    p = base_parser(__doc__)
    p.add_argument("export", help="Meta export at Ad set level, broken down by Day")
    p.add_argument("--target-cpa", type=float)
    p.add_argument("--learning-events", type=float, default=50, help="Weekly events to exit learning")
    p.add_argument("--recent-days", type=int, default=14)
    a = p.parse_args()
    apply_overrides(a)

    h, rows = load_table(a.export)
    c = {k: find_col(h, k) for k in ("date", "adset", "spend", "purchases")}
    c["campaign"] = find_col(h, "campaign", required=False)
    sets = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    for r in rows:
        d = parse_date(r[c["date"]])
        if not d:
            continue
        key = (r.get(c["campaign"], "") if c["campaign"] else "", r[c["adset"]])
        sets[key][d][0] += num(r[c["spend"]])
        sets[key][d][1] += num(r[c["purchases"]])
    if not sets:
        sys.exit("No dated rows. Export at Ad set level with Breakdown > By Time > Day.")

    end = max(d for s in sets.values() for d in s)
    cut = end - timedelta(days=a.recent_days - 1)
    tot = [sum(v[i] for s in sets.values() for v in s.values()) for i in (0, 1)]
    acct_cpa = a.target_cpa or div(tot[0], tot[1])
    if not acct_cpa:
        sys.exit("No purchases in file and no --target-cpa given.")

    out = []
    for (camp, name), days in sets.items():
        def window(lo, hi):
            sp = sum(v[0] for d, v in days.items() if lo <= d <= hi)
            pu = sum(v[1] for d, v in days.items() if lo <= d <= hi)
            return sp, pu
        first = min(d for d, v in days.items() if v[0] > 0) if any(v[0] > 0 for v in days.values()) else end
        rs, rp = window(cut, end)
        bs, bp = window(first, cut - timedelta(days=1))
        l7s, _ = window(end - timedelta(days=6), end)
        l28s, l28p = window(end - timedelta(days=27), end)
        weeks_live = min(4, max(1, ((end - first).days + 1) / 7))
        weekly = l28p / weeks_live
        curve = []
        for w in range(12, -1, -1):
            s, pu = window(end - timedelta(days=7 * w + 6), end - timedelta(days=7 * w))
            if s > 0:
                curve.append(f"{s / pu:.0f}" if pu else "x")
        base_cpa = div(bs, bp)
        r = {"campaign": camp, "ad_set": name, "first_spend": first.isoformat(),
             "spend_90d": bs + rs, "purch_90d": bp + rp, "cpa_before": base_cpa,
             "spend_recent": rs, "purch_recent": rp, "cpa_recent": div(rs, rp, math.inf),
             "weekly_purchases": weekly, "weekly_cpa_curve": " > ".join(curve)}
        flags = []
        if l7s <= 0:
            r["action"] = "INACTIVE"
            out.append(r)
            continue
        if rp == 0 and rs >= 2 * acct_cpa:
            flags.append("DEAD")
        elif base_cpa and bp >= 5 and rs > 0:
            pv = pois_cdf(rp, rs / base_cpa)
            r["decay_p"] = pv
            if div(rs, rp, math.inf) >= 1.4 * base_cpa and pv < 0.10:
                flags.append("DECAYING")
        if weekly < a.learning_events and "DEAD" not in flags:
            flags.append("MERGE?")
        r["action"] = " + ".join(flags) if flags else "STABLE"
        out.append(r)

    # Merge suggestions within each campaign
    by_camp = defaultdict(list)
    for r in out:
        if "MERGE?" in r["action"]:
            by_camp[r["campaign"]].append(r)
    for camp, members in by_camp.items():
        combined = sum(m["weekly_purchases"] for m in members)
        for m in members:
            others = [x["ad_set"] for x in members if x is not m]
            if others:
                m["merge_note"] = (f"Merge with {len(others)} other low-volume ad set(s) in this campaign "
                                   f"-> ~{combined:.0f} events/week combined: {'; '.join(others[:6])}")
            else:
                m["merge_note"] = (f"Only {m['weekly_purchases']:.0f} events/week and nothing to merge with: "
                                   "broaden the audience, raise budget, or optimise for a higher-funnel event")
        for m in members:
            m["action"] = m["action"].replace("MERGE?", "MERGE")

    rank = lambda r: (0 if "DEAD" in r["action"] else 1 if "DECAY" in r["action"] else 2, -r["spend_recent"])
    flagged = sorted([r for r in out if r["action"] not in ("STABLE", "INACTIVE")], key=rank)
    fields = ["action", "campaign", "ad_set", "spend_recent", "purch_recent", "cpa_recent", "cpa_before",
              "decay_p", "weekly_purchases", "weekly_cpa_curve", "spend_90d", "purch_90d", "first_spend",
              "merge_note"]
    f1 = write_csv(os.path.join(a.out, "every-adset-flags.csv"), flagged, fields)
    f2 = write_csv(os.path.join(a.out, "every-adset-all.csv"), out, fields)
    print(f"Account CPA used: {acct_cpa:,.2f}   Ad sets: {len(out)}   Recent window: {cut} to {end}")
    print_summary("every-adset", out, flagged, money_field="spend_recent",
                  show=["action", "ad_set", "cpa_before", "cpa_recent", "weekly_purchases"], files=[f1, f2])


if __name__ == "__main__":
    main()
