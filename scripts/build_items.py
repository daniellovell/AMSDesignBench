from __future__ import annotations
"""Parametric item generation (v0 stub).

This script demonstrates how to create new items by copying templates and
randomizing IDs/labels. In v0 it prints guidance only.
"""

from pathlib import Path
from rich import print


def main():
    print("[yellow]build_items.py[/yellow]: v0 stub — add topology generators here.")
    print("Guidance:")
    print("- Author inventory.json as the source of truth (elements, nets, blocks).")
    print("- Derive artifacts in-place: netlist.sp (and optionally veriloga.va, netlist.cas, netlist.cir).")
    print("- Set meta.json.modalities to include modalities you provide (e.g., spice_netlist, veriloga, cascode, casIR). Or leave auto and rely on file detection.")
    print("- Keep questions.jsonl minimal (use modality=\"auto\"; the harness expands per modality).")


if __name__ == "__main__":
    main()
