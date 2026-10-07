---
name: every-angle
description: Label every Meta ad with its selling angle (pain point, social proof, price, transformation, etc.), then rank the angles by CPA and ROAS to show which messages actually make money. Use whenever the user asks which angle, message, hook type, value prop, or concept works best, wants to group ads by theme, plan the next creative batch, or audit messaging on Meta, even if they don't name this skill.
---

# every-angle

Shows which selling angle actually makes money. The script does the math; you do the labelling and the judgement.

## 1. Get the data

You need a **Meta Ads export at the Ad level** with Ad name, Amount spent, Purchases, and ideally Purchases conversion value. Adding the ad's Body/Primary text and Headline columns makes labelling much better. 30–90 days is ideal; daily rows are fine.

## 2. Work out where angles come from

- If the account uses a naming convention that already contains the angle (e.g. `UGC_PainPoint_v3`), use `--token 1 --sep _`.
- If the user has a sheet mapping ads to angles, use `--angles map.csv` (columns `ad`, `angle`).
- Otherwise, run without either. The script writes `every-angle-to-label.csv`, and you label it yourself (step 3).

```bash
python scripts/every_angle.py <ads.csv> --out sweep-output            # writes the labelling file
python scripts/every_angle.py <ads.csv> --angles sweep-output/every-angle-to-label.csv --out sweep-output
```

## 3. Label every ad (when needed)

Read every row of `every-angle-to-label.csv`: the name, headline, and body. Give each ad one short angle label and fill the `angle` column. Rules:
- Keep it to roughly 5–10 angles for the account. Use the same exact spelling every time, because a typo creates a new angle.
- Label the core reason-to-buy the ad argues, not the format. Example angles: *Pain point*, *Social proof / reviews*, *Price / offer*, *Transformation / before-after*, *Founder story*, *Comparison vs alternative*, *Ingredient / mechanism*, *Urgency / scarcity*. Invent account-specific ones when they fit better.
- If an ad has no text and an uninformative name, label it `unknown` rather than guessing.

Show the user your angle list and a few example labels before rerunning, so they can correct the taxonomy.

## 4. Review every row of the ranking

Read all of `every-angle-ranking.csv`:
- **TOO EARLY / TEST MORE**: fewer than 10 purchases means the CPA is noise. Say so plainly.
- Check if an angle's result is carried by a single ad (see `best_ad`). If so, the "angle" might really be that one creative.
- **SCALE (underfunded winner)** is the most valuable finding: the angle beats account CPA but gets under 15% of spend.

## 5. Report

Lead with the winner and the loser in one sentence. Then the ranking table:

| Angle | Ads | Spend share | Purchases | CPA | vs account | Action |

Every row ends in an action: "Brief 3 new ads on this angle", "Stop producing this angle", "Give 2 more weeks". Close with a short creative brief for the next batch, built around the top angle.
