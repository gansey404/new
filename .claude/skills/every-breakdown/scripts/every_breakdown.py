#!/usr/bin/env python3
"""every-breakdown: find the placements, age and gender slices bleeding spend.

Auto-detects breakdown columns (Placement, Platform, Device, Age, Gender, Region,
Country). Each segment is compared to the account CPA with a Poisson test, so a
segment is only flagged when its shortfall is unlikely to be bad luck.
"""
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep_common import (apply_overrides, base_parser, div, find_col, load_table, num,
                          pois_cdf, print_summary, write_csv)

BREAKDOWNS = ["Platform", "Placement", "Device platform", "Impression device", "Age", "Gender",
              "Region", "Country", "DMA region"]


def main():
    p = base_parser(__doc__)
    p.add_argument("export", help="Meta export with one or more breakdowns applied")
    p.add_argument("--by", help="Comma list of breakdown columns to use (default: auto-detect)")
    p.add_argument("--per-campaign", action="store_true", help="Judge segments within each campaign")
    p.add_argument("--target-cpa", type=float)
    p.add_argument("--alpha", type=float, default=0.10)
    a = p.parse_args()
    apply_overrides(a)

    h, rows = load_table(a.export)
    c = {k: find_col(h, k) for k in ("spend", "purchases")}
    c["revenue"] = find_col(h, "revenue", required=False)
    c["impressions"] = find_col(h, "impressions", required=False)
    c["campaign"] = find_col(h, "campaign", required=False) if a.per_campaign else None
    if a.by:
        dims = [find_col(h, "breakdown", [b.strip()]) for b in a.by.split(",")]
    else:
        dims = [col for b in BREAKDOWNS for col in [find_col(h, "breakdown", [b], required=False)] if col]
        dims = list(dict.fromkeys(dims))
    if not dims:
        sys.exit("No breakdown column found. In Ads Manager use Breakdown > By Delivery "
                 "(Placement, Age, Gender...) before exporting, or pass --by 'Column name'.")

    seg = defaultdict(lambda: defaultdict(float))
    for r in rows:
        key = ((r[c["campaign"]],) if c["campaign"] else ("All",)) + tuple(r[d] or "(blank)" for d in dims)
        s = seg[key]
        s["spend"] += num(r[c["spend"]])
        s["purch"] += num(r[c["purchases"]])
        if c["revenue"]:
            s["rev"] += num(r[c["revenue"]])
        if c["impressions"]:
            s["impr"] += num(r[c["impressions"]])

    groups = defaultdict(lambda: [0.0, 0.0])
    for k, s in seg.items():
        groups[k[0]][0] += s["spend"]
        groups[k[0]][1] += s["purch"]

    out = []
    for k, s in seg.items():
        gsp, gpu = groups[k[0]]
        cpa = a.target_cpa or div(gsp, gpu)
        if not cpa or s["spend"] <= 0:
            continue
        scpa = div(s["spend"], s["purch"], math.inf)
        exp = s["spend"] / cpa
        pv = pois_cdf(s["purch"], exp)
        waste = max(0.0, s["spend"] - s["purch"] * cpa)
        r = {"campaign": k[0], "segment": " | ".join(k[1:]), "spend": s["spend"],
             "spend_share_pct": div(s["spend"], gsp, 0) * 100, "purchases": s["purch"],
             "expected_purchases": exp, "cpa": scpa, "cpa_vs_account": div(scpa, cpa) if s["purch"] else None,
             "roas": div(s["rev"], s["spend"]) if c["revenue"] else None,
             "excess_spend": waste, "p_value": pv}
        for d, v in zip(dims, k[1:]):
            r[d] = v
        if s["purch"] == 0 and pv < a.alpha:
            r["action"] = "EXCLUDE (zero purchases, spend says there should be some)"
        elif scpa >= 3 * cpa and pv < a.alpha:
            r["action"] = "EXCLUDE (CPA 3x+ account)"
        elif scpa >= 1.3 * cpa and pv < a.alpha:
            r["action"] = "REDUCE (CPA well above account)"
        elif s["purch"] >= 5 and scpa <= 0.7 * cpa:
            r["action"] = "OPPORTUNITY (cheap purchases)"
        else:
            r["action"] = "OK"
        out.append(r)
    out.sort(key=lambda r: -r["excess_spend"])
    flagged = [r for r in out if r["action"] != "OK"]
    fields = ["action", "campaign", "segment"] + dims + ["spend", "spend_share_pct", "purchases",
                                                          "expected_purchases", "cpa", "cpa_vs_account",
                                                          "roas", "excess_spend", "p_value"]
    f1 = write_csv(os.path.join(a.out, "every-breakdown-flags.csv"), flagged, fields)
    f2 = write_csv(os.path.join(a.out, "every-breakdown-all.csv"), out, fields)
    print(f"Breakdowns used: {', '.join(dims)}   Segments: {len(out)}")
    print_summary("every-breakdown", out, flagged, money_field="excess_spend",
                  show=["action", "campaign", "segment", "spend", "purchases", "cpa"], files=[f1, f2])


if __name__ == "__main__":
    main()
