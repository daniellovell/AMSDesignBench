from __future__ import annotations
import argparse
import csv
import html
import json
from collections import defaultdict
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple


def esc(s: Any) -> str:
    return html.escape(str(s))


def color_for_score(x: float | None) -> str:
    if x is None:
        return "#eee"
    # green to red gradient
    x = max(0.0, min(1.0, float(x)))
    r = int(255 * (1 - x))
    g = int(200 * x + 55 * (1 - x))
    b = int(120 * x + 50 * (1 - x))
    return f"rgb({r},{g},{b})"


def load_results(path: Path) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            recs.append(json.loads(line))
        except Exception:
            continue
    return recs


def aggregates(recs: List[Dict[str, Any]]):
    per_model = defaultdict(lambda: {
        "n": 0,
        "pass": 0,
        "raw_sum": 0.0,
        "judge_sum": 0.0,
        "judge_n": 0,
        "blended_sum": 0.0,
        "blended_n": 0,
    })
    # Nested dicts keyed by [group][model]
    def _mk():
        return {"n": 0, "raw_sum": 0.0, "judge_sum": 0.0, "judge_n": 0}
    per_family = defaultdict(lambda: defaultdict(_mk))
    per_modality = defaultdict(lambda: defaultdict(_mk))

    for r in recs:
        m = r.get("model", "unknown")
        fam = r.get("topic") or r.get("family", "?")
        mod = r.get("modality", "?")
        raw = float(r.get("scores", {}).get("raw", 0.0))
        per_model[m]["n"] += 1
        per_model[m]["raw_sum"] += raw
        if r.get("scores", {}).get("pass"):
            per_model[m]["pass"] += 1
        j = r.get("judge")
        if isinstance(j, dict) and isinstance(j.get("overall"), (int, float)):
            per_model[m]["judge_sum"] += float(j["overall"])
            per_model[m]["judge_n"] += 1
        if isinstance(r.get("raw_blended"), (int, float)):
            per_model[m]["blended_sum"] += float(r["raw_blended"])
            per_model[m]["blended_n"] += 1

        per_family[fam][m]["n"] += 1
        per_family[fam][m]["raw_sum"] += raw
        if isinstance(j, dict) and isinstance(j.get("overall"), (int, float)):
            per_family[fam][m]["judge_sum"] += float(j["overall"])
            per_family[fam][m]["judge_n"] += 1
        per_modality[mod][m]["n"] += 1
        per_modality[mod][m]["raw_sum"] += raw
        if isinstance(j, dict) and isinstance(j.get("overall"), (int, float)):
            per_modality[mod][m]["judge_sum"] += float(j["overall"])
            per_modality[mod][m]["judge_n"] += 1

    return per_model, per_family, per_modality


def write_csv(path: Path, recs: List[Dict[str, Any]]):
    fields = [
        "model", "family", "item_id", "question_id", "rubric_id", "rubric_path", "modality", "split",
        "raw", "pass", "judge_overall", "raw_blended", "hallucination_penalty", "grounded_ratio",
    ]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in recs:
            # groundedness ratio: average across criteria that have it
            ratios: List[float] = []
            per = r.get("scores", {}).get("per_criterion", {})
            if isinstance(per, dict):
                for v in per.values():
                    if isinstance(v, dict):
                        g = v.get("groundedness")
                        if isinstance(g, dict) and isinstance(g.get("ratio"), (int, float)):
                            ratios.append(float(g.get("ratio")))
            grounded_ratio = sum(ratios)/len(ratios) if ratios else None
            row = {
                "model": r.get("model"),
                "family": r.get("family"),
                "item_id": r.get("item_id"),
                "question_id": r.get("question_id"),
                "rubric_id": r.get("rubric_id"),
                "rubric_path": r.get("rubric_path"),
                "modality": r.get("modality"),
                "split": r.get("split"),
                "raw": r.get("scores", {}).get("raw"),
                "pass": r.get("scores", {}).get("pass"),
                "judge_overall": (r.get("judge") or {}).get("overall"),
                "raw_blended": r.get("raw_blended"),
                "hallucination_penalty": (r.get("scores", {}).get("hallucination") or {}).get("penalty"),
                "grounded_ratio": grounded_ratio,
            }
            w.writerow(row)


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def render_index(path: Path, recs: List[Dict[str, Any]]):
    out_dir = path.parent
    per_model, per_family, per_modality = aggregates(recs)
    models = sorted(per_model.keys())

    # Build a map of unique (family, item_id, question_id) -> list of records per model
    groups: Dict[Tuple[str, str, str], Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for r in recs:
        key = ((r.get("topic") or r.get("family", "?")), r.get("item_id", "?"), r.get("question_id", "?"))
        groups[key][r.get("model", "unknown")] = r

    def model_header_cells():
        return "".join(f"<th class=rot>{esc(m)}</th>" for m in models)

    def model_score_cells(key):
        cells = []
        recs_by_model = groups.get(key, {})
        for m in models:
            r = recs_by_model.get(m)
            judge_overall = None
            if r:
                j = r.get("judge") or {}
                if isinstance(j.get("overall"), (int, float)):
                    judge_overall = float(j["overall"])
            color = color_for_score(judge_overall)
            judge_str = f"{judge_overall:.2f}" if judge_overall is not None else "-"
            cells.append(f"<td style=\"background:{color}\"><span title=\"judged\">{esc(judge_str)}</span></td>")
        return "".join(cells)

    # HTML
    css = """
    body { font-family: Arial, sans-serif; font-size: 12px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 3px 6px; }
    th { background: #f5f5f5; }
    .rot { writing-mode: vertical-rl; transform: rotate(180deg); font-size: 10px; }
    .small { font-size: 11px; }
    .muted { color: #666; }
    .container { max-width: 1200px; margin: 0 auto; }
    details > summary { cursor: pointer; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space: pre-wrap; background: #fafafa; border: 1px solid #eee; padding: 6px; }
    .top { display: flex; gap: 24px; }
    .box { border: 1px solid #ddd; padding: 8px; }
    a { color: #0366d6; text-decoration: none; }
    a:hover { text-decoration: underline; }
    """

    # Leaderboard (judge-only rendering)
    leader_rows = []
    for m in models:
        a = per_model[m]
        judge_avg = a["judge_sum"] / a["judge_n"] if a["judge_n"] else None
        row = f"<tr><td>{esc(m)}</td><td>{a['n']}</td>"
        row += f"<td>{judge_avg:.3f}</td>" if judge_avg is not None else "<td>-</td>"
        leader_rows.append(row + "</tr>")

    # Families table (judge-only)
    fam_tables = []
    if per_family:
        fam_rows = []
        fams = sorted(per_family.keys())
        for fam in fams:
            by_model = per_family[fam]
            for m in models:
                a = by_model.get(m, {})
                n = a.get("n", 0)
                jn = a.get("judge_n", 0)
                javg = (a.get("judge_sum", 0.0) / jn) if jn else None
                fam_rows.append(
                    f"<tr><td>{esc(fam)}</td><td>{esc(m)}</td><td>{n}</td>" + (f"<td>{javg:.3f}</td>" if javg is not None else "<td>-</td>") + "</tr>"
                )
        fam_table = (
            "<div class=box><b>Families</b><table class=small>"
            "<tr><th>Family</th><th>Model</th><th>n</th><th>Judge</th></tr>" + "".join(fam_rows) + "</table></div>"
        )
        fam_tables.append(fam_table)

    # Modalities table (judge-only)
    mod_tables = []
    if per_modality:
        mod_rows = []
        mods = sorted(per_modality.keys())
        for mod in mods:
            by_model = per_modality[mod]
            for m in models:
                a = by_model.get(m, {})
                n = a.get("n", 0)
                jn = a.get("judge_n", 0)
                javg = (a.get("judge_sum", 0.0) / jn) if jn else None
                mod_rows.append(
                    f"<tr><td>{esc(mod)}</td><td>{esc(m)}</td><td>{n}</td>" + (f"<td>{javg:.3f}</td>" if javg is not None else "<td>-</td>") + "</tr>"
                )
        mod_table = (
            "<div class=box><b>Modalities</b><table class=small>"
            "<tr><th>Modality</th><th>Model</th><th>n</th><th>Judge</th></tr>" + "".join(mod_rows) + "</table></div>"
        )
        mod_tables.append(mod_table)

    # Per-question table
    qrows = []
    for key in sorted(groups.keys()):
        fam, item_id, qid = key
        rec_any = next(iter(groups[key].values()))
        mod = rec_any.get("modality", "?")
        track = rec_any.get("track", "?")
        aspect = rec_any.get("aspect", "-")
        rub = rec_any.get("rubric_id", "?")
        item_rel = f"items/{esc(fam)}/{esc(item_id)}_{esc(qid)}.html"
        row = f"<tr><td><a href='{item_rel}'>{esc(fam)}/{esc(item_id)}</a></td><td>{esc(qid)}</td><td>{esc(track)}</td><td>{esc(mod)}</td><td>{esc(aspect)}</td><td>{esc(rub)}</td>"
        row += model_score_cells(key)
        qrows.append(row + "</tr>")

    html_out = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>AMS Oral Bench Report</title>
  <style>{css}</style>
</head>
<body>
<div class="container">
  <h2>AMS Oral Bench Report</h2>
  <div class="top">
    <div class="box">
      <b>Models</b>
      <table class="small">
        <tr><th>Model</th><th>n</th><th>Judge</th></tr>
        {''.join(leader_rows)}
      </table>
    </div>
    {''.join(fam_tables)}
    {''.join(mod_tables)}
    <div class="box">
      <b>Downloads</b>
      <ul>
        <li><a href="../combined_results.jsonl">combined_results.jsonl</a></li>
        <li><a href="results.csv">results.csv</a></li>
        <li><a href="report.md">report.md</a></li>
      </ul>
    </div>
  </div>

  <h3>Per-Question Scores</h3>
  <table class="small">
    <tr><th>Item</th><th>QID</th><th>Track</th><th>Modality</th><th>Aspect</th><th>Rubric</th>{model_header_cells()}</tr>
    {''.join(qrows)}
  </table>
</div>
</body>
</html>
"""
    path.write_text(html_out, encoding="utf-8")


def render_item_pages(report_dir: Path, recs: List[Dict[str, Any]]):
    # group by (family, item_id, question_id)
    groups: Dict[Tuple[str, str, str], Dict[str, Dict[str, Any]]] = defaultdict(dict)
    models = set()
    for r in recs:
        key = (r.get("family", "?"), r.get("item_id", "?"), r.get("question_id", "?"))
        groups[key][r.get("model", "unknown")] = r
        models.add(r.get("model", "unknown"))
    models = sorted(models)

    css = """
    body { font-family: Arial, sans-serif; font-size: 12px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 3px 6px; }
    th { background: #f5f5f5; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space: pre-wrap; background: #fafafa; border: 1px solid #eee; padding: 6px; }
    .small { font-size: 11px; }
    details > summary { cursor: pointer; }
    .score { padding: 0 6px; }
    """

    for (fam, item_id, qid), by_model in groups.items():
        item_dir = report_dir / "items" / fam
        ensure_dir(item_dir)
        out_path = item_dir / f"{item_id}_{qid}.html"
        # Assume prompt same for all records; take from any
        any_rec = next(iter(by_model.values()))
        prompt_text = any_rec.get("prompt") or "(prompt not recorded in results)"
        modality = any_rec.get("modality", "?")
        track = any_rec.get("track", "?")
        aspect = any_rec.get("aspect", "-")
        rubric_id = any_rec.get("rubric_id", "?")
        rubric_path = any_rec.get("rubric_path", "")
        artifact_text = any_rec.get("artifact") or ""
        artifact_path = any_rec.get("artifact_path") or ""
        rand_info = any_rec.get("artifact_randomization") or {}
        rand_seed = rand_info.get("seed") if isinstance(rand_info, dict) else None

        # Build per-model blocks
        blocks = []
        for m in models:
            r = by_model.get(m)
            if not r:
                continue
            scores = r.get("scores", {})
            judge = r.get("judge") or {}
            judge_overall = judge.get("overall")
            # Optional: judge debug prompt
            jdbg = judge.get("debug") or {}
            judge_debug_html = ""
            if isinstance(jdbg, dict) and (jdbg.get("system") or jdbg.get("instructions") or jdbg.get("payload")):
                sys_txt = jdbg.get("system") or ""
                inst_txt = jdbg.get("instructions") or ""
                payload_txt = jdbg.get("payload")
                try:
                    payload_pretty = json.dumps(payload_txt, indent=2) if payload_txt is not None else ""
                except Exception:
                    payload_pretty = esc(str(payload_txt))
                judge_debug_html = (
                    "<details><summary>Judge Prompt</summary>"
                    "<div class=small><b>System</b></div><div class=mono>" + esc(sys_txt) + "</div>"
                    "<div class=small><b>Instructions</b></div><div class=mono>" + esc(inst_txt) + "</div>"
                    "<div class=small><b>Payload</b></div><div class=mono>" + esc(payload_pretty) + "</div>"
                    "</details>"
                )
            # Judge breakdown
            judge_rows = []
            if isinstance(judge, dict) and isinstance(judge.get("scores"), dict):
                for jc, jv in judge["scores"].items():
                    if isinstance(jv, (int, float)):
                        judge_rows.append(f"<tr><td>{esc(jc)}</td><td>{jv:.2f}</td></tr>")
            judge_html = ""
            if judge_rows or isinstance(judge_overall, (int, float)):
                judge_html = "<b>Judge:</b> " + (f"overall {judge_overall:.2f}" if isinstance(judge_overall, (int, float)) else "-")
                if judge_rows:
                    judge_html += "<br/><table class=small><tr><th>Criterion</th><th>Score</th></tr>" + "".join(judge_rows) + "</table>"
                if judge_debug_html:
                    judge_html += "<br/>" + judge_debug_html
            # If judge returned a structured error, surface it prominently
            jerr = judge.get("error") if isinstance(judge, dict) else None
            if jerr:
                judge_html += ("<div class=small style='color:#b00'>Judge error: " + esc(str(jerr)) + "</div>")
            # Show any adapter/harness error captured for this record
            err = r.get("error")
            if err:
                judge_html += ("<div class=small style='color:#b00'>Error: " + esc(str(err)) + "</div>")
            
            # SPICE Verification Details
            verification_html = ""
            verification = r.get("verification_details")
            if verification:
                sim_passed = verification.get("simulation_passed", False)
                metrics = verification.get("metrics", {})
                ver_err = verification.get("error")
                
                status_color = "#0a0" if sim_passed else "#b00"
                status_text = "✅ PASSED" if sim_passed else "❌ FAILED"
                verification_html = f"<div style='margin-top:8px;'><b style='color:{status_color}'>SPICE Verification: {status_text}</b></div>"
                
                if metrics:
                    verification_html += "<table class=small style='margin-top:4px;'><tr><th>Metric</th><th>Value</th><th>Status</th></tr>"
                    per_crit = scores.get("per_criterion", {})
                    for metric_name, value in metrics.items():
                        # Find corresponding criterion to get threshold
                        crit_data = per_crit.get(f"verification_{metric_name.replace('_hz', '').replace('_db', '').replace('_deg', '')}")
                        if crit_data and isinstance(crit_data, dict):
                            threshold = crit_data.get("threshold", "?")
                            passed = crit_data.get("passed", False)
                            status = "✅" if passed else "❌"
                            value_str = f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
                            verification_html += f"<tr><td>{esc(metric_name)}</td><td>{esc(value_str)}</td><td>{status} (req: {esc(threshold)})</td></tr>"
                        else:
                            value_str = f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
                            verification_html += f"<tr><td>{esc(metric_name)}</td><td>{esc(value_str)}</td><td>-</td></tr>"
                    verification_html += "</table>"
                
                if ver_err:
                    verification_html += f"<div class=small style='color:#b00;margin-top:4px;'>Error: {esc(str(ver_err))}</div>"
            
            answer = r.get("answer", "")
            answer_html = f"<details><summary>View answer</summary><div class=mono>{esc(answer)}</div></details>"
            blocks.append(
                f"<tr><td>{esc(m)}</td><td>{judge_html}{verification_html}</td><td>{answer_html}</td></tr>"
            )

        html_out = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{esc(fam)}/{esc(item_id)} {esc(qid)}</title>
  <style>{css}</style>
  
  <script>/* none */</script>
  <base href="../" />
  <style> .hdr td {{ padding: 2px 6px; }} </style>
  </head>
<body>
  <div><a href="../index.html">← Back to index</a></div>
  <h3>{esc(fam)}/{esc(item_id)} — {esc(qid)}</h3>
  <table class="small hdr">
    <tr><td><b>Track</b></td><td>{esc(track)}</td><td><b>Modality</b></td><td>{esc(modality)}</td><td><b>Aspect</b></td><td>{esc(aspect)}</td><td><b>Rubric</b></td><td>{esc(rubric_id)}</td><td><b>Rubric File</b></td><td>{esc(rubric_path) if rubric_path else '-'}</td></tr>
  </table>
  <h4>Artifact</h4>
  <div class="mono">{esc(artifact_text) if artifact_text else '(artifact not recorded)'}</div>
  <div class="small muted">Path: {esc(artifact_path) if artifact_path else '-'}{(' · Seed: ' + esc(rand_seed)) if rand_seed is not None else ''}</div>
  <h4>Prompt</h4>
  <div class="mono">{esc(prompt_text)}</div>
  <h4>Results</h4>
  <table class="small">
    <tr><th>Model</th><th>Judge</th><th>Answer</th></tr>
    {''.join(blocks)}
  </table>
</body>
</html>
"""
        out_path.write_text(html_out, encoding="utf-8")


def write_markdown(path: Path, recs: List[Dict[str, Any]]):
    per_model, _, _ = aggregates(recs)
    models = sorted(per_model.keys())
    lines = ["# AMS Oral Bench Report", "", "## Models"]
    # Judge-only rendering
    lines.append("Model | n | Judge")
    lines.append(":--|--:|--:")
    for m in models:
        a = per_model[m]
        judge_avg = a["judge_sum"] / a["judge_n"] if a["judge_n"] else None
        lines.append(f"{m} | {a['n']} | {('-' if judge_avg is None else f'{judge_avg:.3f}')}")
    path.write_text("\n".join(lines), encoding="utf-8")


def generate_report(results_path: str | Path) -> Path:
    """Generate HTML+CSV+MD report next to the given results jsonl.
    Returns the path to index.html.
    """
    res_path = Path(results_path)
    recs = load_results(res_path)
    if not recs:
        raise SystemExit(f"No records found in {res_path}")

    # Allow passing per-model file; still render index with what we have
    run_dir = res_path.parent.resolve()
    report_dir = run_dir / "report"
    ensure_dir(report_dir)
    ensure_dir(report_dir / "items")

    # CSV and MD
    write_csv(report_dir / "results.csv", recs)
    write_markdown(report_dir / "report.md", recs)

    # HTML
    index_path = report_dir / "index.html"
    render_index(index_path, recs)
    render_item_pages(report_dir, recs)
    return index_path


def _read_latest_target(outputs_root: Path) -> tuple[str | None, Path | None]:
    latest = outputs_root / "latest"
    # If symlink, resolve to name
    try:
        if latest.is_symlink():
            target = os.readlink(latest)
            name = Path(target).name
            return name, outputs_root / name
    except Exception:
        pass
    # Fallback via latest_run.txt
    txt = outputs_root / "latest_run.txt"
    try:
        if txt.exists():
            p = Path(txt.read_text().strip())
            if p.exists():
                return p.name, p
    except Exception:
        pass
    return None, None


def generate_outputs_index(outputs_root: str | Path) -> Path:
    root = Path(outputs_root)
    runs = [p for p in root.iterdir() if p.is_dir() and p.name.startswith("run_")]
    runs.sort(key=lambda p: p.name, reverse=True)
    latest_name, latest_path = _read_latest_target(root)

    css = """
    body { font-family: Arial, sans-serif; font-size: 13px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 4px 6px; }
    th { background: #f5f5f5; }
    .small { font-size: 12px; }
    a { color: #0366d6; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .muted { color: #666; }
    """

    rows = []
    for r in runs:
        rid = r.name
        report = r / "report" / "index.html"
        combined = r / "combined_results.jsonl"
        rows.append(
            f"<tr><td>{esc(rid)}</td>"
            f"<td><a href='{esc(rid)}/report/index.html'>{'report' if report.exists() else '<span class=muted>report</span>'}</a></td>"
            f"<td><a href='{esc(rid)}/combined_results.jsonl'>{'results' if combined.exists() else '<span class=muted>results</span>'}</a></td></tr>"
        )

    latest_html = "<span class=muted>unknown</span>"
    if latest_name:
        latest_html = (
            f"<b>{esc(latest_name)}</b> → "
            f"<a href='latest/report/index.html'>latest report</a> · "
            f"<a href='latest/results.jsonl'>latest results</a>"
        )

    html_out = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset='utf-8'/>
  <title>Outputs Index</title>
  <style>{css}</style>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
<body>
  <h2>Runs</h2>
  <p>Latest: {latest_html}</p>
  <table class=small>
    <tr><th>Run</th><th>Report</th><th>Combined Results</th></tr>
    {''.join(rows)}
  </table>
</body>
</html>
"""
    idx = root / "index.html"
    idx.write_text(html_out, encoding="utf-8")
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="?", help="Path to combined_results.jsonl or per-model results.jsonl")
    ap.add_argument("--outputs-index", default=None, help="Generate outputs index.html for the given outputs root directory")
    args = ap.parse_args()

    if args.outputs_index:
        idx = generate_outputs_index(args.outputs_index)
        print(f"Wrote outputs index to {idx}")
        return
    if not args.results:
        raise SystemExit("Provide either RESULTS path or --outputs-index ROOT")
    index = generate_report(args.results)
    print(f"Wrote report to {index}")


if __name__ == "__main__":
    main()
