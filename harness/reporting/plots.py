from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_results(path: Path) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            recs.append(json.loads(line))
        except Exception:
            pass
    return recs


def modality_label(m: str) -> str:
    m = (m or "").strip()
    if m == "spice_netlist":
        return "SPICE"
    if m.lower() == "cascode":
        return "ADL"
    if m.lower() == "casir":
        return "casIR"
    return m or "?"


def aggregate_judge(recs: List[Dict[str, Any]]):
    # Returns dicts keyed by (model, modality, family)
    data: Dict[Tuple[str, str, str], Dict[str, float]] = {}
    for r in recs:
        model = r.get("model", "?")
        modal = modality_label(r.get("modality", "?"))
        fam = r.get("topic") or r.get("family", "?")
        j = r.get("judge") or {}
        if not isinstance(j.get("overall"), (int, float)):
            continue
        key = (model, modal, fam)
        d = data.setdefault(key, {"sum": 0.0, "n": 0.0})
        d["sum"] += float(j["overall"])
        d["n"] += 1.0
    return data


def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def plot_grouped_bars(data: Dict[Tuple[str, str, str], Dict[str, float]], out_dir: Path, families: List[str] | None = None):
    try:
        import matplotlib.pyplot as plt  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        print("matplotlib/numpy not available; install to generate plots: pip install matplotlib numpy")
        return []
    # Build sets
    models = sorted({k[0] for k in data.keys()})
    modalities = sorted({k[1] for k in data.keys()})
    fams = sorted({k[2] for k in data.keys()})
    if families:
        fams = [f for f in fams if f in families]
    paths = []
    for fam in fams:
        fig, ax = plt.subplots(figsize=(max(6, 1.8 * len(models)), 3.2))
        x = np.arange(len(models))
        width = 0.75 / max(1, len(modalities))
        for i, mod in enumerate(modalities):
            ys = []
            for m in models:
                d = data.get((m, mod, fam))
                avg = (d["sum"] / d["n"]) if d and d["n"] else np.nan
                ys.append(avg)
            ax.bar(x + i * width, ys, width=width, label=mod)
        ax.set_xticks(x + (len(modalities) - 1) * width / 2)
        ax.set_xticklabels(models, rotation=30, ha='right')
        ax.set_ylim(0, 1.0)
        ax.set_ylabel("Judge score")
        ax.set_title(f"{fam}: models × modality (judge avg)")
        ax.legend(ncol=min(4, len(modalities)))
        _ensure_dir(out_dir)
        path = out_dir / f"grouped_bar_{fam.replace('/', '_')}.png"
        fig.tight_layout()
        fig.savefig(path, dpi=200)
        plt.close(fig)
        paths.append(path)
    return paths


def plot_heatmap_overall(data: Dict[Tuple[str, str, str], Dict[str, float]], out_dir: Path):
    try:
        import matplotlib.pyplot as plt  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        print("matplotlib/numpy not available; install to generate plots: pip install matplotlib numpy")
        return None
    # Aggregate across families to a (model, modality) matrix
    mm: Dict[Tuple[str, str], Dict[str, float]] = {}
    for (model, mod, fam), d in data.items():
        key = (model, mod)
        x = mm.setdefault(key, {"sum": 0.0, "n": 0.0})
        x["sum"] += d["sum"]
        x["n"] += d["n"]
    models = sorted({k[0] for k in mm.keys()})
    modalities = sorted({k[1] for k in mm.keys()})
    mat = np.zeros((len(models), len(modalities)))
    mat[:] = np.nan
    for i, m in enumerate(models):
        for j, mod in enumerate(modalities):
            d = mm.get((m, mod))
            if d and d["n"]:
                mat[i, j] = d["sum"] / d["n"]
    fig, ax = plt.subplots(figsize=(1.5 * len(modalities) + 2, 0.5 * len(models) + 2.5))
    im = ax.imshow(mat, vmin=0, vmax=1, cmap='viridis')
    ax.set_xticks(range(len(modalities)))
    ax.set_xticklabels(modalities, rotation=30, ha='right')
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(models)
    ax.set_title("Judge score heatmap (model × modality)")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Judge score")
    fig.tight_layout()
    _ensure_dir(out_dir)
    path = out_dir / "heatmap_model_modality.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", help="Path to combined_results.jsonl")
    ap.add_argument("--out-dir", default=None, help="Directory to write plots (default: alongside results)")
    ap.add_argument("--families", nargs="*", default=None, help="Optional subset of families to plot")
    args = ap.parse_args()
    res_path = Path(args.results)
    recs = load_results(res_path)
    if not recs:
        raise SystemExit(f"No records found in {res_path}")
    data = aggregate_judge(recs)
    out_dir = Path(args.out_dir) if args.out_dir else (res_path.parent / "plots")
    _ensure_dir(out_dir)
    heat = plot_heatmap_overall(data, out_dir)
    bars = plot_grouped_bars(data, out_dir, families=args.families)
    print("Wrote:")
    if heat:
        print(f"  {heat}")
    for p in bars:
        print(f"  {p}")


if __name__ == "__main__":
    main()

