"""Phase 3: the two charts used by the Streamlit app."""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

HOME, OTHER, WORSE = "#1f5f3a", "#9aa5b1", "#c8553d"


def load():
    ht = pd.read_csv(OUT / "host_table.csv")
    era = pd.read_csv(OUT / "era_table.csv")
    res = json.loads((OUT / "results.json").read_text())
    return ht, era, res


def era_bars(era: pd.DataFrame):
    """Average points per game at home vs. other World Cups, per era."""
    e = era[era["metric"] == "ppg"]
    fig = go.Figure()
    fig.add_bar(x=e["era"], y=e["mean_other"], name="Other World Cups", marker_color=OTHER,
                text=e["mean_other"].round(2), textposition="outside")
    fig.add_bar(x=e["era"], y=e["mean_home"], name="Home World Cup", marker_color=HOME,
                text=e["mean_home"].round(2), textposition="outside")
    fig.update_layout(barmode="group", template="plotly_white", height=420,
                      yaxis=dict(title="Points per game", range=[0, 3]),
                      legend=dict(orientation="h", y=1.1, x=0), margin=dict(l=10, r=10, t=40, b=10))
    return fig


def host_gaps(ht: pd.DataFrame):
    """How many more points per game each host earned at home than at its other World Cups."""
    d = ht.assign(label=ht["team"] + " " + ht["year"].astype(str))
    fig = go.Figure(go.Bar(x=d["label"], y=d["ppg_gap"],
                           marker_color=[HOME if g > 0 else WORSE for g in d["ppg_gap"]],
                           hovertemplate="%{x}: %{y:+.2f} points per game<extra></extra>"))
    fig.update_layout(template="plotly_white", height=420, margin=dict(l=10, r=10, t=20, b=10),
                      yaxis_title="Extra points per game at home", xaxis_tickangle=-45)
    return fig
