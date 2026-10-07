---
name: every-event
description: Sweep every day of a Meta Ads account for Pixel / Conversions API tracking outages by comparing Pixel purchases to real store orders (or to spend when no orders file exists). Use whenever the user mentions Pixel problems, CAPI, missing or dropped conversions, "Meta stopped tracking", purchases not matching Shopify, sudden CPA spikes with steady sales, or asks to audit Meta tracking, even if they don't name this skill.
---

# every-event

Finds the days your Pixel quietly stopped counting. A script checks every day; you then review every flagged day and tell the user what happened and what to do.

## 1. Get the data

You need a **Meta Ads export broken down by day**. Any level works (account, campaign, ad); rows are summed per day. Ask the user for it if it isn't in the working folder.
- How to export: Ads Manager → pick a date range (60–90 days is ideal) → Breakdown → By Time → Day → make sure the Purchases and Amount spent columns are showing → Export table data → CSV.

Strongly recommended: a **store orders export** for the same dates (Shopify Orders export, WooCommerce orders, or any report with a date and order count). Without it the script can only compare purchases to spend, which catches hard outages but not slow under-tracking.

## 2. Run the sweep

```bash
python scripts/every_event.py <meta.csv> --orders <orders.csv> --out sweep-output
```
Options: `--min-orders 3` ignores tiny days, `--alpha 0.02` sets how unlikely a gap must be to flag it. If a column isn't detected, the script prints the columns it found; rerun with e.g. `--map "purchases=Website purchases"`.

Outputs in `--out`: `every-event-flags.csv` (flagged days), `every-event-incidents.csv` (consecutive flagged days grouped), `every-event-daily.csv` (all days).

## 3. Review every flagged row

Read the whole flags file, not just the printed top rows. For each incident, check:
- **Timezone shift**: a single day low next to a single day high usually means the ad account and store use different timezones. Mark it "not an outage".
- **Real outage**: zero or near-zero purchases for one or more days with normal orders. Ask whether a site deploy, theme change, checkout app, or consent banner changed on the start date.
- **Gradual under-tracking**: several days at 40–60% of the normal ratio often points to CAPI deduplication breaking, a consent-mode change, or iOS updates.
- **Over-counting**: Pixel above orders usually means duplicate Purchase events (browser + server without matching event_id), or the thank-you page firing on reload.
- Exclude test orders, cancelled orders, and offline/POS orders if the user mentions them.

## 4. Report

Lead with the answer: how many incidents, total estimated missing purchases, and the date ranges. Then a table, one row per incident:

| Incident | Dates | Days | Missing purchases (est.) | Likely cause | Action |

Every row must end in a concrete action, for example "Check Events Manager → Diagnostics for 3–5 Sep", "Verify event_id dedup between Pixel and CAPI", "Ignore: timezone shift". Also remind the user that Meta optimised on bad data during an outage, so CPA and creative results from those days are unreliable.
