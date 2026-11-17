"""Live demo.  Run:  streamlit run app.py"""
import json
import os
from pathlib import Path

import streamlit as st

from src import charts

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"

st.set_page_config(page_title="World Cup Host Advantage", page_icon="⚽")
ht, era, res = charts.load()
r = res["ppg"]

st.title("Do World Cup hosts play better at home?")
st.write("We compared each host nation's results at its home World Cup with **the same team's results "
         "at its other World Cups** (1930–2022).")

c1, c2, c3 = st.columns(3)
c1.metric("Points per game at home", f"{r['mean_home']:.2f}", f"{r['mean_gap']:+.2f} vs. other Cups")
c2.metric("Hosts who did better", f"{r['hosts_improved']} of {r['hosts_total']}")
c3.metric("Could it be luck?", "Very unlikely", "p < 0.001", delta_color="off")

st.subheader("Has the advantage changed over time?")
st.plotly_chart(charts.era_bars(era), width="stretch")
st.write("Hosts still do better today, but the boost is a bit smaller than it used to be.")

st.subheader("Each host's boost")
st.plotly_chart(charts.host_gaps(ht), width="stretch")
st.caption("Green = did better at home, red = did worse. Qatar 2022 is left out (no other World Cups to compare).")

st.subheader("AI-written report")
has_key = bool(os.getenv("OPENAI_API_KEY")) or (ROOT / ".env").exists()
if st.button("Generate report with AI agents", type="primary", disabled=not has_key):
    from agents.pipeline import run_pipeline
    with st.spinner("Analyst → Critic → Writer are working…"):
        try:
            run_pipeline()
        except Exception as e:
            st.error(f"Agent run failed: {e}")

report = OUT / "agent_run.json"
if report.exists():
    st.markdown(json.loads(report.read_text())["report"])
elif not has_key:
    st.info("Add your OpenAI key to `.env` to generate the report.")
