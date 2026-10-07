---
name: every-asset-group
description: Sweep every Performance Max asset group and flag the ones spending with no conversions, underperforming their campaign, low on ROAS, or with Poor ad strength, plus winners to feed. Use whenever the user mentions Performance Max, PMax, asset groups, PMax wasting budget, which asset groups to pause, or wants a PMax audit, even if they don't name this skill.
---

# every-asset-group

Finds PMax asset groups spending with nothing back. The script benchmarks each group against its own campaign; you decide pause, rebuild, or split.

## 1. Get the data

You need a **Google Ads asset group report** for PMax, ideally 30–90 days.
- Google Ads → Campaigns → (filter to Performance Max) → Asset groups → columns Campaign, Asset group, Status, Ad strength, Impr., Clicks, Cost, Conversions, Conv. value → Download → CSV.

## 2. Run the sweep

```bash
python scripts/every_asset_group.py <asset_groups.csv> --target-cpa 45 --out sweep-output
```
Outputs: `every-asset-group-flags.csv` and `every-asset-group-all.csv`. Actions can combine, e.g. `UNDERPERFORMER + FIX ASSETS`.

## 3. Review every flagged row

Read the whole flags file. PMax has quirks, so check each flag before recommending:
- **NO RETURN**: spent 2x target CPA with zero conversions. If it's paused already or less than ~2 weeks old, say "too new, recheck"; otherwise recommend pausing or rebuilding it with a different product set, audience signal, or creative theme.
- **UNDERPERFORMER**: CPA at least 1.75x its campaign's and at least 10% of the campaign's spend. Often the cause is a product group with low-margin or low-demand products. Suggest pairing with every-product.
- **WINNER**: if one asset group carries a campaign, consider moving it to its own campaign so it gets its own budget and target.
- **FIX ASSETS**: Poor ad strength. List what's typically missing: more headlines and long headlines, descriptions, images in all ratios, at least one video (otherwise Google may auto-generate one).
- PMax conversion credit includes view-through and cross-channel; a group that looks weak may be assisting. When a recommendation is a pause, suggest a 2-week holdout comparison when stakes are high.

## 4. Report

Lead with spend in flagged groups and the single biggest drain. Then:

| Campaign | Asset group | Cost | Conv. | CPA vs campaign | Ad strength | Action |

Every row ends in a concrete action: "Pause", "Rebuild with best-sellers only", "Move to own campaign at €X/day", "Add 5 headlines and a video".
