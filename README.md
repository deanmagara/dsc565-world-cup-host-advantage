# Host-Nation Advantage at the FIFA World Cup

DSC 565 — Building Generative AI Applications · Amaan & Dean

**Question:** Do host nations perform better at their home World Cup than in their other World Cups, and has this advantage changed over time?

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then paste your OpenAI key into .env

python src/clean.py             # data/raw -> data/processed/team_matches.csv
python src/analyze.py           # -> outputs/host_table.csv, era_table.csv, results.json
python -m agents.pipeline       # optional: Analyst -> Critic -> Writer report (outputs/report.md)
streamlit run app.py            # live demo
```

The raw Kaggle files are in `data/raw/` already. To re-download them:
`python -c "import kagglehub; print(kagglehub.dataset_download('piterfm/fifa-football-world-cup'))"`

## Method

- Every match becomes two team rows. Scores are after normal and extra time, so a **penalty shootout counts as a draw**. Points are 3 for a win and 1 for a draw in every era.
- **Hosts** come from `world_cup.csv`. Korea Republic and Japan both count as 2002 hosts. West Germany is merged into Germany, and other successor teams are merged the same way.
- Each host's home World Cup is compared with **the same team's other World Cups** (pooled by match), which controls for team strength. Qatar 2022 is excluded because it has no other appearances.
- **Eras:** 1930–1950, 1954–1994, 1998–2022.
- **Permutation test** (10,000 shuffles): for each host, randomly relabel which of its own World Cups is "home", then compare the observed average gap with that null distribution. A second permutation test checks whether the gap shrinks over time (slope of the gap against year).

## Results (22 host instances)

| | Home | Other Cups | Gap | Permutation p |
|---|---|---|---|---|
| Points per game | 2.00 | 1.45 | **+0.55** | < 0.001 |
| Goal diff per game | 0.83 | 0.11 | **+0.72** | < 0.001 |

- 18 of 22 hosts improved at home. 59% reached the last four at home, against 23% in their other World Cups. Six hosts won the tournament.
- By era, the points-per-game gap is +0.56 (1930–50), +0.63 (1954–94) and +0.41 (1998–2022). All three are significant.
- The goal-difference gap shrinks significantly over time (−0.14 per decade, p = 0.03). The points-per-game trend also points down but is not significant (p = 0.12).

## Layout

```
data/raw/         Kaggle CSVs
data/processed/   team_matches.csv, hosts.csv
src/clean.py      cleaning + host labels
src/analyze.py    host table, eras, permutation tests
src/charts.py     Plotly charts
agents/pipeline.py  OpenAI tool-using agents (Analyst, Critic, Writer)
app.py            Streamlit demo
outputs/          results the app and agents read
```

## References

- Dixon, M. J., & Coles, S. G. (1997). Modelling association football scores and inefficiencies in the football betting market. *JRSS Series C*, 46(2), 265–280.
- Pollard, R. (2008). Home advantage in football: A current review of an unsolved puzzle. *The Open Sports Sciences Journal*, 1, 12–14.
- Football – FIFA World Cup, 1930–2026 [Dataset]. Kaggle. kaggle.com/datasets/piterfm/fifa-football-world-cup
