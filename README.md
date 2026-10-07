# Sweep skills for media buyers

10 Claude Code skills that audit Meta and Google Ads exports row by row.
Each one: a Python script sweeps every row of a CSV export and flags problems;
Claude then reads every flagged row, sanity-checks it, and turns it into an action.

## Install (Claude Code)
Copy the 10 `every-*` folders into `~/.claude/skills/` (all your projects)
or `.claude/skills/` inside one project. Restart Claude Code, then run e.g. `/every-search-term`.

Requirements: Python 3.8+. No packages to install (standard library only).

## Usage
Put your CSV exports in the project folder and run the skill, e.g.
  /every-search-term search_terms.csv, target CPA 35, brand words: acme
Each SKILL.md explains which export it needs and how to pull it.

| Skill | Platform | Finds |
|---|---|---|
| every-event | Meta | Days the Pixel stopped counting (vs real orders) |
| every-creative | Meta | Fatigue curve per ad: kill / refresh / scale / watch |
| every-angle | Meta | Selling angles ranked by CPA (Claude labels the ads) |
| every-breakdown | Meta | Placements, ages, genders leaking spend |
| every-adset | Meta | 90-day decay per ad set, dead ad sets, merge candidates |
| every-search-term | Google | Wasted terms + n-grams, paste-ready negatives |
| every-keyword-overlap | Google | Queries your ad groups fight over, where each belongs |
| every-product | Google | Zombie / money-pit / hero products + supplemental feed |
| every-asset-group | Google | PMax asset groups spending with no return |
| every-rsa-asset | Google | Headlines to replace, unpin, clone (+ length checker) |

Thresholds are deliberately conservative and use Poisson tests where small
numbers could mislead. All are adjustable with flags (run any script with --help).
If a column isn't detected, the script tells you which columns it found;
rerun with --map "field=Exact column name".
