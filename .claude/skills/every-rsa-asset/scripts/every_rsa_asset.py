#!/usr/bin/env python3
"""every-rsa-asset: grade every RSA headline and description; flag replace, unpin, clone.

Uses Google's performance label (Best / Good / Low) when present, and CTR vs the
ad group's average for the same field type when labels are missing or Learning.
Also flags ad groups with fewer than 15 headlines or 4 descriptions.

--validate new_assets.csv checks Claude-written replacements (columns: type, text)
against Google's limits: 30 characters for headlines, 90 for descriptions.
"""
import os
import sys
import unicodedata
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep_common import (apply_overrides, base_parser, div, find_col, load_table, num,
                          print_summary, write_csv)

NOT_PINNED = {"", "--", "-", "none", "no", "not pinned", "unpinned", "0"}


def gads_len(s):
    """Google counts wide characters (CJK etc.) as 2."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def kind(t):
    t = (t or "").lower()
    if "long headline" in t:
        return "long headline", 90
    if "headline" in t:
        return "headline", 30
    if "description" in t:
        return "description", 90
    return None, None


def validate(path):
    h, rows = load_table(path)
    tc = find_col(h, "v_type", ["type", "asset type", "field type"])
    xc = find_col(h, "v_text", ["text", "asset", "headline"])
    bad = 0
    for r in rows:
        k, lim = kind(r[tc])
        n = gads_len(r[xc])
        ok = lim is None or n <= lim
        bad += not ok
        print(f"{'OK  ' if ok else 'OVER'} {n:>3}/{lim or '?':<3} {k or r[tc]}: {r[xc]}")
    print(f"\n{len(rows)} checked, {bad} over the limit.")
    sys.exit(1 if bad else 0)


def main():
    p = base_parser(__doc__)
    p.add_argument("export", nargs="?", help="Google Ads asset report (RSA headlines + descriptions)")
    p.add_argument("--min-impr", type=float, default=1000, help="Impressions needed before judging an asset")
    p.add_argument("--validate", metavar="CSV", help="Check new asset text lengths and exit")
    a = p.parse_args()
    apply_overrides(a)
    if a.validate:
        validate(a.validate)
    if not a.export:
        sys.exit("Pass the asset report CSV (or --validate file.csv).")

    h, rows = load_table(a.export)
    c = {k: find_col(h, k) for k in ("asset", "asset_type", "impressions")}
    for k in ("campaign", "ad_group", "clicks", "conversions", "pinned", "performance", "status"):
        c[k] = find_col(h, k, required=False)

    assets = defaultdict(lambda: {"impr": 0.0, "clicks": 0.0, "conv": 0.0, "pins": set(), "labels": set()})
    for r in rows:
        k, _ = kind(r[c["asset_type"]])
        if not k or k == "long headline":
            continue
        if c["status"] and r[c["status"]].lower() in ("removed", "deleted"):
            continue
        key = (r.get(c["campaign"], "") if c["campaign"] else "", r.get(c["ad_group"], "") if c["ad_group"] else "",
               k, r[c["asset"]])
        A = assets[key]
        A["impr"] += num(r[c["impressions"]])
        if c["clicks"]:
            A["clicks"] += num(r[c["clicks"]])
        if c["conversions"]:
            A["conv"] += num(r[c["conversions"]])
        if c["pinned"] and r[c["pinned"]].strip().lower() not in NOT_PINNED:
            A["pins"].add(r[c["pinned"]].strip())
        if c["performance"] and r[c["performance"]].strip():
            A["labels"].add(r[c["performance"]].strip().lower())

    grp = defaultdict(lambda: {"impr": 0.0, "clicks": 0.0, "n": 0})
    for (cn, ag, k, _), A in assets.items():
        G = grp[(cn, ag, k)]
        G["impr"] += A["impr"]
        G["clicks"] += A["clicks"]
        G["n"] += 1

    out = []
    for (cn, ag, k, text), A in assets.items():
        G = grp[(cn, ag, k)]
        ctr = div(A["clicks"], A["impr"])
        gctr = div(G["clicks"], G["impr"])
        rel = div(ctr, gctr) if ctr is not None and gctr else None
        label = "best" if "best" in A["labels"] else "low" if "low" in A["labels"] else \
            "good" if "good" in A["labels"] else next(iter(A["labels"]), "")
        pinned = ", ".join(sorted(A["pins"]))
        r = {"campaign": cn, "ad_group": ag, "type": k, "text": text, "chars": gads_len(text), "label": label,
             "pinned": pinned, "impr": A["impr"], "clicks": A["clicks"], "ctr_pct": (ctr or 0) * 100,
             "ctr_vs_group": rel, "conv": A["conv"]}
        enough = A["impr"] >= a.min_impr
        acts = []
        if label == "low" and A["impr"] >= a.min_impr / 2:
            acts.append("REPLACE (Low label)")
        elif enough and rel is not None and rel < 0.6 and label not in ("best", "good"):
            acts.append("REPLACE (CTR under 60% of ad group)")
        if acts and pinned:
            acts.insert(0, "UNPIN")
        if label == "best" or (enough and rel is not None and rel >= 1.4 and A["conv"] > 0):
            acts.append("CLONE (write 2 variants)")
        r["action"] = " + ".join(acts) if acts else "KEEP"
        out.append(r)

    # Ad groups missing assets
    for (cn, ag, k), G in grp.items():
        need = 15 if k == "headline" else 4
        if G["n"] < need:
            out.append({"campaign": cn, "ad_group": ag, "type": k, "text": f"(ad group has {G['n']} {k}s)",
                        "action": f"ADD {need - G['n']} {k.upper()}S", "impr": G["impr"]})

    rank = {"UNPIN": 0, "REPLACE": 1, "ADD": 2, "CLONE": 3}
    flagged = sorted([r for r in out if r["action"] != "KEEP"],
                     key=lambda r: (r["campaign"], r["ad_group"], rank[r["action"].split(" ")[0]],
                                    -(r.get("impr") or 0)))
    fields = ["action", "campaign", "ad_group", "type", "text", "chars", "label", "pinned", "impr", "clicks",
              "ctr_pct", "ctr_vs_group", "conv"]
    f1 = write_csv(os.path.join(a.out, "every-rsa-asset-flags.csv"), flagged, fields)
    f2 = write_csv(os.path.join(a.out, "every-rsa-asset-all.csv"), out, fields)
    print(f"Assets graded: {len(assets)} across {len({(k[0], k[1]) for k in grp})} ad groups")
    print_summary("every-rsa-asset", out, flagged, show=["action", "ad_group", "type", "text", "label"],
                  files=[f1, f2])


if __name__ == "__main__":
    main()
