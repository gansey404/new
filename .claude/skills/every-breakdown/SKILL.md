---
name: every-breakdown
description: Sweep every placement, platform, device, age, gender, and region slice of a Meta Ads account and flag the ones bleeding spend versus account CPA, with a statistical test so small slices aren't flagged on noise. Use whenever the user asks about placements, Audience Network, Reels vs Feed, age or gender performance, demographic waste, where budget leaks, or wants a Meta breakdown audit, even if they don't name this skill.
---

# every-breakdown

Finds the placements and audience slices leaking spend. The script tests every segment; you review the flagged ones and decide what's actually actionable.

## 1. Get the data

You need a **Meta Ads export with a delivery breakdown** applied. 30–90 days, at Campaign or Ad set level.
- How to export: Ads Manager → Breakdown → By Delivery → pick Placement (gives Platform + Placement), or Age, Gender, Age and Gender, Region, or Impression device → columns Amount spent, Purchases, Purchases conversion value → Export table data → CSV.
- Run one export per breakdown type. Placement and Age in the same file is fine if Meta allowed it.

## 2. Run the sweep

```bash
python scripts/every_breakdown.py <breakdown.csv> --out sweep-output
python scripts/every_breakdown.py <breakdown.csv> --per-campaign --out sweep-output   # judge within each campaign
```
Use `--per-campaign` when campaigns have very different CPAs (e.g. prospecting vs retargeting); otherwise a retargeting slice looks great just because retargeting is cheap. `--target-cpa` overrides the benchmark, `--by "Age,Gender"` forces the columns.

Outputs: `every-breakdown-flags.csv` (sorted by excess spend, the spend above what the purchases justify at account CPA) and `every-breakdown-all.csv`.

## 3. Review every flagged row

Read the whole flags file and check each segment against how Meta actually works:
- **Placements**: excluding placements in an Advantage+ placement campaign can raise CPMs elsewhere. Recommend exclusion when the slice is clearly bad (e.g. Audience Network with zero purchases), and a test (duplicate ad set without the placement) when it's borderline.
- **Age / gender**: Advantage+ audience treats age and gender mostly as suggestions, so a hard exclusion may need an age minimum or original audience controls. Say which applies.
- Attribution differs by placement. Reels and Stories often assist purchases that are credited elsewhere, so treat REDUCE on those as "test before cutting".
- **OPPORTUNITY** slices are where to push: a dedicated ad set, or creative built for that placement or age group.
- If one bad slice is driven by a single campaign, name that campaign.

## 4. Report

Lead with the total excess spend found and the top 3 leaks. Then:

| Campaign | Segment | Spend | Purchases | CPA vs account | Excess spend | Action |

Every row ends in a concrete action: "Exclude Audience Network in Prospecting – Broad", "Set age minimum 25", "Duplicate ad set Feed-only and compare for 7 days", "Build 9:16 creative for Reels 25–34".
