"""HW6 Part 3: what memory costs.

Replays the fixed 30-message conversation (reports/hw06/cases/conversation_30.yaml)
through POST /api/chat for each setting, in a fresh user + session each time, then
asks the five probes from reports/hw06/memory_probes.yaml and scores them.

Settings: SHORT_TERM_N = 4, 12, 30, and the compress_assistant policy at N = 30.

Run from the repository root while the backend is up on port 8458:
    python backend/run_hw06_memory_cost.py                 # all settings (resumes finished ones)
    python backend/run_hw06_memory_cost.py --settings n4 --limit 3 --tag dry   # quick dry run

Outputs in reports/hw06/raw/:
    part3/<setting>.json          full per-turn records, replies and probe answers
    part3_turns.csv               per-turn token / latency rows for every setting
    part3_probe_scores.json       probe replies, matched elements and 1-5 scores
    part3_policy_comparison.json  N=30 vs N=30 + compress_assistant
    part3_summary.json            results table + cost estimate
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "reports" / "hw06"
RAW = HW / "raw"
BASE = "http://127.0.0.1:8458/api"

SETTINGS = {
    "n4": {"label": "SHORT_TERM_N=4", "short_term_n": 4, "policy": "none"},
    "n12": {"label": "SHORT_TERM_N=12", "short_term_n": 12, "policy": "none"},
    "n30": {"label": "SHORT_TERM_N=30", "short_term_n": 30, "policy": "none"},
    "n30_compress": {"label": "Compression policy (N=30, compress_assistant)", "short_term_n": 30, "policy": "compress_assistant"},
}

PRICE_IN = 1.0 / 1_000_000   # $ per input token
PRICE_OUT = 5.0 / 1_000_000  # $ per output token
N_CONVERSATIONS = 10_000


def log(msg: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def post_chat(body: dict) -> dict:
    req = urllib.request.Request(f"{BASE}/chat", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as resp:
        return json.loads(resp.read())


def _contains(text: str, spelling: str) -> bool:
    pattern = r"\b" + re.escape(spelling.lower())
    if len(spelling) <= 3 and spelling.isalnum():
        pattern += r"\b"  # short tokens like "ev" must be whole words
    return re.search(pattern, text) is not None


def score_probe(reply: str, probe: dict) -> dict:
    """Deterministic 1-5 score following the rubric in memory_probes.yaml."""
    text = reply.lower()
    required = probe["required"]
    hits = [any(_contains(text, s) for s in group) for group in required]
    forbidden = [s for s in probe.get("forbidden", []) if _contains(text, s)]
    n_hit = sum(hits)
    if n_hit == len(required):
        score = 4 if forbidden else 5
    elif n_hit >= len(required) / 2:
        score = 3
    elif n_hit > 0 or forbidden:
        score = 2
    else:
        score = 1
    return {"score": score, "required_hits": hits, "forbidden_found": forbidden}


def turn_row(setting: str, phase: str, turn: int, usage: dict, memory_used: dict) -> dict:
    comp = usage["component_tokens_est"]
    return {
        "setting": setting,
        "phase": phase,
        "turn": turn,
        "short_term_n": usage["short_term_n"],
        "policy": usage["policy"],
        "window_messages": memory_used["short_term_count"],
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "cached_prompt_tokens": usage["cached_prompt_tokens"],
        "system_primer_tokens_est": comp["system_primer"],
        "long_term_summary_tokens_est": comp["long_term_summary"],
        "short_term_window_tokens_est": comp["short_term_window"],
        "current_message_tokens_est": comp["current_message"],
        "episodic_facts_tokens_est": comp["episodic_facts"],
        "template_overhead_tokens": usage["template_overhead_tokens"],
        "maintenance_input_tokens": usage["memory_maintenance_tokens"]["input"],
        "maintenance_output_tokens": usage["memory_maintenance_tokens"]["output"],
        "latency_ms": usage["latency_ms"],
        "model_latency_ms": usage["model_latency_ms"],
        "summary_triggered": usage["summary_triggered"],
        "episodic_facts_retrieved": len(memory_used["episodic_facts"]),
    }


def run_setting(key: str, conversation: list[str], probes: list[dict], tag: str, limit: int | None) -> dict:
    cfg = SETTINGS[key]
    user_id = f"p3_{key}_{tag}"
    session_id = f"{user_id}_s1"
    rows, transcript, probe_results = [], [], []
    msgs = conversation[:limit] if limit else conversation
    log(f"setting {key} ({cfg['label']}) user={user_id} messages={len(msgs)}")
    for i, message in enumerate(msgs, 1):
        res = post_chat({"user_id": user_id, "session_id": session_id, "message": message,
                         "short_term_n": cfg["short_term_n"], "policy": cfg["policy"]})
        rows.append(turn_row(key, "conversation", i, res["usage"], res["memory_used"]))
        transcript.append({"turn": i, "user": message, "assistant": res["reply"]})
        u = res["usage"]
        log(f"  {key} turn {i:2d}: prompt={u['prompt_tokens']:5d} completion={u['completion_tokens']:4d} "
            f"window={res['memory_used']['short_term_count']:2d} latency={u['latency_ms'] / 1000:.1f}s")
    for j, probe in enumerate(probes if not limit else probes[:1], 1):
        res = post_chat({"user_id": user_id, "session_id": session_id, "message": probe["question"],
                         "short_term_n": cfg["short_term_n"], "policy": cfg["policy"]})
        rows.append(turn_row(key, "probe", len(msgs) + j, res["usage"], res["memory_used"]))
        scored = score_probe(res["reply"], probe)
        probe_results.append({"probe": probe["id"], "question": probe["question"], "reply": res["reply"],
                              "episodic_facts": [f["fact"] for f in res["memory_used"]["episodic_facts"]], **scored})
        log(f"  {key} {probe['id']}: score={scored['score']}  reply={res['reply'][:110]!r}")
    return {"setting": key, **cfg, "user_id": user_id, "session_id": session_id,
            "complete": limit is None, "rows": rows, "transcript": transcript, "probes": probe_results}


def summarize(results: dict[str, dict]) -> dict:
    table, costs = [], []
    for key, res in results.items():
        conv = [r for r in res["rows"] if r["phase"] == "conversation"]
        mean = lambda field: round(statistics.mean(r[field] for r in conv), 1)  # noqa: E731
        probe_scores = [p["score"] for p in res["probes"]]
        chat_in = sum(r["prompt_tokens"] for r in conv)
        chat_out = sum(r["completion_tokens"] for r in conv)
        maint_in = sum(r["maintenance_input_tokens"] for r in conv)
        maint_out = sum(r["maintenance_output_tokens"] for r in conv)
        chat_cost = chat_in * PRICE_IN + chat_out * PRICE_OUT
        total_cost = chat_cost + maint_in * PRICE_IN + maint_out * PRICE_OUT
        table.append({
            "setting": key, "label": res["label"], "turns": len(conv),
            "mean_prompt_tokens_per_turn": mean("prompt_tokens"),
            "mean_completion_tokens_per_turn": mean("completion_tokens"),
            "mean_latency_ms": mean("latency_ms"),
            "mean_model_latency_ms": mean("model_latency_ms"),
            "mean_window_tokens_est": mean("short_term_window_tokens_est"),
            "mean_summary_tokens_est": mean("long_term_summary_tokens_est"),
            "mean_episodic_tokens_est": mean("episodic_facts_tokens_est"),
            "probe_quality": round(statistics.mean(probe_scores), 2) if probe_scores else None,
            "probe_scores": probe_scores,
        })
        costs.append({
            "setting": key, "label": res["label"],
            "chat_input_tokens_per_conversation": chat_in,
            "chat_output_tokens_per_conversation": chat_out,
            "maintenance_input_tokens_per_conversation": maint_in,
            "maintenance_output_tokens_per_conversation": maint_out,
            "chat_cost_per_conversation_usd": round(chat_cost, 6),
            "chat_cost_10k_usd": round(chat_cost * N_CONVERSATIONS, 2),
            "total_cost_10k_usd": round(total_cost * N_CONVERSATIONS, 2),
        })
    return {"table": table, "costs": costs}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--settings", nargs="+", default=list(SETTINGS))
    ap.add_argument("--limit", type=int, default=None, help="only send the first K messages (dry run)")
    ap.add_argument("--tag", default=datetime.now().strftime("%m%d%H%M"))
    ap.add_argument("--rerun", action="store_true", help="ignore finished results")
    args = ap.parse_args()

    conversation = yaml.safe_load((HW / "cases" / "conversation_30.yaml").read_text(encoding="utf-8"))["messages"]
    probes = yaml.safe_load((HW / "memory_probes.yaml").read_text(encoding="utf-8"))["probes"]
    assert len(conversation) == 30 and len(probes) == 5

    out_dir = RAW / ("part3_dry" if args.limit else "part3")
    out_dir.mkdir(parents=True, exist_ok=True)
    for key in args.settings:
        path = out_dir / f"{key}.json"
        if path.exists() and not args.rerun and json.loads(path.read_text(encoding="utf-8")).get("complete"):
            log(f"setting {key}: already finished, skipping (use --rerun to redo)")
            continue
        t0 = time.perf_counter()
        result = run_setting(key, conversation, probes, args.tag, args.limit)
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        log(f"setting {key} done in {(time.perf_counter() - t0) / 60:.1f} min -> {path.relative_to(ROOT)}")

    if args.limit:
        return
    results = {}
    for key in SETTINGS:
        path = out_dir / f"{key}.json"
        if path.exists():
            results[key] = json.loads(path.read_text(encoding="utf-8"))
    if not results:
        return

    with (RAW / "part3_turns.csv").open("w", newline="", encoding="utf-8") as fh:
        rows = [r for res in results.values() for r in res["rows"]]
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (RAW / "part3_probe_scores.json").write_text(json.dumps(
        {k: r["probes"] for k, r in results.items()}, indent=2), encoding="utf-8")

    summary = summarize(results)
    (RAW / "part3_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if "n30" in results and "n30_compress" in results:
        by = {row["setting"]: row for row in summary["table"]}
        base, pol = by["n30"], by["n30_compress"]
        comparison = {
            "baseline": base, "policy": pol,
            "prompt_token_savings_per_turn": round(base["mean_prompt_tokens_per_turn"] - pol["mean_prompt_tokens_per_turn"], 1),
            "prompt_token_savings_pct": round(100 * (1 - pol["mean_prompt_tokens_per_turn"] / base["mean_prompt_tokens_per_turn"]), 1),
            "probe_quality_change": round(pol["probe_quality"] - base["probe_quality"], 2),
            "per_probe": [
                {"probe": a["probe"], "baseline_score": a["score"], "policy_score": b["score"]}
                for a, b in zip(results["n30"]["probes"], results["n30_compress"]["probes"])
            ],
        }
        (RAW / "part3_policy_comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")

    log("results table")
    for row in summary["table"]:
        log(f"  {row['label']:<48} prompt/turn={row['mean_prompt_tokens_per_turn']:7.1f}  "
            f"latency={row['mean_latency_ms']:8.1f} ms  probe={row['probe_quality']}  {row['probe_scores']}")
    for c in summary["costs"]:
        log(f"  {c['label']:<48} chat cost/10k=${c['chat_cost_10k_usd']:.2f}  with maintenance=${c['total_cost_10k_usd']:.2f}")


if __name__ == "__main__":
    main()
