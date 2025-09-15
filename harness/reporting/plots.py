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


def plot_grouped_bars(
    data: Dict[Tuple[str, str, str], Dict[str, float]],
    out_dir: Path,
    families: List[str] | None = None,
    silent: bool = False,
):
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
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            fig.savefig(path, dpi=200)
        except Exception as e:
            print(f"[plots] Failed to save {path}: {e}")
        if silent:
            plt.close(fig)
        else:
            try:
                plt.show(block=False)
            except Exception:
                pass
        paths.append(path)
    return paths


def plot_heatmap_overall(
    data: Dict[Tuple[str, str, str], Dict[str, float]],
    out_dir: Path,
    silent: bool = False,
):
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
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        fig.savefig(path, dpi=200)
    except Exception as e:
        print(f"[plots] Failed to save {path}: {e}")
    if silent:
        plt.close(fig)
    else:
        try:
            plt.show(block=False)
        except Exception:
            pass
    return path


def _find_latest_results() -> Path | None:
    # Prefer outputs/latest/results.jsonl if available
    latest = Path("outputs/latest/results.jsonl")
    if latest.exists():
        return latest
    # Fallback: try outputs/latest symlink to run dir
    latest_dir = Path("outputs/latest")
    if latest_dir.is_dir():
        p = latest_dir / "combined_results.jsonl"
        if p.exists():
            return p
    # Fallback: scan outputs/run_* for latest modified combined_results.jsonl
    root = Path("outputs")
    if root.exists():
        cands = sorted(root.glob("run_*/combined_results.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if cands:
            return cands[0]
    return None


def main():
    ap = argparse.ArgumentParser(description="Generate plots from combined_results.jsonl. If no path is provided, uses outputs/latest.")
    ap.add_argument("results", nargs="?", help="Path to combined_results.jsonl (default: outputs/latest/results.jsonl)")
    ap.add_argument("--out-dir", default=None, help="Directory to write plots (default: alongside results)")
    ap.add_argument("--families", nargs="*", default=None, help="Optional subset of families to plot (e.g., analysis/ota)")
    ap.add_argument("--silent", action="store_true", help="Do not open interactive windows; only write files")
    args = ap.parse_args()
    res_path = Path(args.results) if args.results else (_find_latest_results() or Path("outputs/latest/results.jsonl"))
    if not res_path.exists():
        raise SystemExit(f"Results not found: {res_path}. Provide a path or run an eval first.")
    recs = load_results(res_path)
    if not recs:
        raise SystemExit(f"No records found in {res_path}")
    print(f"[plots] Using results: {res_path}")
    data = aggregate_judge(recs)
    out_dir = Path(args.out_dir) if args.out_dir else (res_path.parent / "plots")
    _ensure_dir(out_dir)
    heat = plot_heatmap_overall(data, out_dir, silent=args.silent)
    bars = plot_grouped_bars(data, out_dir, families=args.families, silent=args.silent)
    print("Wrote:")
    if heat:
        print(f"  {heat}")
    for p in bars:
        print(f"  {p}")
    # If not silent, bring figures to front / block once at end
    if not args.silent:
        try:
            import matplotlib.pyplot as plt  # type: ignore
            plt.show()
        except Exception:
            pass


if __name__ == "__main__":
    main()

