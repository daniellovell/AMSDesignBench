from __future__ import annotations
import argparse
import json
import os
import sys
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
        return "Cascode ADL"
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


def _sort_modalities(modalities: List[str]) -> List[str]:
    """
    Sort modalities in consistent order: SPICE -> CasIR -> Cascode ADL.
    Any other modalities are appended at the end.
    """
    order = ["SPICE", "casIR", "Cascode ADL"]
    ordered = []
    remaining = set(modalities)
    
    # Add in specified order
    for mod in order:
        if mod in remaining:
            ordered.append(mod)
            remaining.remove(mod)
    
    # Add any remaining modalities in sorted order
    ordered.extend(sorted(remaining))
    return ordered


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
    modalities = _sort_modalities(list({k[1] for k in data.keys()}))
    fams = sorted({k[2] for k in data.keys()})
    if families:
        fams = [f for f in fams if f in families]
    
    paths = []
    for fam in fams:
        # Determine which modalities actually have data for this specific family
        fam_modalities_set = set()
        for (model, mod, fam_key) in data.keys():
            if fam_key == fam:
                fam_modalities_set.add(mod)
        
        # Sort modalities in consistent order, but only include those with data for this family
        fam_modalities = _sort_modalities(list(fam_modalities_set))
        
        if not fam_modalities:
            print(f"[plots] Skipping {fam}: no modality data found")
            continue
        
        fig, ax = plt.subplots(figsize=(max(6, 1.8 * len(models)), 3.2))
        x = np.arange(len(models))
        width = 0.75 / max(1, len(fam_modalities))
        
        for i, mod in enumerate(fam_modalities):
            ys = []
            for m in models:
                d = data.get((m, mod, fam))
                avg = (d["sum"] / d["n"]) if d and d["n"] else np.nan
                ys.append(avg)
            ax.bar(x + i * width, ys, width=width, label=mod)
        ax.set_xticks(x + (len(fam_modalities) - 1) * width / 2)
        ax.set_xticklabels(models, rotation=30, ha='right')
        ax.set_ylim(0, 1.0)
        ax.set_ylabel("Judge score")
        ax.set_title(f"{fam}: models × modality (judge avg)")
        ax.legend(ncol=min(4, len(fam_modalities)))
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
                import matplotlib
                backend = str(matplotlib.get_backend()).lower()
                can_gui = ("agg" not in backend)
                if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
                    can_gui = False
                if can_gui:
                    plt.show(block=False)
                else:
                    print(f"[plots] Non-interactive backend '{backend}'; skipping GUI display for grouped bars.")
            except Exception:
                pass
        paths.append(path)
    return paths


def plot_top_family_breakdowns(
    data: Dict[Tuple[str, str, str], Dict[str, float]],
    out_dir: Path,
    silent: bool = False,
):
    """
    Create breakdown plots for top-level families (analysis, debugging, design).
    Each plot shows models × modalities with consistent styling matching the OTA plot.
    """
    try:
        import matplotlib.pyplot as plt  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        print("matplotlib/numpy not available; install to generate plots: pip install matplotlib numpy")
        return []
    
    # Extract top-level families from topic strings (e.g., "analysis/ota" -> "analysis")
    def get_top_family(fam: str) -> str:
        if "/" in fam:
            return fam.split("/")[0]
        return fam
    
    # Aggregate data by (model, modality, top_family)
    top_fam_data: Dict[Tuple[str, str, str], Dict[str, float]] = {}
    for (model, mod, fam), d in data.items():
        top_fam = get_top_family(fam)
        key = (model, mod, top_fam)
        if key not in top_fam_data:
            top_fam_data[key] = {"sum": 0.0, "n": 0.0}
        top_fam_data[key]["sum"] += d["sum"]
        top_fam_data[key]["n"] += d["n"]
    
    # Build sets
    models = sorted({k[0] for k in top_fam_data.keys()})
    modalities = _sort_modalities(list({k[1] for k in top_fam_data.keys()}))
    top_fams = sorted({k[2] for k in top_fam_data.keys()})
    
    # Filter to only the main families: analysis, debugging, design
    main_families = ["analysis", "debugging", "design"]
    top_fams = [f for f in top_fams if f in main_families]
    
    if not top_fams:
        print("[plots] No top-level family data found; skipping breakdown plots.")
        return []
    
    # Define color scheme matching the attached plot: Blue=SPICE, Orange=casIR, Yellow=Cascode ADL
    modality_colors = {
        "SPICE": "#1f77b4",  # Blue
        "casIR": "#ff7f0e",  # Orange
        "Cascode ADL": "#d4af37",  # Gold/Yellow
    }
    
    paths = []
    for fam in top_fams:
        fig, ax = plt.subplots(figsize=(max(8, 1.8 * len(models)), 4.5))
        x = np.arange(len(models))
        width = 0.75 / max(1, len(modalities))
        
        for i, mod in enumerate(modalities):
            ys = []
            for m in models:
                d = top_fam_data.get((m, mod, fam))
                avg = (d["sum"] / d["n"]) if d and d["n"] else np.nan
                ys.append(avg)
            
            color = modality_colors.get(mod, None)
            bars = ax.bar(x + i * width, ys, width=width, label=mod, color=color)
            
            # Add value labels on top of bars
            for bar, y_val in zip(bars, ys):
                if not np.isnan(y_val):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width() / 2., height,
                           f'{y_val:.2f}',
                           ha='center', va='bottom', fontsize=9)
        
        ax.set_xticks(x + (len(modalities) - 1) * width / 2)
        ax.set_xticklabels(models, rotation=30, ha='right')
        ax.set_ylim(0, 1.05)  # Extended to 1.05 to prevent label clipping
        ax.set_ylabel("Judge score", fontsize=11)
        # Title format matching the attached plot
        ax.set_title(f"AMSDesignBench: {fam.capitalize()} Evaluation", fontsize=13, fontweight='bold')
        ax.legend(ncol=min(3, len(modalities)), loc='upper left', framealpha=0.9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        _ensure_dir(out_dir)
        path = out_dir / f"breakdown_{fam}.png"
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
                import matplotlib
                backend = str(matplotlib.get_backend()).lower()
                can_gui = ("agg" not in backend)
                if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
                    can_gui = False
                if can_gui:
                    plt.show(block=False)
                else:
                    print(f"[plots] Non-interactive backend '{backend}'; skipping GUI display for breakdown plots.")
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
    modalities = _sort_modalities(list({k[1] for k in mm.keys()}))
    mat = np.zeros((len(models), len(modalities)))
    mat[:] = np.nan
    for i, m in enumerate(models):
        for j, mod in enumerate(modalities):
            d = mm.get((m, mod))
            if d and d["n"]:
                mat[i, j] = d["sum"] / d["n"]
    fig, ax = plt.subplots(figsize=(1.5 * len(modalities) + 2, 0.5 * len(models) + 2.5))
    im = ax.imshow(mat, vmin=0, vmax=1, cmap='RdYlGn')
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
            import matplotlib
            backend = str(matplotlib.get_backend()).lower()
            can_gui = ("agg" not in backend)
            if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
                can_gui = False
            if can_gui:
                plt.show(block=False)
            else:
                print(f"[plots] Non-interactive backend '{backend}'; skipping GUI display for heatmap.")
        except Exception:
            pass
    return path


def plot_modality_by_top_families(
    data: Dict[Tuple[str, str, str], Dict[str, float]],
    out_dir: Path,
    silent: bool = False,
):
    """
    Figures 1-3: One chart per modality showing performance across models and across ALL top-level families.
    Each chart shows models × families (analysis, debugging, design) for a specific modality.
    """
    try:
        import matplotlib.pyplot as plt  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        print("matplotlib/numpy not available; install to generate plots: pip install matplotlib numpy")
        return []
    
    # Extract top-level families from topic strings (e.g., "analysis/ota" -> "analysis")
    def get_top_family(fam: str) -> str:
        if "/" in fam:
            return fam.split("/")[0]
        return fam
    
    # Aggregate data by (model, modality, top_family)
    top_fam_data: Dict[Tuple[str, str, str], Dict[str, float]] = {}
    for (model, mod, fam), d in data.items():
        top_fam = get_top_family(fam)
        key = (model, mod, top_fam)
        if key not in top_fam_data:
            top_fam_data[key] = {"sum": 0.0, "n": 0.0}
        top_fam_data[key]["sum"] += d["sum"]
        top_fam_data[key]["n"] += d["n"]
    
    # Build sets
    models = sorted({k[0] for k in top_fam_data.keys()})
    modalities = _sort_modalities(list({k[1] for k in top_fam_data.keys()}))
    top_fams = sorted({k[2] for k in top_fam_data.keys()})
    
    paths = []
    for mod in modalities:
        fig, ax = plt.subplots(figsize=(max(6, 1.8 * len(models)), 3.2))
        x = np.arange(len(models))
        width = 0.75 / max(1, len(top_fams))
        for i, fam in enumerate(top_fams):
            ys = []
            for m in models:
                d = top_fam_data.get((m, mod, fam))
                avg = (d["sum"] / d["n"]) if d and d["n"] else np.nan
                ys.append(avg)
            ax.bar(x + i * width, ys, width=width, label=fam)
        ax.set_xticks(x + (len(top_fams) - 1) * width / 2)
        ax.set_xticklabels(models, rotation=30, ha='right')
        ax.set_ylim(0, 1.0)
        ax.set_ylabel("Judge score")
        ax.set_title(f"{mod}: models × families (judge avg)")
        ax.legend(ncol=min(4, len(top_fams)))
        _ensure_dir(out_dir)
        path = out_dir / f"modality_{mod.replace('/', '_')}_by_top_families.png"
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
                import matplotlib
                backend = str(matplotlib.get_backend()).lower()
                can_gui = ("agg" not in backend)
                if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
                    can_gui = False
                if can_gui:
                    plt.show(block=False)
                else:
                    print(f"[plots] Non-interactive backend '{backend}'; skipping GUI display for modality by top families.")
            except Exception:
                pass
        paths.append(path)
    return paths


def plot_modality_by_analysis_subfamilies(
    data: Dict[Tuple[str, str, str], Dict[str, float]],
    out_dir: Path,
    silent: bool = False,
):
    """
    Figures 4-6: One chart per modality showing performance across models and across ALL analysis subfamilies.
    Each chart shows models × analysis subfamilies (analysis/ota, analysis/filters, analysis/feedback) for a specific modality.
    """
    try:
        import matplotlib.pyplot as plt  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        print("matplotlib/numpy not available; install to generate plots: pip install matplotlib numpy")
        return []
    
    # Filter to only analysis subfamilies (topics starting with "analysis/")
    analysis_data: Dict[Tuple[str, str, str], Dict[str, float]] = {}
    for (model, mod, fam), d in data.items():
        if fam.startswith("analysis/"):
            key = (model, mod, fam)
            analysis_data[key] = d
    
    if not analysis_data:
        print("[plots] No analysis subfamily data found; skipping analysis subfamily plots.")
        return []
    
    # Build sets
    models = sorted({k[0] for k in analysis_data.keys()})
    modalities = _sort_modalities(list({k[1] for k in analysis_data.keys()}))
    
    # Expected analysis subfamilies - always include all, even if no data
    expected_subfams = ["analysis/ota", "analysis/filters", "analysis/feedback"]
    found_subfams = sorted({k[2] for k in analysis_data.keys()})
    # Use found subfamilies, but ensure expected ones are included
    analysis_subfams = sorted(set(expected_subfams + found_subfams))
    
    # Extract subfamily names (e.g., "analysis/ota" -> "ota")
    subfam_labels = {sf: sf.split("/")[-1] if "/" in sf else sf for sf in analysis_subfams}
    
    paths = []
    for mod in modalities:
        fig, ax = plt.subplots(figsize=(max(6, 1.8 * len(models)), 3.2))
        x = np.arange(len(models))
        width = 0.75 / max(1, len(analysis_subfams))
        for i, subfam in enumerate(analysis_subfams):
            ys = []
            for m in models:
                d = analysis_data.get((m, mod, subfam))
                avg = (d["sum"] / d["n"]) if d and d["n"] else np.nan
                ys.append(avg)
            label = subfam_labels[subfam]
            ax.bar(x + i * width, ys, width=width, label=label)
        ax.set_xticks(x + (len(analysis_subfams) - 1) * width / 2)
        ax.set_xticklabels(models, rotation=30, ha='right')
        ax.set_ylim(0, 1.0)
        ax.set_ylabel("Judge score")
        ax.set_title(f"{mod}: models × analysis subfamilies (judge avg)")
        ax.legend(ncol=min(4, len(analysis_subfams)))
        _ensure_dir(out_dir)
        path = out_dir / f"modality_{mod.replace('/', '_')}_by_analysis_subfamilies.png"
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
                import matplotlib
                backend = str(matplotlib.get_backend()).lower()
                can_gui = ("agg" not in backend)
                if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
                    can_gui = False
                if can_gui:
                    plt.show(block=False)
                else:
                    print(f"[plots] Non-interactive backend '{backend}'; skipping GUI display for modality by analysis subfamilies.")
            except Exception:
                pass
        paths.append(path)
    return paths


def plot_family_modality_aggregated(
    data: Dict[Tuple[str, str, str], Dict[str, float]],
    out_dir: Path,
    silent: bool = False,
):
    """
    Bar chart showing aggregate performance across ALL models for each (family, modality) combination.
    X-axis: families, grouped bars: modalities.
    Answers: Do all models perform better with Cascode ADL and CasIR than SPICE?
    """
    try:
        import matplotlib.pyplot as plt  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        print("matplotlib/numpy not available; install to generate plots: pip install matplotlib numpy")
        return None
    
    # Extract top-level families from topic strings (e.g., "analysis/ota" -> "analysis")
    def get_top_family(fam: str) -> str:
        if "/" in fam:
            return fam.split("/")[0]
        return fam
    
    # Aggregate across all models to (modality, top_family) matrix
    fm: Dict[Tuple[str, str], Dict[str, float]] = {}
    for (model, mod, fam), d in data.items():
        top_fam = get_top_family(fam)
        key = (mod, top_fam)
        x = fm.setdefault(key, {"sum": 0.0, "n": 0.0})
        x["sum"] += d["sum"]
        x["n"] += d["n"]
    
    modalities = _sort_modalities(list({k[0] for k in fm.keys()}))
    families = sorted({k[1] for k in fm.keys()})
    
    # Use RdYlGn colormap to match heatmap colors
    cmap = plt.get_cmap('RdYlGn')
    # Get colors for modalities (red=low, green=high, but we want consistent colors per modality)
    # Use a consistent color scheme: SPICE=reddish, Cascode ADL=greenish, casIR=yellowish-green
    modality_colors = {}
    if len(modalities) == 3:
        # Map to RdYlGn colors: SPICE (low performance expected) = red, Cascode ADL = green, casIR = yellow-green
        modality_colors = {
            "SPICE": cmap(0.0),  # Red
            "Cascode ADL": cmap(1.0),  # Green
            "casIR": cmap(0.6),  # Yellow-green
        }
    else:
        # Fallback: use colormap evenly distributed
        for i, mod in enumerate(modalities):
            modality_colors[mod] = cmap(i / max(1, len(modalities) - 1))
    
    fig, ax = plt.subplots(figsize=(max(6, 1.5 * len(families)), 4.0))
    x = np.arange(len(families))
    width = 0.75 / max(1, len(modalities))
    
    for i, mod in enumerate(modalities):
        ys = []
        for fam in families:
            d = fm.get((mod, fam))
            avg = (d["sum"] / d["n"]) if d and d["n"] else np.nan
            ys.append(avg)
        color = modality_colors.get(mod, cmap(i / max(1, len(modalities) - 1)))
        ax.bar(x + i * width, ys, width=width, label=mod, color=color)
    
    ax.set_xticks(x + (len(modalities) - 1) * width / 2)
    ax.set_xticklabels(families, rotation=0, ha='center')
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Judge score (aggregated across all models)")
    ax.set_title("Performance by family × modality (all models aggregated)")
    ax.legend(ncol=min(3, len(modalities)), loc='upper left')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    _ensure_dir(out_dir)
    path = out_dir / "family_modality_aggregated.png"
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
            import matplotlib
            backend = str(matplotlib.get_backend()).lower()
            can_gui = ("agg" not in backend)
            if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
                can_gui = False
            if can_gui:
                plt.show(block=False)
            else:
                print(f"[plots] Non-interactive backend '{backend}'; skipping GUI display for family×modality aggregated bars.")
        except Exception:
            pass
    return path


def _find_latest_results() -> Path | None:
    # Prefer outputs/latest/results.jsonl if available
    latest = Path("outputs/latest/results.jsonl")
    try:
        if latest.exists():
            return latest
    except OSError:
        # Windows may fail to access symlinks
        pass
    # Fallback: try outputs/latest symlink to run dir
    latest_dir = Path("outputs/latest")
    try:
        if latest_dir.is_dir():
            p = latest_dir / "combined_results.jsonl"
            if p.exists():
                return p
    except OSError:
        # Windows may fail to access symlinks
        pass
    # Fallback: scan outputs/run_* for latest modified combined_results.jsonl
    root = Path("outputs")
    try:
        if root.exists():
            cands = sorted(root.glob("run_*/combined_results.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
            if cands:
                return cands[0]
    except OSError:
        pass
    return None


def main():
    ap = argparse.ArgumentParser(description="Generate plots from combined_results.jsonl. If no path is provided, uses outputs/latest.")
    ap.add_argument("results", nargs="?", help="Path to combined_results.jsonl (default: outputs/latest/results.jsonl)")
    ap.add_argument("--out-dir", default=None, help="Directory to write plots (default: alongside results)")
    ap.add_argument("--families", nargs="*", default=None, help="Optional subset of families to plot (e.g., analysis/ota)")
    ap.add_argument("--silent", action="store_true", help="Do not open interactive windows; only write files")
    args = ap.parse_args()
    res_path = Path(args.results) if args.results else (_find_latest_results() or Path("outputs/latest/results.jsonl"))
    try:
        if not res_path.exists():
            raise SystemExit(f"Results not found: {res_path}. Provide a path or run an eval first.")
    except OSError:
        # Windows may fail to access symlinks
        raise SystemExit(f"Cannot access {res_path} (possibly a symlink issue on Windows). Please provide an explicit path: python harness/reporting/plots.py <path_to_results.jsonl>")
    recs = load_results(res_path)
    if not recs:
        raise SystemExit(f"No records found in {res_path}")
    print(f"[plots] Using results: {res_path}")
    data = aggregate_judge(recs)
    out_dir = Path(args.out_dir) if args.out_dir else (res_path.parent / "plots")
    _ensure_dir(out_dir)
    heat = plot_heatmap_overall(data, out_dir, silent=args.silent)
    bars = plot_grouped_bars(data, out_dir, families=args.families, silent=args.silent)
    # Figures 1-3: One chart per modality showing models × top-level families
    mod_top_fams = plot_modality_by_top_families(data, out_dir, silent=args.silent)
    # Figures 4-6: One chart per modality showing models × analysis subfamilies
    mod_analysis_subfams = plot_modality_by_analysis_subfamilies(data, out_dir, silent=args.silent)
    # Aggregated bar chart: all models aggregated by family × modality
    fam_mod_agg = plot_family_modality_aggregated(data, out_dir, silent=args.silent)
    # Breakdown plots for top-level families (analysis, debugging, design)
    breakdowns = plot_top_family_breakdowns(data, out_dir, silent=args.silent)
    print("Wrote:")
    if heat:
        print(f"  {heat}")
    for p in bars:
        print(f"  {p}")
    for p in mod_top_fams:
        print(f"  {p}")
    for p in mod_analysis_subfams:
        print(f"  {p}")
    if fam_mod_agg:
        print(f"  {fam_mod_agg}")
    for p in breakdowns:
        print(f"  {p}")
    # If not silent and GUI-capable, bring figures to front / block once at end
    if not args.silent:
        try:
            import matplotlib
            import matplotlib.pyplot as plt  # type: ignore
            backend = str(matplotlib.get_backend()).lower()
            can_gui = ("agg" not in backend)
            if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
                can_gui = False
            if can_gui:
                plt.show()
            else:
                print(f"[plots] Non-interactive backend '{backend}'; use --silent or set MPLBACKEND to a GUI backend to suppress warnings.")
        except Exception:
            pass


if __name__ == "__main__":
    main()

