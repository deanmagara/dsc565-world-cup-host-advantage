"""Phase 5: live demo.  Run:  streamlit run app.py"""
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src import charts

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"

st.set_page_config(page_title="World Cup Host Advantage", page_icon="⚽", layout="wide")

if not (OUT / "results.json").exists():
    st.error("Run `python src/clean.py && python src/analyze.py` first.")
    st.stop()

ht, era, res = charts.load()
tt = pd.read_csv(OUT / "team_tournaments.csv")


def fmt_p(p):
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


st.title("Host-Nation Advantage at the FIFA World Cup")
st.caption("Do host nations perform better at their home World Cup than in their other World Cups, "
           "and has this advantage changed over time?  ·  Amaan & Dean · DSC 565")

r = res["ppg"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Avg points/game at home", f"{r['mean_home']:.2f}", f"{r['mean_gap']:+.2f} vs. other Cups")
c2.metric("Hosts who improved", f"{r['hosts_improved']} / {r['hosts_total']}")
c3.metric("Permutation p-value", fmt_p(r["perm_p_one_sided"]))
c4.metric("Reached last four", f"{res['last_four']['home_rate']:.0%} at home",
          f"{res['last_four']['home_rate'] - res['last_four']['other_rate_mean']:+.0%} vs. elsewhere")

metric = st.radio("Metric", ["ppg", "gdpg"], horizontal=True, format_func=charts.LABELS.get)

tab_res, tab_era, tab_data, tab_agents = st.tabs(["Results", "Over time", "Explore a host", "Agent report"])

with tab_res:
    st.plotly_chart(charts.host_dumbbell(ht, metric), width="stretch")
    st.plotly_chart(charts.permutation_hist(res, metric), width="stretch")
    st.caption("Null model: for each host, randomly relabel which of its own World Cups is the 'home' one "
               f"({res['n_permutations']:,} shuffles). Excluded: "
               + "; ".join(f"{e['team']} {e['year']} ({e['reason']})" for e in res["excluded_hosts"]))

with tab_era:
    left, right = st.columns(2)
    left.plotly_chart(charts.era_bars(era, metric), width="stretch")
    right.plotly_chart(charts.gap_over_time(ht, res, metric), width="stretch")
    show = era[era["metric"] == metric].drop(columns="metric").copy()
    show["perm_p_one_sided"] = show["perm_p_one_sided"].map(fmt_p)
    st.dataframe(show.round(2), hide_index=True, width="stretch")

with tab_data:
    team = st.selectbox("Host nation", sorted(ht["team"].unique()), index=sorted(ht["team"].unique()).index("England"))
    rec = tt[tt["team"] == team][["year", "is_host", "matches", "wins", "draws", "losses", "gf", "ga", "ppg", "gdpg", "last_four"]]
    st.bar_chart(rec.assign(year=rec["year"].astype(str) + rec["is_host"].map({True: " (host)", False: ""}))
                 .set_index("year")[metric], color=charts.HOME)
    st.dataframe(rec.round(2), hide_index=True, width="stretch")
    with st.expander("Full host table"):
        st.dataframe(ht.round(2), hide_index=True, width="stretch")

with tab_agents:
    st.markdown("Three OpenAI agents write the report. They can only get numbers through tools that read the "
                "analysis outputs: **Analyst** drafts findings → **Critic** checks every number and flags "
                "overclaims → **Writer** produces the final report.")
    has_key = bool(os.getenv("OPENAI_API_KEY")) or (ROOT / ".env").exists()
    run = st.button("Run agents live", type="primary", disabled=not has_key,
                    help=None if has_key else "Add OPENAI_API_KEY to .env")
    if run:
        from agents.pipeline import run_pipeline
        boxes = {}
        with st.status("Agents working…", expanded=True) as status:
            def emit(agent, kind, text):
                if kind == "tool":
                    st.write(f"**{agent}** called `{text}`")
                else:
                    st.write(f"**{agent}** finished ✓")
            try:
                out = run_pipeline(emit)
                status.update(label="Report ready", state="complete")
            except Exception as e:
                status.update(label="Agent run failed — showing cached report", state="error")
                st.error(str(e))
    cached = OUT / "agent_run.json"
    if cached.exists():
        out = json.loads(cached.read_text())
        st.caption(f"Model: {out['model']}" + ("" if run else " · cached from last run"))
        st.markdown(out["report"])
        with st.expander("Analyst draft"):
            st.markdown(out["analyst"])
        with st.expander("Critic review"):
            st.markdown(out["critic"])
        st.download_button("Download report (.md)", out["report"], file_name="host_advantage_report.md")
    elif not run:
        st.info("No report yet — click **Run agents live**.")
