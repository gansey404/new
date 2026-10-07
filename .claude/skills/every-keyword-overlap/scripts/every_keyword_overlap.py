#!/usr/bin/env python3
"""every-keyword-overlap: find the queries your own ad groups fight over.

Every search term that triggered ads in 2+ ad groups is listed with each ad group's
stats. A winner (home) is picked: the ad group whose keyword exactly equals the
term, else the best smoothed conversion rate, else the most clicks. Losing ad
groups get the term as an exact negative.
"""
import os
import re
import sys
from collections import defaultdict
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep_common import (apply_overrides, base_parser, div, find_col, load_table, num,
                          print_summary, write_csv)


def main():
    p = base_parser(__doc__)
    p.add_argument("export", help="Google Ads search terms report with Campaign and Ad group columns")
    p.add_argument("--min-clicks", type=float, default=3, help="Ignore terms with fewer total clicks")
    a = p.parse_args()
    apply_overrides(a)

    h, rows = load_table(a.export)
    c = {k: find_col(h, k) for k in ("search_term", "campaign", "ad_group", "clicks", "spend", "conversions")}
    c["impressions"] = find_col(h, "impressions", required=False)
    c["keyword"] = find_col(h, "keyword", required=False)

    data = defaultdict(lambda: defaultdict(lambda: {"impr": 0.0, "clicks": 0.0, "cost": 0.0, "conv": 0.0,
                                                    "kw": set()}))
    for r in rows:
        t = r[c["search_term"]].strip().lower()
        if not t:
            continue
        g = data[t][(r[c["campaign"]], r[c["ad_group"]])]
        g["clicks"] += num(r[c["clicks"]])
        g["cost"] += num(r[c["spend"]])
        g["conv"] += num(r[c["conversions"]])
        if c["impressions"]:
            g["impr"] += num(r[c["impressions"]])
        if c["keyword"] and r[c["keyword"]]:
            g["kw"].add(re.sub(r'[\[\]"+]', "", r[c["keyword"]]).strip().lower())

    tc = sum(g["clicks"] for t in data.values() for g in t.values())
    tv = sum(g["conv"] for t in data.values() for g in t.values())
    cvr = div(tv, tc, 0.0)
    K = 20  # smoothing clicks

    out, pairs = [], defaultdict(lambda: {"terms": 0, "cost": 0.0})
    for t, groups in data.items():
        live = {k: g for k, g in groups.items() if g["clicks"] > 0 or g["impr"] > 0}
        if len(live) < 2 or sum(g["clicks"] for g in live.values()) < a.min_clicks:
            continue
        exact_home = [k for k, g in live.items() if t in g["kw"]]
        if len(exact_home) == 1:
            home, why = exact_home[0], "exact keyword match"
        elif sum(g["conv"] for g in live.values()) > 0:
            home = max(live, key=lambda k: (live[k]["conv"] + K * cvr) / (live[k]["clicks"] + K))
            why = "best conversion rate"
        else:
            home = max(live, key=lambda k: live[k]["clicks"])
            why = "most clicks (no conversions anywhere)"
        losers = [k for k in live if k != home]
        contested = sum(live[k]["cost"] for k in losers)
        same_campaign = len({k[0] for k in live}) == 1
        stats = "; ".join(f"{k[0]} > {k[1]}: {g['clicks']:.0f} clk, {g['cost']:.2f} cost, {g['conv']:.1f} conv"
                          for k, g in sorted(live.items(), key=lambda kv: -kv[1]["cost"]))
        out.append({"search_term": t, "ad_groups": len(live),
                    "total_cost": sum(g["cost"] for g in live.values()),
                    "total_conv": sum(g["conv"] for g in live.values()),
                    "cost_outside_home": contested, "home": f"{home[0]} > {home[1]}", "home_reason": why,
                    "add_exact_negative_in": "; ".join(f"{k[0]} > {k[1]}" for k in losers),
                    "negative_level": "ad group" if same_campaign else "ad group (cross-campaign)",
                    "per_ad_group": stats,
                    "action": f"ROUTE to home, negate in {len(losers)} other ad group(s)"})
        for x, y in combinations(sorted(live), 2):
            pk = (f"{x[0]} > {x[1]}", f"{y[0]} > {y[1]}")
            pairs[pk]["terms"] += 1
            pairs[pk]["cost"] += live[x]["cost"] + live[y]["cost"]

    out.sort(key=lambda r: -r["cost_outside_home"])
    prs = sorted(({"ad_group_a": k[0], "ad_group_b": k[1], **v} for k, v in pairs.items()),
                 key=lambda r: -r["cost"])
    fields = ["action", "search_term", "ad_groups", "total_cost", "total_conv", "cost_outside_home", "home",
              "home_reason", "add_exact_negative_in", "negative_level", "per_ad_group"]
    f1 = write_csv(os.path.join(a.out, "every-keyword-overlap-flags.csv"), out, fields)
    f2 = write_csv(os.path.join(a.out, "every-keyword-overlap-pairs.csv"), prs,
                   ["ad_group_a", "ad_group_b", "terms", "cost"])
    print(f"Unique terms: {len(data)}   Terms shown by 2+ ad groups: {len(out)}   "
          f"Ad group pairs in conflict: {len(prs)}")
    print_summary("every-keyword-overlap", list(data), out, money_field="cost_outside_home",
                  show=["search_term", "ad_groups", "cost_outside_home", "home"], files=[f1, f2])


if __name__ == "__main__":
    main()
