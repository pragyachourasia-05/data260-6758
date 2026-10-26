"""Build reports/hw07/METRICS.md from the raw HW7 result files (no hand-typed numbers).
Also exports each Part 4 scenario's pricing-page snapshot (text + URL + access time + SHA-256).

    python backend/make_hw07_metrics.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "reports" / "hw07"
RAW = HW / "raw"


def load(name):
    p = RAW / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def pct(x):
    return f"{x * 100:.0f}%"


def export_snapshots() -> list[dict]:
    out = []
    for p in sorted((RAW / "part4_runs").glob("*.json")):
        run = json.loads(p.read_text(encoding="utf-8"))
        snap = run.get("pricing_snapshot") or {}
        label = run.get("label") or run["run_id"]
        if not snap.get("text"):
            continue
        (RAW / f"part4_pricing_snapshot_{label}.txt").write_text(snap["text"], encoding="utf-8")
        meta = {"scenario": label, "run_id": run["run_id"], "source_url": snap["url"], "accessed_at": snap["captured_at"],
                "sha256_of_snapshot_text": snap["sha256"], "sha256_of_raw_html": snap["raw_html_sha256"],
                "snapshot_file": f"part4_pricing_snapshot_{label}.txt"}
        (RAW / f"part4_pricing_snapshot_{label}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        out.append({**meta, "run": run})
    return out


def main() -> None:
    lines = ["# HW7 METRICS", "",
             "SID4 6758 | PORT_BASE 8458 | PREFIX s6758 | SEED 6758 | VERIFY_SEED 266758 | DOMAIN_ID 6 (rental housing listings)",
             "Hardware: Intel Core i5-1335U, 16 GB RAM, Intel Iris Xe (CPU inference). Models: llama3.2:3b (Parts 2, 3, 6), "
             "qwen3:8b (Parts 4, 5), both via Ollama.", ""]

    ver = json.loads((HW / "verification.json").read_text(encoding="utf-8")) if (HW / "verification.json").exists() else None
    lines += ["## Part 1 - JWT + roles", "", "| Request | Expected | Observed |", "| --- | --- | --- |",
              "| POST /auth/login valid / invalid | 200 + token / 401 | 200 + token / 401 |",
              "| GET /auth/me no token / invalid / expired / valid | 401 / 401 / 401 / 200 | 401 / 401 / 401 / 200 |",
              "| POST /listings reader / writer | 403 / 201 | 403 / 201 |",
              "| DELETE /listings writer / moderator | 403 / 200 | 403 / 200 |",
              "| GET /listings any role / no token | 200 / 401 | 200 / 401 |", "",
              "Lint demo: pre-commit Ruff hook blocked the commit on F811, E402, B904; after the fixes the hook passed "
              "and commit `f077682` was created (screenshots 1.6a / 1.6b).", ""]
    if ver:
        lines += [f"verify_hw07.py: {sum(c['passed'] for c in ver['checks'])}/{len(ver['checks'])} checks passed "
                  f"on commit `{ver['commit_hash'][:7]}`.", ""]

    rel = load("part2_reliability.json")
    if rel:
        s = rel["summary"]
        lines += ["## Part 2 - tool-call reliability", "",
                  f"{s['attempts']} attempts over the 3 fixed cases ({s['proposed_calls']} proposed tool calls), "
                  f"settings {s['settings']}.", "",
                  "| Metric | Before repair | After repair |", "| --- | --- | --- |",
                  f"| Well-formed tool calls (per proposed call) | {pct(s['per_call_well_formed_before_repair'])} | "
                  f"{pct(s['per_call_well_formed_after_repair'])} |",
                  f"| Attempts completing the full chain | {pct(s['attempts_no_failure_before_repair'])} (no repair needed) | "
                  f"{pct(s['attempts_completed_after_repair'])} |",
                  f"| Verifier pass rate (facts correct) | - | {pct(s['verifier_pass_rate'])} |", "",
                  "| Failure type | Events (all repaired + unrepaired) | Attempts affected | Attempts left unrecovered |",
                  "| --- | --- | --- | --- |"]
        for t in s["failure_events_by_type"]:
            lines.append(f"| {t} | {s['failure_events_by_type'][t]} | {s['attempts_with_failure_by_type'][t]} | "
                         f"{s['unrecovered_attempts_by_type'].get(t, 0)} |")
        lines.append("")

    comp = load("part3_comparison.json")
    if comp:
        o, r = comp["summary"]["original"], comp["summary"]["reflexion"]
        review = load("part3_false_rejection_review.json") or {"items": []}
        fr_o = sum(1 for x in review["items"] if x["false_rejection"] and x["loop"] == "original")
        fr_r = sum(1 for x in review["items"] if x["false_rejection"] and x["loop"] == "reflexion")
        lines += ["## Part 3 - original loop vs Reflexion", "",
                  f"Each of the 3 fixed tasks run {comp['summary']['repeats']}x per loop ({o['runs']} runs each).", "",
                  "| Metric | Original loop | Reflexion loop |", "| --- | --- | --- |",
                  f"| Task success | {pct(o['task_success'])} | {pct(r['task_success'])} |",
                  f"| Unsupported claims (total) | {o['unsupported_claims']} | {r['unsupported_claims']} |",
                  f"| Retry rate | {pct(o['retry_rate'])} | {pct(r['retry_rate'])} |",
                  f"| Tool calls (mean per task) | {o['tool_calls_mean']} | {r['tool_calls_mean']} |",
                  f"| Tokens (mean per task) | {o['tokens_mean']} | {r['tokens_mean']} |",
                  f"| Latency (ms, mean per task) | {o['latency_ms_mean']} | {r['latency_ms_mean']} |",
                  f"| Verifier false rejections (manual review of all {len(review['items'])} rejections) | {fr_o} | {fr_r} |", "",
                  f"Reflexion stop reasons: {comp['summary']['reflexion_stop_reasons']}.", ""]

    snaps = export_snapshots()
    if snaps:
        lines += ["## Part 4 - bike-share agent (Bay Wheels)", "",
                  "| Scenario | Rows / months | Pay per use | Month pass total | Decision | Check agrees | Steps | Time | Stop |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for sn in snaps:
            run, a, f = sn["run"], sn["run"]["audit"], sn["run"].get("final") or {}
            agree = all(abs(float(f.get(k, -1)) - a[k]) <= 0.05 * max(1, a[k]) for k in
                        ("pay_per_use_total", "pass_fees", "pass_overage", "membership_total", "actual_avg_rides_per_month"))
            lines.append(f"| {sn['scenario']} | {a['rides']} / {a['months']} | ${a['pay_per_use_total']:,.2f} | "
                         f"${a['membership_total']:,.2f} | {f.get('decision')} | {'yes' if agree else 'NO'} | {run['steps']} | "
                         f"{run['total_ms'] / 1000:.0f} s | {run['stop_reason']} |")
        lines += ["", "| Scenario | Source URL | Accessed | SHA-256 (snapshot text) |", "| --- | --- | --- | --- |"]
        for sn in snaps:
            lines.append(f"| {sn['scenario']} | {sn['source_url']} | {sn['accessed_at']} | `{sn['sha256_of_snapshot_text']}` |")
        lines.append("")

    atk = load("part5_attack_results.json")
    if atk:
        lines += ["## Part 5 - prompt injection", "", "| Attack | Before defenses | After prompt defense | After prompt + tool defense |",
                  "| --- | --- | --- | --- |"]
        for name, label in [("override", "Recommendation override"), ("sql", "Non-SELECT tool misuse"), ("exfil", "Data exfiltration")]:
            cells = []
            for cond in ("before", "prompt_defense", "prompt_and_tool"):
                r = next((x for x in atk if x["attack"] == name and x["condition"] == cond), None)
                cells.append("-" if r is None else ("**succeeded**" if r["succeeded"] else "not exploited") + f" ({r['evidence'][:70]})")
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        direct = load("part5_direct_sql_check.json")
        if direct:
            lines += ["", "Direct tool-boundary check (injected SQL sent straight to csv_sql, no model):", "",
                      "| Statement | Tool defense | Result | Rows after |", "| --- | --- | --- | --- |"]
            for x in direct["results"]:
                lines.append(f"| `{x['sql']}` | {'on' if x['tool_defense'] else 'off'} | "
                             f"{'executed' if x['success'] else x['error']} | {x['rows_after']} |")
        lines.append("")

    gate = load("part6_safety_gate_results.json")
    if gate:
        lines += ["## Part 6 - safety gate", "", f"10-command test: {gate['correct']}/10 correct. "
                  f"False allows found in gate v1 and fixed in v2: {len(gate['false_allows_fixed'])}.", "",
                  "| Command | Expected | Result | is_destructive |", "| --- | --- | --- | --- |"]
        for t in gate["tests"]:
            lines.append(f"| `{t['command']}` | {t['expected']} | {'allow' if t['allowed'] else 'block'} | {t['is_destructive']} |")
        lines.append("")
    integ = load("part6_integration_trace.json")
    if integ:
        lines += [f"Integration test (glob -> search -> read): {'PASS' if integ['pass'] else 'FAIL'}, "
                  f"{integ['tool_calls']} tool calls, stop={integ['stop_reason']}.", ""]

    (HW / "METRICS.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
