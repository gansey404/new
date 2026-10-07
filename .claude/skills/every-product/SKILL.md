---
name: every-product
description: Sweep every product in Google Shopping or Performance Max to find zombie products getting no impressions, money-pit products spending without converting, low-ROAS products, and hero products, then write a Merchant Center supplemental feed with custom labels ready to upload. Use whenever the user mentions Shopping, PMax products, product feed, Merchant Center, zombie products, SKUs not showing, product-level ROAS, or custom labels, even if they don't name this skill.
---

# every-product

Finds zombie products (and the other three product problems) across the whole catalogue, and labels them for restructuring.

## 1. Get the data

You need a **Google Ads product performance report** by Item ID, ideally 30–90 days.
- Google Ads → Campaigns → Products (for Shopping and PMax campaigns) → columns Item ID, Title, Impr., Clicks, Cost, Conversions, Conv. value → Download → CSV.
- Strongly recommended: the **Merchant Center product list** (Products → All products → Download). Products that never served at all don't appear in the Ads report, so without the feed the worst zombies are invisible.

## 2. Run the sweep

```bash
python scripts/every_product.py <products.csv> --feed <merchant_center.csv> --out sweep-output
```
Options: `--min-impr 100` (zombie threshold for the period, raise it for 90 days of data), `--target-cpa`, `--label-slot custom_label_0` (pick a custom label slot the account isn't already using).

Outputs: `every-product-flags.csv` and `supplemental-feed-labels.csv` (id + label).

## 3. Review every flagged row

Read the whole flags file:
- **ZOMBIE (out of stock)**: not an ads problem. Leave it out of the restructure and tell the user.
- **ZOMBIE (never served / almost none)**: check disapprovals and limited status in Merchant Center first, then price competitiveness and title quality. Look at the titles: vague or short titles are a common cause. Suggest specific title rewrites for the top zombies (brand + product type + key attribute + size/colour).
- **MONEY PIT**: spent 2x CPA with no conversion. Check the price and the landing page before excluding; a broken variant or an out-of-stock size can cause this.
- **HERO**: the products to put in their own campaign or asset group with their own budget, so they aren't starved by the average.
- If the user's goal is ROAS, not CPA, lean on the ROAS column.

## 4. Report

Lead with counts: "212 zombies (38% of catalogue), 14 money pits that spent €2,100, 9 heroes." Then a table per action:

| Item ID | Title | Impr. | Cost | Conv. | Action |

For long zombie lists, show the top 25 by catalogue importance and attach the file. Close with the restructure plan: upload `supplemental-feed-labels.csv` as a supplemental feed in Merchant Center, then use the custom label to split listing groups (heroes get their own campaign or asset group, zombies a low-ROAS-target "zombie" campaign, money pits excluded or fixed).
