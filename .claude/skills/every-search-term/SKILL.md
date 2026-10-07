---
name: every-search-term
description: Sweep every row of a Google Ads search terms report (90 days), find wasted spend at the term and n-gram level, and write negative keyword lists ready to paste, plus converting terms to add as keywords. Use whenever the user mentions search terms, negative keywords, wasted spend, irrelevant queries, search query report (SQR), n-grams, or wants a Google Search audit, even if they don't name this skill.
---

# every-search-term

Reads 90 days of search terms and writes negatives ready to paste. The script flags candidates; you check every one, because a wrong negative silently kills good traffic.

## 1. Get the data

You need a **Google Ads search terms report**, ideally the last 90 days, all Search campaigns.
- How to export: Google Ads → Campaigns → Insights and reports → Search terms → date range → make sure columns include Search term, Match type, Campaign, Ad group, Keyword, Impr., Clicks, Cost, Conversions, Conv. value → Download → CSV. (Menu names move around; any export with these columns works.)
- Ask the user for their **brand terms** and **target CPA** if you don't know them.

## 2. Run the sweep

```bash
python scripts/every_search_term.py <search_terms.csv> --target-cpa 35 --brand "acme,acmeshop" --out sweep-output
```
Outputs:
- `every-search-term-flags.csv`: NEGATIVE, EXPENSIVE, CHECK INTENT, BRAND, PROMOTE rows
- `every-search-term-ngrams.csv`: word fragments that never convert across several terms
- `negatives-exact.txt` and `negatives-phrase.txt`: draft paste lists (**review before sharing**)

## 3. Review every flagged row

Read every row of the flags and n-gram files. For each NEGATIVE candidate, judge **relevance first, numbers second**:
- Remove it from the negatives if the term is clearly something the business sells and it's just low data. Mark it "keep, low data" instead.
- Never negate brand, competitor terms the user deliberately bids on, or a term that's a substring of a converting keyword.
- **N-grams**: a phrase negative blocks every query containing that word. Before keeping one, search the flags file for converting terms containing that word. If any exist, drop it or narrow it to a 2-word phrase.
- **CHECK INTENT** rows (jobs, free, DIY, how to…) usually are negatives, but not always. "Free shipping" can be a buyer.
- **PROMOTE**: these terms convert at or under target CPA and aren't keywords yet. Recommend them as exact-match keywords in the ad group they performed best in.
- Google hides low-volume terms for privacy, so the report never covers all spend. Mention what share of cost the report covers if the user gives total campaign cost.

After review, rewrite `negatives-exact.txt` and `negatives-phrase.txt` with only the approved negatives, one per line. Exact as `[term]`, phrase as `"term"`, so they paste straight into a negative keyword list or Google Ads Editor.

## 4. Report

Lead with spend on terms you're negating and how many negatives. Then:

| Search term | Clicks | Cost | Conv. | Decision | Why |

Separate tables for n-gram negatives and keywords to add. Finish with the two final paste-ready lists in code blocks, plus a note on where to add them (shared negative list for account-wide junk, campaign-level for the rest).
