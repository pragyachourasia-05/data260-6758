"""HW10 Part 1: operations dashboard for my s6758 listing Q&A system.

    streamlit run dashboard/app.py --server.port 8459

Reads only files my system writes: reports/hw10/raw/spans.jsonl (one JSON span per stage), evaluations.jsonl
(evaluator output), judge_validation.json / judge_vs_human.csv (Part 3) and latency_summary.json (Part 4.3).
"""
import json
import os
import sys
import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "reports" / "hw10" / "raw"
SPANS = Path(os.getenv("HW10_SPANS", RAW / "spans.jsonl"))
EVALS = RAW / "evaluations.jsonl"
sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="s6758 operations - HW10", layout="wide")
st.markdown("**Pragya Chourasia - DATA-260 HW10 - s6758 rental listings Q&A**")


@st.cache_data(ttl=15)
def load_jsonl(path: str, mtime: float) -> pd.DataFrame:  # mtime is part of the cache key, so a new line reloads
    rows = []
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return pd.DataFrame(rows)


@st.cache_data(ttl=60)
def load_json(path: str, mtime: float):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


@st.cache_resource
def redis_client():
    import redis

    return redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, decode_responses=True, socket_timeout=2)


def mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


def spans() -> pd.DataFrame:
    return load_jsonl(str(SPANS), mtime(SPANS))


def evaluations() -> pd.DataFrame:
    return load_jsonl(str(EVALS), mtime(EVALS))


def pct(values: pd.Series, q: float) -> float:
    return float(values.quantile(q)) if len(values) else float("nan")


# ---------------------------------------------------------------- Summary
def summary_page():
    st.header("Summary")
    df = spans()
    if df.empty:
        st.info(f"No spans yet in {SPANS}")
        return
    window = st.sidebar.selectbox("Time window", ["All recorded data", "Last 24 hours", "Last 1 hour"])
    now = time.time()
    if window != "All recorded data":
        df = df[df["start_ts"] >= now - (86400 if "24" in window else 3600)]
    lookups = df[df["stage"] == "cache_lookup"]
    if lookups.empty:
        st.info("No requests in this window.")
        return
    first, last = df["start_ts"].min(), df["end_ts"].max()
    st.caption(f"Time window: {pd.to_datetime(first, unit='s'):%Y-%m-%d %H:%M} to {pd.to_datetime(last, unit='s'):%Y-%m-%d %H:%M} UTC "
               f"({window.lower()}). Data source: {SPANS.relative_to(ROOT)}.")

    traces = set(lookups["trace_id"])
    hits = lookups[lookups["cache"] == "hit"]
    misses = lookups[lookups["cache"] == "miss"]
    error_traces = set(df[(df["status"] == "error") & df["trace_id"].isin(traces)]["trace_id"])
    requests = df[(df["stage"] == "request") & df["trace_id"].isin(traces)]
    miss_req = requests[requests["cache"] == "miss"]["duration_ms"]
    hit_req = requests[requests["cache"] == "hit"]["duration_ms"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Requests", len(traces))
    c1.caption("Distinct trace_ids with a cache_lookup span.")
    c2.metric("Cache hit rate", f"{100 * len(hits) / len(lookups):.0f}%")
    c2.caption(f"{len(hits)} hits / {len(misses)} misses, from the cache attribute on cache_lookup spans.")
    c3.metric("Error rate", f"{100 * len(error_traces) / len(traces):.0f}%")
    c3.caption(f"{len(error_traces)} trace(s) with any span status = error.")
    c4.metric("Cache-hit latency p50", f"{pct(hit_req, 0.5):.0f} ms" if len(hit_req) else "-")
    c4.caption("Kept apart from misses: hit requests never reach Kafka.")

    d1, d2, d3 = st.columns(3)
    d1.metric("Cache-miss latency p50 (to final answer)", f"{pct(miss_req, 0.5) / 1000:.1f} s" if len(miss_req) else "-")
    d2.metric("Cache-miss latency p95 (to final answer)", f"{pct(miss_req, 0.95) / 1000:.1f} s" if len(miss_req) else "-")
    evals = df[(df["stage"] == "evaluation") & df["trace_id"].isin(set(misses["trace_id"]))]
    full = []
    for tid, end in zip(evals["trace_id"], evals["end_ts"], strict=True):
        start = lookups[lookups["trace_id"] == tid]["start_ts"].min()
        full.append((end - start) * 1000)
    d3.metric("Cache-miss end-to-end p50 (incl. evaluation)", f"{pct(pd.Series(full), 0.5) / 1000:.1f} s" if full else "-")
    st.caption("Latency source: request spans (cache lookup to final answer) and cache_lookup start to evaluation end.")

    left, right = st.columns(2)
    counts = pd.DataFrame({"path": ["cache hit", "cache miss"], "requests": [len(hits), len(misses)]})
    left.altair_chart(alt.Chart(counts, title="Cache hits vs misses").mark_bar().encode(
        x="path", y="requests", color=alt.Color("path", scale=alt.Scale(range=["#2e7d32", "#ef6c00"]), legend=None)),
        width="stretch")
    if len(miss_req):
        right.altair_chart(alt.Chart(pd.DataFrame({"seconds": miss_req / 1000}), title="Cache-miss latency to final answer")
                           .mark_bar().encode(x=alt.X("seconds", bin=alt.Bin(maxbins=20)), y="count()"), width="stretch")

    lat = load_json(str(RAW / "latency_summary.json"), mtime(RAW / "latency_summary.json"))
    if lat:
        st.subheader("Stage latency, 50 confirmed cache misses (Part 4.3)")
        st.caption(f"Source: {(RAW / 'latency_summary.json').relative_to(ROOT)} - {lat['confirmed_misses']} misses, "
                   f"{lat['served_from_cache']} served from cache. End-to-end = {lat['e2e_definition']}.")
        st.dataframe(pd.DataFrame(lat["table"]).rename(columns={"stage": "Stage", "p50_ms": "p50 (ms)", "p95_ms": "p95 (ms)",
                                                                  "pct_of_e2e": "% of cache-miss end-to-end"}), hide_index=True)
    try:
        r = redis_client()
        st.caption(f"Live from Redis: {sum(1 for _ in r.scan_iter('s6758:semcache:*'))} entries in the semantic cache.")
    except Exception as exc:  # Redis down should not break the page
        st.caption(f"Redis not reachable: {exc}")


# ---------------------------------------------------------------- Evaluation
def evaluation_page():
    st.header("Evaluation")
    if st.query_params.get("section") == "judge":  # open straight at the Part 3 results
        judge_section()
        return
    ev = evaluations()
    if ev.empty:
        st.info(f"No evaluations yet in {EVALS}")
    else:
        rows = pd.DataFrame({
            "trace_id": ev["trace_id"], "question": ev["question"],
            "Plan Quality": ev["plan_quality"].map(lambda x: x["score"]),
            "Writer Helpfulness": ev["writer_helpfulness"].map(lambda x: x["score"]),
            "Final Answer Helpfulness": ev["final_answer_helpfulness"].map(lambda x: x["score"]),
            "Final - Draft": ev["final_vs_draft"].map(lambda x: x["difference"]),
            "Same text": ev["final_vs_draft"].map(lambda x: x["same_text"]),
            "Reviewer": ev["final_answer_helpfulness"].map(lambda x: x["reviewer_status"]),
        })
        st.caption(f"Source: {EVALS.relative_to(ROOT)}. Judge: {ev.iloc[0]['judge']['model']} via DeepEval GEval, "
                   f"temperature 0, seed 6758, scale 1 (very poor) to 5 (excellent).")
        means = rows[["Plan Quality", "Writer Helpfulness", "Final Answer Helpfulness"]].mean()
        c = st.columns(4)
        c[0].metric("Cases evaluated", len(rows))
        c[1].metric("Plan Quality (mean)", f"{means['Plan Quality']:.2f}")
        c[2].metric("Writer Helpfulness (mean)", f"{means['Writer Helpfulness']:.2f}")
        c[3].metric("Final Answer Helpfulness (mean)", f"{means['Final Answer Helpfulness']:.2f}")
        st.altair_chart(alt.Chart(means.reset_index().rename(columns={"index": "stage", 0: "mean score"}), title="Mean score by stage")
                        .mark_bar().encode(x=alt.X("stage", sort=None), y=alt.Y("mean score", scale=alt.Scale(domain=[0, 5]))),
                        width="stretch")
        st.subheader("Scores by case")
        st.dataframe(rows, hide_index=True, width="stretch")
        same = int(rows["Same text"].sum())
        diffs = rows["Final - Draft"].dropna()
        st.subheader("What the scores say about coordination")
        st.write(
            f"Plans average {means['Plan Quality']:.1f}/5 and drafts {means['Writer Helpfulness']:.1f}/5. "
            f"In {same} of {len(rows)} cases the final answer is the Writer's draft word for word: my Reviewer approves "
            f"or rejects but never rewrites. So Final-vs-Draft cannot show a real improvement; the mean difference of "
            f"{diffs.mean():+.2f} (range {diffs.min():+.0f} to {diffs.max():+.0f}) is the judge scoring the same text twice. "
            f"The Reviewer adds a gate, not a better answer.")
        pick = st.selectbox("Show details for trace_id", ev["trace_id"])
        rec = ev[ev["trace_id"] == pick].iloc[0]
        st.write(f"**Question:** {rec['question']}")
        st.write("**Plan:** " + " | ".join(rec["plan_quality"]["plan"]) + f"  \nPlan Quality {rec['plan_quality']['score']}: {rec['plan_quality']['reason']}")
        st.write(f"**Writer Helpfulness {rec['writer_helpfulness']['score']}:** {rec['writer_helpfulness']['reason']}")
        st.write(f"**Final answer ({rec['final_answer_helpfulness']['reviewer_status']}), score {rec['final_answer_helpfulness']['score']}:** "
                 f"{rec['final_answer_helpfulness']['final_answer']}")
        st.write(f"**Final vs draft:** {rec['final_vs_draft']['interpretation']}")

    judge_section()


def judge_section():
    st.subheader("Judge validation (Part 3)")
    val = load_json(str(RAW / "judge_validation.json"), mtime(RAW / "judge_validation.json"))
    if not val:
        st.info("Judge validation has not been run yet.")
        return
    st.caption("Source: reports/hw10/raw/judge_validation.json and judge_vs_human.csv (20 frozen drafts, my labels vs 3 judge runs).")
    agree = val["agreement_by_run"]
    rep = val["repeatability"]
    c = st.columns(4)
    c[0].metric("Spearman rho (run 1)", f"{agree['run1']['spearman_rho']:.2f}")
    c[1].metric("Mean abs difference (run 1)", f"{agree['run1']['mean_abs_diff']:.2f}")
    c[2].metric("Cases with a changed score", f"{rep['cases_where_score_changed']}/{rep['cases_compared']}")
    c[3].metric("Max change across runs", rep["max_abs_change"])
    st.dataframe(pd.DataFrame(agree).T, width="stretch")
    per_case = RAW / "judge_vs_human.csv"
    if per_case.exists():
        st.dataframe(pd.read_csv(per_case), hide_index=True, width="stretch")


# ---------------------------------------------------------------- Trace lookup
def trace_page():
    st.header("Trace lookup")
    df = spans()
    examples = load_json(str(RAW / "trace_examples.json"), mtime(RAW / "trace_examples.json")) or []
    if examples:
        st.caption("Example traces: " + ", ".join(f"{e['label']} = {e['trace_id']}" for e in examples))
    default = st.query_params.get("trace", examples[0]["trace_id"] if examples else "")
    trace_id = st.text_input("trace_id", value=default).strip()
    if not trace_id or df.empty:
        return
    t = df[df["trace_id"] == trace_id].sort_values("start_ts")
    if t.empty:
        st.warning("No spans for this trace_id.")
        return
    lookup = t[t["stage"] == "cache_lookup"]
    path = lookup.iloc[0].get("cache", "?") if not lookup.empty else "?"
    failed = t[t["status"] == "error"]
    color = {"hit": "green", "miss": "orange"}.get(path, "gray")
    st.markdown(f"Path: :{color}[**CACHE {str(path).upper()}**]" + (" - " + ("cache hit: answered from Redis, Kafka never used"
                if path == "hit" else "cache miss: Planner -> Writer -> Reviewer -> evaluator")))
    if not failed.empty:
        # the root cause is the earliest pipeline stage that failed; request/evaluation only fail as a result of it
        order = ["cache_lookup", "planner", "writer", "reviewer", "evaluation", "request"]
        root = failed.assign(rank=failed["stage"].map(lambda x: order.index(x) if x in order else 3)).sort_values("rank").iloc[0]
        st.error(f"Failed at stage **{root['stage']}**: {root['error']}")
        later = [f"{r.stage} ({r.error})" for r in failed.itertuples() if r.stage != root["stage"]]
        if later:
            st.caption("Then failed because of it: " + "; ".join(later))
    start0 = t["start_ts"].min()
    view = t.assign(offset_s=(t["start_ts"] - start0).round(3))[
        ["stage", "start", "end", "duration_ms", "status", "error", "offset_s"]]
    st.dataframe(view, hide_index=True, width="stretch", height=36 * (len(view) + 1) + 4)
    chart = t.assign(start_s=t["start_ts"] - start0, end_s=t["end_ts"] - start0)
    st.altair_chart(alt.Chart(chart, title="Stage timeline (seconds from the cache lookup)").mark_bar().encode(
        y=alt.Y("stage", sort=list(chart["stage"])), x="start_s", x2="end_s",
        color=alt.Color("status", scale=alt.Scale(domain=["ok", "error"], range=["#1976d2", "#c62828"]))),
        width="stretch")


pages = {"Summary": summary_page, "Evaluation": evaluation_page, "Trace lookup": trace_page}
start_page = st.query_params.get("page", "Summary")  # e.g. ?page=Trace%20lookup&trace=<id>
choice = st.sidebar.radio("Page", list(pages), index=list(pages).index(start_page) if start_page in pages else 0)
pages[choice]()
