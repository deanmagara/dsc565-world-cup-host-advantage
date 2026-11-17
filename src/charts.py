"""Phase 3: Plotly charts used by the Streamlit app."""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

HOME, OTHER, ACCENT, MUTED = "#1f5f3a", "#9aa5b1", "#c8553d", "#6b7280"
LABELS = {"ppg": "Points per game", "gdpg": "Goal difference per game"}


def load():
    ht = pd.read_csv(OUT / "host_table.csv")
    era = pd.read_csv(OUT / "era_table.csv")
    res = json.loads((OUT / "results.json").read_text())
    return ht, era, res


def _layout(fig, title, **kw):
    fig.update_layout(title=title, template="plotly_white", height=kw.pop("height", 480),
                      margin=dict(l=10, r=10, t=60, b=10), legend=dict(orientation="h", y=1.08, x=0), **kw)
    return fig


def host_dumbbell(ht: pd.DataFrame, metric="ppg"):
    """Each host: home value vs. its own other-Cup average."""
    d = ht.assign(label=ht["team"] + " " + ht["year"].astype(str)).sort_values("year", ascending=False)
    fig = go.Figure()
    for _, r in d.iterrows():
        fig.add_trace(go.Scatter(x=[r[f"other_{metric}"], r[f"home_{metric}"]], y=[r["label"]] * 2, mode="lines",
                                 line=dict(color=HOME if r[f"{metric}_gap"] > 0 else ACCENT, width=2),
                                 showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=d[f"other_{metric}"], y=d["label"], mode="markers", name="Other World Cups",
                             marker=dict(color=OTHER, size=10)))
    fig.add_trace(go.Scatter(x=d[f"home_{metric}"], y=d["label"], mode="markers", name="Home World Cup",
                             marker=dict(color=HOME, size=11),
                             customdata=d[["home_record", f"{metric}_gap"]],
                             hovertemplate="%{y}<br>Home: %{x:.2f} (W-D-L %{customdata[0]})<br>Gap: %{customdata[1]:+.2f}<extra></extra>"))
    return _layout(fig, f"{LABELS[metric]}: home World Cup vs. the same team's other World Cups",
                   height=640, xaxis_title=LABELS[metric])


def era_bars(era: pd.DataFrame, metric="ppg"):
    e = era[era["metric"] == metric]
    fig = go.Figure()
    fig.add_bar(x=e["era"], y=e["mean_other"], name="Other World Cups", marker_color=OTHER)
    fig.add_bar(x=e["era"], y=e["mean_home"], name="Home World Cup", marker_color=HOME,
                text=[f"gap {g:+.2f}<br>p={p:.3f}" for g, p in zip(e["mean_gap"], e["perm_p_one_sided"])],
                textposition="outside")
    fig.update_yaxes(range=[min(0, e["mean_other"].min() - 0.2), e["mean_home"].max() * 1.3])
    return _layout(fig, f"{LABELS[metric]} by era (n hosts: " + ", ".join(map(str, e["n_hosts"])) + ")",
                   barmode="group", yaxis_title=LABELS[metric])


def gap_over_time(ht: pd.DataFrame, res: dict, metric="ppg"):
    import numpy as np
    fig = go.Figure()
    fig.add_hline(y=0, line=dict(color=MUTED, dash="dot"))
    fig.add_trace(go.Scatter(x=ht["year"], y=ht[f"{metric}_gap"], mode="markers+text", text=ht["team"],
                             textposition="top center", textfont=dict(size=10),
                             marker=dict(color=[HOME if g > 0 else ACCENT for g in ht[f"{metric}_gap"]], size=10),
                             name="Host gap"))
    b, a = np.polyfit(ht["year"], ht[f"{metric}_gap"], 1)
    xs = np.array([1930, 2018])
    fig.add_trace(go.Scatter(x=xs, y=a + b * xs, mode="lines", line=dict(color=MUTED), name="Linear trend"))
    r = res[metric]
    return _layout(fig, f"Host gap over time — trend {r['trend_slope_per_decade']:+.3f} per decade "
                        f"(one-sided p={r['trend_perm_p_shrinking']:.3f})",
                   xaxis_title="Home World Cup year", yaxis_title=f"{LABELS[metric]} gap (home − other)")


def permutation_hist(res: dict, metric="ppg"):
    r = res[metric]
    fig = go.Figure()
    fig.add_histogram(x=r["null_distribution_sample"], nbinsx=40, marker_color=OTHER, name="Shuffled 'home' labels")
    fig.add_vline(x=r["mean_gap"], line=dict(color=HOME, width=3),
                  annotation_text=f"Observed {r['mean_gap']:+.2f}", annotation_position="top left")
    p = r["perm_p_one_sided"]
    ptxt = "p < 0.001" if p < 0.001 else f"p = {p:.3f}"
    return _layout(fig, f"Permutation test: average host gap vs. chance ({ptxt})",
                   xaxis_title=f"Average {LABELS[metric].lower()} gap", yaxis_title="Count", showlegend=False)
