#!/usr/bin/env python3
"""every-product: find zombie products getting no impressions (plus money pits and heroes).

Product report: Shopping / PMax product performance by Item ID.
Optional --feed: Merchant Center product list, so items that never appear in the
report at all are caught as zombies too. Writes a supplemental feed
(id + custom label) ready to upload to Merchant Center.
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
    p.add_argument("export", help="Google Ads products report (Item ID, Impr., Clicks, Cost, Conversions...)")
    p.add_argument("--feed", help="Merchant Center product export (id, title, availability)")
    p.add_argument("--min-impr", type=float, default=100, help="Below this many impressions = zombie")
    p.add_argument("--target-cpa", type=float)
    p.add_argument("--label-slot", default="custom_label_0", help="Supplemental feed column to write")
    a = p.parse_args()
    apply_overrides(a)

    h, rows = load_table(a.export)
    c = {k: find_col(h, k) for k in ("item_id", "impressions", "clicks", "spend", "conversions")}
    c["revenue"] = find_col(h, "revenue", required=False)
    c["title"] = find_col(h, "title", required=False)
    prods = defaultdict(lambda: defaultdict(float))
    titles = {}
    for r in rows:
        iid = r[c["item_id"]].strip()
        if not iid:
            continue
        k = iid.lower()
        titles.setdefault(k, (iid, r.get(c["title"], "") if c["title"] else ""))
        for f, col in (("impr", "impressions"), ("clicks", "clicks"), ("cost", "spend"), ("conv", "conversions")):
            prods[k][f] += num(r[c[col]])
        if c["revenue"]:
            prods[k]["rev"] += num(r[c["revenue"]])

    feed = {}
    if a.feed:
        fh, frows = load_table(a.feed)
        fid = find_col(fh, "feed_id", ["id", "Item ID", "Offer ID", "Product ID"])
        ft = find_col(fh, "title", required=False)
        fav = find_col(fh, "availability", required=False)
        for r in frows:
            if r[fid].strip():
                k = r[fid].strip().lower()
                feed[k] = (r[fid].strip(), r.get(ft, "") if ft else "", r.get(fav, "") if fav else "")
                titles.setdefault(k, (feed[k][0], feed[k][1]))
                prods.setdefault(k, defaultdict(float))

    cost = sum(v["cost"] for v in prods.values())
    conv = sum(v["conv"] for v in prods.values())
    rev = sum(v["rev"] for v in prods.values())
    cpa = a.target_cpa or div(cost, conv)
    roas = div(rev, cost)
    if not cpa:
        sys.exit("No conversions in file and no --target-cpa given.")

    out = []
    for k, v in prods.items():
        iid, title = titles[k]
        avail = feed.get(k, ("", "", ""))[2]
        proas = div(v["rev"], v["cost"])
        r = {"item_id": iid, "title": title, "availability": avail, "impr": v["impr"], "clicks": v["clicks"],
             "cost": v["cost"], "conv": v["conv"], "cpa": div(v["cost"], v["conv"], math.inf),
             "conv_value": v["rev"], "roas": proas, "label": ""}
        oos = avail and "out" in avail.lower()
        if v["impr"] < a.min_impr:
            r["action"] = ("ZOMBIE (out of stock)" if oos else
                           "ZOMBIE (never served)" if v["impr"] == 0 else "ZOMBIE (almost no impressions)")
            r["label"] = "" if oos else "zombie"
        elif v["conv"] == 0 and v["cost"] >= 2 * cpa:
            r["action"], r["label"] = "MONEY PIT (2x CPA spent, 0 conv)", "money_pit"
        elif roas and proas is not None and v["cost"] >= 2 * cpa and proas < 0.5 * roas:
            r["action"], r["label"] = "LOW ROAS (under half account ROAS)", "low_roas"
        elif v["conv"] >= 3 and ((roas and proas and proas >= 1.5 * roas) or
                                 (not roas and r["cpa"] <= 0.6 * cpa)):
            r["action"], r["label"] = "HERO (give it its own budget)", "hero"
        else:
            r["action"] = "OK"
        out.append(r)

    rank = {"MONEY": 0, "LOW": 1, "ZOMBIE": 2, "HERO": 3}
    flagged = sorted([r for r in out if r["action"] != "OK"],
                     key=lambda r: (rank[r["action"].split(" ")[0]], -r["cost"], r["impr"]))
    fields = ["action", "item_id", "title", "availability", "impr", "clicks", "cost", "conv", "cpa",
              "conv_value", "roas", "label"]
    f1 = write_csv(os.path.join(a.out, "every-product-flags.csv"), flagged, fields)
    supp = [{"id": r["item_id"], a.label_slot: r["label"]} for r in flagged if r["label"]]
    f2 = write_csv(os.path.join(a.out, "supplemental-feed-labels.csv"), supp, ["id", a.label_slot])
    print(f"Products: {len(out)} ({len(feed)} in feed)   Target CPA: {cpa:,.2f}"
          + (f"   Account ROAS: {roas:.2f}" if roas else ""))
    print_summary("every-product", out, flagged, money_field="cost",
                  show=["action", "item_id", "title", "impr", "cost", "conv"], files=[f1, f2])


if __name__ == "__main__":
    main()
