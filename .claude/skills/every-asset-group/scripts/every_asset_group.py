#!/usr/bin/env python3
"""every-asset-group: find Performance Max asset groups spending with nothing back.

Asset groups share their campaign's budget, so each one is judged against its own
campaign's CPA / ROAS as well as the target. Poisson-tested so small groups
aren't flagged on noise.
"""
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep_common import (apply_overrides, base_parser, div, find_col, load_table, num, pois_cdf,
                          print_summary, write_csv)


def main():
    p = base_parser(__doc__)
    p.add_argument("export", help="Google Ads asset group report (PMax)")
    p.add_argument("--target-cpa", type=float)
    a = p.parse_args()
    apply_overrides(a)

    h, rows = load_table(a.export)
    c = {k: find_col(h, k) for k in ("campaign", "asset_group", "spend", "conversions")}
    for k in ("revenue", "impressions", "clicks", "ad_strength", "status"):
        c[k] = find_col(h, k, required=False)
    g = defaultdict(lambda: defaultdict(float))
    meta = {}
    for r in rows:
        k = (r[c["campaign"]], r[c["asset_group"]])
        if not k[1]:
            continue
        for f, col in (("cost", "spend"), ("conv", "conversions"), ("rev", "revenue"),
                       ("impr", "impressions"), ("clicks", "clicks")):
            if c[col]:
                g[k][f] += num(r[c[col]])
        meta[k] = (r.get(c["ad_strength"], "") if c["ad_strength"] else "",
                   r.get(c["status"], "") if c["status"] else "")

    camp = defaultdict(lambda: defaultdict(float))
    for (cn, _), v in g.items():
        for f in ("cost", "conv", "rev"):
            camp[cn][f] += v[f]
        camp[cn]["groups"] += 1
    tot_cost = sum(v["cost"] for v in g.values())
    tot_conv = sum(v["conv"] for v in g.values())
    tcpa = a.target_cpa or div(tot_cost, tot_conv)
    if not tcpa:
        sys.exit("No conversions in file and no --target-cpa given.")

    out = []
    for (cn, ag), v in g.items():
        C = camp[cn]
        ccpa = div(C["cost"], C["conv"]) or tcpa
        croas = div(C["rev"], C["cost"]) if c["revenue"] else None
        gcpa = div(v["cost"], v["conv"], math.inf)
        groas = div(v["rev"], v["cost"]) if c["revenue"] else None
        share = div(v["cost"], C["cost"], 0)
        strength, status = meta[(cn, ag)]
        r = {"campaign": cn, "asset_group": ag, "status": status, "ad_strength": strength, "cost": v["cost"],
             "cost_share_in_campaign_pct": share * 100, "conv": v["conv"], "cpa": gcpa, "campaign_cpa": ccpa,
             "roas": groas, "campaign_roas": croas, "impr": v["impr"]}
        bench = min(ccpa, tcpa * 1.5)
        pv = pois_cdf(v["conv"], v["cost"] / bench) if v["cost"] > 0 else 1
        r["p_value"] = pv
        flags = []
        if v["conv"] == 0 and v["cost"] >= 2 * tcpa:
            flags.append("NO RETURN (2x target CPA spent, 0 conv)")
        elif C["groups"] > 1 and gcpa >= 1.75 * ccpa and share >= 0.10 and pv < 0.10:
            flags.append("UNDERPERFORMER (CPA 1.75x+ campaign)")
        elif groas is not None and croas and v["cost"] >= 2 * tcpa and groas < 0.5 * croas:
            flags.append("LOW ROAS (under half campaign ROAS)")
        elif C["groups"] > 1 and v["conv"] >= 5 and gcpa <= 0.7 * ccpa:
            flags.append("WINNER (feed it budget)")
        if strength and strength.strip().lower() == "poor":
            flags.append("FIX ASSETS (ad strength Poor)")
        r["action"] = " + ".join(flags) if flags else "OK"
        out.append(r)

    rank = {"NO": 0, "UNDERPERFORMER": 1, "LOW": 2, "FIX": 3, "WINNER": 4}
    flagged = sorted([r for r in out if r["action"] != "OK"],
                     key=lambda r: (rank[r["action"].split(" ")[0]], -r["cost"]))
    fields = ["action", "campaign", "asset_group", "status", "ad_strength", "cost", "cost_share_in_campaign_pct",
              "conv", "cpa", "campaign_cpa", "roas", "campaign_roas", "impr", "p_value"]
    f1 = write_csv(os.path.join(a.out, "every-asset-group-flags.csv"), flagged, fields)
    f2 = write_csv(os.path.join(a.out, "every-asset-group-all.csv"), sorted(out, key=lambda r: -r["cost"]), fields)
    print(f"Asset groups: {len(out)} in {len(camp)} campaigns   Target CPA: {tcpa:,.2f}")
    print_summary("every-asset-group", out, flagged, money_field="cost",
                  show=["action", "campaign", "asset_group", "cost", "conv"], files=[f1, f2])


if __name__ == "__main__":
    main()
