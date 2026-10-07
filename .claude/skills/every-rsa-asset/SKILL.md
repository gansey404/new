---
name: every-rsa-asset
description: Grade every Google Ads responsive search ad (RSA) headline and description using performance labels and CTR versus the ad group, flag which to replace, unpin, or clone, find ad groups missing assets, then write replacement copy within Google's character limits. Use whenever the user mentions RSAs, ad copy, headlines, descriptions, pinning, asset performance labels, ad strength, or wants to improve Google search ads, even if they don't name this skill.
---

# every-rsa-asset

Grades every headline and says which to replace, unpin, or clone. Then you write the new copy.

## 1. Get the data

You need a **Google Ads asset report for RSA headlines and descriptions**, at ad group level, 30–90 days.
- Google Ads → Campaigns → Assets → view the asset table with Headlines and Descriptions → segment or add columns for Campaign, Ad group, Asset type, Pinned position, Performance, Status, Impr., Clicks, Conversions → Download → CSV. (Menu names move around; any export with these columns works.)
- Ask for the landing page or product details too. You'll need them to write good replacements.

## 2. Run the sweep

```bash
python scripts/every_rsa_asset.py <rsa_assets.csv> --out sweep-output
```
`--min-impr 1000` sets how many impressions an asset needs before it is judged on CTR.

Outputs: `every-rsa-asset-flags.csv` (sorted by ad group so you can work one ad group at a time) and `every-rsa-asset-all.csv`.

## 3. Review every flagged row

Read the whole flags file, one ad group at a time:
- **REPLACE**: Low label, or CTR under 60% of the ad group's average for that field type. Read the text and say *why* it's weak (generic, duplicates another headline, no benefit, no keyword).
- **UNPIN**: a pinned asset that is also weak. Pinning forces it into every impression, so a weak pin hurts most. If a pin exists for legal or brand reasons, keep it and replace the text instead.
- **CLONE**: Best label or strong CTR with conversions. Write 2 variants that keep the winning idea but change wording.
- **ADD N HEADLINES / DESCRIPTIONS**: counts are unique assets across the ad group. Fill toward 15 headlines and 4 descriptions per RSA.
- Labels take time and impressions. "Learning" or empty with low impressions means too early. Don't replace those.

## 4. Write the new copy

For every REPLACE, CLONE, and ADD row, write the new text. Rules:
- Headlines max **30 characters**, descriptions max **90**.
- Each headline must work alone and in any order. No headline should depend on another.
- Cover different jobs across the set: keyword, benefit, proof (reviews, numbers), offer, CTA, objection-handling.
- Don't repeat the same phrase across headlines; Google limits near-duplicates.

Save your copy to a CSV with columns `type,text` and check it before showing the user:
```bash
python scripts/every_rsa_asset.py --validate new_assets.csv
```
Fix anything marked OVER and re-check.

## 5. Report

Lead with counts: "Replace 23, unpin 4, clone 9, add 31 assets across 12 ad groups." Then per ad group:

| Current asset | Type | Label | CTR vs group | Action | New text |

Every row ends in the action and, where relevant, the ready-to-paste new text.
