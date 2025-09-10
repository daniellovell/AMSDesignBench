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
    per_family = defaultdict(lambda: defaultdict(lambda: {"n": 0, "raw_sum": 0.0}))
    per_modality = defaultdict(lambda: defaultdict(lambda: {"n": 0, "raw_sum": 0.0}))

    for r in recs:
        m = r.get("model", "unknown")
        fam = r.get("family", "?")
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
        per_modality[mod][m]["n"] += 1
        per_modality[mod][m]["raw_sum"] += raw

    return per_model, per_family, per_modality


def write_csv(path: Path, recs: List[Dict[str, Any]]):
    fields = [
        "model", "family", "item_id", "question_id", "rubric_id", "modality", "split",
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
        key = (r.get("family", "?"), r.get("item_id", "?"), r.get("question_id", "?"))
        groups[key][r.get("model", "unknown")] = r

    def model_header_cells():
        return "".join(f"<th class=rot>{esc(m)}</th>" for m in models)

    def model_score_cells(key):
        cells = []
        recs_by_model = groups.get(key, {})
        for m in models:
            r = recs_by_model.get(m)
            raw = float(r.get("scores", {}).get("raw", 0.0)) if r else None
            color = color_for_score(raw)
            disp = f"{raw:.2f}" if raw is not None else "-"
            cells.append(f"<td style=\"background:{color}\">{esc(disp)}</td>")
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

    # Leaderboard
    leader_rows = []
    for m in models:
        a = per_model[m]
        n = max(a["n"], 1)
        pass_rate = a["pass"] / n * 100.0
        raw_avg = a["raw_sum"] / n
        judge_avg = a["judge_sum"] / a["judge_n"] if a["judge_n"] else None
        blended_avg = a["blended_sum"] / a["blended_n"] if a["blended_n"] else None
        row = f"<tr><td>{esc(m)}</td><td>{a['n']}</td><td>{pass_rate:.1f}%</td><td>{raw_avg:.3f}</td>"
        row += f"<td>{judge_avg:.3f}</td>" if judge_avg is not None else "<td>-</td>"
        row += f"<td>{blended_avg:.3f}</td>" if blended_avg is not None else "<td>-</td>"
        leader_rows.append(row + "</tr>")

    # Per-question table
    qrows = []
    for key in sorted(groups.keys()):
        fam, item_id, qid = key
        rec_any = next(iter(groups[key].values()))
        mod = rec_any.get("modality", "?")
        rub = rec_any.get("rubric_id", "?")
        item_rel = f"items/{esc(fam)}/{esc(item_id)}_{esc(qid)}.html"
        row = f"<tr><td><a href='{item_rel}'>{esc(fam)}/{esc(item_id)}</a></td><td>{esc(qid)}</td><td>{esc(mod)}</td><td>{esc(rub)}</td>"
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
        <tr><th>Model</th><th>n</th><th>Pass</th><th>Raw</th><th>Judge</th><th>Blended</th></tr>
        {''.join(leader_rows)}
      </table>
    </div>
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
    <tr><th>Item</th><th>QID</th><th>Modality</th><th>Rubric</th>{model_header_cells()}</tr>
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
        rubric_id = any_rec.get("rubric_id", "?")

        # Build per-model blocks
        blocks = []
        for m in models:
            r = by_model.get(m)
            if not r:
                continue
            scores = r.get("scores", {})
            raw = scores.get("raw")
            passed = scores.get("pass")
            hallu = (scores.get("hallucination") or {}).get("penalty")
            judge = r.get("judge") or {}
            judge_overall = judge.get("overall")
            per = scores.get("per_criterion") or {}
            # per-criterion rows
            prows = []
            for cid, v in per.items():
                if isinstance(v, dict):
                    sc = v.get("score")
                    g = v.get("groundedness") or {}
                    gratio = g.get("ratio") if isinstance(g.get("ratio"), (int, float)) else None
                    bg = color_for_score(sc if isinstance(sc, (int, float)) else None)
                    sc_str = f"{sc:.2f}" if isinstance(sc, (int, float)) else "-"
                    gr_str = f"{gratio:.2f}" if isinstance(gratio, (int, float)) else "-"
                    prows.append(f"<tr><td>{esc(cid)}</td><td style=\"background:{bg}\" class=score>{esc(sc_str)}</td><td>{esc(gr_str)}</td></tr>")
            percrit_html = "<table class=small><tr><th>Criterion</th><th>Score</th><th>Gnd.</th></tr>" + "".join(prows) + "</table>"

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

            answer = r.get("answer", "")
            answer_html = f"<details><summary>View answer</summary><div class=mono>{esc(answer)}</div></details>"
            raw_str = f"{float(raw):.3f}" if isinstance(raw, (int, float)) else "-"
            pass_str = " ✅" if passed else ""
            hallu_str = f"{float(hallu):.2f}" if isinstance(hallu, (int, float)) else "-"
            blocks.append(
                f"<tr><td>{esc(m)}</td><td>{raw_str}{pass_str}</td>"
                f"<td>{hallu_str}</td><td>{percrit_html}</td><td>{judge_html}</td><td>{answer_html}</td></tr>"
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
    <tr><td><b>Modality</b></td><td>{esc(modality)}</td><td><b>Rubric</b></td><td>{esc(rubric_id)}</td></tr>
  </table>
  <h4>Prompt</h4>
  <div class="mono">{esc(prompt_text)}</div>
  <h4>Results</h4>
  <table class="small">
    <tr><th>Model</th><th>Raw</th><th>Halluc. Pen.</th><th>Per-criterion</th><th>Judge</th><th>Answer</th></tr>
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
    lines.append("Model | n | Pass% | Raw | Judge | Blended")
    lines.append(":--|--:|--:|--:|--:|--:")
    for m in models:
        a = per_model[m]
        n = max(a["n"], 1)
        pass_rate = a["pass"] / n * 100.0
        raw_avg = a["raw_sum"] / n
        judge_avg = a["judge_sum"] / a["judge_n"] if a["judge_n"] else None
        blended_avg = a["blended_sum"] / a["blended_n"] if a["blended_n"] else None
        lines.append(f"{m} | {a['n']} | {pass_rate:.1f}% | {raw_avg:.3f} | {('-' if judge_avg is None else f'{judge_avg:.3f}')} | {('-' if blended_avg is None else f'{blended_avg:.3f}')}")
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
