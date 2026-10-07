"""Shared helpers for the sweep skills.

Handles the messy parts of Meta Ads Manager and Google Ads CSV exports:
title / date-range lines above the header, "Total:" rows at the bottom,
UTF-16 tab-separated "Excel" exports, semicolon CSVs, currency symbols,
US or EU thousands/decimal separators, and many date formats.
Standard library only, so it runs anywhere Python 3.8+ runs.
"""
import argparse
import csv
import io
import math
import os
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, date

csv.field_size_limit(10_000_000)
OVERRIDES = {}

# Column aliases, most specific first. Matching ignores case and punctuation.
ALIASES = {
    "date": ["Day", "Date", "Reporting starts", "Created at", "Order date", "Processed at", "Week"],
    "campaign": ["Campaign name", "Campaign"],
    "adset": ["Ad set name", "Ad set"],
    "ad": ["Ad name", "Ad"],
    "ad_id": ["Ad ID"],
    "spend": ["Amount spent", "Spend", "Cost"],
    "impressions": ["Impressions", "Impr."],
    "clicks": ["Link clicks", "Clicks"],
    "purchases": ["Purchases", "Website purchases", "Conversions", "Results"],
    "revenue": ["Purchases conversion value", "Purchase conversion value",
                "Website purchases conversion value", "Conv. value", "Conversion value",
                "Total conv. value"],
    "frequency": ["Frequency"],
    "body": ["Body", "Primary text", "Body (ad settings)"],
    "headline": ["Title", "Headline", "Title (ad settings)"],
    "ad_group": ["Ad group", "Ad group name"],
    "search_term": ["Search term", "Search terms"],
    "match_type": ["Match type", "Search term match type"],
    "keyword": ["Keyword", "Search keyword", "Keyword text"],
    "conversions": ["Conversions", "Purchases", "Conv."],
    "item_id": ["Item ID", "Product ID", "Offer ID", "Item Id", "id"],
    "title": ["Title", "Product title", "Product", "Item title"],
    "availability": ["Availability", "Status"],
    "asset_group": ["Asset group", "Asset group name"],
    "ad_strength": ["Ad strength"],
    "asset": ["Asset", "Asset text", "Text"],
    "asset_type": ["Asset type", "Field type", "Type"],
    "pinned": ["Pinned position", "Pinned", "Pin"],
    "performance": ["Performance", "Performance label", "Asset performance"],
    "status": ["Status", "Asset status"],
    "order_count": ["Orders", "Total orders", "Order count", "Number of orders"],
    "order_id": ["Name", "Order ID", "Order", "Order number", "Id"],
}
# Tokens that make a prefix match wrong unless the alias itself contains them
# (stops "Cost" matching "Cost / conv." or "Impressions" matching "Impr. share").
_AVOID = ("per", "value", "rate", "conv", "ctr", "cpc", "cpm", "share", "top", "abs", "roas")


def base_parser(desc):
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--out", default=".", help="Folder for output files (default: current folder)")
    p.add_argument("--map", action="append", default=[], metavar="FIELD=Column name",
                   help="Force a column mapping, e.g. --map 'spend=Amount spent (EUR)'. Repeatable.")
    return p


def apply_overrides(args):
    for m in args.map:
        if "=" not in m:
            sys.exit(f"--map needs FIELD=Column name, got {m!r}")
        k, v = m.split("=", 1)
        OVERRIDES[k.strip().lower()] = v.strip()
    os.makedirs(args.out, exist_ok=True)


def _read_text(path):
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


_TOTAL = re.compile(r"^Total(:|\s*-|\s*$)")


def load_table(path):
    """Return (header, rows) where rows are dicts. Skips preamble and total rows."""
    if not os.path.exists(path):
        sys.exit(f"File not found: {path}")
    if path.lower().endswith((".xlsx", ".xls")):
        sys.exit(f"{path} is an Excel file. Re-export as CSV, or convert it first "
                 f"(e.g. python -c \"import pandas as p; p.read_excel('{path}').to_csv('out.csv', index=False)\").")
    text = _read_text(path)
    sample = "\n".join(text.splitlines()[:30])
    delim = max([",", "\t", ";"], key=sample.count)
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim) if any(c.strip() for c in r)]
    if not rows:
        sys.exit(f"{path} is empty.")
    widths = Counter(len(r) for r in rows if len(r) > 1)
    if not widths:
        sys.exit(f"Could not find a table in {path}.")
    width = widths.most_common(1)[0][0]
    hi = next(i for i, r in enumerate(rows) if len(r) == width)
    header = [h.strip() for h in rows[hi]]
    out = []
    for r in rows[hi + 1:]:
        if len(r) != width:
            continue
        if any(_TOTAL.match(c.strip()) for c in r[:4]):
            continue
        out.append(dict(zip(header, (c.strip() for c in r))))
    return header, out


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def find_col(header, field, aliases=None, required=True):
    """Find the column for a logical field. --map overrides win."""
    nh = {}
    for h in header:
        nh.setdefault(_norm(h), h)
    if field in OVERRIDES:
        want = OVERRIDES[field]
        if want in header:
            return want
        if _norm(want) in nh:
            return nh[_norm(want)]
        sys.exit(f"--map {field}={want!r}: no such column. Columns: {header}")
    aliases = aliases or ALIASES.get(field, [field])
    for a in aliases:
        if _norm(a) in nh:
            return nh[_norm(a)]
    for a in aliases:
        na = _norm(a)
        for k, h in nh.items():
            if k.startswith(na) and not any(t in k and t not in na for t in _AVOID):
                return h
    if required:
        sys.exit(f"Could not find a column for '{field}' (tried: {', '.join(aliases)}).\n"
                 f"Columns in file: {header}\n"
                 f"Fix: rerun with --map '{field}=<exact column name>'")
    return None


def num(v):
    """Parse '$1,234.50', '1.234,50 Ft', '12,5%', '--', '(30)' into a float."""
    if v is None:
        return 0.0
    s = str(v).strip()
    if not s or s in ("--", "-", "—", "–", "N/A", "n/a", "null", "None"):
        return 0.0
    neg = (s.startswith("(") and s.endswith(")")) or s.startswith("-")
    s = re.sub(r"[^0-9.,]", "", s)
    if not s or not re.search(r"\d", s):
        return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) > 2 or len(parts[-1]) == 3:
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        x = float(s)
    except ValueError:
        return 0.0
    return -x if neg else x


_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y.%m.%d", "%Y/%m/%d",
                 "%b %d, %Y", "%a, %b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y",
                 "%m/%d/%y", "%d-%m-%Y", "%Y%m%d")


def parse_date(s):
    if not s:
        return None
    s = str(s).strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            pass
    s = re.sub(r"\s*\.\s*", ".", s).strip(".")  # "2026. 09. 01." -> "2026.09.01"
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def div(a, b, default=None):
    return a / b if b else default


def median(xs, default=None):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else default


def pois_cdf(k, lam):
    """P(X <= k) for X ~ Poisson(lam). Normal approximation for large lam."""
    if lam <= 0:
        return 1.0
    k = int(math.floor(k))
    if k < 0:
        return 0.0
    if lam > 300:
        return 0.5 * (1 + math.erf((k + 0.5 - lam) / math.sqrt(2 * lam)))
    term = math.exp(-lam)
    s = term
    for i in range(1, k + 1):
        term *= lam / i
        s += term
    return min(1.0, s)


def pois_sf(k, lam):
    """P(X >= k)."""
    return 1.0 - pois_cdf(k - 1, lam)


def r2(x, d=2):
    if x is None:
        return ""
    if isinstance(x, float) and (math.isinf(x) or math.isnan(x)):
        return ""
    return round(x, d)


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r2(v) if isinstance(v, float) else v for k, v in r.items()})
    return path


def print_summary(title, all_rows, flagged, action_field="action", money_field=None,
                  show=(), limit=25, files=()):
    print(f"\n=== {title} ===")
    print(f"Rows swept: {len(all_rows)}   Flagged: {len(flagged)}")
    counts = Counter(r[action_field].split(" ")[0] for r in flagged)
    for k, v in counts.most_common():
        extra = ""
        if money_field:
            amt = sum(r.get(money_field) or 0 for r in flagged if r[action_field].split(" ")[0] == k)
            extra = f"   {money_field}: {amt:,.2f}"
        print(f"  {k:<16} {v:>5}{extra}")
    if flagged and show:
        print(f"\nTop {min(limit, len(flagged))} flagged rows:")
        print(" | ".join(show))
        for r in flagged[:limit]:
            print(" | ".join(str(r2(r.get(c)) if isinstance(r.get(c), float) else r.get(c, "")) for c in show))
    for f in files:
        print(f"\nWrote {f}")
    print("\nNext: read EVERY row of the flags file before reporting (see SKILL.md).")
