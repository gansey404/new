---
name: every-creative
description: Sweep every Meta ad's fatigue curve (CTR, CPA, and frequency, first week vs last week) and flag which ads to kill, refresh, scale, or watch. Use whenever the user asks about creative fatigue, ad fatigue, which ads to turn off, creative refresh, winning or losing ads, frequency problems, or wants a Meta creative audit, even if they don't name this skill.
---

# every-creative

Reads the fatigue curve of every single ad. A script computes each curve; you review every flagged ad and give a decision.

## 1. Get the data

You need a **Meta Ads export at the Ad level, broken down by day**, ideally the last 60–90 days.
- How to export: Ads Manager → Ads tab → date range → Breakdown → By Time → Day → columns must include Ad name, Ad set name, Amount spent, Impressions, Link clicks, Purchases, and Frequency → Export table data → CSV.
- Ad ID helps when several ads share a name; include it if available.

## 2. Run the sweep

```bash
python scripts/every_creative.py <ads_by_day.csv> --target-cpa 40 --out sweep-output
```
Leave out `--target-cpa` to use the account CPA in the file. `--min-days 10` sets the active days needed before judging a curve. Use `--map` if a column isn't detected.

Outputs: `every-creative-flags.csv` (KILL / REFRESH / SCALE / WATCH, ordered by priority then spend) and `every-creative-all.csv`.

## 3. Review every flagged row

Read the whole flags file. For each ad, sanity-check the rule-based action against the `weekly_ctr_curve`:
- A steady downward curve plus a rising CPA is classic fatigue. Keep the KILL.
- A single bad week after good ones may be an auction or seasonality dip. If other ads in the same ad set dipped the same week, downgrade to WATCH and say why.
- **REFRESH** means the concept works but the execution is worn out. Suggest what to change: new first 3 seconds, new thumbnail, new opening line, or a different format of the same angle.
- **SCALE** ads should get more budget, or be duplicated into a fresh ad set, and be used as a template for new variations.
- Small spend makes CPA noisy. Treat any ad with fewer than about 5 purchases in its last 7 days with care, and say so.

## 4. Report

Lead with counts and spend: "Kill 6 ads (€3,240 in the last 30 days), refresh 4, scale 2." Then one table per action:

| Ad | Ad set | Spend | CPA last 7d | CTR curve | Why | Action |

Each row's action must be something the user can do now: "Turn off", "Brief a new hook for this concept", "Raise ad set budget 20%", "Duplicate into new ad set". Finish with the pattern you noticed across winners and losers (formats, hooks, lengths), because that is what the next creative brief should use.
