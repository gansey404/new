---
name: every-keyword-overlap
description: Sweep a Google Ads search terms report for queries that trigger ads in more than one ad group or campaign (keyword cannibalization), pick the right home for each query, and list the exact negatives to add everywhere else. Use whenever the user mentions keyword overlap, cannibalization, ad groups competing, duplicate keywords, query sculpting, messy account structure, or broad match stealing traffic, even if they don't name this skill.
---

# every-keyword-overlap

Finds the queries your own ad groups fight over, and says where each one should live.

## 1. Get the data

Same export as every-search-term: a **Google Ads search terms report** for the last 30–90 days. It **must include Campaign and Ad group columns**, plus Keyword if possible (that's how the script knows which ad group was built for the query).
- Google Ads → Campaigns → Insights and reports → Search terms → add Campaign, Ad group, Keyword, Clicks, Cost, Conversions → Download → CSV.

## 2. Run the sweep

```bash
python scripts/every_keyword_overlap.py <search_terms.csv> --out sweep-output
```
`--min-clicks 3` skips trivial overlaps. Outputs:
- `every-keyword-overlap-flags.csv`: one row per contested query, with the chosen home, the reason, and the ad groups to negate it in
- `every-keyword-overlap-pairs.csv`: which ad group pairs fight most (structural problems show up here)

## 3. Review every flagged row

Read the whole flags file. The script's choice of home is a starting point; check it:
- **Home logic**: an exact-match keyword equal to the query wins. Otherwise best smoothed conversion rate. Override it when the query's meaning clearly belongs elsewhere (e.g. "running shoes women" belongs in the Women ad group even if Men converted once). Say when you override.
- **Cross-campaign overlap** (Brand vs Generic, Search vs Shopping-intent, different geos) often needs campaign-level negatives, or is intentional. Ask before negating brand out of generic if unsure.
- Overlap with **broad match** is expected. Only route it when the cost outside home is meaningful.
- Use the pairs file to spot structural causes: if two ad groups share dozens of queries, they probably should be merged or their keywords tightened, which beats adding 40 negatives.

## 4. Report

Lead with the total spend landing outside the right home and the top conflicting pairs. Then:

| Query | Ad groups | Cost outside home | Home | Negate in |

Finish with paste-ready negatives grouped by destination: each `Campaign > Ad group` heading followed by its `[exact]` negatives in a code block. Add structural fixes (merge, tighten keywords) as a separate short list.
