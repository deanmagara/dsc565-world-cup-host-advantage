"""Phases 2-3: host vs. other-World-Cup comparison, era split, permutation tests.

Outputs (in outputs/):
  host_table.csv        one row per host instance (team, home year)
  era_table.csv         gap per era with permutation p-values
  team_tournaments.csv  every team's record in every tournament
  results.json          every headline number the agents and the app use
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "outputs"

ERAS = [("1930-1950", 1930, 1950), ("1954-1994", 1954, 1994), ("1998-2022", 1998, 2022)]
METRICS = {"ppg": "points", "gdpg": "gd"}  # per-game metric -> summed column
N_PERM = 10_000
SEED = 565


def era_of(year: int) -> str:
    for name, lo, hi in ERAS:
        if lo <= year <= hi:
            return name
    raise ValueError(year)


def team_tournaments(tm: pd.DataFrame) -> pd.DataFrame:
    tt = tm.groupby(["team", "year"]).agg(
        matches=("points", "size"), points=("points", "sum"), gd=("gd", "sum"),
        gf=("gf", "sum"), ga=("ga", "sum"),
        wins=("result", lambda s: (s == "W").sum()),
        draws=("result", lambda s: (s == "D").sum()),
        losses=("result", lambda s: (s == "L").sum()),
        last_four=("is_last_four_round", "any"), is_host=("is_host", "any"),
    ).reset_index()
    tt["ppg"] = tt["points"] / tt["matches"]
    tt["gdpg"] = tt["gd"] / tt["matches"]
    return tt


def host_table(tt: pd.DataFrame, hosts: pd.DataFrame):
    rows, excluded = [], []
    for _, h in hosts.sort_values("year").iterrows():
        team, year = h["host"], h["year"]
        mine = tt[tt["team"] == team]
        home = mine[mine["year"] == year].iloc[0]
        other = mine[~mine["is_host"]]  # all the team's non-host Cups
        if other.empty:
            excluded.append({"team": team, "year": int(year), "reason": "no other World Cup appearances"})
            continue
        n_other = other["matches"].sum()
        rows.append({
            "team": team, "year": int(year), "era": era_of(year),
            "home_matches": int(home["matches"]), "home_record": f"{home['wins']}-{home['draws']}-{home['losses']}",
            "home_ppg": home["ppg"], "other_ppg": other["points"].sum() / n_other,
            "home_gdpg": home["gdpg"], "other_gdpg": other["gd"].sum() / n_other,
            "home_last_four": bool(home["last_four"]), "other_last_four_rate": other["last_four"].mean(),
            "other_cups": int(len(other)), "other_matches": int(n_other),
        })
    ht = pd.DataFrame(rows)
    ht["ppg_gap"] = ht["home_ppg"] - ht["other_ppg"]
    ht["gdpg_gap"] = ht["home_gdpg"] - ht["other_gdpg"]
    ht["last_four_gap"] = ht["home_last_four"].astype(float) - ht["other_last_four_rate"]
    return ht, excluded


def permutation_null(tt: pd.DataFrame, ht: pd.DataFrame, metric: str, n_perm=N_PERM, seed=SEED):
    """Null: a host's home Cup is no different from a randomly chosen Cup of its own.

    For each host team we randomly relabel which of its tournaments are 'home'
    (keeping the number of home Cups fixed) and recompute every instance's gap.
    Returns an (n_perm, n_instances) array aligned with ht's rows.
    """
    rng = np.random.default_rng(seed)
    col = METRICS[metric]
    null = np.zeros((n_perm, len(ht)))
    for team, idx in ht.groupby("team").groups.items():
        mine = tt[tt["team"] == team]
        val, n = mine[col].to_numpy(float), mine["matches"].to_numpy(float)
        k = len(idx)  # number of home instances for this team (e.g. Italy = 2)
        tot_v, tot_n = val.sum(), n.sum()
        for p in range(n_perm):
            pick = rng.choice(len(val), size=k, replace=False)
            other_v, other_n = tot_v - val[pick].sum(), tot_n - n[pick].sum()
            null[p, [ht.index.get_loc(i) for i in idx]] = val[pick] / n[pick] - other_v / other_n
    return null


def p_greater(obs, null_stats):
    return float((np.sum(null_stats >= obs) + 1) / (len(null_stats) + 1))


def slope(x, y):
    x = np.asarray(x, float)
    return float(np.polyfit(x, y, 1)[0])


def main():
    OUT.mkdir(exist_ok=True)
    tm = pd.read_csv(PROCESSED / "team_matches.csv")
    hosts = pd.read_csv(PROCESSED / "hosts.csv")
    tt = team_tournaments(tm)
    ht, excluded = host_table(tt, hosts)

    results = {"n_host_instances": len(ht), "excluded_hosts": excluded,
               "n_permutations": N_PERM, "seed": SEED,
               "notes": ["Shootouts count as draws; scores are after normal + extra time.",
                         "Points are 3 for a win, 1 for a draw in every era.",
                         "West Germany is merged into Germany; 2002 co-hosts Korea Republic and Japan are each a host.",
                         "'Other' = all of the host team's non-host World Cups, pooled at match level.",
                         "Permutation null: randomly relabel which of each host's own Cups is 'home'."]}

    era_rows = []
    rng = np.random.default_rng(SEED)
    for metric in METRICS:
        gap = ht[f"{metric}_gap"].to_numpy()
        null = permutation_null(tt, ht, metric)
        obs = float(gap.mean())
        null_mean = null.mean(axis=1)
        results[metric] = {
            "mean_home": float(ht[f"home_{metric}"].mean()), "mean_other": float(ht[f"other_{metric}"].mean()),
            "mean_gap": obs, "hosts_improved": int((gap > 0).sum()), "hosts_total": len(gap),
            "perm_p_one_sided": p_greater(obs, null_mean),
            "null_mean": float(null_mean.mean()), "null_sd": float(null_mean.std()),
            "null_distribution_sample": np.round(null_mean[:2000], 4).tolist(),
        }
        for era, _, _ in ERAS:
            mask = (ht["era"] == era).to_numpy()
            obs_e = float(gap[mask].mean())
            null_e = null[:, mask].mean(axis=1)
            era_rows.append({"metric": metric, "era": era, "n_hosts": int(mask.sum()),
                             "hosts": ", ".join(f"{t} {y}" for t, y in ht.loc[mask, ["team", "year"]].values),
                             "mean_home": float(ht.loc[mask, f"home_{metric}"].mean()),
                             "mean_other": float(ht.loc[mask, f"other_{metric}"].mean()),
                             "mean_gap": obs_e, "perm_p_one_sided": p_greater(obs_e, null_e)})
        # Trend: does the gap shrink over time? Slope of gap on year, permutation over years.
        obs_slope = slope(ht["year"], gap)
        perm_slopes = np.array([slope(ht["year"], rng.permutation(gap)) for _ in range(N_PERM)])
        results[metric]["trend_slope_per_decade"] = obs_slope * 10
        results[metric]["trend_perm_p_shrinking"] = float((np.sum(perm_slopes <= obs_slope) + 1) / (N_PERM + 1))

    results["last_four"] = {
        "home_rate": float(ht["home_last_four"].mean()),
        "other_rate_mean": float(ht["other_last_four_rate"].mean()),
        "hosts_reaching_last_four_at_home": int(ht["home_last_four"].sum()),
    }
    hosts_won = tt.merge(pd.read_csv(ROOT / "data/raw/world_cup.csv")[["Year", "Champion"]],
                         left_on="year", right_on="Year")
    champs = hosts_won[hosts_won["is_host"] & (hosts_won["team"] == hosts_won["Champion"].replace({"West Germany": "Germany"}))]
    results["host_champions"] = [f"{t} {y}" for t, y in champs[["team", "year"]].values]

    era_df = pd.DataFrame(era_rows)
    results["eras"] = era_df.to_dict(orient="records")
    ht.round(4).to_csv(OUT / "host_table.csv", index=False)
    era_df.round(4).to_csv(OUT / "era_table.csv", index=False)
    tt.round(4).to_csv(OUT / "team_tournaments.csv", index=False)
    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=float))

    pd.set_option("display.width", 200)
    print(ht[["team", "year", "era", "home_record", "home_ppg", "other_ppg", "ppg_gap", "gdpg_gap", "home_last_four"]].round(2).to_string())
    print("\nExcluded:", excluded)
    print(era_df.drop(columns="hosts").round(3).to_string())
    for m in METRICS:
        r = results[m]
        print(f"{m}: gap={r['mean_gap']:.3f}, improved {r['hosts_improved']}/{r['hosts_total']}, "
              f"p={r['perm_p_one_sided']:.4f}, trend/decade={r['trend_slope_per_decade']:.3f}, p_shrink={r['trend_perm_p_shrinking']:.3f}")
    print(results["last_four"], results["host_champions"])


if __name__ == "__main__":
    main()
