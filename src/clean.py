"""Phase 1: clean World Cup matches into a team-level table with host labels.

Output: data/processed/team_matches.csv — one row per team per match.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

# Merge historical names into their modern successor so a nation's record is continuous.
NAME_MAP = {
    "West Germany": "Germany",
    "Soviet Union": "Russia",
    "Yugoslavia": "Serbia",
    "FR Yugoslavia": "Serbia",
    "Serbia and Montenegro": "Serbia",
    "Czechoslovakia": "Czech Republic",
    "Zaire": "DR Congo",
    "Dutch East Indies": "Indonesia",
}

# Rounds that mean a team finished in the last four.
LAST_FOUR_ROUNDS = {"Semi-finals", "Final", "Third-place match", "Final stage"}


def load_hosts() -> pd.DataFrame:
    wc = pd.read_csv(RAW / "world_cup.csv")
    rows = []
    for _, r in wc.iterrows():
        for host in str(r["Host"]).split(","):
            rows.append({"year": int(r["Year"]), "host": NAME_MAP.get(host.strip(), host.strip())})
    return pd.DataFrame(rows)


def build_team_matches() -> pd.DataFrame:
    m = pd.read_csv(RAW / "matches_1930_2022.csv")
    m = m[m["Year"] <= 2022].reset_index(drop=True)
    m["match_id"] = m.index

    cols = ["match_id", "Year", "Round", "Date", "Venue", "Attendance"]
    home = m[cols + ["home_team", "away_team", "home_score", "away_score"]].rename(
        columns={"home_team": "team", "away_team": "opponent", "home_score": "gf", "away_score": "ga"}
    )
    away = m[cols + ["away_team", "home_team", "away_score", "home_score"]].rename(
        columns={"away_team": "team", "home_team": "opponent", "away_score": "gf", "home_score": "ga"}
    )
    tm = pd.concat([home, away], ignore_index=True)
    tm = tm.rename(columns={"Year": "year", "Round": "round", "Date": "date",
                            "Venue": "venue", "Attendance": "attendance"})

    tm["team"] = tm["team"].replace(NAME_MAP)
    tm["opponent"] = tm["opponent"].replace(NAME_MAP)

    # Scores are after normal + extra time; shootouts are excluded, so a shootout game is a draw.
    tm["result"] = (tm["gf"] > tm["ga"]).map({True: "W", False: ""})
    tm.loc[tm["gf"] == tm["ga"], "result"] = "D"
    tm.loc[tm["gf"] < tm["ga"], "result"] = "L"
    tm["points"] = tm["result"].map({"W": 3, "D": 1, "L": 0})  # 3-1-0 in every era for comparability
    tm["gd"] = tm["gf"] - tm["ga"]

    hosts = load_hosts()
    host_pairs = set(zip(hosts["year"], hosts["host"]))
    tm["is_host"] = [(y, t) in host_pairs for y, t in zip(tm["year"], tm["team"])]
    tm["is_last_four_round"] = tm["round"].isin(LAST_FOUR_ROUNDS)
    return tm.sort_values(["year", "date", "match_id"]).reset_index(drop=True)


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    tm = build_team_matches()
    tm.to_csv(PROCESSED / "team_matches.csv", index=False)
    load_hosts().to_csv(PROCESSED / "hosts.csv", index=False)
    print(f"team_matches: {len(tm)} rows, {tm['match_id'].nunique()} matches, "
          f"{tm['year'].nunique()} tournaments, {tm['is_host'].sum()} host team-matches")


if __name__ == "__main__":
    main()
