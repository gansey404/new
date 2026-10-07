#!/usr/bin/env python3
"""every-angle: rank your selling angles by CPA.

Angles come from (in order): --angles mapping CSV (ad name -> angle), or a token in
the ad name (--token N --sep _). With neither, the script writes
every-angle-to-label.csv so Claude can label each ad's angle, then you rerun.
"""
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep_common import (apply_overrides, base_parser, div, find_col, load_table, num,
                          print_summary, write_csv)


def main():
    p = base_parser(__doc__)
    p.add_argument("export", help="Meta export at Ad level (totals or daily rows; both work)")
    p.add_argument("--angles", help="CSV with columns ad (or ad_name) and angle")
    p.add_argument("--token", type=int, help="Angle is this 0-based token of the ad name")
    p.add_argument("--sep", default="_", help="Separator for --token (default _)")
    p.add_argument("--target-cpa", type=float)
    p.add_argument("--min-purchases", type=int, default=10, help="Purchases needed to call an angle")
    a = p.parse_args()
    apply_overrides(a)

    h, rows = load_table(a.export)
    c = {k: find_col(h, k) for k in ("ad", "spend", "purchases")}
    c["revenue"] = find_col(h, "revenue", required=False)
    c["body"] = find_col(h, "body", required=False)
    c["headline"] = find_col(h, "headline", required=False)

    ads = defaultdict(lambda: defaultdict(float))
    text = {}
    for r in rows:
        name = r[c["ad"]]
        if not name:
            continue
        ads[name]["spend"] += num(r[c["spend"]])
        ads[name]["purch"] += num(r[c["purchases"]])
        if c["revenue"]:
            ads[name]["rev"] += num(r[c["revenue"]])
        if name not in text:
            text[name] = (r.get(c["headline"], "") if c["headline"] else "",
                          r.get(c["body"], "") if c["body"] else "")

    angle_of = {}
    if a.angles:
        mh, mrows = load_table(a.angles)
        adc = find_col(mh, "map_ad", ["ad", "ad_name", "Ad name"])
        anc = find_col(mh, "angle", ["angle", "Angle", "selling angle"])
        angle_of = {r[adc]: r[anc].strip() for r in mrows if r[anc].strip()}
    elif a.token is not None:
        for n in ads:
            parts = n.split(a.sep)
            if len(parts) > a.token:
                angle_of[n] = parts[a.token].strip()
    else:
        path = os.path.join(a.out, "every-angle-to-label.csv")
        lab = [{"ad": n, "angle": "", "spend": v["spend"], "purchases": v["purch"],
                "headline": text[n][0], "body": text[n][1][:500]}
               for n, v in sorted(ads.items(), key=lambda kv: -kv[1]["spend"])]
        write_csv(path, lab, ["ad", "angle", "spend", "purchases", "headline", "body"])
        print(f"No angle source given. Wrote {path} with {len(lab)} ads.\n"
              "Fill the 'angle' column (one short label per ad, reuse labels exactly), then rerun:\n"
              f"  python scripts/every_angle.py {a.export} --angles {path} --out {a.out}")
        return

    tot_spend = sum(v["spend"] for v in ads.values())
    tot_purch = sum(v["purch"] for v in ads.values())
    tot_rev = sum(v["rev"] for v in ads.values())
    cpa = a.target_cpa or div(tot_spend, tot_purch)
    if not cpa:
        sys.exit("No purchases in file and no --target-cpa given.")

    ang = defaultdict(lambda: {"spend": 0.0, "purch": 0.0, "rev": 0.0, "ads": 0, "best": None})
    for n, v in ads.items():
        g = ang[angle_of.get(n, "(unlabeled)")]
        g["spend"] += v["spend"]
        g["purch"] += v["purch"]
        g["rev"] += v["rev"]
        g["ads"] += 1
        acpa = div(v["spend"], v["purch"], math.inf)
        if v["purch"] >= 3 and (g["best"] is None or acpa < g["best"][1]):
            g["best"] = (n, acpa)

    out = []
    for name, g in ang.items():
        gcpa = div(g["spend"], g["purch"], math.inf)
        share = div(g["spend"], tot_spend, 0)
        r = {"angle": name, "ads": g["ads"], "spend": g["spend"], "spend_share_pct": share * 100,
             "purchases": g["purch"], "cpa": gcpa, "cpa_vs_account": div(gcpa, cpa) if gcpa != math.inf else None,
             "roas": div(g["rev"], g["spend"]) if c["revenue"] else None,
             "best_ad": g["best"][0] if g["best"] else ""}
        if name == "(unlabeled)":
            act = "LABEL (ads without an angle)"
        elif g["purch"] == 0 and g["spend"] >= 3 * cpa:
            act = "CUT (no purchases after 3x CPA)"
        elif g["purch"] < a.min_purchases:
            act = "TOO EARLY (needs more purchases)" if gcpa > 0.8 * cpa else "TEST MORE (promising, low data)"
        elif gcpa <= 0.8 * cpa and share < 0.15:
            act = "SCALE (underfunded winner)"
        elif gcpa <= 0.8 * cpa:
            act = "SCALE"
        elif gcpa >= 1.3 * cpa:
            act = "CUT"
        else:
            act = "HOLD"
        r["action"] = act
        out.append(r)
    out.sort(key=lambda r: r["cpa"])
    flagged = [r for r in out if not r["action"].startswith("HOLD")]
    fields = ["angle", "action", "ads", "spend", "spend_share_pct", "purchases", "cpa", "cpa_vs_account",
              "roas", "best_ad"]
    f1 = write_csv(os.path.join(a.out, "every-angle-ranking.csv"), out, fields)
    print(f"Account CPA used: {cpa:,.2f}   Ads: {len(ads)}   Angles: {len(out)}"
          + (f"   Account ROAS: {tot_rev / tot_spend:.2f}" if c["revenue"] and tot_spend else ""))
    print_summary("every-angle", out, flagged, money_field="spend",
                  show=["angle", "action", "spend", "purchases", "cpa"], files=[f1])


if __name__ == "__main__":
    main()
