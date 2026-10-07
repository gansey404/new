---
name: every-adset
description: Sweep 90 days of every Meta ad set to flag decaying CPA, dead ad sets, and low-volume ad sets that should be merged so they can exit the learning phase. Use whenever the user asks about ad set performance over time, CPA creeping up, "learning limited", account structure, consolidation, too many ad sets, or wants a Meta ad set audit, even if they don't name this skill.
---

# every-adset

Tracks 90 days per ad set and flags decay and merges. The script measures; you decide what to restructure.

## 1. Get the data

You need a **Meta Ads export at the Ad set level, broken down by day**, covering the last 90 days.
- How to export: Ads Manager → Ad sets tab → last 90 days → Breakdown → By Time → Day → columns Campaign name, Ad set name, Amount spent, Purchases (or the ad set's optimisation event) → Export table data → CSV.
- If ad sets optimise for something other than purchases (leads, add to cart), map that column: `--map "purchases=Leads"`.

## 2. Run the sweep

```bash
python scripts/every_adset.py <adsets_by_day.csv> --out sweep-output
```
Options: `--recent-days 14` (window compared to the ad set's own history), `--learning-events 50` (weekly events Meta needs to exit learning), `--target-cpa`.

Outputs: `every-adset-flags.csv` and `every-adset-all.csv`. Actions can combine, e.g. `DECAYING + MERGE`.

## 3. Review every flagged row

Read the whole flags file. Check each ad set:
- **DEAD**: spent 2x account CPA in the recent window with zero purchases. Turn off unless it's brand new or retargeting a tiny audience.
- **DECAYING**: recent CPA at least 40% worse than its own history, and the drop passed a significance test. Look at `weekly_cpa_curve` ("x" = a week with spend and no purchases). A steady climb usually means audience saturation or creative fatigue (suggest running every-creative on it). A sudden jump on one date usually means an external change: an edit that reset learning, a budget jump, or a tracking issue (suggest every-event).
- **MERGE**: under ~50 events a week, so it is likely stuck in learning. `merge_note` lists the other low-volume ad sets in the same campaign. Only recommend merging ad sets with compatible targeting and the same optimisation event. Say which to keep (best CPA, most history) and which to fold in.
- Don't flag seasonality as decay. If every ad set got worse in the same weeks, it's the market. Say that once instead of flagging each one.

## 4. Report

Lead with the headline: "3 ad sets dead, 4 decaying, 11 small enough to merge into 3." Then:

| Campaign | Ad set | CPA before → recent | Weekly events | Curve | Action |

Then a short **proposed structure**: for each campaign with merges, list the ad sets after consolidation and their expected combined weekly events. Every row ends in an action: "Turn off", "Swap creative, then recheck in 7 days", "Merge into X and pause".
