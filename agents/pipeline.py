"""Phase 4: three-agent report pipeline (Analyst -> Critic -> Writer) on the OpenAI API.

Agents never see raw numbers in their prompts; they must fetch them through tools
that read outputs/*.csv and outputs/results.json, so every figure is grounded.

Run:  python -m agents.pipeline      (needs OPENAI_API_KEY in .env)
"""
import json
import os
from pathlib import Path
from typing import Callable

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
load_dotenv(ROOT / ".env")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
MAX_TOOL_ROUNDS = 8


# ---------- tools ----------
def _results():
    r = json.loads((OUT / "results.json").read_text())
    for m in ("ppg", "gdpg"):
        r[m] = {k: v for k, v in r[m].items() if k != "null_distribution_sample"}
    r.pop("eras", None)  # served by get_era_table
    return r


def get_summary() -> str:
    return json.dumps(_results(), indent=1)


def get_host_table() -> str:
    return pd.read_csv(OUT / "host_table.csv").round(3).to_csv(index=False)


def get_era_table() -> str:
    return pd.read_csv(OUT / "era_table.csv").round(3).to_csv(index=False)


def get_team_record(team: str) -> str:
    tt = pd.read_csv(OUT / "team_tournaments.csv")
    rows = tt[tt["team"].str.lower() == team.lower()]
    if rows.empty:
        return f"No team named '{team}'. Known hosts: " + ", ".join(sorted(pd.read_csv(OUT / "host_table.csv")["team"].unique()))
    return rows[["year", "is_host", "matches", "wins", "draws", "losses", "gf", "ga", "ppg", "last_four"]].round(3).to_csv(index=False)


def get_tournament_matches(team: str, year: int) -> str:
    tm = pd.read_csv(ROOT / "data" / "processed" / "team_matches.csv")
    rows = tm[(tm["team"].str.lower() == team.lower()) & (tm["year"] == int(year))]
    if rows.empty:
        return f"No matches for {team} in {year}."
    return rows[["date", "round", "opponent", "gf", "ga", "result"]].to_csv(index=False)


TOOLS = {"get_summary": get_summary, "get_host_table": get_host_table, "get_era_table": get_era_table,
         "get_team_record": get_team_record, "get_tournament_matches": get_tournament_matches}

TOOL_SPECS = [
    {"type": "function", "function": {"name": "get_summary", "description":
        "Headline results: overall mean home vs other points-per-game (ppg) and goal-difference-per-game (gdpg), "
        "permutation p-values, trend over time, last-four rates, host champions, excluded hosts, method notes.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_host_table", "description":
        "One row per host nation per home World Cup: home record, home vs other ppg/gdpg, gaps, last-four flags.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_era_table", "description":
        "Average home vs other ppg and gdpg for each era (1930-1950, 1954-1994, 1998-2022) with permutation p-values.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_team_record", "description":
        "A single team's record in every World Cup it played (1930-2022).",
        "parameters": {"type": "object", "properties": {"team": {"type": "string"}}, "required": ["team"]}}},
    {"type": "function", "function": {"name": "get_tournament_matches", "description":
        "Every match a team played at one World Cup: date, round, opponent, goals for/against, result "
        "(shootouts already counted as draws).",
        "parameters": {"type": "object", "properties": {"team": {"type": "string"}, "year": {"type": "integer"}},
                       "required": ["team", "year"]}}},
]

# ---------- agents ----------
CONTEXT = ("Project: 'Host-Nation Advantage at the FIFA World Cup' (DSC 565). Research question: Do host nations "
           "perform better at their home World Cup than in their other World Cups, and has this advantage changed "
           "over time? Hypothesis: hosts outperform their usual results, but the gap is smaller in recent tournaments. "
           "Method: compare each host's points per game and goal difference per game at home vs. its own other "
           "World Cups (controls for team strength), split by era, and test against chance with a permutation test. "
           "References: Pollard (2008) review of home advantage; Dixon & Coles (1997) score model with a home effect.")

ANALYST = CONTEXT + """
You are the ANALYST. Call the tools to get the data, then write the findings in markdown:
1. Overall result (home vs other ppg and goal difference, how many hosts improved, permutation p-value).
2. Era comparison and whether the gap shrinks over time (cite the trend slope and its p-value).
3. Notable hosts (biggest gains, hosts that did worse at home, host champions).
4. Reaching the last four at home vs. elsewhere.
Use ONLY numbers returned by tools. Round to 2 decimals. Report p-values of 0.0001 as "p < 0.001"."""

CRITIC = CONTEXT + """
You are the CRITIC. You receive the Analyst's draft. Use the tools to verify EVERY number and claim in it.
Return a markdown list with two sections:
- **Errors**: each wrong or unsupported number/claim, with the correct value from the tools.
- **Caveats to add**: overclaiming (e.g. causation, 'proves'), small samples (era n), the trend test's
  significance, confounders noted by Pollard (crowd, travel, referees, qualification/automatic entry,
  investment before hosting), format changes, the Qatar exclusion, and successor-team merges.
Check record totals (wins/draws/losses, goals for/against) against get_team_record exactly. Be concise and specific. If the draft is fully correct, say so under Errors."""

WRITER = CONTEXT + """
You are the WRITER. Using the Analyst draft and the Critic's review, write the final report in markdown with
these sections: ## Summary (3 bullets), ## Data and Method, ## Results, ## Has the advantage changed over time?,
## Limitations, ## Conclusion (answer the research question and say whether the hypothesis held).
Fix every error the Critic found. Keep it under 700 words, plain language, numbers to 2 decimals.
You may call tools to double-check figures. Do not invent numbers."""


def run_agent(client: OpenAI, name: str, system: str, user: str, emit: Callable) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOL_SPECS)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            emit(name, "output", msg.content)
            return msg.content
        messages.append(msg)
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            emit(name, "tool", f"{call.function.name}({', '.join(f'{k}={v!r}' for k, v in args.items())})")
            try:
                result = TOOLS[call.function.name](**args)
            except Exception as e:  # surface tool errors to the model instead of crashing
                result = f"Tool error: {e}"
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    raise RuntimeError(f"{name} did not finish within {MAX_TOOL_ROUNDS} tool rounds")


HOST_ANALYST = CONTEXT + """
You are the ANALYST. Focus on ONE host nation's home World Cup (given by the user). Call the tools to get:
its row in the host table, its record at every World Cup, its match-by-match results at the home Cup,
and the overall summary for context. Then write findings in markdown:
1. How the host did at home (record, points per game, goal difference, how far it went, key results).
2. How that compares with the same team's other World Cups (the gap).
3. How this host compares with the other hosts (rank of its gap among all hosts, the average gap of +0.55).
Use ONLY numbers returned by tools. Round to 2 decimals. Copy every number exactly as a tool returns it (e.g. goals for/against are the gf/ga columns of get_team_record); never add up or calculate totals yourself, but do round decimals to 2 places."""

HOST_WRITER = CONTEXT + """
You are the WRITER. Using the Analyst draft and the Critic's review, write a short report on this ONE host
in markdown, with a title '## <Team> <Year>: ...' that states the main finding, then sections
four ### sections titled exactly: At home | Compared with its other World Cups | Compared with other hosts | Caveats (2-3 bullets). No punctuation after headings.
Fix every error the Critic found. Under 300 words, plain language, numbers to 2 decimals. Do not invent numbers. Copy every number exactly as a tool returns it (e.g. goals for/against are the gf/ga columns of get_team_record); never add up or calculate totals yourself, but do round decimals to 2 places. Do not repeat overall trend p-values; keep the report about this host."""


def run_pipeline(emit: Callable = lambda agent, kind, text: None, host: str | None = None) -> dict:
    """host: e.g. 'Brazil 2014' for a single-host report; None for the overall report."""
    client = OpenAI()
    analyst, writer, task = ANALYST, WRITER, "Write the findings."
    if host:
        analyst, writer, task = HOST_ANALYST, HOST_WRITER, f"The host to analyze is {host}."
    draft = run_agent(client, "Analyst", analyst, task, emit)
    review = run_agent(client, "Critic", CRITIC, f"{task}\n\nAnalyst draft:\n\n{draft}", emit)
    report = run_agent(client, "Writer", writer,
                       f"{task}\n\nAnalyst draft:\n\n{draft}\n\nCritic review:\n\n{review}", emit)
    out = {"model": MODEL, "host": host, "analyst": draft, "critic": review, "report": report}
    if host:  # one saved report per host, used as a fallback if a live run fails
        (OUT / "host_reports").mkdir(exist_ok=True)
        (OUT / "host_reports" / f"{host.replace(' ', '_')}.json").write_text(json.dumps(out, indent=2))
    else:
        (OUT / "agent_run.json").write_text(json.dumps(out, indent=2))
        (OUT / "report.md").write_text(report)
    return out


if __name__ == "__main__":
    def show(agent, kind, text):
        print(f"[{agent}] {'→ ' + text if kind == 'tool' else ''}")
        if kind == "output":
            print(text, "\n" + "-" * 60)
    run_pipeline(show)
