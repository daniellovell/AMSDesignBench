#!/usr/bin/env python3
"""
Generate multiple-choice answer keys for all debugging and analysis questions.
Creates mc_answer_key.json files with correct answers and plausible distractors.
"""
import json
import random
import yaml
from pathlib import Path
from typing import Dict, List, Any
import re

# Optional: sympy used to derive transfer functions for opamp-based filters in a netlist-aware way.
# (Listed in requirements.txt; keep import local where used to avoid overhead for other tasks.)


def _read_text_smart(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-16")


def _load_ota_inventory(item_id: str) -> dict:
    inv_path = Path(__file__).parent.parent / "data" / "dev" / "templates" / "ota" / item_id / "inventory.json"
    if not inv_path.exists():
        return {}
    return json.loads(inv_path.read_text(encoding="utf-8"))


def _load_ota_netlist_text(item_id: str) -> str:
    net_path = Path(__file__).parent.parent / "data" / "dev" / "templates" / "ota" / item_id / "netlist.sp"
    if not net_path.exists():
        return ""
    return _read_text_smart(net_path)


def _par(a: str, b: str) -> str:
    return f"({a} || {b})"


def _cascode_stack(ro_casc: str, ro_dev: str, gm_casc: str) -> str:
    # ro_casc + ro_dev + gm_casc*ro_casc*ro_dev
    return f"({ro_casc} + {ro_dev} + {gm_casc}·{ro_casc}·{ro_dev})"


def _ota_role_map_for_analysis(item_id: str) -> Dict[str, str]:
    """
    Map the canonical role names from the user's answer-key (M1a/M1b/... etc) to
    template netlist instance IDs (M*, Mp*, Mtail, etc).
    NOTE: These template IDs will be renamed at runtime via run_eval's instance renamer,
    so the MCQ still shows shuffled instance names.
    """
    # Start with any explicit mappings we can confidently assert from the template netlists.
    if item_id == "ota001":
        return {"M1a": "M2", "M1b": "M1", "M2a": "Mp1", "M2b": "Mp2", "MT": "Mtail", "CL": "Cload"}

    if item_id == "ota002":
        # Branch a = vop, branch b = von in the template.
        return {
            "M1a": "M4", "M1b": "M3",
            "M3a": "M1", "M3b": "M2",
            "M2a": "M9", "M2b": "M8",
            "M4a": "M7", "M4b": "M6",
            "MT": "M5",
            "CLP": "C1", "CLN": "C2",
        }

    # If a mapping isn't defined here yet, fall back to existing generic answer generation.
    return {}


def _ota_canonical_mc_formula(item_id: str, aspect: str) -> str | None:
    """
    Canonical OTA analysis answers, mapped 1:1 to template netlists under data/dev/templates/ota.
    Returned formulas are MC-safe: every instance subscript uses {INSTANCE} so run_eval can
    rename instance names per run while keeping topology fixed.
    """
    # Helper shorthands (MC-safe): use braces so run_eval can rename inside gm_{...}/ro_{...}
    def gm(x: str) -> str:
        return f"gm_{{{x}}}"
    def ro(x: str) -> str:
        return f"ro_{{{x}}}"
    def gam(x: str) -> str:
        return f"γ_{{{x}}}"
    def wl(x: str) -> str:
        return f"(W/L)_{{{x}}}"
    def idc(x: str) -> str:
        return f"I_D,{{{x}}}"

    def _pwr0() -> str:
        eqs = _ota_power_equivalents_mc(item_id)
        if eqs:
            return eqs[0]
        # Fallback: keep previous behavior if we somehow missed a mapping.
        return f"P_q ≈ VDD·{idc('Mtail')}"

    if item_id == "ota001":
        if aspect == "rout":
            return f"rout ≈ {ro('M2')} || {ro('Mp1')}"
        if aspect == "gain_dc":
            return f"|A0| ≈ (({gm('M1')} + {gm('M2')})/2)·({ro('M2')} || {ro('Mp1')})"
        if aspect == "psrr":
            return f"PSRR+ ≈ (({gm('M1')} + {gm('M2')})/2)·{ro('Mp1')}"
        if aspect == "noise_white":
            return (
                f"S_v,out ≈ ({ro('M2')} || {ro('Mp1')})²·4kT·["
                f"{gam('M2')}·{gm('M2')} + {gam('Mp1')}·{gm('Mp1')} + "
                f"(({wl('Mp1')}/{wl('Mp2')})²·{gam('Mp2')}·{gm('Mp2')}) + "
                f"(({gm('M2')}/({gm('M1')}+{gm('M2')}))²·{gam('Mtail')}·{gm('Mtail')})"
                f"]"
            )
        if aspect == "power_quiescent":
            return _pwr0()
        if aspect == "gbw":
            return f"GBW ≈ ({gm('M1')} + {gm('M2')})/(4π·Cload)"

    if item_id == "ota002":
        rbot_n = f"({ro('M2')} + {ro('M3')} + {gm('M2')}·{ro('M2')}·{ro('M3')})"
        rtop_n = f"({ro('M6')} + {ro('M8')} + {gm('M6')}·{ro('M6')}·{ro('M8')})"
        rout_n = f"{rbot_n} || {rtop_n}"
        rbot_p = f"({ro('M1')} + {ro('M4')} + {gm('M1')}·{ro('M1')}·{ro('M4')})"
        rtop_p = f"({ro('M7')} + {ro('M9')} + {gm('M7')}·{ro('M7')}·{ro('M9')})"
        rout_p = f"{rbot_p} || {rtop_p}"
        if aspect == "rout":
            return f"rout ≈ ({rout_p} + {rout_n})/2"
        if aspect == "gain_dc":
            return f"|A0,od| ≈ (1/2)·[{gm('M4')}·({rout_p}) + {gm('M3')}·({rout_n})]"
        if aspect == "psrr":
            voutp_vdd = f"({rbot_p})/(({rtop_p})+({rbot_p}))"
            voutn_vdd = f"({rbot_n})/(({rtop_n})+({rbot_n}))"
            vod_vdd = f"({voutp_vdd}) - ({voutn_vdd})"
            return f"PSRR+_od ≈ |(A0,od)/({vod_vdd})|"
        if aspect == "noise_white":
            return (
                f"S_v,od ≈ ({rout_p})²·4kT·[{gam('M1')}·{gm('M1')}+{gam('M4')}·{gm('M4')}+{gam('M7')}·{gm('M7')}+{gam('M9')}·{gm('M9')}+"
                f"(({gm('M4')}/({gm('M3')}+{gm('M4')}))²·{gam('M5')}·{gm('M5')})]"
                f" + ({rout_n})²·4kT·[{gam('M2')}·{gm('M2')}+{gam('M3')}·{gm('M3')}+{gam('M6')}·{gm('M6')}+{gam('M8')}·{gm('M8')}+"
                f"(({gm('M3')}/({gm('M3')}+{gm('M4')}))²·{gam('M5')}·{gm('M5')})]"
            )
        if aspect == "power_quiescent":
            return _pwr0()
        if aspect == "gbw":
            # Load-dominated, fully-differential: ω_p,od = 2/((rout_p+rout_n)·C1), GBP = |A0,od|·ω_p,od/(2π)
            return f"GBW ≈ |A0,od|·(2/(({rout_p}+{rout_n})·C1))/(2π)"

    if item_id == "ota003":
        if aspect == "rout":
            return f"rout ≈ {ro('M6')} || {ro('M8')}"
        if aspect == "gain_dc":
            k = f"[{wl('M6')}/{wl('M3')} - ({wl('M5')}/{wl('M3')})·({wl('M8')}/{wl('M7')})]"
            return f"|A0| ≈ ({ro('M6')} || {ro('M8')})·{k}·(({gm('M1')}+{gm('M2')})/2)"
        if aspect == "psrr":
            k = f"[{wl('M6')}/{wl('M3')} - ({wl('M5')}/{wl('M3')})·({wl('M8')}/{wl('M7')})]"
            return f"PSRR+ ≈ (({gm('M1')}+{gm('M2')})/2)·{k}·{ro('M6')}"
        if aspect == "noise_white":
            return (
                f"S_v,out ≈ ({ro('M6')} || {ro('M8')})²·4kT·["
                f"{gam('M6')}·{gm('M6')} + {gam('M8')}·{gm('M8')} + "
                f"(({wl('M6')}/{wl('M3')})²·{gam('M3')}·{gm('M3')}) + "
                f"(({wl('M8')}/{wl('M7')})²·{gam('M7')}·{gm('M7')}) + "
                f"(({wl('M5')}/{wl('M3')})²·({wl('M8')}/{wl('M7')})²·{gam('M5')}·{gm('M5')}) + "
                f"(({gm('M1')}/({gm('M1')}+{gm('M2')}))²·{gam('Mtail')}·{gm('Mtail')})"
                f"]"
            )
        if aspect == "power_quiescent":
            return _pwr0()
        if aspect == "gbw":
            # ω_p = 1/(rout·Cload), ω_u = |A0|·ω_p
            return f"GBW ≈ |A0|·(1/(({ro('M6')}||{ro('M8')})·Cload))/(2π)"

    if item_id == "ota004":
        if aspect == "rout":
            return f"rout ≈ {ro('M6')} || {ro('M7')}"
        if aspect == "gain_dc":
            return f"|A0| ≈ (({gm('M1')}+{gm('M2')})/2)·({ro('M2')}||{ro('M4')})·{gm('M6')}·({ro('M6')}||{ro('M7')})"
        if aspect == "psrr":
            return f"PSRR+ ≈ |A0 / ({ro('M6')}/({ro('M6')}+{ro('M7')}) + {gm('M6')}·({ro('M6')}||{ro('M7')})·({ro('M2')}/({ro('M2')}+{ro('M4')})))|"
        if aspect == "noise_white":
            return (
                f"S_v,out ≈ ({ro('M6')}||{ro('M7')})²·4kT·({gam('M6')}·{gm('M6')}+{gam('M7')}·{gm('M7')})"
                f" + [{gm('M6')}·({ro('M6')}||{ro('M7')})]²·({ro('M2')}||{ro('M4')})²·4kT·["
                f"{gam('M2')}·{gm('M2')} + {gam('M4')}·{gm('M4')} + "
                f"(({wl('M4')}/{wl('M3')})²·{gam('M3')}·{gm('M3')}) + "
                f"(({gm('M2')}/({gm('M1')}+{gm('M2')}))²·{gam('M5')}·{gm('M5')})"
                f"]"
            )
        if aspect == "power_quiescent":
            return _pwr0()
        if aspect == "gbw":
            return f"GBW ≈ (({gm('M1')}+{gm('M2')})/2)·({ro('M2')}||{ro('M4')})·{gm('M6')}/(2π·Cload)"

    if item_id == "ota005":
        rbot = f"({ro('M1')}+{ro('M2')}+{gm('M1')}·{ro('M1')}·{ro('M2')})"
        rtop = f"({ro('M10')}+{ro('M6')}+{gm('M10')}·{ro('M10')}·{ro('M6')})"
        if aspect == "rout":
            return f"rout ≈ {rbot} || {rtop}"
        if aspect == "gain_dc":
            return f"|A0| ≈ (({gm('M2')}+{gm('M3')})/2)·({rbot} || {rtop})"
        if aspect == "psrr":
            return f"PSRR+ ≈ (({gm('M2')}+{gm('M3')})/2)·({rtop})"
        if aspect == "noise_white":
            return f"S_v,out ≈ ({rbot}||{rtop})²·4kT·[{gam('M1')}·{gm('M1')}+{gam('M2')}·{gm('M2')}+{gam('M10')}·{gm('M10')}+{gam('M6')}·{gm('M6')}+(({gm('M2')}/({gm('M2')}+{gm('M3')}))²·{gam('M4')}·{gm('M4')})]"
        if aspect == "power_quiescent":
            return _pwr0()
        if aspect == "gbw":
            return f"GBW ≈ ({gm('M2')}+{gm('M3')})/(4π·C1)"

    if item_id == "ota006":
        rbot = f"({ro('M6')}+{ro('M7')}+{gm('M6')}·{ro('M6')}·{ro('M7')})"
        rtop = f"({ro('M1')}+{ro('M2')}+{gm('M1')}·{ro('M1')}·{ro('M2')})"
        if aspect == "rout":
            return f"rout ≈ {rbot} || {rtop}"
        if aspect == "gain_dc":
            return f"|A0| ≈ (({gm('M7')}+{gm('M8')})/2)·({rbot} || {rtop})"
        if aspect == "psrr":
            return f"PSRR+ ≈ (({gm('M7')}+{gm('M8')})/2)·({rtop})"
        if aspect == "noise_white":
            return f"S_v,out ≈ ({rbot}||{rtop})²·4kT·[{gam('M6')}·{gm('M6')}+{gam('M7')}·{gm('M7')}+{gam('M1')}·{gm('M1')}+{gam('M2')}·{gm('M2')}+(({gm('M7')}/({gm('M7')}+{gm('M8')}))²·{gam('M9')}·{gm('M9')})]"
        if aspect == "power_quiescent":
            return _pwr0()
        if aspect == "gbw":
            return f"GBW ≈ ({gm('M7')}+{gm('M8')})/(4π·C1)"

    if item_id == "ota007":
        if aspect == "rout":
            return f"rout ≈ {ro('M2')} || {ro('M1')}"
        if aspect == "gain_dc":
            return f"|A0| ≈ {gm('M2')}·({ro('M2')}||{ro('M1')})"
        if aspect == "psrr":
            return f"PSRR+ ≈ {gm('M2')}·{ro('M1')}"
        if aspect == "noise_white":
            return f"S_v,out ≈ ({ro('M2')}||{ro('M1')})²·4kT·({gam('M2')}·{gm('M2')}+{gam('M1')}·{gm('M1')})"
        if aspect == "power_quiescent":
            return _pwr0()
        if aspect == "gbw":
            return f"GBW ≈ {gm('M2')}/(2π·Cload)"

    if item_id == "ota008":
        rbot = f"({ro('M2')}+{ro('M1')}+{gm('M2')}·{ro('M2')}·{ro('M1')})"
        rtop = f"({ro('M3')}+{ro('M4')}+{gm('M3')}·{ro('M3')}·{ro('M4')})"
        if aspect == "rout":
            return f"rout ≈ {rbot} || {rtop}"
        if aspect == "gain_dc":
            return f"|A0| ≈ {gm('M1')}·({rbot}||{rtop})"
        if aspect == "psrr":
            return f"PSRR+ ≈ {gm('M1')}·({rtop})"
        if aspect == "noise_white":
            return f"S_v,out ≈ ({rbot}||{rtop})²·4kT·({gam('M1')}·{gm('M1')}+{gam('M2')}·{gm('M2')}+{gam('M3')}·{gm('M3')}+{gam('M4')}·{gm('M4')})"
        if aspect == "power_quiescent":
            return _pwr0()
        if aspect == "gbw":
            return f"GBW ≈ {gm('M1')}/(2π·Cload)"

    if item_id == "ota009":
        rbot = f"({ro('M2')}+{ro('M1')}+{gm('M2')}·{ro('M2')}·{ro('M1')})"
        rtop = f"({ro('M3')}+{ro('M4')}+{gm('M3')}·(1+{gm('M7')}·({ro('M7')}||{ro('M6')}))·{ro('M3')}·{ro('M4')})"
        if aspect == "rout":
            return f"rout ≈ {rbot} || {rtop}"
        if aspect == "gain_dc":
            return f"|A0| ≈ {gm('M1')}·({rbot}||{rtop})"
        if aspect == "psrr":
            return f"PSRR+ ≈ {gm('M1')}·({rtop})"
        if aspect == "noise_white":
            return f"S_v,out ≈ ({rbot}||{rtop})²·4kT·[{gam('M1')}·{gm('M1')}+{gam('M2')}·{gm('M2')}+{gam('M3')}·{gm('M3')}+{gam('M4')}·{gm('M4')}+{gam('M6')}·{gm('M6')}+{gam('M7')}·{gm('M7')}+{gam('M5')}·{gm('M5')}+{gam('M8')}·{gm('M8')}]"
        if aspect == "power_quiescent":
            return _pwr0()
        if aspect == "gbw":
            return f"GBW ≈ {gm('M1')}/(2π·Cload)"

    if item_id == "ota010":
        r_outp = f"({ro('M6')}+{ro('M4')}+{gm('M6')}·{ro('M6')}·{ro('M4')}) || ({ro('M10')}+{ro('M11')}+{gm('M10')}·{ro('M10')}·{ro('M11')})"
        r_outn = f"({ro('M7')}+{ro('M5')}+{gm('M7')}·{ro('M7')}·{ro('M5')}) || ({ro('M8')}+{ro('M9')}+{gm('M8')}·{ro('M8')}·{ro('M9')})"
        if aspect == "rout":
            return f"rout ≈ ({r_outp}+{r_outn})/2"
        if aspect == "gain_dc":
            return f"|A0,od| ≈ (1/2)·[{gm('M1')}·({r_outp}) + {gm('M2')}·({r_outn})]"
        if aspect == "psrr":
            # Explicit per-branch dividers (bottom stack / (top+bottom)), then differential subtraction.
            rtop_p = f"({ro('M6')}+{ro('M4')}+{gm('M6')}·{ro('M6')}·{ro('M4')})"
            rbot_p = f"({ro('M10')}+{ro('M11')}+{gm('M10')}·{ro('M10')}·{ro('M11')})"
            rtop_n = f"({ro('M7')}+{ro('M5')}+{gm('M7')}·{ro('M7')}·{ro('M5')})"
            rbot_n = f"({ro('M8')}+{ro('M9')}+{gm('M8')}·{ro('M8')}·{ro('M9')})"
            vop_vdd = f"({rbot_p})/(({rtop_p})+({rbot_p}))"
            von_vdd = f"({rbot_n})/(({rtop_n})+({rbot_n}))"
            vod_vdd = f"({vop_vdd}) - ({von_vdd})"
            return f"PSRR+_od ≈ |(|A0,od|)/({vod_vdd})|"
        if aspect == "noise_white":
            return f"S_v,od ≈ ({r_outp})²·4kT·({gam('M6')}·{gm('M6')}+{gam('M4')}·{gm('M4')}+{gam('M10')}·{gm('M10')}+{gam('M11')}·{gm('M11')}) + ({r_outn})²·4kT·({gam('M7')}·{gm('M7')}+{gam('M5')}·{gm('M5')}+{gam('M8')}·{gm('M8')}+{gam('M9')}·{gm('M9')})"
        if aspect == "power_quiescent":
            return _pwr0()
        if aspect == "gbw":
            return f"GBW ≈ |A0,od|·(2/(({r_outp}+{r_outn})·Cload))/(2π)"

    if item_id == "ota011":
        r_top = f"({ro('M7')}+{ro('M5')}+{gm('M7')}·{ro('M7')}·{ro('M5')})"
        r_bot = f"({ro('M8')}+{ro('M9')}+{gm('M8')}·{ro('M8')}·{ro('M9')})"
        if aspect == "rout":
            return f"rout ≈ ({r_top}) || ({r_bot})"
        if aspect == "gain_dc":
            return f"|A0| ≈ (({gm('M1')}+{gm('M2')})/2)·(({r_top})||({r_bot}))"
        if aspect == "psrr":
            return f"PSRR+ ≈ (({gm('M1')}+{gm('M2')})/2)·({r_top})"
        if aspect == "noise_white":
            return f"S_v,out ≈ (({r_top})||({r_bot}))²·4kT·({gam('M7')}·{gm('M7')}+{gam('M5')}·{gm('M5')}+{gam('M8')}·{gm('M8')}+{gam('M9')}·{gm('M9')})"
        if aspect == "power_quiescent":
            return _pwr0()
        if aspect == "gbw":
            return f"GBW ≈ ({gm('M1')}+{gm('M2')})/(4π·1p)"

    if item_id == "ota012":
        r_top = f"({ro('M7')}+{ro('M5')}+{gm('M7')}·{ro('M7')}·{ro('M5')})"
        r_bot = f"({ro('M8')}+{ro('M9')}+{gm('M8')}·{ro('M8')}·{ro('M9')})"
        if aspect == "rout":
            return f"rout ≈ ({r_top}) || ({r_bot})"
        if aspect == "gain_dc":
            return f"|A0| ≈ (({gm('M1')}+{gm('M2')})/2)·(({r_top})||({r_bot}))"
        if aspect == "psrr":
            return f"PSRR+ ≈ (({gm('M1')}+{gm('M2')})/2)·({r_top})"
        if aspect == "noise_white":
            return f"S_v,out ≈ (({r_top})||({r_bot}))²·4kT·({gam('M7')}·{gm('M7')}+{gam('M5')}·{gm('M5')}+{gam('M8')}·{gm('M8')}+{gam('M9')}·{gm('M9')})"
        if aspect == "power_quiescent":
            return _pwr0()
        if aspect == "gbw":
            return f"GBW ≈ ({gm('M1')}+{gm('M2')})/(4π·1p)"

    return None


def _parse_passives_from_netlist_text(netlist_text: str) -> tuple[set[str], List[str], List[str], List[str]]:
    """
    Parse instance IDs for R/C/L elements from a SPICE netlist text.
    Returns (inst_set, resistors, capacitors, inductors) in first-seen order.
    """
    inst: set[str] = set()
    resistors: List[str] = []
    capacitors: List[str] = []
    inductors: List[str] = []
    for ln in (netlist_text or "").splitlines():
        s = ln.strip()
        if not s or s.startswith(("*", ";", "//", ".")):
            continue
        tok = s.split()[0]
        if not tok:
            continue
        pref = tok[0].upper()
        if pref not in {"R", "C", "L"}:
            continue
        inst.add(tok)
        if pref == "R":
            resistors.append(tok)
        elif pref == "C":
            capacitors.append(tok)
        else:
            inductors.append(tok)
    return inst, resistors, capacitors, inductors


def _apply_symbol_map_tokens(expr: str, sym_map: Dict[str, str]) -> str:
    """Replace whole-token occurrences only (e.g. R1 -> Rin)."""
    if not expr or not sym_map:
        return expr
    for k, v in sym_map.items():
        expr = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(k)}(?![A-Za-z0-9_])", v, expr)
    return expr


def _valid_passive_tokens(expr: str, inst: set[str]) -> bool:
    """Any referenced R*/C*/L* token must exist in inst."""
    # Only match SPICE-style passive instance IDs: R/C/L followed by a digit.
    # Avoid false positives like "Low-side" or symbolic names like "Rtail".
    for m in re.finditer(r"\b([RCL][0-9][A-Za-z0-9_]*)\b", expr or ""):
        name = m.group(1)
        if name not in inst:
            return False
    return True


def _passive_swap_distractors(expr: str, inst: set[str], resistors: List[str], capacitors: List[str], inductors: List[str], limit: int = 8) -> List[str]:
    """
    Generate distractors by swapping one passive component token for another token of the same type
    that exists in the same netlist (e.g. use wrong resistor ID in an otherwise-correct formula).
    """
    if not expr:
        return []
    by_type = {"R": resistors, "C": capacitors, "L": inductors}
    out: List[str] = []
    seen: set[str] = set()
    tokens = list(dict.fromkeys(re.findall(r"\b([RCL][A-Za-z0-9_]+)\b", expr)))
    for tok in tokens:
        t = tok[0].upper()
        alts = [x for x in by_type.get(t, []) if x != tok]
        if not alts:
            continue
        for alt in alts[:3]:
            cand = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(tok)}(?![A-Za-z0-9_])", alt, expr)
            if cand == expr:
                continue
            if not _valid_passive_tokens(cand, inst):
                continue
            if cand in seen:
                continue
            seen.add(cand)
            out.append(cand)
            if len(out) >= limit:
                return out
    return out


def _semantic_choice_key(s: str) -> str:
    """
    Canonicalize a math-ish expression so commutative reorderings don't bypass dedupe.
    Handles +, *, ·, and || as commutative+associative. Everything else is kept ordered.
    """
    if not s:
        return ""
    x = (s or "").strip()
    x = x.replace("·", "*")
    x = x.replace("²", "^2").replace("³", "^3")
    x = re.sub(r"\s+", "", x.lower())

    # Many choices include a "LHS ≈ RHS" label. Canonicalize RHS (math) but keep LHS+op fixed
    # so different questions/aspects don't accidentally collide.
    lhs_prefix = ""
    op = None
    if "≈" in x:
        lhs_prefix, x = x.split("≈", 1)
        op = "≈"
    elif "=" in x:
        lhs_prefix, x = x.split("=", 1)
        op = "="
    if op is not None:
        lhs_prefix = lhs_prefix + op
    # Normalize wrappers we use in formulas but don't tokenize as operators.
    # - Absolute value bars: treat as purely syntactic wrapper for uniqueness purposes.
    # - Brackets: normalize to parentheses.
    x = x.replace("|", "")
    x = x.replace("[", "(").replace("]", ")")

    toks: list[str] = []
    i = 0
    while i < len(x):
        if x.startswith("||", i):
            toks.append("||")
            i += 2
            continue
        ch = x[i]
        if ch in "+-*/()^":
            toks.append(ch)
            i += 1
            continue
        if ch == "√":
            toks.append("sqrt")
            i += 1
            continue
        j = i
        while j < len(x):
            if x.startswith("||", j):
                break
            if x[j] in "+-*/()^":
                break
            j += 1
        toks.append(x[i:j])
        i = j

    pos = 0

    def peek() -> str | None:
        return toks[pos] if pos < len(toks) else None

    def take() -> str:
        nonlocal pos
        t = toks[pos]
        pos += 1
        return t

    def parse_atom():
        t = peek()
        if t is None:
            return ("lit", "")
        if t == "(":
            take()
            node = parse_add()
            if peek() == ")":
                take()
            return node
        return ("lit", take())

    def parse_unary():
        t = peek()
        if t in ("+", "-"):
            op = take()
            return ("un", op, parse_unary())
        if t == "sqrt":
            take()
            if peek() == "(":
                take()
                inner = parse_add()
                if peek() == ")":
                    take()
                return ("fn", "sqrt", inner)
            return ("fn", "sqrt", parse_unary())
        return parse_atom()

    def parse_pow():
        node = parse_unary()
        while peek() == "^":
            take()
            rhs = parse_unary()
            node = ("bin", "^", node, rhs)
        return node

    def parse_mul():
        node = parse_pow()
        while peek() in ("*", "/"):
            op = take()
            rhs = parse_pow()
            node = ("bin", op, node, rhs)
        return node

    def parse_par():
        node = parse_mul()
        while peek() == "||":
            take()
            rhs = parse_mul()
            node = ("bin", "||", node, rhs)
        return node

    def parse_add():
        node = parse_par()
        while peek() in ("+", "-"):
            op = take()
            rhs = parse_par()
            node = ("bin", op, node, rhs)
        return node

    def canon_node(n) -> str:
        kind = n[0]
        if kind == "lit":
            return str(n[1])
        if kind == "un":
            return f"({n[1]}{canon_node(n[2])})"
        if kind == "fn":
            return f"({n[1]}{canon_node(n[2])})"
        if kind == "bin":
            op = n[1]
            a = n[2]
            b = n[3]
            if op in ("+", "*", "||"):
                parts: list = []

                def gather(m):
                    if m[0] == "bin" and m[1] == op:
                        gather(m[2])
                        gather(m[3])
                    else:
                        parts.append(m)

                gather(a)
                gather(b)
                cparts = [canon_node(p) for p in parts]
                cparts.sort()
                return f"({op}{','.join(cparts)})"
            return f"({op}{canon_node(a)},{canon_node(b)})"
        return str(n)

    try:
        ast = parse_add()
        # CRITICAL: if we didn't consume all tokens, the parse was partial; falling back avoids
        # collapsing distinct long formulas into the same semantic key.
        if pos != len(toks):
            return lhs_prefix + x
        return lhs_prefix + canon_node(ast)
    except Exception:
        return lhs_prefix + x


def _ota_power_equivalents_mc(item_id: str) -> list[str]:
    """
    Multiple valid DC-equivalent quiescent power expressions per OTA (MC-safe).
    Used to ensure none of these become distractors.
    """
    if item_id == "ota001":
        return [
            "P_q ≈ VDD·(I_D,{Mp1} + I_D,{Mp2})",
            "P_q ≈ VDD·I_D,{Mtail}",
            "P_q ≈ VDD·(I_D,{M1} + I_D,{M2})",
        ]
    if item_id == "ota002":
        return [
            "P_q ≈ VDD·(I_D,{M8} + I_D,{M9})",
            "P_q ≈ VDD·(I_D,{M6} + I_D,{M7})",
            "P_q ≈ VDD·I_D,{M5}",
            "P_q ≈ VDD·(I_D,{M1} + I_D,{M2})",
            "P_q ≈ VDD·(I_D,{M3} + I_D,{M4})",
        ]
    if item_id == "ota003":
        return [
            "P_q ≈ VDD·(I_D,{M3} + I_D,{M4} + I_D,{M5} + I_D,{M6})",
            "P_q ≈ VDD·(I_D,{M1} + I_D,{M2} + I_D,{M7} + I_D,{M8})",
            "P_q ≈ VDD·(I_D,{Mtail} + I_D,{M7} + I_D,{M8})",
        ]
    if item_id == "ota004":
        return [
            "P_q ≈ VDD·(I_D,{M3} + I_D,{M4} + I_D,{M7})",
            "P_q ≈ VDD·(I_D,{M5} + I_D,{M7})",
            "P_q ≈ VDD·(I_D,{M1} + I_D,{M2} + I_D,{M7})",
            "P_q ≈ VDD·(I_D,{M5} + I_D,{M6})",
        ]
    if item_id == "ota005":
        return [
            "P_q ≈ VDD·(I_D,{M6} + I_D,{M7})",
            "P_q ≈ VDD·I_D,{M4}",
            "P_q ≈ VDD·(I_D,{M2} + I_D,{M3})",
            "P_q ≈ VDD·(I_D,{M10} + I_D,{M8})",
            "P_q ≈ VDD·(I_D,{M1} + I_D,{M9})",
        ]
    if item_id == "ota006":
        return [
            "P_q ≈ VDD·(I_D,{M2} + I_D,{M3})",
            "P_q ≈ VDD·I_D,{M9}",
            "P_q ≈ VDD·(I_D,{M7} + I_D,{M8})",
            "P_q ≈ VDD·(I_D,{M6} + I_D,{M5})",
            "P_q ≈ VDD·(I_D,{M1} + I_D,{M4})",
        ]
    if item_id == "ota007":
        return ["P_q ≈ VDD·I_D,{M1}", "P_q ≈ VDD·I_D,{M2}"]
    if item_id == "ota008":
        return ["P_q ≈ VDD·I_D,{M4}", "P_q ≈ VDD·I_D,{M3}", "P_q ≈ VDD·I_D,{M2}", "P_q ≈ VDD·I_D,{M1}"]
    if item_id == "ota009":
        return [
            "P_q ≈ VDD·(I_D,{M4} + I_D,{M7} + I_D,{M8})",
            "P_q ≈ VDD·(I_D,{M3} + I_D,{M6} + I_D,{M5})",
            "P_q ≈ VDD·(I_D,{M2} + I_D,{M6} + I_D,{M5})",
            "P_q ≈ VDD·(I_D,{M1} + I_D,{M6} + I_D,{M5})",
        ]
    if item_id == "ota010":
        return [
            "P_q ≈ VDD·(I_D,{M3} + I_D,{M4} + I_D,{M5})",
            "P_q ≈ VDD·(I_D,{M1} + I_D,{M2} + I_D,{M4} + I_D,{M5})",
            "P_q ≈ VDD·(I_D,{M6} + I_D,{M7} + I_D,{M3})",
            "P_q ≈ VDD·(I_D,{M10} + I_D,{M8} + I_D,{M3})",
        ]
    if item_id == "ota011":
        return [
            "P_q ≈ VDD·(I_D,{M3} + I_D,{M4} + I_D,{M5})",
            "P_q ≈ VDD·(I_D,{M1} + I_D,{M2} + I_D,{M4} + I_D,{M5})",
            "P_q ≈ VDD·(I_D,{M7} + I_D,{M6} + I_D,{M3})",
            "P_q ≈ VDD·(I_D,{M8} + I_D,{M10} + I_D,{M3})",
        ]
    if item_id == "ota012":
        # IMPORTANT: M12 is NOT a separate VDD-fed branch in this netlist.
        return [
            "P_q ≈ VDD·(I_D,{M3} + I_D,{M4} + I_D,{M5})",
            "P_q ≈ VDD·(I_D,{M1} + I_D,{M2} + I_D,{M4} + I_D,{M5})",
            "P_q ≈ VDD·(I_D,{M7} + I_D,{M6} + I_D,{M3})",
            "P_q ≈ VDD·(I_D,{M8} + I_D,{M10} + I_D,{M3})",
        ]
    return []


def _finalize_mc_key(
    question_id: str,
    track: str,
    aspect: str,
    correct_answer: str,
    distractors: List[str],
    template_role_map: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """
    Shared MC key finalization: enforce 10 unique A-J options and return the mc_answer_key payload.
    """
    template_role_map = template_role_map or {}

    # Basic guard: no illegal placeholders
    for s in [correct_answer] + list(distractors):
        if "distractor" in (s or "").lower() or "correct answer for" in (s or "").lower():
            raise ValueError(f"Illegal placeholder choice generated for {question_id}: {s}")

    # Normalize + dedupe distractors, and ensure exactly 9 distractors so the correct answer is always within A-J.
    uniq: List[str] = []
    seen: set[str] = set()
    for d in list(distractors):
        if _semantic_choice_key(d) == _semantic_choice_key(correct_answer):
            continue
        nd = _semantic_choice_key(d)
        if nd in seen:
            continue
        seen.add(nd)
        uniq.append(d)

    if len(uniq) < 9:
        raise ValueError(f"Not enough unique MC choices for {question_id} (got {1 + len(uniq)}).")

    random.shuffle(uniq)
    uniq = uniq[:9]
    all_choices = [correct_answer] + uniq
    random.shuffle(all_choices)
    correct_letter = chr(65 + all_choices.index(correct_answer))
    choices = {chr(65 + i): all_choices[i] for i in range(10)}

    return {
        "question_id": question_id,
        "correct_answer": correct_letter,
        "answer_text": correct_answer,
        "choices": choices,
        "track": track,
        "aspect": aspect,
        "template_role_map": template_role_map,
    }


def _harmonize_choice_format(correct_answer: str, distractors: List[str]) -> List[str]:
    """
    Ensure consistent formatting across choices by forcing all options to use the same
    LHS label + operator as the correct answer, and using only the RHS from each distractor.
    """
    s = (correct_answer or "").strip()
    op = "≈" if "≈" in s else ("=" if "=" in s else None)
    if not op:
        return distractors
    lhs, rhs = s.split(op, 1)
    lhs = lhs.strip()
    op = op.strip()

    out: List[str] = []
    for d in list(distractors):
        ds = (d or "").strip()
        if not ds:
            continue
        # Pull RHS if the distractor already has an operator; otherwise treat whole string as RHS.
        if "≈" in ds:
            _lhs_d, rhs_d = ds.split("≈", 1)
            rhs_d = rhs_d.strip()
        elif "=" in ds:
            _lhs_d, rhs_d = ds.split("=", 1)
            rhs_d = rhs_d.strip()
        else:
            rhs_d = ds
        out.append(f"{lhs} {op} {rhs_d}")
    return out


def _ensure_positive_gain(expr: str) -> str:
    """
    For gain expressions, enforce magnitude (positive) by removing a leading negative sign on the RHS.
    (We keep other minus signs inside expressions, e.g. '1 - ...', intact.)
    """
    s = (expr or "").strip()
    if "≈" in s:
        lhs, rhs = s.split("≈", 1)
        rhs_s = rhs.strip()
        rhs_s = re.sub(r"^[\-\u2212]\s*", "", rhs_s)  # '-' or Unicode '−'
        return f"{lhs.strip()} ≈ {rhs_s}"
    if "=" in s:
        lhs, rhs = s.split("=", 1)
        rhs_s = rhs.strip()
        rhs_s = re.sub(r"^[\-\u2212]\s*", "", rhs_s)
        return f"{lhs.strip()} = {rhs_s}"
    return re.sub(r"^[\-\u2212]\s*", "", s)


def _gbw_distractors_hz(correct_answer: str) -> List[str]:
    """
    Generate GBW distractors that keep the same unit convention as the correct answer:
    Hz (cycles/second) with explicit 2π/π factors shown (no ω / rad/s tokens).
    """
    s = (correct_answer or "").strip()
    op = "≈" if "≈" in s else ("=" if "=" in s else None)
    if not op:
        return []
    lhs, rhs = s.split(op, 1)
    lhs = lhs.strip()
    op = op.strip()
    rhs = rhs.strip()

    # Require π to be present so the Hz convention is explicit in every option.
    if "π" not in rhs:
        rhs = f"({rhs})/(2π)"

    pool: List[str] = []

    # π-factor mistakes (keep explicit π, keep Hz convention)
    pool.extend([
        f"{lhs} {op} ({rhs})/π",
        f"{lhs} {op} π·({rhs})",
    ])

    # A few scalar mistakes (dimensionless scaling; units preserved)
    pool.extend([
        f"{lhs} {op} ({rhs})/2",
        f"{lhs} {op} 2·({rhs})",
        f"{lhs} {op} ({rhs})/4",
        f"{lhs} {op} 4·({rhs})",
    ])

    # Nonlinear “wrong math” variants
    pool.extend([
        f"{lhs} {op} √({rhs})",
        f"{lhs} {op} ({rhs})²",
    ])

    # Replace 2π/4π mistakes if present (keeps π explicit)
    if "4π" in rhs:
        pool.append(f"{lhs} {op} {rhs.replace('4π', '2π')}")
        pool.append(f"{lhs} {op} {rhs.replace('4π', '8π')}")
    if "2π" in rhs:
        pool.append(f"{lhs} {op} {rhs.replace('2π', '4π')}")
        pool.append(f"{lhs} {op} {rhs.replace('2π', '8π')}")

    # Device-grounded mistakes: swap which transistor's gm appears.
    # Use runtime placeholders {X1}/{X2}/{X3}/{OUTN}/{OUTP} where possible.
    gm_tokens = re.findall(r"gm_\{([A-Za-z0-9_]+)\}", rhs)
    if gm_tokens:
        # Swap the first gm term to a wrong device role.
        for wrong in ["X1", "X2", "X3", "OUTN", "OUTP", "INP", "INN"]:
            pool.append(f"{lhs} {op} {rhs.replace(f'gm_{{{gm_tokens[0]}}}', f'gm_{{{wrong}}}', 1)}")
        # If we have a sum of two gms, swap one side.
        if len(gm_tokens) >= 2:
            pool.append(f"{lhs} {op} {rhs.replace(f'gm_{{{gm_tokens[1]}}}', 'gm_{X1}', 1)}")
            pool.append(f"{lhs} {op} {rhs.replace(f'gm_{{{gm_tokens[1]}}}', 'gm_{X2}', 1)}")
            # Replace sum with product (unit-wrong but common misconception; still unique)
            pool.append(f"{lhs} {op} {rhs.replace('+', '·', 1)}")

    # Capacitor token swaps/scalings can be equivalent to scalar mistakes; we still include a couple,
    # but semantic dedupe will drop equivalences automatically.
    for cap_tok in ["Cload", "C1", "C2", "Cload1", "Cc"]:
        if cap_tok in rhs:
            pool.extend([
                f"{lhs} {op} {rhs.replace(cap_tok, f'2·{cap_tok}')}",
                f"{lhs} {op} {rhs.replace(cap_tok, f'({cap_tok}/2)')}",
            ])

    # Remove any rad/s-style tokens defensively
    bad_tokens = ("ω", "omega", "wt", "rad/s", "rad/sec")
    pool = [x for x in pool if not any(t in x for t in bad_tokens)]

    # Finally, semantic-dedupe inside the generator to ensure we return enough unique candidates.
    out: List[str] = []
    seen: set[str] = set()
    corr_k = _semantic_choice_key(correct_answer)
    for cand in pool:
        k = _semantic_choice_key(cand)
        if not k or k == corr_k or k in seen:
            continue
        seen.add(k)
        out.append(cand)
    return out


def _noise_distractors_device_grounded(correct_answer: str, is_ota: bool) -> List[str]:
    """
    Generate realistic noise distractors that still reference specific device parameters (gm/ro/γ/WL).
    We do this by mutating the correct expression in plausible ways:
    - swapping a contributing device to a wrong device (X1/X2/X3 when available)
    - dropping a term
    - mismatching γ and gm subscripts
    - removing a squared partition factor
    - changing the rout exponent (e.g., missing the square)
    - simple kT factor mistakes
    """
    s = (correct_answer or "").strip()
    # Collect device placeholders used in gm/ro/gamma terms: {M1}, {Mp1}, etc.
    ids = list(dict.fromkeys(re.findall(r"\{([A-Za-z0-9_]+)\}", s)))
    # Add extra wrong-device roles for OTAs if available at runtime
    wrong_ids = ["X1", "X2", "X3"] if is_ota else []

    # Find gamma*gm term IDs used: γ_{ID}·gm_{ID}
    term_ids = re.findall(r"γ_\{([A-Za-z0-9_]+)\}\s*·\s*gm_\{\1\}", s)
    term_ids = list(dict.fromkeys(term_ids))

    out: List[str] = []

    def _swap_one_term(to_id: str) -> None:
        if not term_ids:
            return
        tid = term_ids[0]
        out.append(
            s.replace(f"γ_{{{tid}}}·gm_{{{tid}}}", f"γ_{{{to_id}}}·gm_{{{to_id}}}", 1)
        )

    # 1) Swap one contributor to a wrong device
    if wrong_ids:
        _swap_one_term(wrong_ids[0])
        if len(wrong_ids) > 1:
            _swap_one_term(wrong_ids[1])
        if len(wrong_ids) > 2:
            _swap_one_term(wrong_ids[2])
    elif len(term_ids) >= 2:
        _swap_one_term(term_ids[1])

    # 2) Mismatch gamma vs gm subscripts
    if len(term_ids) >= 2:
        a, b = term_ids[0], term_ids[1]
        out.append(s.replace(f"γ_{{{a}}}·gm_{{{a}}}", f"γ_{{{a}}}·gm_{{{b}}}", 1))
        out.append(s.replace(f"γ_{{{a}}}·gm_{{{a}}}", f"γ_{{{b}}}·gm_{{{a}}}", 1))

    # 3) Drop one term from the sum (remove first '+ <term>')
    if term_ids:
        a = term_ids[0]
        out.append(re.sub(rf"\s*\+\s*γ_\{{{re.escape(a)}\}}\s*·\s*gm_\{{{re.escape(a)}\}}", "", s, count=1))

    # 4) Remove square from a partition factor ( (gm_x/(gm_y+gm_z))² -> (gm_x/(gm_y+gm_z)) )
    out.append(s.replace(")²", ")", 1))
    out.append(s.replace("^2", "", 1))

    # 5) Missing rout square: replace first '²·4kT' with '·4kT'
    out.append(s.replace(")²·4kT", ")·4kT", 1))
    # Another plausible exponent slip: use cube instead of square once
    out.append(s.replace(")²·4kT", ")³·4kT", 1))

    # 6) Wrong kT factor: 4kT -> 8kT or 2kT (keep same structure)
    out.append(s.replace("4kT", "8kT", 1))
    out.append(s.replace("4kT", "2kT", 1))

    # 7) Replace parallel operator in rout with '+' (plausible algebra slip)
    out.append(s.replace(" || ", " + ", 1))
    # Another algebra slip: subtract instead of add between branch contributions (diff OTAs)
    out.append(s.replace(" + (", " - (", 1))

    # 8) If WL ratio exists, invert it once ( (W/L)_A/(W/L)_B -> (W/L)_B/(W/L)_A )
    m = re.search(r"\(\(W/L\)_\{([A-Za-z0-9_]+)\}/\(W/L\)_\{([A-Za-z0-9_]+)\}\)", s)
    if m:
        a, b = m.group(1), m.group(2)
        out.append(s.replace(f"((W/L)_{{{a}}}/(W/L)_{{{b}}})", f"((W/L)_{{{b}}}/(W/L)_{{{a}}})", 1))

    # 9) Swap a raw gm/ro/gamma subscript to a wrong device role (device-grounded but incorrect).
    if wrong_ids:
        out.append(re.sub(r"gm_\{[A-Za-z0-9_]+\}", f"gm_{{{wrong_ids[0]}}}", s, count=1))
        out.append(re.sub(r"ro_\{[A-Za-z0-9_]+\}", f"ro_{{{wrong_ids[1] if len(wrong_ids)>1 else wrong_ids[0]}}}", s, count=1))
        out.append(re.sub(r"γ_\{[A-Za-z0-9_]+\}", f"γ_{{{wrong_ids[2] if len(wrong_ids)>2 else wrong_ids[0]}}}", s, count=1))

    # 10) Scalar mistakes on the whole bracketed sum (still device-grounded and unit-consistent)
    out.append(s.replace("·4kT·[", "·4kT·2·[", 1))
    out.append(s.replace("·4kT·[", "·4kT·(1/2)·[", 1))

    # Clean empties and obvious duplicates; _finalize_mc_key also dedupes.
    out = [x for x in out if x and x != correct_answer]
    return out


def _gain_dc_distractors_device_grounded(correct_answer: str) -> List[str]:
    """
    Gain_dc distractors that remain dimensionless (V/V) and device-grounded.
    We mutate the RHS of the correct expression:
    - scaling factors (2x, 1/2, 1/4)
    - swap gm subscripts to {X1}/{X2} or to another gm token in the expression
    - swap ro subscripts similarly
    - replace '||' with '+' or vice-versa
    - exponent slips on the rout factor (square, sqrt)
    """
    s = (correct_answer or "").strip()
    op = "≈" if "≈" in s else ("=" if "=" in s else None)
    if not op or op not in s:
        return []
    lhs, rhs = s.split(op, 1)
    lhs = lhs.strip()
    rhs = rhs.strip()

    gm_tokens = re.findall(r"gm_\{[A-Za-z0-9_]+\}", rhs)
    ro_tokens = re.findall(r"ro_\{[A-Za-z0-9_]+\}", rhs)
    gm_tokens = list(dict.fromkeys(gm_tokens))
    ro_tokens = list(dict.fromkeys(ro_tokens))

    def fmt(rhs_new: str) -> str:
        return f"{lhs} {op} {rhs_new}"

    out: List[str] = []
    # scalar factor slips
    out.extend([
        fmt(f"2·({rhs})"),
        fmt(f"({rhs})/2"),
        fmt(f"({rhs})/4"),
        fmt(f"4·({rhs})"),
    ])
    # algebra slips on parallel
    out.append(fmt(rhs.replace(" || ", " + ", 1)))
    out.append(fmt(rhs.replace(" + ", " || ", 1)))
    # exponent slips
    out.append(fmt(f"({rhs})²"))
    out.append(fmt(f"√({rhs})"))

    # wrong-device gm/ro swaps (uses runtime X roles when available)
    if gm_tokens:
        out.append(fmt(rhs.replace(gm_tokens[0], "gm_{X1}", 1)))
        out.append(fmt(rhs.replace(gm_tokens[0], "gm_{X2}", 1)))
    if ro_tokens:
        out.append(fmt(rhs.replace(ro_tokens[0], "ro_{X1}", 1)))
        out.append(fmt(rhs.replace(ro_tokens[0], "ro_{X2}", 1)))

    # swap between gm tokens that already exist
    if len(gm_tokens) >= 2:
        out.append(fmt(rhs.replace(gm_tokens[0], gm_tokens[1], 1)))
    if len(ro_tokens) >= 2:
        out.append(fmt(rhs.replace(ro_tokens[0], ro_tokens[1], 1)))

    # keep only those still device-grounded (must contain at least one gm_{...} and one ro_{...})
    out = [x for x in out if ("gm_{" in x and "ro_{" in x) and x != correct_answer]
    return out


def _rout_distractors_device_grounded(correct_answer: str) -> List[str]:
    """
    Rout distractors that remain device-grounded:
    - swap ro subscripts to X roles
    - swap || to +, or change grouping
    - scale by 2 or 1/2
    - if gm·ro+1 cascode factors appear, swap gm/ro subscripts
    """
    s = (correct_answer or "").strip()
    op = "≈" if "≈" in s else ("=" if "=" in s else None)
    if not op or op not in s:
        return []
    lhs, rhs = s.split(op, 1)
    lhs = lhs.strip()
    rhs = rhs.strip()

    ro_tokens = list(dict.fromkeys(re.findall(r"ro_\{[A-Za-z0-9_]+\}", rhs)))
    gm_tokens = list(dict.fromkeys(re.findall(r"gm_\{[A-Za-z0-9_]+\}", rhs)))

    def fmt(rhs_new: str) -> str:
        return f"{lhs} {op} {rhs_new}"

    out: List[str] = []
    out.extend([
        fmt(f"2·({rhs})"),
        fmt(f"({rhs})/2"),
        fmt(f"4·({rhs})"),
        fmt(f"({rhs})/4"),
        fmt(f"√({rhs})"),
        fmt(f"({rhs})²"),
        fmt(rhs.replace(" || ", " + ", 1)),
        fmt(rhs.replace(" + ", " || ", 1)),
    ])
    # swap one ro to wrong device role
    if ro_tokens:
        out.append(fmt(rhs.replace(ro_tokens[0], "ro_{X1}", 1)))
        out.append(fmt(rhs.replace(ro_tokens[0], "ro_{X2}", 1)))
        out.append(fmt(rhs.replace(ro_tokens[0], "ro_{X3}", 1)))
        if len(ro_tokens) > 1:
            out.append(fmt(rhs.replace(ro_tokens[1], "ro_{X1}", 1)))
            out.append(fmt(rhs.replace(ro_tokens[1], "ro_{X2}", 1)))
            out.append(fmt(rhs.replace(ro_tokens[1], "ro_{X3}", 1)))
    # swap one gm (if present) to wrong device role
    if gm_tokens:
        out.append(fmt(rhs.replace(gm_tokens[0], "gm_{X1}", 1)))
        out.append(fmt(rhs.replace(gm_tokens[0], "gm_{X2}", 1)))
        out.append(fmt(rhs.replace(gm_tokens[0], "gm_{X3}", 1)))
        if len(gm_tokens) > 1:
            out.append(fmt(rhs.replace(gm_tokens[1], "gm_{X1}", 1)))
            out.append(fmt(rhs.replace(gm_tokens[1], "gm_{X2}", 1)))
    # keep only those still grounded (must mention at least one ro_{...})
    out = [x for x in out if ("ro_{" in x) and x != correct_answer]
    return out


def _psrr_distractors_device_grounded(correct_answer: str) -> List[str]:
    """
    PSRR distractors that remain device-grounded:
    - swap gm/ro subscripts to X roles
    - flip divider algebra (|| -> +) in the load resistance if present
    - scale factor slips
    """
    s = (correct_answer or "").strip()
    op = "≈" if "≈" in s else ("=" if "=" in s else None)
    if not op or op not in s:
        return []
    lhs, rhs = s.split(op, 1)
    lhs = lhs.strip()
    rhs = rhs.strip()

    gm_tokens = list(dict.fromkeys(re.findall(r"gm_\{[A-Za-z0-9_]+\}", rhs)))
    ro_tokens = list(dict.fromkeys(re.findall(r"ro_\{[A-Za-z0-9_]+\}", rhs)))

    def fmt(rhs_new: str) -> str:
        return f"{lhs} {op} {rhs_new}"

    out: List[str] = []
    out.extend([
        fmt(f"2·({rhs})"),
        fmt(f"({rhs})/2"),
        fmt(f"4·({rhs})"),
        fmt(f"({rhs})/4"),
        fmt(f"√({rhs})"),
        fmt(rhs.replace(" || ", " + ", 1)),
    ])
    if gm_tokens:
        out.append(fmt(rhs.replace(gm_tokens[0], "gm_{X1}", 1)))
        out.append(fmt(rhs.replace(gm_tokens[0], "gm_{X2}", 1)))
        out.append(fmt(rhs.replace(gm_tokens[0], "gm_{X3}", 1)))
        if len(gm_tokens) > 1:
            out.append(fmt(rhs.replace(gm_tokens[1], "gm_{X1}", 1)))
            out.append(fmt(rhs.replace(gm_tokens[1], "gm_{X2}", 1)))
    if ro_tokens:
        out.append(fmt(rhs.replace(ro_tokens[0], "ro_{X1}", 1)))
        out.append(fmt(rhs.replace(ro_tokens[0], "ro_{X2}", 1)))
        out.append(fmt(rhs.replace(ro_tokens[0], "ro_{X3}", 1)))
        if len(ro_tokens) > 1:
            out.append(fmt(rhs.replace(ro_tokens[1], "ro_{X1}", 1)))
            out.append(fmt(rhs.replace(ro_tokens[1], "ro_{X2}", 1)))
    # keep only grounded ones (must mention gm_ and ro_ somewhere, otherwise too abstract)
    out = [x for x in out if (("gm_{" in x) and ("ro_{" in x)) and x != correct_answer]
    return out

# Set seed for reproducible distractor generation
random.seed(42)

# Answer key templates for different question types
DEBUGGING_OTA_SWAP_ANSWERS = {
    "ota001": {"device": "M3", "from_type": "NMOS", "to_type": "PMOS", "correct_type": "NMOS"},
    "ota002": {"device": "M5", "from_type": "PMOS", "to_type": "NMOS", "correct_type": "PMOS"},
    "ota003": {"device": "M7", "from_type": "NMOS", "to_type": "PMOS", "correct_type": "NMOS"},
    "ota004": {"device": "M4", "from_type": "PMOS", "to_type": "NMOS", "correct_type": "PMOS"},
    "ota005": {"device": "M2", "from_type": "NMOS", "to_type": "PMOS", "correct_type": "NMOS"},
    "ota006": {"device": "M6", "from_type": "PMOS", "to_type": "NMOS", "correct_type": "PMOS"},
    "ota007": {"device": "M3", "from_type": "NMOS", "to_type": "PMOS", "correct_type": "NMOS"},
    "ota008": {"device": "M1", "from_type": "PMOS", "to_type": "NMOS", "correct_type": "PMOS"},
    "ota009": {"device": "M5", "from_type": "NMOS", "to_type": "PMOS", "correct_type": "NMOS"},
    "ota010": {"device": "M4", "from_type": "PMOS", "to_type": "NMOS", "correct_type": "PMOS"},
    "ota011": {"device": "M7", "from_type": "NMOS", "to_type": "PMOS", "correct_type": "NMOS"},
    "ota012": {"device": "M3", "from_type": "PMOS", "to_type": "NMOS", "correct_type": "PMOS"},
}

DEBUGGING_FEEDBACK_POLARITY_ANSWERS = {
    "feedback001": {"issue": "positive feedback", "fix": "swap opamp inputs"},
    "feedback002": {"issue": "positive feedback", "fix": "swap opamp inputs"},
    "feedback003": {"issue": "positive feedback", "fix": "move feedback to inverting terminal"},
    "feedback004": {"issue": "positive feedback", "fix": "swap opamp inputs"},
}

ANALYSIS_OTA_DC_GAIN = {
    "ota001": "gm·ro/2",       # 5T OTA with current mirror load
    "ota002": "(gm·ro)²/2",    # Telescopic cascode (fully differential)
    "ota003": "gm·ro/2",       # High-swing current mirror OTA
    "ota004": "(gm·ro)²/4",    # Two-stage Miller: (gm1·ro1/2) × (gm2·ro2/2) = (gm·ro)²/4
    "ota005": "(gm·ro)²/2",    # Single-ended telescopic cascode
    "ota006": "(gm·ro)²/2",    # Single-ended telescopic cascode
    "ota007": "gm·ro/2",       # Single-stage common source with current mirror load
    "ota008": "(gm·ro)²/2",    # NMOS cascode with PMOS cascode load
    "ota009": "(gm·ro)³/2",    # Gain-boosted cascode (still has parallel ro at output)
    "ota010": "(gm·ro)²/2",    # Folded cascode (fully differential)
    "ota011": "(gm·ro)²/2",    # Folded cascode (single-ended)
    "ota012": "gm·ro/2",       # Folded cascode with current mirror load
}

ANALYSIS_OTA_GBW = {
    "ota001": "gm/CL",
    "ota002": "gm/CL",
    # ota003 template is single-stage (no explicit compensation cap); use load cap.
    "ota003": "gm/CL",
    "ota004": "gm/CL",
    "ota005": "gm/CL",
    "ota006": "gm/CL",
    "ota007": "gm/CL",
    "ota008": "gm/CL",
    "ota009": "gm/CL",
    "ota010": "gm/CL",
    "ota011": "gm/CL",
    "ota012": "gm/CL",
}

ANALYSIS_FEEDBACK_LOOP_GAIN = {
    # Loop gain T = A0·β. For unity feedback, β=1 so T=A0.
    "feedback001": "T = A0",
    "feedback002": "T = A0",
    "feedback003": "T = A0·R1/(R1+R2)",
    # Inverting amplifier: beta = R2/(R1+R2)
    "feedback004": "T = A0·R2/(R1+R2)",
}

ANALYSIS_FEEDBACK_BETA = {
    # Keep component-level (avoid abstracting away the divider details).
    "feedback001": "β = 1",
    "feedback002": "β = 1",
    "feedback003": "β = R1/(R1+R2)",
    "feedback004": "β = R2/(R1+R2)",
}

ANALYSIS_FEEDBACK_CL_GAIN = {
    "feedback001": "Vout/Iin = R1",
    # Capacitive feedback TIA acts as an integrator: Zf = 1/(sC1)
    "feedback002": "Vout/Iin = 1/(s*C1)",
    "feedback003": "Vout/Vin = 1 + R2/R1",
    # Inverting amplifier: -Rfb/Rin = -R1/R2 for the template netlist
    "feedback004": "Vout/Vin = R1/R2",
}

ANALYSIS_FEEDBACK_SIGNAL_MODALITY = {
    # TIA: current in, voltage out
    "feedback001": "I-V",
    "feedback002": "I-V",
    # Voltage amplifiers: voltage in, voltage out
    "feedback003": "V-V",
    "feedback004": "V-V",
}

ANALYSIS_FILTER_TF = {
    # Avoid ω0/ωc/Q/H0 in MCQ choices so we can safely rename component IDs at runtime.
    # Use coefficient forms in terms of R/C/L names (the runtime renamer will update R*/C*/L* tokens).
    "filter001": "H(s) = 1/(1 + s*R1*C1)",
    "filter002": "H(s) = (s*R1*C1)/(1 + s*R1*C1)",
    # Generic 2nd-order bandpass coefficient form (component-level, no Q/ω0)
    "filter003": "H(s) = (s*R1*C1)/(s^2*R1*R2*C1*C2 + s*(R1*C1 + R2*C2) + 1)",
    # RLC shunt bandpass-ish coefficient form
    "filter004": "H(s) = (s*L1/R1)/(s^2*L1*C1 + s*(L1/Rload + R1*C1) + 1)",
    "filter005": "H(s) = 1/(s^2*R1*R2*C1*C2 + s*(R1*C1 + R2*C2) + 1)",
    "filter006": "H(s) = (s^2*R1*R2*C1*C2)/(s^2*R1*R2*C1*C2 + s*(R1*C1 + R2*C2) + 1)",
    "filter007": "H(s) = (s^2*R1*R2*C1*C2 + 1)/(s^2*R1*R2*C1*C2 + s*(R1*C1 + R2*C2) + 1)",
    "filter008": "H(s) = (s^2*R1*R2*C1*C2 - s*(R1*C1 + R2*C2) + 1)/(s^2*R1*R2*C1*C2 + s*(R1*C1 + R2*C2) + 1)",
    "filter009": "H(s) = 1/(s^2*R1*R2*C1*C2 + s*1.41421356*R1*C1 + 1)",
    "filter010": "H(s) = (s^2*R1*R2*C1*C2)/(s^2*R1*R2*C1*C2 + s*1.41421356*R1*C1 + 1)",
    "filter011": "H(s) = (s*R2*C1)/(s^2*R2*R3*C1*C2 + s*(R2*C1 + R3*C2) + 1)",
    "filter012": "H(s) = (s*R2*C1)/(s^2*R2*R3*C1*C2 + s*(R2*C1 + R3*C2) + 1)",
}

# Add answer keys for missing aspects
ANALYSIS_OTA_PSRR = {
    "ota001": "PSRR+ ≈ (gm·ro)",
    "ota002": "PSRR+ ≈ (gm·ro)²",
    "ota003": "PSRR+ ≈ CMRR·Acm",
    "ota004": "PSRR+ ≈ (gm·ro)²",
    "ota005": "PSRR+ ≈ (gm·ro)²",
    "ota006": "PSRR+ ≈ (gm·ro)²",
    "ota007": "PSRR+ ≈ (gm·ro)³",
    "ota008": "PSRR+ ≈ (gm·ro)³",
    "ota009": "PSRR+ ≈ gm·ro",
    "ota010": "PSRR+ ≈ (gm·ro)²",
    "ota011": "PSRR+ ≈ (gm·ro)²",
    "ota012": "PSRR+ ≈ gm·ro",
}

ANALYSIS_OTA_ROUT = {
    "ota001": "rout ≈ ro",
    "ota002": "rout ≈ (gm·ro)·ro",
    "ota003": "rout ≈ ro",
    "ota004": "rout ≈ (gm·ro)·ro",
    "ota005": "rout ≈ (gm·ro)·ro",
    "ota006": "rout ≈ (gm·ro)·ro",
    "ota007": "rout ≈ (gm·ro)²·ro",
    "ota008": "rout ≈ (gm·ro)²·ro",
    "ota009": "rout ≈ ro",
    "ota010": "rout ≈ (gm·ro)·ro",
    "ota011": "rout ≈ (gm·ro)·ro",
    "ota012": "rout ≈ ro",
}

ANALYSIS_OTA_SWING = {
    "ota001": "Max swing ≈ VDD - 2·|VDsat|",
    "ota002": "Max swing ≈ VDD - 4·|VDsat|",
    "ota003": "Max swing ≈ VDD - |VDsat|",
    "ota004": "Max swing ≈ VDD - 3·|VDsat|",
    "ota005": "Max swing ≈ VDD - 4·|VDsat|",
    "ota006": "Max swing ≈ VDD - 3·|VDsat|",
    "ota007": "Max swing ≈ VDD - 5·|VDsat|",
    "ota008": "Max swing ≈ VDD - 5·|VDsat|",
    "ota009": "Max swing ≈ VDD - 2·|VDsat|",
    "ota010": "Max swing ≈ VDD - 4·|VDsat|",
    "ota011": "Max swing ≈ VDD - 3·|VDsat|",
    "ota012": "Max swing ≈ VDD - |VDsat|",
}

ANALYSIS_OTA_POWER = {
    "ota001": "P = VDD·Itail",
    "ota002": "P = VDD·(Itail + Ibias_cascode)",
    "ota003": "P = VDD·(Itail + Ibias_2nd_stage)",
    "ota004": "P = VDD·(Itail + Ibias_fold)",
    "ota005": "P = VDD·(Itail + Ibias_cascode)",
    "ota006": "P = VDD·(Itail + Ibias_cascode)",
    "ota007": "P = VDD·(Imain + Iaux_amps)",
    "ota008": "P = VDD·(Imain + Iaux_amps)",
    "ota009": "P = VDD·Itail",
    "ota010": "P = VDD·(Itail + Ibias)",
    "ota011": "P = VDD·(Itail + Ibias)",
    "ota012": "P = VDD·Itail",
}

ANALYSIS_OTA_NOISE = {
    "ota001": "Vn,out² ≈ 8kT/(3gm)",
    "ota002": "Vn,out² ≈ 8kT/(3gm)·(1 + gmn/gmp)",
    "ota003": "Vn,out² ≈ 8kT/(3gm1)·(1 + A1²·gm2/gm1)",
    "ota004": "Vn,out² ≈ 8kT/(3gm)·(1 + fold_factor)",
    "ota005": "Vn,out² ≈ 8kT/(3gm)·(1 + gmcas/gmdiff)",
    "ota006": "Vn,out² ≈ 8kT/(3gm)·(1 + fold_factor)",
    "ota007": "Vn,out² ≈ 8kT/(3gm)·(1 + aux_contribution)",
    "ota008": "Vn,out² ≈ 8kT/(3gm)·(1 + aux_contribution)",
    "ota009": "Vn,out² ≈ 8kT/(3gm)",
    "ota010": "Vn,out² ≈ 8kT/(3gm)·(1 + gmcas/gmdiff)",
    "ota011": "Vn,out² ≈ 8kT/(3gm)·(1 + fold_factor)",
    "ota012": "Vn,out² ≈ 8kT/(3gm)",
}



def generate_device_swap_distractors(correct_device: str, all_devices: List[str], correct_type: str) -> List[str]:
    """Generate plausible distractors for device swap debugging questions."""
    distractors = []
    other_devices = [d for d in all_devices if d != correct_device]
    
    # Type 1: Correct device, but wrong diagnosis
    distractors.append(f"{correct_device} has incorrect body connection. Fix: tie body to opposite rail.")
    distractors.append(f"{correct_device} width/length ratio is incorrect. Fix: adjust W/L to match current requirement.")
    
    # Type 2: Wrong device identified
    for dev in other_devices[:5]:
        wrong_type = "NMOS" if correct_type == "PMOS" else "PMOS"
        distractors.append(f"{dev} is incorrectly typed as {wrong_type}. Fix: change to {correct_type}.")
    
    # Type 3: Structural issues
    distractors.append("Current mirror is missing a device. Fix: add cascode MOSFET.")
    distractors.append("Differential pair devices are swapped. Fix: exchange drain connections.")
    distractors.append("Bias network has wrong polarity. Fix: invert bias voltage source.")
    
    return distractors


def generate_formula_distractors(correct_formula: str, formula_type: str) -> List[str]:
    """Generate plausible formula distractors for analysis questions."""
    distractors = []
    
    if formula_type == "dc_gain":
        # Generate distractors based on the correct formula to avoid duplicates
        # Base pool of modifications
        base_alternatives = [
            "gm·ro²",          # Extra ro term
            "gm²·ro",          # Extra gm term  
            "2·gm·ro",         # Factor of 2 (wrong direction)
            "4·gm·ro",         # Factor of 4
            "gm/ro",           # Division instead of multiplication
            "(gm·ro)³",        # Cubed
            "(gm·ro)³/2",      # Cubed with /2
            "√(gm·ro)",        # Square root
            "gm·ro/4",         # Factor of 1/4
            "3·gm·ro/2",       # Factor of 3/2
            "(gm·ro)²",        # Squared (no /2)
            "(gm·ro)²/4",      # Squared with /4
            "gm·ro",           # No /2 factor
            "(gm·ro)²/2",      # Squared with /2
        ]
        
        # Filter based on correct answer to avoid mathematical equivalents
        if "gm·ro/2" in correct_formula:
            # Correct is gm·ro/2, exclude equivalent forms
            alternatives = [d for d in base_alternatives if d not in ["gm·ro/2"]]
        elif "(gm·ro)²/2" in correct_formula:
            # Correct is (gm·ro)²/2, exclude equivalent forms
            alternatives = [d for d in base_alternatives if d not in ["(gm·ro)²/2"]]
        elif "(gm·ro)³/2" in correct_formula:
            # Correct is (gm·ro)³/2, exclude equivalent forms  
            alternatives = [d for d in base_alternatives if d not in ["(gm·ro)³/2"]]
        else:
            alternatives = base_alternatives
    elif formula_type == "gbw":
        alternatives = [
            "gm·CL",
            "gm/(2πCL)",
            "gm1·Cc/CL",
            "gm1/(Cc+CL)",
            "ωt = gm·CL",
            "gm/Cc",
            "A0·ωp",
            "(gm/CL)·(Cc/CL)",
            "gm/(Cc·CL)",
        ]
    elif formula_type == "loop_gain":
        alternatives = [
            "T = A0·β",
            "T = β/A0",
            "T = 1/(1+A0·β)",
            "T = A0/(1+β)",
            "T = β",
            "T = A0²",
            "T = A0/(1+A0·β)",
            "T = (A0·β)/2",
            "T = √(A0·β)",
        ]
    elif formula_type == "beta":
        alternatives = [
            "β = 0",
            "β = R2/(R1+R2)",
            "β = R1",
            "β = 1/R1",
            "β = R1·R2",
            "β = (R1+R2)/R1",
            "β = 2R1/(R1+R2)",
            "β = 1/(R1+R2)",
            "β = R1/R2",
        ]
    elif formula_type == "cl_gain":
        alternatives = [
            "Vout/Vin = R1",
            "Vout/Vin = -R1·R2",
            "Vout/Vin = 1/R1",
            "Vout/Vin = R2/R1 (missing sign)",
            "Vout/Vin = -(R1+R2)/R1",
            "Vout/Vin = A0/(1+A0·β)",
            "Vout/Vin = 1 + R1/R2",
            "Vout/Vin = R1/(R1+R2)",
            "Vout/Vin = A0·β",
        ]
    elif formula_type == "filter_tf":
        alternatives = [
            # Component-level forms only (no ω0/ωc/Q/H0, no parentheticals).
            "H(s) = 1/(1 + s*R1*C1)",
            "H(s) = (s*R1*C1)/(1 + s*R1*C1)",
            "H(s) = 1/(s^2*R1*R2*C1*C2 + s*(R1*C1 + R2*C2) + 1)",
            "H(s) = (s^2*R1*R2*C1*C2)/(s^2*R1*R2*C1*C2 + s*(R1*C1 + R2*C2) + 1)",
            "H(s) = (s*R2*C1)/(s^2*R2*R3*C1*C2 + s*(R2*C1 + R3*C2) + 1)",
            "H(s) = (s^2*R1*R2*C1*C2 + 1)/(s^2*R1*R2*C1*C2 + s*(R1*C1 + R2*C2) + 1)",
            "H(s) = (s^2*R1*R2*C1*C2 - s*(R1*C1 + R2*C2) + 1)/(s^2*R1*R2*C1*C2 + s*(R1*C1 + R2*C2) + 1)",
            "H(s) = (s*L1/R1)/(s^2*L1*C1 + s*(L1/Rload + R1*C1) + 1)",
            "H(s) = R1/(R1 + s*L1)",
            # Extra pool to ensure we can always produce A–J after netlist-aware filtering
            "H(s) = 1/(1 + (s*R1*C1)^2)",
            "H(s) = 1/(1 + s^2*R1*R1*C1*C1)",
            "H(s) = 1/(1 + 2*s*R1*C1)",
            "H(s) = 1/(1 + (s*R1*C1)/2)",
            "H(s) = (s^2*R1*R1*C1*C1)/(1 + s^2*R1*R1*C1*C1)",
            "H(s) = (s*R1*C1)/(1 + (s*R1*C1)^2)",
            "H(s) = 1/(1 + s*R1*C1)^2",
            "H(s) = 1/(1 + s*C1/R1)",
            "H(s) = 1/(1 + s*R1/C1)",
            "H(s) = 1/(1 + s/(R1*C1))",
            "H(s) = (s*R1*C1)/(1 + s^2*R1*R1*C1*C1)",
            "H(s) = (s*L1)/(R1 + s*L1)",
            "H(s) = 1/(1 + s*L1/R1)",
            "H(s) = (s*L1/R1)/(1 + s*L1/R1)",
            "H(s) = R1/(R1 + 2*s*L1)",
            "H(s) = (2*s*L1)/(R1 + 2*s*L1)",
            "H(s) = R1/(R1 + s*L1)^2",
            "H(s) = 1/(1 + (s*L1/R1)^2)",
            "H(s) = (s^2*L1*L1)/(R1*R1 + s^2*L1*L1)",
            "H(s) = (R1*Rload)/(R1*Rload + s*L1*(R1+Rload))",
            "H(s) = R1/(R1 + s*L1 + 1/(s*C1))",
            "H(s) = 1/(s^2*L1*C1 + s*(R1*C1) + 1)",
            "H(s) = (s^2*L1*C1)/(s^2*L1*C1 + s*(R1*C1) + 1)",
        ]
    elif formula_type == "psrr":
        alternatives = [
            "PSRR+ ≈ gm/ro",
            "PSRR+ ≈ gm²·ro",
            "PSRR+ ≈ (gm·ro)/2",
            "PSRR+ ≈ 2·gm·ro",
            "PSRR+ ≈ √(gm·ro)",
            "PSRR+ ≈ (gm·ro)³/2",
            "PSRR+ ≈ A0·CMRR",
            "PSRR+ ≈ gm·(ro || rds)",
            "PSRR+ ≈ ro/gm",
        ]
    elif formula_type == "rout":
        alternatives = [
            "rout ≈ 2ro",
            "rout ≈ ro/2",
            "rout ≈ gm·ro",
            "rout ≈ ro²/gm",
            "rout ≈ (gm·ro)³·ro",
            "rout ≈ ro/(1+gm·ro)",
            "rout ≈ √(ro³)",
            "rout ≈ ro·(1+gm·ro)",
            "rout ≈ ro + gm·ro²",
        ]
    elif formula_type == "swing":
        alternatives = [
            "Max swing ≈ VDD - |VDsat|",
            "Max swing ≈ VDD - 3·|VDsat|",
            "Max swing ≈ VDD - 5·|VDsat|",
            "Max swing ≈ VDD - 6·|VDsat|",
            "Max swing ≈ VDD/2",
            "Max swing ≈ VDD - VTH",
            "Max swing ≈ VDD - 2·VTH",
            "Max swing ≈ VDD·(1 - VDsat/VDD)",
            "Max swing ≈ VDD - |VGS - VTH|",
            # Extra pool so we can de-dup and still emit A–J reliably
            "Max swing ≈ VDD - (VDSsat_n + VDSsat_p)",
            "Max swing ≈ VDD - 2·|Vov|",
            "Max swing ≈ VDD - 4·|Vov|",
            "Max swing ≈ VDD - |Vov|",
            "Max swing ≈ VDD - (|VGS - VTH| + |VDsat|)",
            "Max swing ≈ VDD - (VTH_n + |VDsat|)",
            "Max swing ≈ VDD - (VTH_p + |VDsat|)",
        ]
    elif formula_type == "power":
        # IMPORTANT: power distractors must remain grounded and should not introduce magic symbols
        # like Itail, Rtail, A0, or gm with no subscript. Prefer I_D,{Mx}-style expressions.
        # If we can't infer any device-current terms from the correct formula, return an empty pool
        # and let the caller provide aspect-specific distractors.
        alternatives = []
    elif formula_type == "noise":
        alternatives = [
            "Vn,out² ≈ 4kT·(2/3gm)",
            "Vn,out² ≈ 16kT/gm",
            "Vn,out² ≈ 8kT·gm",
            "Vn,out² ≈ 4kT/(gm·ro)",
            "Vn,out² ≈ 8kT/(gm·√3)",
            "Vn,out² ≈ 8kT·ro/(3gm)",
            "Vn,out² ≈ √(8kT/(3gm))",
            "Vn,out² ≈ 8kT/(3gm²)",
            "Vn,out² ≈ 16kT/(3gm)",
            "Vn,out² ≈ 4kT/gm",
            "Vn,out² ≈ 8kT/gm",
            "Vn,out² ≈ 8kT/(6gm)",
        ]
    else:
        alternatives = ["Alternative " + chr(65+i) for i in range(14)]
    
    # Remove the correct answer if it accidentally got included
    return [d for d in alternatives if d != correct_formula]


def _power_distractors_device_grounded(correct_answer: str) -> List[str]:
    """
    Generate grounded distractors for quiescent power:
    - Only uses VDD and sums/scalings of DC device currents I_D,{<id>}
    - Allows swapping device subscripts to {X1}/{X2}/{X3} to create realistic wrong-device distractors
    """
    s = (correct_answer or "").strip()
    op = "≈" if "≈" in s else ("=" if "=" in s else None)
    if not op or op not in s:
        return []
    lhs, rhs = s.split(op, 1)
    lhs = lhs.strip()
    rhs = rhs.strip()

    # Extract device-current tokens (brace form preferred).
    toks = list(dict.fromkeys(re.findall(r"I_D,\{([A-Za-z0-9_]+)\}", rhs)))
    if not toks:
        # also support already-rendered form I_D,M123...
        toks = list(dict.fromkeys(re.findall(r"\\bI_D,([A-Za-z0-9_]+)\\b", rhs)))
    if not toks:
        return []

    # Build a simple sum expression from the extracted tokens.
    def _id(tok: str) -> str:
        return f"I_D,{{{tok}}}"

    # Attempt to find the sum inside parentheses: VDD·( ... )
    sum_expr = None
    m = re.search(r"VDD\s*[*·]\s*\((.*)\)\s*$", rhs)
    if m:
        sum_expr = m.group(1).strip()
    else:
        # Otherwise, just use a canonical sum of extracted tokens
        sum_expr = " + ".join(_id(t) for t in toks)

    def fmt(rhs_new: str) -> str:
        return f"{lhs} {op} {rhs_new}"

    out: List[str] = []
    # Global scaling mistakes (still grounded)
    out.extend([
        fmt(f"(VDD/2)·({sum_expr})"),
        fmt(f"2·VDD·({sum_expr})"),
        fmt(f"VDD·({sum_expr})/2"),
        fmt(f"4·VDD·({sum_expr})"),
        fmt(f"VDD·({sum_expr})/4"),
    ])

    # Drop-one-term mistakes (forget a branch current)
    if len(toks) >= 2:
        out.append(fmt(f"VDD·(" + " + ".join(_id(t) for t in toks[:-1]) + ")"))
        out.append(fmt(f"VDD·(" + " + ".join(_id(t) for t in toks[1:]) + ")"))

    # Swap-one-device mistakes using X roles (runtime-mapped to existing MOS IDs)
    for wrong in ["X1", "X2", "X3"]:
        out.append(fmt(f"VDD·(" + " + ".join((_id(wrong) if i == 0 else _id(t)) for i, t in enumerate(toks)) + ")"))
        if len(toks) >= 2:
            out.append(fmt(f"VDD·(" + " + ".join((_id(wrong) if i == 1 else _id(t)) for i, t in enumerate(toks)) + ")"))

    # Add an extra (wrong) device current term
    out.append(fmt(f"VDD·(({sum_expr}) + I_D,{{X1}})"))

    # Keep only those that are clearly grounded
    out2: List[str] = []
    seen: set[str] = set()
    for c in out:
        if "I_D," not in c:
            continue
        # Avoid exact duplicates (final semantic dedupe happens in _finalize_mc_key)
        k = re.sub(r"\\s+", "", c)
        if k in seen:
            continue
        seen.add(k)
        out2.append(c)
    return out2


def generate_mc_answer_key(question_id: str, track: str, aspect: str, item_id: str) -> Dict[str, Any]:
    """Generate MC answer key for a specific question."""
    template_role_map: Dict[str, str] = {}
    if track == "debugging" and "device_swap" in aspect:
        device_info = DEBUGGING_OTA_SWAP_ANSWERS.get(item_id, {})
        device = device_info.get("device", "M3")
        correct_type = device_info.get("correct_type", "NMOS")
        wrong_type = "PMOS" if correct_type == "NMOS" else "NMOS"
        correct_answer = f"{device} is incorrectly typed as {wrong_type} when it should be {correct_type}. Fix: change {device}'s model to the correct type and update body connection appropriately."
        # Generate distractors
        all_devices = [f"M{i}" for i in range(1, 13)]
        distractors = generate_device_swap_distractors(device, all_devices, correct_type)
        
    elif track == "debugging" and "feedback_polarity" in aspect:
        feedback_info = DEBUGGING_FEEDBACK_POLARITY_ANSWERS.get(item_id, {})
        issue = feedback_info.get("issue", "positive feedback")
        fix = feedback_info.get("fix", "swap opamp inputs")
        
        correct_answer = f"The circuit has {issue} instead of negative feedback. Fix: {fix}."
        distractors = [
            "Resistor values are incorrect. Fix: recalculate R1 based on desired gain.",
            "Capacitor is missing at critical node. Fix: add compensation capacitor.",
            "Op-amp is saturating due to insufficient supply voltage. Fix: increase VDD.",
            "Input bias current causes DC offset. Fix: add input bias current compensation.",
            "Feedback network has too much attenuation. Fix: increase feedback resistor.",
            "Circuit is oscillating due to insufficient phase margin. Fix: add lead compensation.",
            "Op-amp bandwidth is insufficient. Fix: select faster op-amp.",
            "Load capacitance is too large. Fix: add buffer stage.",
            "Common-mode rejection is inadequate. Fix: use fully differential topology.",
        ]
        
    # -------------------------
    # ANALYSIS: OTA
    # -------------------------
    elif track == "analysis" and aspect == "gain_dc":
        canon = _ota_canonical_mc_formula(item_id, aspect)
        if canon:
            # Use the canonical sign convention (do not force magnitude).
            correct_answer = canon
            # Device-grounded distractors only (avoid unrealistic gm·ro without subscripts).
            distractors = _gain_dc_distractors_device_grounded(correct_answer)
            for cand in [
                correct_answer.replace("/2", ""),
                correct_answer.replace("/2", "/4"),
                correct_answer.replace("||", "+"),
                correct_answer.replace("A0", "A0,od"),
            ]:
                if cand and cand != correct_answer and cand not in distractors:
                    distractors.append(cand)
            distractors = _harmonize_choice_format(correct_answer, distractors)
            return _finalize_mc_key(question_id, track, aspect, correct_answer, distractors, template_role_map)

        # Full expressions in terms of device-level gm/ro (no shorthand like gm·ro/2).
        # We express gm_eff = (gm_INP + gm_INN)/2 and r_out = r_out_n || r_out_p.
        #
        # Use stack roles (N1..N3, P1..P2) from the runtime-shuffled artifact.
        # - For simple 5T OTAs, N1 is typically an input device at the output; we intentionally
        #   ignore the tail device in r_out_n and use ro_{N1} only (matches the user's example).
        # - For cascode/telescopic stacks, include (gm·ro + 1) factors for each additional stacked device.
        tmpl_path = Path(__file__).parent.parent / "data" / "dev" / "templates" / "ota" / item_id / "netlist.sp"
        tmpl_text = ""
        if tmpl_path.exists():
            try:
                tmpl_text = tmpl_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                tmpl_text = tmpl_path.read_text(encoding="utf-16")

        def _parse_mos(net: str):
            out = []
            for raw in (net or "").splitlines():
                s = raw.strip()
                if not s or s.startswith(("*", ";", "//", ".")):
                    continue
                if not s[:1].upper().startswith("M"):
                    continue
                parts = s.split()
                if len(parts) < 6:
                    continue
                mid, d, g, src, b, model = parts[:6]
                out.append({"id": mid, "d": d, "s": src, "g": g, "model": model.lower()})
            return out

        def _find_out_node(net: str) -> str:
            nodes = set()
            for m in _parse_mos(net):
                nodes.add((m.get("d") or "").lower())
                nodes.add((m.get("s") or "").lower())
            for cand in ("vout", "voutn", "voutp", "vop", "von", "outp", "outn", "out"):
                if cand in nodes:
                    return cand
            return "vout" if "vout" in nodes else ""

        def _is_input_gate(g: str) -> bool:
            return (g or "").lower() in {"vinp", "vinn", "vip", "vin", "inp", "inn", "in_p", "in_n", "in", "in+", "in-"}

        out_node = _find_out_node(tmpl_text)
        mos_t = _parse_mos(tmpl_text)
        # Detect if the first NMOS device in the output->ground stack is an input device (5T diff pair case).
        n1_is_input = False
        if out_node:
            for m in mos_t:
                if (m.get("d") or "").lower() == out_node and _is_input_gate(m.get("g") or ""):
                    n1_is_input = True
                    break

        # Decide how many NMOS stack devices to include in r_out_n:
        # - if N1 is an input device at the output: include only ro_{N1}
        # - else: include 1..3 stack devices (N1, N2, N3)
        n_terms = 1 if n1_is_input else (3 if "{N3}" in "{N3}" else 3)  # placeholder; runtime picks N2/N3 existence
        # We'll build expressions that conditionally include N2/N3 only if present at runtime;
        # but MCQs should render without braces, so we include up to N3 and rely on role mapping.
        # If an OTA doesn't have N3, role selection maps N3 to a real device but swing logic ensures
        # N3 exists only for telescopic; so for non-telescopic, avoid referencing N3 by using template BFS.

        # Infer NMOS stack length, but stop at the input device (exclude tail devices).
        # For example, cascode diff pair: output->cascode->input (do not include tail).
        def _shortest_dev_path(net: str, pol: str, start: str, targets: set[str], max_devs: int) -> List[str]:
            from collections import deque
            mos = _parse_mos(net)

            def _is_pol(model: str) -> bool:
                m = (model or "").lower()
                if pol == "n":
                    return ("nch" in m) or ("nfet" in m) or ("nmos" in m)
                return ("pch" in m) or ("pfet" in m) or ("pmos" in m)

            adj: Dict[str, List[tuple[str, str]]] = {}
            for m in mos:
                if not _is_pol(m.get("model", "")):
                    continue
                a = (m.get("d") or "").strip()
                b = (m.get("s") or "").strip()
                mid = (m.get("id") or "").strip()
                if not a or not b or not mid:
                    continue
                adj.setdefault(a, []).append((b, mid))
                adj.setdefault(b, []).append((a, mid))

            q = deque([(start, [])])
            seen: set[tuple[str, int]] = {(start, 0)}
            best: List[str] | None = None
            while q:
                node, dpath = q.popleft()
                if node.lower() in {t.lower() for t in targets}:
                    if best is None or len(dpath) < len(best):
                        best = dpath
                    continue
                if len(dpath) >= max_devs:
                    continue
                for nxt, did in adj.get(node, []):
                    st = (nxt, len(dpath) + 1)
                    if st in seen:
                        continue
                    seen.add(st)
                    q.append((nxt, dpath + [did]))
            return best or []

        # Compute raw paths
        n_path_raw = _shortest_dev_path(tmpl_text, "n", out_node or "vout", {"0", "gnd", "vss"}, max_devs=3) if out_node else []
        p_path_raw = _shortest_dev_path(tmpl_text, "p", out_node or "vout", {"vdd", "VDD"}, max_devs=2) if out_node else []

        # Trim NMOS path to last input device in the path (drops tail devices).
        input_ids = {m["id"] for m in mos_t if _is_input_gate(m.get("g") or "")}
        last_in_idx = None
        for i in range(len(n_path_raw) - 1, -1, -1):
            if n_path_raw[i] in input_ids:
                last_in_idx = i
                break
        if last_in_idx is not None:
            n_path_raw = n_path_raw[: last_in_idx + 1]

        n_len = len(n_path_raw)
        p_len = len(p_path_raw)
        has_n3 = (not n1_is_input) and (n_len >= 3)
        has_n2 = (not n1_is_input) and (n_len >= 2)
        has_p2 = (p_len >= 2)

        gm_eff = "(gm_{INP} + gm_{INN})/2"
        # Use dedicated output-resistance stack placeholders (RN*/RP*) so we don't collide with swing placeholders (N*/P*).
        # Convention:
        # - RN1 is the bottom device whose ro is being multiplied (typically the input device at the output node)
        # - RN2/RN3 are cascodes above RN1
        # - RP1 is the bottom PMOS device at the output node (mirror/load)
        # - RP2 is the cascode above RP1
        rout_n = "ro_{RN1}" if n1_is_input else (
            "(gm_{RN3}·ro_{RN3} + 1)·(gm_{RN2}·ro_{RN2} + 1)·ro_{RN1}" if has_n3 else
            "(gm_{RN2}·ro_{RN2} + 1)·ro_{RN1}" if has_n2 else
            "ro_{RN1}"
        )
        rout_p = "(gm_{RP2}·ro_{RP2} + 1)·ro_{RP1}" if has_p2 else "ro_{RP1}"
        # If the OTA is fully differential (both voutn and voutp exist), use:
        # rout_eff = (rout_at_voutn + rout_at_voutp)/2
        # A0 ≈ gm_eff · rout_eff
        nodes = set()
        for m in mos_t:
            nodes.add((m.get("d") or "").lower())
            nodes.add((m.get("s") or "").lower())
        is_diff = ("voutn" in nodes and "voutp" in nodes) or ("von" in nodes and "vop" in nodes) or ("outn" in nodes and "outp" in nodes)
        if is_diff:
            # Use side-specific stack roles; run_eval will map these from each output node's stack.
            rout_n_neg = "ro_{RN1N}" if n1_is_input else (
                "(gm_{RN3N}·ro_{RN3N} + 1)·(gm_{RN2N}·ro_{RN2N} + 1)·ro_{RN1N}" if has_n3 else
                "(gm_{RN2N}·ro_{RN2N} + 1)·ro_{RN1N}" if has_n2 else
                "ro_{RN1N}"
            )
            rout_p_neg = "(gm_{RP2N}·ro_{RP2N} + 1)·ro_{RP1N}" if has_p2 else "ro_{RP1N}"
            rout_n_pos = "ro_{RN1P}" if n1_is_input else (
                "(gm_{RN3P}·ro_{RN3P} + 1)·(gm_{RN2P}·ro_{RN2P} + 1)·ro_{RN1P}" if has_n3 else
                "(gm_{RN2P}·ro_{RN2P} + 1)·ro_{RN1P}" if has_n2 else
                "ro_{RN1P}"
            )
            rout_p_pos = "(gm_{RP2P}·ro_{RP2P} + 1)·ro_{RP1P}" if has_p2 else "ro_{RP1P}"
            rout_eff = f"(({rout_n_neg} || {rout_p_neg}) + ({rout_n_pos} || {rout_p_pos}))/2"
            correct_answer = f"DC gain A0 ≈ {gm_eff}·{rout_eff}"
        else:
            correct_answer = f"DC gain A0 ≈ {gm_eff}·({rout_n} || {rout_p})"

        # Distractors: wrong device subscripts, missing '+1', wrong averaging, wrong stacking.
        distractors = [
            f"DC gain A0 ≈ (gm_{{INP}} + gm_{{INN}})·({rout_n} || {rout_p})",
            f"DC gain A0 ≈ (gm_{{INP}} + gm_{{INN}})/4·({rout_n} || {rout_p})",
            f"DC gain A0 ≈ (gm_{{INP}}·gm_{{INN}})·({rout_n} || {rout_p})",
            f"DC gain A0 ≈ {gm_eff}·({rout_n} + {rout_p})",
            f"DC gain A0 ≈ {gm_eff}·({rout_n} || ro_{{RP1}})",
            f"DC gain A0 ≈ {gm_eff}·(ro_{{RN1}} || {rout_p})",
            f"DC gain A0 ≈ (gm_{{X1}} + gm_{{INN}})/2·({rout_n} || {rout_p})",
            f"DC gain A0 ≈ (gm_{{INP}} + gm_{{X2}})/2·({rout_n} || {rout_p})",
            f"DC gain A0 ≈ {gm_eff}·((gm_{{RN2}}·ro_{{RN2}})·ro_{{RN1}} || {rout_p})",
            f"DC gain A0 ≈ {gm_eff}·({rout_n} || (gm_{{RP2}}·ro_{{RP2}})·ro_{{RP1}})",
            f"DC gain A0 ≈ {gm_eff}·({rout_n} || {rout_p})/2",
        ]
        # If the template doesn't have a second NMOS/PMOS stack device, remove any distractor
        # that would leak {N2}/{N3} or {P2} placeholders at runtime.
        if not has_n2:
            distractors = [d for d in distractors if "{RN2}" not in d and "{RN3}" not in d]
        if not has_p2:
            distractors = [d for d in distractors if "{RP2}" not in d]
        # For fully differential expressions, don't allow single-ended-only placeholders.
        if is_diff:
            # Drop any distractor that references non-side-specific stack roles.
            distractors = [d for d in distractors if not any(tok in d for tok in ("{RN1}", "{RN2}", "{RN3}", "{RP1}", "{RP2}"))]
        else:
            # Drop any distractor that references side-specific roles.
            distractors = [d for d in distractors if not any(tok in d for tok in ("{RN1N}", "{RN2N}", "{RN3N}", "{RP1N}", "{RP2N}", "{RN1P}", "{RN2P}", "{RN3P}", "{RP1P}", "{RP2P}"))]

        # Backfill: after topology-aware filtering, some single-ended OTAs (e.g. with no N2/P2)
        # may not have enough unique distractors to reach 10 total options.
        # Generate additional plausible algebraic variants that only use placeholders that exist
        # for the current topology (no N2/P2 if absent; no side-specific roles unless is_diff).
        def _norm_choice(s: str) -> str:
            return (s or "").lower().replace(" ", "")

        def _add_unique(items: List[str], cand: str) -> None:
            if not cand:
                return
            if _norm_choice(cand) == _norm_choice(correct_answer):
                return
            if any(_norm_choice(cand) == _norm_choice(x) for x in items):
                return
            items.append(cand)

        # Which placeholder tokens are allowed in additional distractors?
        if is_diff:
            base_rout = "(((gm_{RN2N}·ro_{RN2N} + 1)·ro_{RN1N} || (gm_{RP2N}·ro_{RP2N} + 1)·ro_{RP1N}) + ((gm_{RN2P}·ro_{RN2P} + 1)·ro_{RN1P} || (gm_{RP2P}·ro_{RP2P} + 1)·ro_{RP1P}))/2"
            base_expr = f"{gm_eff}·{base_rout}"
        else:
            base_rout = f"({rout_n} || {rout_p})"
            base_expr = f"{gm_eff}·{base_rout}"

        # Algebraic distractor pool (no extra placeholders beyond what base_expr uses)
        extra_pool = [
            f"DC gain A0 ≈ {base_expr}/2",
            f"DC gain A0 ≈ 2·{base_expr}",
            f"DC gain A0 ≈ ({base_expr})²",
            f"DC gain A0 ≈ √({base_expr})",
            f"DC gain A0 ≈ {gm_eff}·{base_rout.replace('||', '+')}",
            f"DC gain A0 ≈ (gm_{{INP}} + gm_{{INN}})·{base_rout}",
            f"DC gain A0 ≈ (gm_{{INP}} + gm_{{INN}})/4·{base_rout}",
            f"DC gain A0 ≈ (gm_{{X1}} + gm_{{INN}})/2·{base_rout}",
            f"DC gain A0 ≈ (gm_{{INP}} + gm_{{X2}})/2·{base_rout}",
            f"DC gain A0 ≈ {gm_eff}/{base_rout}",
        ]

        # Remove any extras that would introduce illegal placeholders for this topology.
        if not is_diff:
            if not has_n2:
                extra_pool = [x for x in extra_pool if "{RN2}" not in x and "{RN3}" not in x]
            if not has_p2:
                extra_pool = [x for x in extra_pool if "{RP2}" not in x]

        for cand in extra_pool:
            _add_unique(distractors, cand)
        
    elif track == "analysis" and aspect == "gbw":
        canon = _ota_canonical_mc_formula(item_id, aspect)
        if canon:
            correct_answer = canon
            distractors = _gbw_distractors_hz(correct_answer)
            return _finalize_mc_key(question_id, track, aspect, correct_answer, distractors, template_role_map)
        # Subscript gm to encourage device-ID grounded reasoning on the shuffled netlist.
        correct_formula = ANALYSIS_OTA_GBW.get(item_id, "gm/CL")
        # Map CL/Cc symbols to actual capacitor instance names from the OTA template netlist
        # so answer choices only reference components that exist in the artifact.
        ota_tmpl_path = Path(__file__).parent.parent / "data" / "dev" / "templates" / "ota" / item_id / "netlist.sp"
        ota_tmpl_text = ""
        if ota_tmpl_path.exists():
            try:
                ota_tmpl_text = ota_tmpl_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                ota_tmpl_text = ota_tmpl_path.read_text(encoding="utf-16")
        cap_load: str | None = None
        cap_comp: str | None = None
        caps: List[tuple[str, str, str]] = []
        for ln in ota_tmpl_text.splitlines():
            s = ln.strip()
            if not s or s.startswith(("*", ";", "//", ".")):
                continue
            parts = s.split()
            if parts and parts[0][:1].upper() == "C" and len(parts) >= 3:
                cid, n1, n2 = parts[0], parts[1], parts[2]
                caps.append((cid, n1, n2))
        # Prefer cap from vout to ground as CL
        for cid, n1, n2 in caps:
            if {"vout", "0"} == {n1.lower(), n2.lower()}:
                cap_load = cid
                break
        if not cap_load and caps:
            cap_load = caps[0][0]
        # Any other capacitor is treated as Cc (comp cap) when present
        for cid, _n1, _n2 in caps:
            if cap_load and cid != cap_load:
                cap_comp = cid
                break

        def _capify(expr: str) -> str:
            if not expr:
                return expr
            if cap_load:
                expr = re.sub(r"(?<![A-Za-z0-9_])CL(?![A-Za-z0-9_])", cap_load, expr)
            # Only keep Cc references if a real comp cap exists; otherwise we will drop those choices.
            if cap_comp:
                expr = re.sub(r"(?<![A-Za-z0-9_])Cc(?![A-Za-z0-9_])", cap_comp, expr)
            return expr

        if "gm1/Cc" in correct_formula:
            correct_answer = _capify("GBW ≈ gm_{IN}/Cc")
            distractors = [
                _capify("GBW ≈ gm_{OUTN}/Cc"),
                _capify("GBW ≈ gm_{IN}/CL"),
                _capify("GBW ≈ gm_{IN}/(2·Cc)"),
                _capify("GBW ≈ (gm_{IN})²/Cc"),
                _capify("GBW ≈ Cc/gm_{IN}"),
                _capify("GBW ≈ gm_{IN}/(Cc + CL)"),
                "GBW ≈ gm_{OUTP}/CL",
                _capify("GBW ≈ gm_{IN}/(Cc·CL)"),
                _capify("GBW ≈ gm_{IN}·Cc"),
            ]
        else:
            correct_answer = _capify("GBW ≈ gm_{IN}/CL")
            distractors = [
                _capify("GBW ≈ gm_{OUTN}/CL"),
                _capify("GBW ≈ gm_{OUTP}/CL"),
                _capify("GBW ≈ gm_{X1}/CL"),
                _capify("GBW ≈ gm_{X2}/CL"),
                _capify("GBW ≈ gm_{IN}/Cc"),
                _capify("GBW ≈ (gm_{IN})²/CL"),
                _capify("GBW ≈ CL/gm_{IN}"),
                _capify("GBW ≈ gm_{IN}/(2·CL)"),
                _capify("GBW ≈ gm_{IN}/(CL + Cc)"),
                _capify("GBW ≈ gm_{IN}/(CL·Cc)"),
                _capify("GBW ≈ gm_{IN}·CL"),
                _capify("GBW ≈ gm_{IN}/(2πCL)"),
            ]
        # If no comp capacitor exists in the template, remove any choice that still references Cc.
        if cap_comp is None:
            distractors = [d for d in distractors if "Cc" not in d]
            # Also sanitize correct_answer if something is inconsistent (shouldn't happen)
            if "Cc" in correct_answer:
                correct_answer = _capify(correct_answer).replace("Cc", cap_load or "CL")

    elif track == "analysis" and aspect == "psrr":
        canon = _ota_canonical_mc_formula(item_id, aspect)
        if canon:
            correct_answer = canon
            distractors = _psrr_distractors_device_grounded(correct_answer)
            distractors = _harmonize_choice_format(correct_answer, distractors)
            return _finalize_mc_key(question_id, track, aspect, correct_answer, distractors, template_role_map)
        # Expanded transistor-parameter form:
        # - Replace gm shorthand with gm_eff = (gm_INP + gm_INN)/2 (diff-pair effective gm)
        # - Replace ro shorthand with explicit output resistance (rout_n || rout_p), including cascode stack factors
        correct_formula = ANALYSIS_OTA_PSRR.get(item_id, "PSRR+ ≈ (gm·ro)")

        # ota003 is not expressed as gm/ro in our key dict.
        if "CMRR" in correct_formula:
            correct_answer = correct_formula.replace("≈", "≈").strip()
            distractors = generate_formula_distractors(correct_answer, "psrr")
        else:
            tmpl_path = Path(__file__).parent.parent / "data" / "dev" / "templates" / "ota" / item_id / "netlist.sp"
            tmpl_text = ""
            if tmpl_path.exists():
                try:
                    tmpl_text = tmpl_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    tmpl_text = tmpl_path.read_text(encoding="utf-16")

            def _parse_mos(net: str):
                out = []
                for raw in (net or "").splitlines():
                    s = raw.strip()
                    if not s or s.startswith(("*", ";", "//", ".")):
                        continue
                    if not s[:1].upper().startswith("M"):
                        continue
                    parts = s.split()
                    if len(parts) < 6:
                        continue
                    mid, d, g, src, b, model = parts[:6]
                    out.append({"id": mid, "d": d, "s": src, "g": g, "model": model.lower()})
                return out

            def _find_out_node(net: str) -> str:
                nodes = set()
                for m in _parse_mos(net):
                    nodes.add((m.get("d") or "").lower())
                    nodes.add((m.get("s") or "").lower())
                for cand in ("vout", "voutn", "voutp", "vop", "von", "outp", "outn", "out"):
                    if cand in nodes:
                        return cand
                return "vout" if "vout" in nodes else ""

            def _is_input_gate(g: str) -> bool:
                return (g or "").lower() in {"vinp", "vinn", "vip", "vin", "inp", "inn", "in_p", "in_n", "in", "in+", "in-"}

            out_node = _find_out_node(tmpl_text)
            mos_t = _parse_mos(tmpl_text)
            n1_is_input = False
            if out_node:
                for m in mos_t:
                    if (m.get("d") or "").lower() == out_node and _is_input_gate(m.get("g") or ""):
                        n1_is_input = True
                        break

            def _bfs_len(net: str, pol: str, start: str, targets: set[str], max_devs: int) -> int:
                from collections import deque
                mos = _parse_mos(net)

                def _is_pol(model: str) -> bool:
                    m = (model or "").lower()
                    if pol == "n":
                        return ("nch" in m) or ("nfet" in m) or ("nmos" in m)
                    return ("pch" in m) or ("pfet" in m) or ("pmos" in m)

                adj = {}
                for m in mos:
                    if not _is_pol(m.get("model", "")):
                        continue
                    a = (m.get("d") or "").lower()
                    b = (m.get("s") or "").lower()
                    if not a or not b:
                        continue
                    adj.setdefault(a, set()).add(b)
                    adj.setdefault(b, set()).add(a)
                q = deque([(start.lower(), 0)])
                seen = {start.lower()}
                while q:
                    node, dist = q.popleft()
                    if node in {t.lower() for t in targets}:
                        return dist
                    if dist >= max_devs:
                        continue
                    for nxt in adj.get(node, set()):
                        if nxt in seen:
                            continue
                        seen.add(nxt)
                        q.append((nxt, dist + 1))
                return -1

            n_len = _bfs_len(tmpl_text, "n", out_node or "vout", {"0", "gnd", "vss"}, max_devs=3) if out_node else -1
            p_len = _bfs_len(tmpl_text, "p", out_node or "vout", {"vdd"}, max_devs=2) if out_node else -1
            has_n3 = (not n1_is_input) and (n_len >= 3)
            has_n2 = (not n1_is_input) and (n_len >= 2)
            has_p2 = (p_len >= 2)

            gm_eff = "(gm_{INP} + gm_{INN})/2"
            rout_n = "ro_{RN1}" if n1_is_input else (
                "(gm_{RN3}·ro_{RN3} + 1)·(gm_{RN2}·ro_{RN2} + 1)·ro_{RN1}" if has_n3 else
                "(gm_{RN2}·ro_{RN2} + 1)·ro_{RN1}" if has_n2 else
                "ro_{RN1}"
            )
            rout_p = "(gm_{RP2}·ro_{RP2} + 1)·ro_{RP1}" if has_p2 else "ro_{RP1}"
            gro = f"{gm_eff}·({rout_n} || {rout_p})"

            if "³" in correct_formula:
                correct_answer = f"PSRR+ ≈ ({gro})³"
            elif "²" in correct_formula:
                correct_answer = f"PSRR+ ≈ ({gro})²"
            else:
                correct_answer = f"PSRR+ ≈ {gro}"

            # Distractors: wrong exponent, wrong gm averaging, wrong devices, wrong parallel/series.
            distractors = [
                f"PSRR+ ≈ {gm_eff}·({rout_n} + {rout_p})",
                f"PSRR+ ≈ (gm_{{INP}} + gm_{{INN}})·({rout_n} || {rout_p})",
                f"PSRR+ ≈ (gm_{{INP}} + gm_{{INN}})/4·({rout_n} || {rout_p})",
                f"PSRR+ ≈ gm_{{X1}}·({rout_n} || {rout_p})",
                f"PSRR+ ≈ {gm_eff}·(ro_{{RN1}} || ro_{{RP1}})",
                f"PSRR+ ≈ ({gro})²",
                f"PSRR+ ≈ ({gro})³",
                f"PSRR+ ≈ √({gro})",
                f"PSRR+ ≈ {gro}/2",
                f"PSRR+ ≈ {gm_eff}/({rout_n} || {rout_p})",
            ]
            # Remove the correct one if we accidentally duplicated it
            distractors = [d for d in distractors if d != correct_answer]

    elif track == "analysis" and aspect == "rout":
        canon = _ota_canonical_mc_formula(item_id, aspect)
        if canon:
            correct_answer = canon
            distractors = _rout_distractors_device_grounded(correct_answer)
            distractors = _harmonize_choice_format(correct_answer, distractors)
            return _finalize_mc_key(question_id, track, aspect, correct_answer, distractors, template_role_map)
        # Full device-level expression for output resistance:
        # rout ≈ r_out_n || r_out_p, where each side includes (gm·ro + 1) factors for stacked devices.
        tmpl_path = Path(__file__).parent.parent / "data" / "dev" / "templates" / "ota" / item_id / "netlist.sp"
        tmpl_text = ""
        if tmpl_path.exists():
            try:
                tmpl_text = tmpl_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                tmpl_text = tmpl_path.read_text(encoding="utf-16")

        def _parse_mos(net: str):
            out = []
            for raw in (net or "").splitlines():
                s = raw.strip()
                if not s or s.startswith(("*", ";", "//", ".")):
                    continue
                if not s[:1].upper().startswith("M"):
                    continue
                parts = s.split()
                if len(parts) < 6:
                    continue
                mid, d, g, src, b, model = parts[:6]
                out.append({"id": mid, "d": d, "s": src, "g": g, "model": model.lower()})
            return out

        def _find_out_node(net: str) -> str:
            nodes = set()
            for m in _parse_mos(net):
                nodes.add((m.get("d") or "").lower())
                nodes.add((m.get("s") or "").lower())
            for cand in ("vout", "voutn", "voutp", "vop", "von", "outp", "outn", "out"):
                if cand in nodes:
                    return cand
            return "vout" if "vout" in nodes else ""

        def _is_input_gate(g: str) -> bool:
            return (g or "").lower() in {"vinp", "vinn", "vip", "vin", "inp", "inn", "in_p", "in_n", "in", "in+", "in-"}

        out_node = _find_out_node(tmpl_text)
        mos_t = _parse_mos(tmpl_text)
        n1_is_input = False
        if out_node:
            for m in mos_t:
                if (m.get("d") or "").lower() == out_node and _is_input_gate(m.get("g") or ""):
                    n1_is_input = True
                    break

        def _bfs_len(net: str, pol: str, start: str, targets: set[str], max_devs: int) -> int:
            from collections import deque
            mos = _parse_mos(net)
            def _is_pol(model: str) -> bool:
                m = (model or "").lower()
                if pol == "n":
                    return ("nch" in m) or ("nfet" in m) or ("nmos" in m)
                return ("pch" in m) or ("pfet" in m) or ("pmos" in m)
            adj = {}
            for m in mos:
                if not _is_pol(m.get("model", "")):
                    continue
                a = (m.get("d") or "").lower()
                b = (m.get("s") or "").lower()
                if not a or not b:
                    continue
                adj.setdefault(a, set()).add(b)
                adj.setdefault(b, set()).add(a)
            q = deque([(start.lower(), 0)])
            seen = {start.lower()}
            while q:
                node, dist = q.popleft()
                if node in {t.lower() for t in targets}:
                    return dist
                if dist >= max_devs:
                    continue
                for nxt in adj.get(node, set()):
                    if nxt in seen:
                        continue
                    seen.add(nxt)
                    q.append((nxt, dist + 1))
            return -1

        n_len = _bfs_len(tmpl_text, "n", out_node or "vout", {"0", "gnd", "vss"}, max_devs=3) if out_node else -1
        p_len = _bfs_len(tmpl_text, "p", out_node or "vout", {"vdd"}, max_devs=2) if out_node else -1
        has_n3 = (not n1_is_input) and (n_len >= 3)
        has_n2 = (not n1_is_input) and (n_len >= 2)
        has_p2 = (p_len >= 2)

        rout_n = "ro_{RN1}" if n1_is_input else (
            "(gm_{RN3}·ro_{RN3} + 1)·(gm_{RN2}·ro_{RN2} + 1)·ro_{RN1}" if has_n3 else
            "(gm_{RN2}·ro_{RN2} + 1)·ro_{RN1}" if has_n2 else
            "ro_{RN1}"
        )
        rout_p = "(gm_{RP2}·ro_{RP2} + 1)·ro_{RP1}" if has_p2 else "ro_{RP1}"
        correct_answer = f"rout ≈ {rout_n} || {rout_p}"
        distractors = [
            f"rout ≈ {rout_n} + {rout_p}",
            "rout ≈ ro_{RN1} || ro_{RP1}",
            f"rout ≈ {rout_n}",
            f"rout ≈ {rout_p}",
            f"rout ≈ (gm_{{RN2}}·ro_{{RN2}})·ro_{{RN1}} || {rout_p}",
            f"rout ≈ {rout_n} || (gm_{{RP2}}·ro_{{RP2}})·ro_{{RP1}}",
            "rout ≈ ro_{X1}",
            "rout ≈ ro_{RN1}·ro_{RP1}",
            "rout ≈ √(ro_{RN1})",
            "rout ≈ 2·(ro_{RN1} || ro_{RP1})",
        ]

    elif track == "analysis" and aspect == "swing":
        # Output swing limits in terms of overdrive voltages for the actual stack devices.
        # User requirement:
        # - folded cascodes and single-ended cascodes:  Vout,min ≈ Vov_{N1} + Vov_{N2}
        #                                            Vout,max ≈ VDD - Vov_{P1} - Vov_{P2}
        # - telescopic:                                Vout,min ≈ Vov_{N1} + Vov_{N2} + Vov_{N3}
        #                                            Vout,max ≈ VDD - Vov_{P1} - Vov_{P2}
        #
        # We infer whether N3 exists from the OTA template netlist's NMOS stack length (vout -> 0 path).
        tmpl_path = Path(__file__).parent.parent / "data" / "dev" / "templates" / "ota" / item_id / "netlist.sp"
        tmpl_text = ""
        if tmpl_path.exists():
            try:
                tmpl_text = tmpl_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                tmpl_text = tmpl_path.read_text(encoding="utf-16")

        # Minimal stack inference: count NMOS/PMOS devices in the shortest D-S path from output to rails.
        def _parse_mos(net: str):
            out = []
            for raw in (net or "").splitlines():
                s = raw.strip()
                if not s or s.startswith(("*", ";", "//", ".")):
                    continue
                if not s[:1].upper().startswith("M"):
                    continue
                parts = s.split()
                if len(parts) < 6:
                    continue
                mid, d, g, src, b, model = parts[:6]
                out.append({"id": mid, "d": d, "s": src, "model": model.lower()})
            return out

        def _find_out_node(net: str) -> str:
            # Prefer vout/voutn/voutp if present, else empty.
            nodes = set()
            for m in _parse_mos(net):
                nodes.add((m.get("d") or "").lower())
                nodes.add((m.get("s") or "").lower())
            for cand in ("vout", "voutn", "voutp", "vop", "von", "outp", "outn", "out"):
                if cand in nodes:
                    return cand
            return "vout" if "vout" in nodes else ""

        def _bfs_len(net: str, pol: str, start: str, targets: set[str], max_devs: int) -> int:
            from collections import deque
            mos = _parse_mos(net)
            adj = {}
            for m in mos:
                model = m["model"]
                is_n = ("nch" in model) or ("nfet" in model) or ("nmos" in model)
                is_p = ("pch" in model) or ("pfet" in model) or ("pmos" in model)
                if pol == "n" and not is_n:
                    continue
                if pol == "p" and not is_p:
                    continue
                a = (m["d"] or "").lower()
                b = (m["s"] or "").lower()
                if not a or not b:
                    continue
                adj.setdefault(a, []).append(b)
                adj.setdefault(b, []).append(a)
            q = deque([(start, 0)])
            seen = {start}
            while q:
                node, depth = q.popleft()
                if node in targets:
                    return depth
                if depth >= max_devs:
                    continue
                for nxt in adj.get(node, []):
                    if nxt in seen:
                        continue
                    seen.add(nxt)
                    q.append((nxt, depth + 1))
            return 0

        out_node = _find_out_node(tmpl_text)
        n_len = _bfs_len(tmpl_text, "n", out_node, {"0", "gnd", "vss"}, max_devs=3) if out_node else 0
        p_len = _bfs_len(tmpl_text, "p", out_node, {"vdd"}, max_devs=2) if out_node else 0

        # Build correct answer with placeholders that runtime will map to the correct transistors.
        low_terms = ["Vov_{N1}"]
        if n_len >= 2:
            low_terms.append("Vov_{N2}")
        if n_len >= 3:
            low_terms.append("Vov_{N3}")
        high_terms: List[str] = []
        if p_len >= 1:
            high_terms = ["Vov_{P1}"]
            if p_len >= 2:
                high_terms.append("Vov_{P2}")
        # If we couldn't infer a PMOS path (rare), emit a high-side expression without device subscripts.
        high_expr = "VDD" if not high_terms else ("VDD - " + " - ".join(high_terms))
        correct_answer = f"Low-side: " + " + ".join(low_terms) + f"; High-side: " + high_expr

        # Distractors: wrong term count, wrong signs, and wrong device by reusing the wrong stack device.
        # IMPORTANT: do not reference {X1}/{X2}/{X3} here. For swing, we want subscripts to correspond
        # specifically to the stack devices that limit swing (N1/N2(/N3) and P1(/P2)).
        distractors = []
        # Missing one NMOS term (telescopic miss)
        if n_len >= 3:
            distractors.append("Low-side: Vov_{N1} + Vov_{N2}; High-side: VDD - " + " - ".join(high_terms))
        # Add extra NMOS term (cascode miss)
        if n_len == 2:
            distractors.append("Low-side: Vov_{N1} + Vov_{N2} + Vov_{N1}; High-side: VDD - " + " - ".join(high_terms))
        # Wrong NMOS: reuse the wrong lower device (same-type but incorrect subscript selection)
        if n_len >= 2:
            distractors.append("Low-side: Vov_{N1} + Vov_{N1}; High-side: VDD - " + " - ".join(high_terms))
            distractors.append("Low-side: Vov_{N2} + Vov_{N2}; High-side: VDD - " + " - ".join(high_terms))
        # Wrong PMOS: reuse the same PMOS overdrive twice
        if len(high_terms) >= 1:
            distractors.append("Low-side: " + " + ".join(low_terms) + "; High-side: VDD - Vov_{P1} - Vov_{P1}")
        # Missing PMOS term
        if len(high_terms) >= 2:
            distractors.append("Low-side: " + " + ".join(low_terms) + "; High-side: VDD - Vov_{P1}")
        # Wrong sign
        distractors.append("Low-side: VDD - " + " - ".join(high_terms) + "; High-side: " + " + ".join(low_terms))
        # Multiply instead of add (avoid referencing N2 when it doesn't exist)
        if n_len >= 2:
            distractors.append("Low-side: Vov_{N1}·Vov_{N2}; High-side: " + high_expr)
        else:
            distractors.append("Low-side: Vov_{N1}·Vov_{N1}; High-side: " + high_expr)
        # Wrong: subtract NMOS
        if len(low_terms) >= 2:
            distractors.append("Low-side: Vov_{N1} - Vov_{N2}; High-side: VDD - " + " - ".join(high_terms))
        # Wrong: add PMOS
        distractors.append("Low-side: " + " + ".join(low_terms) + "; High-side: VDD + " + " + ".join(high_terms))
        # Ensure list is long enough; add generic plausible variants
        distractors.extend([
            "Low-side: Vov_{N1}; High-side: " + high_expr,
            "Low-side: " + " + ".join(low_terms) + "; High-side: " + ("VDD - Vov_{P1} - Vov_{P1}" if p_len >= 1 else "VDD"),
        ])

        # Additional variants only when the referenced terms exist (prevents placeholder leakage).
        if n_len >= 2:
            distractors.extend([
                "Low-side: Vov_{N2}; High-side: " + high_expr,
                "Low-side: Vov_{N1} + Vov_{N2}; High-side: " + (high_expr if p_len == 0 else "VDD - Vov_{P1}"),
            ])
        if p_len >= 2:
            distractors.extend([
                "Low-side: " + " + ".join(low_terms) + "; High-side: VDD - Vov_{P2} - Vov_{P1}",
                "Low-side: " + " + ".join(low_terms) + "; High-side: VDD - (Vov_{P1} + Vov_{P2})",
            ])
        if n_len >= 2:
            distractors.append("Low-side: (" + " + ".join(low_terms) + ")/2; High-side: " + high_expr)

        # If the inferred NMOS stack is only 1 device (common-source / mirror OTAs),
        # add extra plausible distractors that still only use N1 (no N2/N3 placeholders).
        if n_len < 2:
            distractors.extend([
                "Low-side: 2·Vov_{N1}; High-side: " + high_expr,
                "Low-side: Vov_{N1}/2; High-side: " + high_expr,
                "Low-side: Vov_{N1} + Vov_{N1}; High-side: " + high_expr,
                "Low-side: √(Vov_{N1}); High-side: " + high_expr,
                "Low-side: Vov_{N1}²; High-side: " + high_expr,
            ])
        # Similarly, if the PMOS stack is only 1 device, add extra variants that only use P1.
        if p_len < 2 and p_len >= 1:
            distractors.extend([
                "Low-side: " + " + ".join(low_terms) + "; High-side: VDD - 2·Vov_{P1}",
                "Low-side: " + " + ".join(low_terms) + "; High-side: VDD - Vov_{P1}/2",
                "Low-side: " + " + ".join(low_terms) + "; High-side: VDD - √(Vov_{P1})",
            ])

    elif track == "analysis" and aspect == "power_quiescent":
        canon = _ota_canonical_mc_formula(item_id, aspect)
        if canon:
            correct_answer = canon
            distractors = _power_distractors_device_grounded(correct_answer)
            # Block any *other* DC-equivalent valid expressions from ever appearing as distractors.
            eqs = _ota_power_equivalents_mc(item_id)
            blocked = {_semantic_choice_key(x) for x in eqs}
            distractors = [d for d in distractors if _semantic_choice_key(d) not in blocked]
            distractors = _harmonize_choice_format(correct_answer, distractors)
            return _finalize_mc_key(question_id, track, aspect, correct_answer, distractors, template_role_map)
        raise ValueError(f"Missing canonical power_quiescent formula for {item_id}")

    elif track == "analysis" and aspect == "noise_white":
        canon = _ota_canonical_mc_formula(item_id, aspect)
        if canon:
            correct_answer = canon
            # Device-grounded noise distractors (avoid unrealistic gm-only placeholders).
            distractors = _noise_distractors_device_grounded(correct_answer, is_ota=item_id.startswith("ota"))
            # Filter to keep only device-grounded expressions (must reference specific device params).
            def _is_grounded_noise(x: str) -> bool:
                return ("gm_{" in x) and (("γ_{" in x) or ("ro_{" in x) or ("(W/L)_" in x))
            distractors = [d for d in distractors if _is_grounded_noise(d)]
            distractors = _harmonize_choice_format(correct_answer, distractors)
            return _finalize_mc_key(question_id, track, aspect, correct_answer, distractors, template_role_map)
        # Expanded transistor-parameter form:
        # Replace gm shorthand with explicit input-pair gm sum (no hidden "gm_IN" proxy).
        correct_formula = ANALYSIS_OTA_NOISE.get(item_id, "Vn,out² ≈ 8kT/(3gm)")
        gm_sum = "(gm_{INP} + gm_{INN})"
        base = f"8kT/(3*{gm_sum})"

        if "gmn/gmp" in correct_formula:
            correct_answer = f"Vn,out² ≈ {base}·(1 + gm_{{OUTN}}/gm_{{OUTP}})"
            distractors = [
                f"Vn,out² ≈ {base}·(1 + gm_{{OUTP}}/gm_{{OUTN}})",
                "Vn,out² ≈ 8kT/(3*gm_{INP})·(1 + gm_{OUTN}/gm_{OUTP})",
                "Vn,out² ≈ 8kT/(3*gm_{INN})·(1 + gm_{OUTN}/gm_{OUTP})",
                f"Vn,out² ≈ {base}·(1 - gm_{{OUTN}}/gm_{{OUTP}})",
                f"Vn,out² ≈ {base}·(1 + gm_{{OUTN}}·gm_{{OUTP}})",
                f"Vn,out² ≈ 16kT/(3*{gm_sum})·(1 + gm_{{OUTN}}/gm_{{OUTP}})",
                f"Vn,out² ≈ 8kT/({gm_sum})",
                f"Vn,out² ≈ 8kT·{gm_sum}",
                f"Vn,out² ≈ {base}·(1 + gm_{{X1}}/gm_{{OUTP}})",
                f"Vn,out² ≈ {base}·(1 + gm_{{OUTN}}/gm_{{X2}})",
            ]
        else:
            correct_answer = f"Vn,out² ≈ {base}"
            distractors = [
                f"Vn,out² ≈ 16kT/(3*{gm_sum})",
                "Vn,out² ≈ 8kT/(3*gm_{INP})",
                "Vn,out² ≈ 8kT/(3*gm_{INN})",
                "Vn,out² ≈ 8kT/(3*gm_{X1})",
                f"Vn,out² ≈ 8kT/({gm_sum})",
                f"Vn,out² ≈ 8kT·{gm_sum}",
                f"Vn,out² ≈ √(8kT/(3*{gm_sum}))",
                f"Vn,out² ≈ 8kT/(3*{gm_sum}²)",
                "Vn,out² ≈ 4kT/(gm_{INP}·(ro_{OUTN} || ro_{OUTP}))",
                f"Vn,out² ≈ 8kT/({gm_sum}·√3)",
            ]
        
    # -------------------------
    # ANALYSIS: Feedback
    # NOTE: use exact aspect match; "closed_loop_gain" contains "loop_gain" as a substring.
    # -------------------------
    elif track == "analysis" and aspect == "loop_gain":
        # Keep component-level: avoid bare β as an answer choice.
        correct_formula = ANALYSIS_FEEDBACK_LOOP_GAIN.get(item_id, "T = A0")

        # Map generic R1/R2/C1 tokens to real passive IDs from the corresponding feedback template netlist.
        tmpl_path = Path(__file__).parent.parent / "data" / "dev" / "templates" / "feedback" / item_id / "netlist.sp"
        tmpl_text = tmpl_path.read_text(encoding="utf-8") if tmpl_path.exists() else ""
        inst, resistors, capacitors, inductors = _parse_passives_from_netlist_text(tmpl_text)
        sym_map: Dict[str, str] = {}
        if resistors:
            sym_map["R1"] = resistors[0]
            if len(resistors) > 1:
                sym_map["R2"] = resistors[1]
            if len(resistors) > 2:
                sym_map["R3"] = resistors[2]
        if capacitors:
            sym_map["C1"] = capacitors[0]
            if len(capacitors) > 1:
                sym_map["C2"] = capacitors[1]
        correct_answer = _ensure_positive_gain(_apply_symbol_map_tokens(correct_formula, sym_map))

        # Build distractors consistent with the chosen feedback topology.
        if item_id in {"feedback003", "feedback004"}:
            distractors = [
                "T = A0",
                "T = A0·R2/(R1+R2)",
                "T = A0·(R1+R2)/R1",
                "T = A0·(R1+R2)/R2",
                "T = A0·R1/R2",
                "T = A0/R1",
                "T = A0/(1 + A0·R1/(R1+R2))",
                "T = R1/(R1+R2)",
                "T = 1/(1 + A0·R1/(R1+R2))",
            ]
        else:
            # Unity feedback TIAs (β = 1)
            distractors = [
                "T = A0/(1+A0)",
                "T = A0/(1+2A0)",
                "T = A0/(2+A0)",
                "T = A0²",
                "T = √(A0)",
                "T = 1/(1+A0)",
                "T = A0/2",
                "T = 2A0",
                "T = A0/(1+A0²)",
            ]
        # Apply symbol map and add passive-swap distractors (wrong component IDs) when applicable.
        distractors = [_apply_symbol_map_tokens(d, sym_map) for d in distractors]
        distractors.extend(_passive_swap_distractors(correct_answer, inst, resistors, capacitors, inductors, limit=6))
        
    elif track == "analysis" and aspect == "beta_factor":
        correct_formula = ANALYSIS_FEEDBACK_BETA.get(item_id, "β = 1")

        tmpl_path = Path(__file__).parent.parent / "data" / "dev" / "templates" / "feedback" / item_id / "netlist.sp"
        tmpl_text = tmpl_path.read_text(encoding="utf-8") if tmpl_path.exists() else ""
        inst, resistors, capacitors, inductors = _parse_passives_from_netlist_text(tmpl_text)
        sym_map: Dict[str, str] = {}
        if resistors:
            sym_map["R1"] = resistors[0]
            if len(resistors) > 1:
                sym_map["R2"] = resistors[1]
            if len(resistors) > 2:
                sym_map["R3"] = resistors[2]
        if capacitors:
            sym_map["C1"] = capacitors[0]
            if len(capacitors) > 1:
                sym_map["C2"] = capacitors[1]

        correct_answer = _apply_symbol_map_tokens(correct_formula, sym_map)
        if item_id in {"feedback003", "feedback004"}:
            distractors = [
                "β = R2/(R1+R2)",
                "β = (R1+R2)/R1",
                "β = R1/R2",
                "β = R2/R1",
                "β = 1/(R1+R2)",
                "β = R1",
                "β = 1/R1",
                "β = 2R1/(R1+R2)",
                "β = 0",
            ]
        else:
            # Unity feedback. Keep distractors purely non-self-referential and non-A0-based.
            # Also avoid referencing components that don't exist (e.g. feedback002 has no R1).
            distractors = [
                "β = 0",
                "β = 1/2",
                "β = 2",
                "β = -1",
                "β = -1/2",
                "β = -2",
                "β = 1/4",
                "β = 4",
                "β = 1/10",
            ]
        distractors = [_apply_symbol_map_tokens(d, sym_map) for d in distractors]
        distractors.extend(_passive_swap_distractors(correct_answer, inst, resistors, capacitors, inductors, limit=6))
        
    elif track == "analysis" and aspect == "closed_loop_gain":
        correct_formula = ANALYSIS_FEEDBACK_CL_GAIN.get(item_id, "Vout/Vin = -R2/R1")

        tmpl_path = Path(__file__).parent.parent / "data" / "dev" / "templates" / "feedback" / item_id / "netlist.sp"
        tmpl_text = tmpl_path.read_text(encoding="utf-8") if tmpl_path.exists() else ""
        inst, resistors, capacitors, inductors = _parse_passives_from_netlist_text(tmpl_text)
        sym_map: Dict[str, str] = {}
        if resistors:
            sym_map["R1"] = resistors[0]
            if len(resistors) > 1:
                sym_map["R2"] = resistors[1]
            if len(resistors) > 2:
                sym_map["R3"] = resistors[2]
        if capacitors:
            sym_map["C1"] = capacitors[0]
            if len(capacitors) > 1:
                sym_map["C2"] = capacitors[1]

        correct_answer = _apply_symbol_map_tokens(correct_formula, sym_map)

        # Keep all choices at the same abstraction level and same signal modality (V/V or V/I).
        if item_id == "feedback001":
            # Transimpedance (resistive feedback)
            distractors = [
                "Vout/Iin = -R1/2",
                "Vout/Iin = R1",
                "Vout/Iin = -1/R1",
                "Vout/Iin = -2·R1",
                "Vout/Iin = +R1",
                "Vout/Iin = +R1/2",
                "Vout/Iin = -R1²",
                "Vout/Iin = -√R1",
                "Vout/Iin = -R1/4",
                "Vout/Iin = -4·R1",
            ]
            distractors = [_ensure_positive_gain(d) for d in distractors]
        elif item_id == "feedback002":
            # Transimpedance with capacitive feedback
            distractors = [
                "Vout/Iin = +1/(s*C1)",
                "Vout/Iin = -1/(C1)",
                "Vout/Iin = -s*C1",
                "Vout/Iin = -1/(s*2*C1)",
                "Vout/Iin = -1/(s*(C1/2))",
                "Vout/Iin = -1/(s*C1)²",
                "Vout/Iin = -1/(s*√C1)",
                "Vout/Iin = -1/(s*C1) + 1",
                "Vout/Iin = -1/(s*C1) - 1",
            ]
            distractors = [_ensure_positive_gain(d) for d in distractors]
        elif item_id == "feedback003":
            # Non-inverting amplifier
            distractors = [
                "Vout/Vin = 1 + R1/R2",
                "Vout/Vin = R2/R1",
                "Vout/Vin = R1/(R1+R2)",
                "Vout/Vin = R2/(R1+R2)",
                "Vout/Vin = (R1+R2)/R1",
                "Vout/Vin = -(R1+R2)/R1",
                "Vout/Vin = 1 - R2/R1",
                "Vout/Vin = 1/(1+R2/R1)",
                "Vout/Vin = (R1+R2)/R2",
            ]
            distractors = [_ensure_positive_gain(d) for d in distractors]
        else:
            # Inverting amplifier
            distractors = [
                "Vout/Vin = R2/R1",
                "Vout/Vin = -R1/R2",
                "Vout/Vin = -(R1+R2)/R1",
                "Vout/Vin = -R2/(R1+R2)",
                "Vout/Vin = -R1/(R1+R2)",
                "Vout/Vin = -(R1+R2)/R2",
                "Vout/Vin = 1 + R2/R1",
                "Vout/Vin = 1 + R1/R2",
                "Vout/Vin = -R1·R2",
            ]
            distractors = [_ensure_positive_gain(d) for d in distractors]
        distractors = [_apply_symbol_map_tokens(d, sym_map) for d in distractors]
        distractors = _harmonize_choice_format(correct_answer, distractors)
        distractors.extend(_passive_swap_distractors(correct_answer, inst, resistors, capacitors, inductors, limit=6))

    elif track == "analysis" and aspect == "signal_modality":
        # Keep everything at the same abstraction: transfer ratio form.
        # Correct for TIAs: Vout/Iin; for voltage amps: Vout/Vin.
        correct_answer = "Vout/Iin" if item_id in {"feedback001", "feedback002"} else "Vout/Vin"
        distractors = [
            "Vout/Vin",
            "Vout/Iin",
            "Iout/Vin",
            "Iout/Iin",
            "Vout/Vdiff",
            "Iout/Vdiff",
            "Vout/Idiff",
            "Iout/Idiff",
            "Vout/Vcm",
            "Iout/Vcm",
        ]
        # Remove the correct one (and any exact duplicates); the filtering below will also enforce.
        distractors = [d for d in distractors if d != correct_answer]
        
    # -------------------------
    # ANALYSIS: Filters
    # -------------------------
    elif track == "analysis" and aspect == "identify_transfer_function":
        # Netlist-aware: only use component symbols that actually exist in this filter's template netlist.
        tmpl_path = Path(__file__).parent.parent / "data" / "dev" / "templates" / "filters" / item_id / "netlist.sp"
        tmpl_text = ""
        if tmpl_path.exists():
            try:
                tmpl_text = tmpl_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                tmpl_text = tmpl_path.read_text(encoding="utf-16")
        inst = set()
        resistors: List[str] = []
        capacitors: List[str] = []
        inductors: List[str] = []
        # capture simple 2-terminal elements for topology-aware passive TFs
        elems: List[Dict[str, str]] = []
        for ln in tmpl_text.splitlines():
            s = ln.strip()
            if not s or s.startswith(("*", ";", "//", ".")):
                continue
            tok = s.split()[0]
            if tok and tok[0].upper() in {"R", "C", "L", "X"}:
                inst.add(tok)
                if tok[0].upper() == "R":
                    resistors.append(tok)
                elif tok[0].upper() == "C":
                    capacitors.append(tok)
                elif tok[0].upper() == "L":
                    inductors.append(tok)
            # Parse 2-terminal passive components (R/C/L) for passive divider detection
            if tok and tok[0].upper() in {"R", "C", "L"}:
                parts = s.split()
                if len(parts) >= 3:
                    elems.append({"id": parts[0], "a": parts[1], "b": parts[2], "type": parts[0][0].upper()})

        # Map generic symbols (R1, C1, L1, Rload, Cload) used in formula templates
        # onto actual instance IDs present in this filter template.
        def _pick_by_substring(items: List[str], needle: str) -> str | None:
            needle = needle.lower()
            for x in items:
                if needle in x.lower():
                    return x
            return None

        rload = _pick_by_substring(resistors, "load") or (resistors[-1] if resistors else None)
        cload = _pick_by_substring(capacitors, "load") or (capacitors[-1] if capacitors else None)
        sym_map: Dict[str, str] = {}
        if resistors:
            sym_map["R1"] = resistors[0]
            if len(resistors) > 1:
                sym_map["R2"] = resistors[1]
            if len(resistors) > 2:
                sym_map["R3"] = resistors[2]
        if capacitors:
            sym_map["C1"] = capacitors[0]
            if len(capacitors) > 1:
                sym_map["C2"] = capacitors[1]
        if inductors:
            sym_map["L1"] = inductors[0]
        if rload:
            sym_map["Rload"] = rload
        if cload:
            sym_map["Cload"] = cload

        def _apply_symbol_map(expr: str) -> str:
            if not expr or not sym_map:
                return expr
            # Replace whole-token occurrences only.
            for k, v in sym_map.items():
                expr = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(k)}(?![A-Za-z0-9_])", v, expr)
            return expr

        def _valid_for_template(expr: str) -> bool:
            # Any referenced R*/C*/L* token must exist in template.
            for m in re.finditer(r"\b([RCL][A-Za-z0-9_]+)\b", expr):
                name = m.group(1)
                if name not in inst:
                    return False
            return True

        # If this is a simple passive divider (no OPAMP macro), derive TF from actual topology
        # to avoid nonsense choices (e.g. filter007 RL divider should not get RC biquad forms).
        has_opamp = any(x.upper().startswith("XU") or x.upper().startswith("X") for x in inst)
        series_id = None
        series_type = None
        shunt: List[Dict[str, str]] = []
        if not has_opamp:
            # Find element between vin and vout (series element)
            for e in elems:
                n1 = e["a"].lower()
                n2 = e["b"].lower()
                if {n1, n2} == {"vin", "vout"}:
                    series_id = e["id"]
                    series_type = e["type"]
                    break
            # Find elements from vout to 0 (shunt network)
            for e in elems:
                n1 = e["a"].lower()
                n2 = e["b"].lower()
                if "vout" in {n1, n2} and "0" in {n1, n2}:
                    shunt.append(e)

        def _zs(t: str, name: str) -> str:
            if t == "R":
                return name
            if t == "C":
                return f"1/(s*{name})"
            if t == "L":
                return f"s*{name}"
            return name

        def _y(t: str, name: str) -> str:
            if t == "R":
                return f"1/{name}"
            if t == "C":
                return f"s*{name}"
            if t == "L":
                return f"1/(s*{name})"
            return f"1/{name}"

        if series_id and shunt:
            # H(s) = Zp/(Zs + Zp) = 1/(1 + Zs*Ysum) where Ysum is parallel admittance.
            ysum = " + ".join(_y(e["type"], e["id"]) for e in shunt)
            zs = _zs(series_type or series_id[0].upper(), series_id)
            correct_formula = f"H(s) = 1/(1 + ({zs})*({ysum}))"

            # Build plausible distractors using same available components only
            distractors_raw = [
                f"H(s) = 1/(1 + ({zs})*({_y(shunt[0]['type'], shunt[0]['id'])}))",  # missing parallel term(s)
                f"H(s) = 1/(1 + ({zs})*({_y(shunt[-1]['type'], shunt[-1]['id'])}))",
                f"H(s) = 1/(1 + ({zs})*({ysum.replace(' + ', ' - ')}))",  # wrong sign
                f"H(s) = 1/(1 + ({zs})/({ysum}))",  # divide by admittance
                f"H(s) = 1/(1 + ({ysum})/({zs}))",  # inverted ratio
                f"H(s) = ({zs})/(({zs}) + 1/({ysum}))",  # inverted divider
                f"H(s) = 1/(1 + ({zs})*({ysum}) + 1)",  # extra +1
                f"H(s) = 1/(1 + (2*{zs})*({ysum}))",  # wrong scale
                f"H(s) = 1/(1 + ({zs})*(2*({ysum})))",
                f"H(s) = 1/(1 + ({zs})*({ysum})^2)",  # wrong power
                f"H(s) = 1/(1 - ({zs})*({ysum}))",
                f"H(s) = ({zs})*({ysum})/(1 + ({zs})*({ysum}))",  # complementary HP form
                f"H(s) = 1 - 1/(1 + ({zs})*({ysum}))",
                f"H(s) = 1/(2 + ({zs})*({ysum}))",
                f"H(s) = 1/(1 + ({zs})*({ysum}) + ({zs})*({ysum}))",
                f"H(s) = 1/(1 + ({zs})*({ysum}) + ({zs})^2*({ysum}))",
                f"H(s) = 1/(1 + ({zs})*({ysum}) + ({zs})*({ysum})^2)",
                f"H(s) = 1/(1 + ({zs})^2*({ysum}))",
                f"H(s) = 1/(1 + ({zs})*({ysum})^3)",
            ]
            # Filter out anything that references missing components
            cand_tf = [d for d in distractors_raw if _valid_for_template(d)]
            correct_answer = f"Transfer function: {correct_formula}"
            # Add "wrong passive" distractors by swapping one passive token for another existing token.
            swapped = _passive_swap_distractors(correct_formula, inst, resistors, capacitors, inductors, limit=6)
            cand_tf = swapped + cand_tf
            distractors = [f"Transfer function: {d}" for d in cand_tf]
        else:
            # Opamp-based (or non-divider) filters: derive H(s)=Vout/Vin from the actual netlist using
            # ideal-opamp constraints (V+ = V-, input currents = 0). This keeps MCQs grounded and avoids ω0/Q.
            def _derive_tf_sympy(netlist: str) -> str:
                import sympy as sp
                s = sp.Symbol("s")
                A = sp.Symbol("A0")  # opamp open-loop gain (take A0 -> oo for ideal opamp)

                # Parse passives and opamps
                passives = []
                opamps = []
                vin_node = None
                vout_node = "vout"

                for raw in netlist.splitlines():
                    line = raw.strip()
                    if not line or line.startswith(("*", ";", "//", ".")):
                        continue
                    parts = line.split()
                    name = parts[0]
                    if name.lower() == "vin" and len(parts) >= 3:
                        # Vin <node> 0 AC 1
                        vin_node = parts[1]
                        continue
                    t = name[0].upper()
                    if t in {"R", "C", "L"} and len(parts) >= 3:
                        n1, n2 = parts[1], parts[2]
                        sym = sp.Symbol(name)
                        if t == "R":
                            y = 1 / sym
                        elif t == "C":
                            y = s * sym
                        else:  # L
                            y = 1 / (s * sym)
                        passives.append((name, n1, n2, y))
                    elif t == "X" and len(parts) >= 4 and parts[-1].upper() == "OPAMP":
                        # Assume ordering: XU? out in- in+ OPAMP
                        out, inn, inp = parts[1], parts[2], parts[3]
                        opamps.append((name, out, inn, inp))

                if vin_node is None:
                    raise ValueError("No Vin source found.")

                # Collect nodes (excluding ground and vin which is forced to 1)
                nodes = set()
                for _, a, b, _y in passives:
                    if a != "0":
                        nodes.add(a)
                    if b != "0":
                        nodes.add(b)
                for _xname, out, inn, inp in opamps:
                    if out != "0":
                        nodes.add(out)
                    if inn != "0":
                        nodes.add(inn)
                    if inp != "0":
                        nodes.add(inp)
                # unknown node voltages
                nodes.discard("0")
                nodes.discard(vin_node)

                V = {n: sp.Symbol(f"V_{n}") for n in nodes}
                # known voltages
                V_known = {"0": sp.Integer(0), vin_node: sp.Integer(1)}

                def v(n: str):
                    if n in V_known:
                        return V_known[n]
                    return V[n]

                # MNA: model each OPAMP as a dependent voltage source between out and 0:
                #   v(out) - A0*(v(in+) - v(in-)) = 0
                # and include an unknown source current I_xu injected at the out node in KCL.
                Iop = {xname: sp.Symbol(f"I_{xname}") for xname, *_rest in opamps}

                eqs = []
                # KCL at each unknown node (include opamp output current injections)
                for n in sorted(nodes):
                    expr = 0
                    for _name, a, b, y in passives:
                        if a == n:
                            expr += y * (v(a) - v(b))
                        elif b == n:
                            expr += y * (v(b) - v(a))
                    # Current from opamp output source into node n
                    for xname, out, _inn, _inp in opamps:
                        if out == n:
                            expr += Iop[xname]
                    eqs.append(sp.Eq(sp.simplify(expr), 0))

                # OPAMP dependent source equations
                for xname, out, inn, inp in opamps:
                    eqs.append(sp.Eq(v(out) - A * (v(inp) - v(inn)), 0))

                # Solve linear system
                unknowns = [V[n] for n in sorted(nodes)] + [Iop[x] for x in sorted(Iop.keys())]
                sol = sp.solve(eqs, unknowns, dict=True)
                if not sol:
                    raise ValueError("Could not solve TF system.")
                sol = sol[0]
                # Output node voltage
                Vout = v(vout_node)
                if vout_node in V:
                    Vout = sol.get(V[vout_node], Vout)
                # Take ideal-opamp limit A0 -> infinity
                Vout = sp.simplify(sp.limit(Vout, A, sp.oo))
                num, den = sp.fraction(sp.together(Vout))
                num = sp.expand(num)
                den = sp.expand(den)
                # Render compact polynomial ratio
                # Use ^ for powers to match existing style
                sstr = sp.sstr(num/den)
                sstr = sstr.replace("**", "^")
                return f"H(s) = {sstr}"

            # Prefer sympy-derived TF for opamp filters. If sympy derivation fails, fail loudly
            # (shipping a fallback here risks emitting MCQs that don't match the netlist topology).
            correct_formula = _derive_tf_sympy(tmpl_text)

            correct_answer = f"Transfer function: {correct_formula}"
            # Distractors: start from component-level library, map symbols, and filter to what's present.
            cand = generate_formula_distractors(correct_formula, "filter_tf")
            cand = [_apply_symbol_map(d) for d in cand]
            cand = [d for d in cand if _valid_for_template(d)]
            # Also include "wrong passive" swaps (wrong R/C/L token) from the same netlist.
            cand = _passive_swap_distractors(correct_formula, inst, resistors, capacitors, inductors, limit=6) + cand
            distractors = [f"Transfer function: {d}" for d in cand]
        
    else:
        # Never emit placeholders; fail loudly so we don't ship illegitimate MCQs.
        raise ValueError(f"Unhandled MCQ generation case: track={track} aspect={aspect} item_id={item_id} qid={question_id}")
    
    # Filter out correct answer from distractors (case-insensitive, whitespace-normalized)
    def normalize(s):
        return s.lower().replace(" ", "").replace("≈", "").replace("~", "")
    
    correct_norm = normalize(correct_answer)
    # Remove exact-correct matches, then de-dup distractors (normalized) so we never create
    # equivalent/duplicate answer options.
    dedup = []
    seen_norm = {correct_norm}
    for d in distractors:
        dn = normalize(d)
        if dn in seen_norm:
            continue
        seen_norm.add(dn)
        dedup.append(d)
    distractors = dedup[:9]

    # Reject placeholder content (should be impossible after the ValueError above)
    for s in [correct_answer] + distractors:
        if "distractor" in s.lower() or "correct answer for" in s.lower():
            raise ValueError(f"Illegal placeholder choice generated for {question_id}: {s}")
    
    # Shuffle and assign A-J. Enforce 10 unique choices.
    all_choices = [correct_answer] + distractors
    if len(all_choices) < 10:
        raise ValueError(f"Not enough unique MC choices for {question_id} (got {len(all_choices)}).")
    random.shuffle(all_choices)
    
    # Find correct letter
    correct_letter = chr(65 + all_choices.index(correct_answer))
    
    choices = {chr(65+i): all_choices[i] for i in range(min(10, len(all_choices)))}
    if len(choices) != 10:
        raise ValueError(f"MC choices must be A-J (10). Got {len(choices)} for {question_id}.")
    
    return {
        "question_id": question_id,
        "correct_answer": correct_letter,
        "answer_text": correct_answer,
        "choices": choices,
        "track": track,
        "aspect": aspect,
        # Optional: map canonical role names (M1a/M1b/...) to template instance IDs (M2/Mp1/...)
        # so run_eval can substitute into formulas and then rename instances for MCQs.
        "template_role_map": template_role_map,
    }


def main():
    data_dir = Path(__file__).parent.parent / "data" / "dev"
    # Process debugging OTA questions
    for ota_id in DEBUGGING_OTA_SWAP_ANSWERS.keys():
        item_dir = data_dir / "debugging" / "ota" / ota_id
        questions_file = item_dir / "questions.yaml"
        if questions_file.exists():
            with open(questions_file) as f:
                questions = yaml.safe_load(f)
            
            for q in questions['questions']:
                qid = q['id']
                mc_key = generate_mc_answer_key(qid, "debugging", "device_swap", ota_id)
                
                output_file = item_dir / "mc_answer_key.json"
                with open(output_file, 'w') as f:
                    json.dump(mc_key, f, indent=2)
                print(f"Generated {output_file}")
    
    # Process debugging feedback questions
    for fb_id in DEBUGGING_FEEDBACK_POLARITY_ANSWERS.keys():
        item_dir = data_dir / "debugging" / "feedback" / fb_id
        questions_file = item_dir / "questions.yaml"
        if questions_file.exists():
            with open(questions_file) as f:
                questions = yaml.safe_load(f)
            
            for q in questions['questions']:
                qid = q['id']
                mc_key = generate_mc_answer_key(qid, "debugging", "feedback_polarity", fb_id)
                
                output_file = item_dir / "mc_answer_key.json"
                with open(output_file, 'w') as f:
                    json.dump(mc_key, f, indent=2)
                print(f"Generated {output_file}")
    
    # Process analysis OTA questions (dc_gain, gbw, etc.)
    for ota_id in ANALYSIS_OTA_DC_GAIN.keys():
        item_dir = data_dir / "analysis" / "ota" / ota_id
        questions_file = item_dir / "questions.yaml"
        if questions_file.exists():
            with open(questions_file) as f:
                questions_data = yaml.safe_load(f)
            
            for q in questions_data['questions']:
                qid = q['id']
                aspect = q.get('meta', {}).get('aspect', '')
                
                mc_key = generate_mc_answer_key(qid, "analysis", aspect, ota_id)
                
                # Save as mc_answer_key_{aspect}.json
                output_file = item_dir / f"mc_answer_key_{aspect}.json"
                with open(output_file, 'w') as f:
                    json.dump(mc_key, f, indent=2)
                print(f"Generated {output_file}")
    
    # Process analysis feedback questions
    for fb_id in ANALYSIS_FEEDBACK_LOOP_GAIN.keys():
        item_dir = data_dir / "analysis" / "feedback" / fb_id
        questions_file = item_dir / "questions.yaml"
        if questions_file.exists():
            with open(questions_file) as f:
                questions_data = yaml.safe_load(f)
            
            for q in questions_data['questions']:
                qid = q['id']
                aspect = q.get('meta', {}).get('aspect', '')
                
                mc_key = generate_mc_answer_key(qid, "analysis", aspect, fb_id)
                
                output_file = item_dir / f"mc_answer_key_{aspect}.json"
                with open(output_file, 'w') as f:
                    json.dump(mc_key, f, indent=2)
                print(f"Generated {output_file}")
    
    # Process analysis filter questions
    for filter_id in ANALYSIS_FILTER_TF.keys():
        item_dir = data_dir / "analysis" / "filters" / filter_id
        questions_file = item_dir / "questions.yaml"
        if questions_file.exists():
            with open(questions_file) as f:
                questions_data = yaml.safe_load(f)
            
            for q in questions_data['questions']:
                qid = q['id']
                aspect = q.get('meta', {}).get('aspect', 'identify_tf')
                
                mc_key = generate_mc_answer_key(qid, "analysis", aspect, filter_id)
                
                output_file = item_dir / f"mc_answer_key_{aspect}.json"
                with open(output_file, 'w') as f:
                    json.dump(mc_key, f, indent=2)
                print(f"Generated {output_file}")
    
    print("\nDone generating MC answer keys!")


if __name__ == "__main__":
    main()

