#!/usr/bin/env python3
"""every-search-term: sweep every search term and write negatives ready to paste.

Term level: zero-conversion terms that spent at least the target CPA, or got
enough clicks that ~3 conversions were expected at the account's conversion rate.
N-gram level: 1- and 2-word fragments that never convert across many terms
become phrase-match negatives. Converting non-keyword terms are flagged to promote.
"""
import math
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep_common import (apply_overrides, base_parser, div, find_col, load_table, num,
                          print_summary, write_csv)

STOP = set("a an and the of for to in on at by with from or is are my your our near me best top".split())
INTENT = re.compile(r"\b(free|jobs?|careers?|salary|hiring|internship|how to|diy|used|second hand|"
                    r"login|log in|sign in|download|pdf|meaning|definition|wiki|reddit|youtube|"
                    r"template|course|tutorial|repair|manual|torrent|crack)\b", re.I)


def clean_kw(k):
    return re.sub(r'[\[\]"+]', "", k or "").strip().lower()


def main():
    p = base_parser(__doc__)
    p.add_argument("export", help="Google Ads search terms report (90 days recommended)")
    p.add_argument("--target-cpa", type=float, help="Default: account cost / conversions in the file")
    p.add_argument("--brand", default="", help="Comma list of brand words that must never be negated")
    p.add_argument("--min-ngram-terms", type=int, default=3)
    a = p.parse_args()
    apply_overrides(a)

    h, rows = load_table(a.export)
    c = {k: find_col(h, k) for k in ("search_term", "clicks", "spend", "conversions")}
    for k in ("impressions", "revenue", "campaign", "ad_group", "keyword", "match_type"):
        c[k] = find_col(h, k, required=False)
    brand = [b.strip().lower() for b in a.brand.split(",") if b.strip()]

    terms = defaultdict(lambda: {"impr": 0.0, "clicks": 0.0, "cost": 0.0, "conv": 0.0, "rev": 0.0,
                                 "camps": set(), "kws": set(), "mts": set()})
    keywords = set()
    for r in rows:
        t = r[c["search_term"]].strip().lower()
        if not t:
            continue
        s = terms[t]
        s["clicks"] += num(r[c["clicks"]])
        s["cost"] += num(r[c["spend"]])
        s["conv"] += num(r[c["conversions"]])
        for k, f in (("impr", "impressions"), ("rev", "revenue")):
            if c[f]:
                s[k] += num(r[c[f]])
        if c["campaign"]:
            s["camps"].add(r[c["campaign"]] + (f" > {r[c['ad_group']]}" if c["ad_group"] else ""))
        if c["keyword"] and r[c["keyword"]]:
            s["kws"].add(r[c["keyword"]])
            keywords.add(clean_kw(r[c["keyword"]]))
        if c["match_type"] and r[c["match_type"]]:
            s["mts"].add(r[c["match_type"]])

    cost = sum(s["cost"] for s in terms.values())
    conv = sum(s["conv"] for s in terms.values())
    clicks = sum(s["clicks"] for s in terms.values())
    tcpa = a.target_cpa or div(cost, conv)
    cvr = div(conv, clicks)
    if not tcpa:
        sys.exit("No conversions in file and no --target-cpa given.")
    clicks_needed = max(15, 3 / cvr) if cvr else 30

    out = []
    for t, s in terms.items():
        is_brand = any(b in t for b in brand)
        cpa = div(s["cost"], s["conv"], math.inf)
        r = {"search_term": t, "impr": s["impr"], "clicks": s["clicks"], "cost": s["cost"], "conv": s["conv"],
             "cpa": cpa, "conv_value": s["rev"], "is_keyword": "yes" if t in keywords else "",
             "match_types": "; ".join(sorted(s["mts"])), "keywords": "; ".join(sorted(s["kws"]))[:200],
             "where": "; ".join(sorted(s["camps"]))[:300]}
        if is_brand:
            act = "BRAND (never negate)" if s["conv"] == 0 and s["cost"] >= tcpa else "OK"
        elif s["conv"] == 0 and s["cost"] >= tcpa:
            act = f"NEGATIVE (spent {s['cost'] / tcpa:.1f}x target CPA, 0 conv)"
        elif s["conv"] == 0 and s["clicks"] >= clicks_needed:
            act = f"NEGATIVE ({s['clicks']:.0f} clicks, 0 conv)"
        elif s["conv"] > 0 and cpa >= 2.5 * tcpa and s["cost"] >= 3 * tcpa:
            act = "EXPENSIVE (converts, but at 2.5x+ target CPA)"
        elif s["conv"] == 0 and s["clicks"] >= 1 and INTENT.search(t):
            act = "CHECK INTENT (wrong-intent word)"
        elif s["conv"] >= 2 and cpa <= tcpa and t not in keywords:
            act = "PROMOTE (add as exact keyword)"
        else:
            act = "OK"
        r["action"] = act
        out.append(r)

    # N-gram sweep
    grams = defaultdict(lambda: {"cost": 0.0, "clicks": 0.0, "conv": 0.0, "terms": 0})
    for t, s in terms.items():
        toks = re.findall(r"[\w'&-]+", t)
        seen = set()
        for n in (1, 2):
            for i in range(len(toks) - n + 1):
                g = " ".join(toks[i:i + n])
                if g in seen or (n == 1 and (g in STOP or len(g) < 3)):
                    continue
                seen.add(g)
                G = grams[g]
                G["cost"] += s["cost"]
                G["clicks"] += s["clicks"]
                G["conv"] += s["conv"]
                G["terms"] += 1
    ng = []
    for g, G in grams.items():
        if (G["conv"] == 0 and G["cost"] >= 2 * tcpa and G["terms"] >= a.min_ngram_terms
                and not any(b in g for b in brand) and g not in keywords):
            ng.append({"ngram": g, "terms": G["terms"], "clicks": G["clicks"], "cost": G["cost"],
                       "action": "NGRAM NEGATIVE (phrase)"})
    ng.sort(key=lambda x: -x["cost"])
    # Drop 2-grams fully explained by an already-flagged 1-gram
    ones = {x["ngram"] for x in ng if " " not in x["ngram"]}
    ng = [x for x in ng if " " not in x["ngram"] or not any(w in ones for w in x["ngram"].split())]

    rank = {"NEGATIVE": 0, "EXPENSIVE": 1, "CHECK": 2, "BRAND": 3, "PROMOTE": 4}
    flagged = sorted([r for r in out if r["action"] != "OK"],
                     key=lambda r: (rank[r["action"].split(" ")[0]], -r["cost"]))
    fields = ["action", "search_term", "clicks", "cost", "conv", "cpa", "conv_value", "impr", "is_keyword",
              "match_types", "keywords", "where"]
    f1 = write_csv(os.path.join(a.out, "every-search-term-flags.csv"), flagged, fields)
    f2 = write_csv(os.path.join(a.out, "every-search-term-ngrams.csv"), ng,
                   ["action", "ngram", "terms", "clicks", "cost"])
    neg_exact = [f"[{r['search_term']}]" for r in flagged if r["action"].startswith("NEGATIVE")]
    neg_phrase = [f'"{x["ngram"]}"' for x in ng]
    f3 = os.path.join(a.out, "negatives-exact.txt")
    f4 = os.path.join(a.out, "negatives-phrase.txt")
    open(f3, "w", encoding="utf-8").write("\n".join(neg_exact) + ("\n" if neg_exact else ""))
    open(f4, "w", encoding="utf-8").write("\n".join(neg_phrase) + ("\n" if neg_phrase else ""))
    wasted = sum(r["cost"] for r in flagged if r["action"].startswith("NEGATIVE"))
    print(f"Target CPA used: {tcpa:,.2f}   Account conv. rate: {cvr or 0:.2%}   "
          f"Zero-conv click threshold: {clicks_needed:.0f}")
    print(f"Unique terms: {len(out)}   Draft negatives: {len(neg_exact)} exact + {len(neg_phrase)} phrase   "
          f"Spend on negative candidates: {wasted:,.2f}")
    print_summary("every-search-term", out, flagged, money_field="cost",
                  show=["action", "search_term", "clicks", "cost", "conv"], files=[f1, f2, f3, f4])


if __name__ == "__main__":
    main()
