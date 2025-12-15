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
    for m in re.finditer(r"\b([RCL][A-Za-z0-9_]+)\b", expr or ""):
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
    "feedback004": "T = A0·R1/(R1+R2)",
}

ANALYSIS_FEEDBACK_BETA = {
    # Keep component-level (avoid abstracting away the divider details).
    "feedback001": "β = 1",
    "feedback002": "β = 1",
    "feedback003": "β = R1/(R1+R2)",
    "feedback004": "β = R1/(R1+R2)",
}

ANALYSIS_FEEDBACK_CL_GAIN = {
    "feedback001": "Vout/Iin = -R1",
    # Capacitive feedback TIA acts as an integrator: Zf = 1/(sC1)
    "feedback002": "Vout/Iin = -1/(s*C1)",
    "feedback003": "Vout/Vin = 1 + R2/R1",
    "feedback004": "Vout/Vin = -R2/R1",
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
        alternatives = [
            "P = VDD²/Rtail",
            "P = VDD·Itail/2",
            "P = 2·VDD·Itail",
            "P = VDD·√(Itail)",
            "P = VDD·(Itail + IDD)",
            "P = (VDD - VTH)·Itail",
            "P = VDD·Itail·gm",
            "P = VDD·Itail/(1 + A0)",
            "P = VDD²·gm",
            "P = (VDD/2)·Itail",
            "P = VDD·(Itail + Ibias)",
            "P = VDD·(Itail - IDD)",
        ]
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


def generate_mc_answer_key(question_id: str, track: str, aspect: str, item_id: str) -> Dict[str, Any]:
    """Generate MC answer key for a specific question."""
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
        # Use placeholder device IDs so MCQs can substitute shuffled transistor names at runtime.
        # {IN} = representative input device; {OUTN}/{OUTP} = representative output NMOS/PMOS.
        correct_formula = ANALYSIS_OTA_DC_GAIN.get(item_id, "gm·ro/2")
        # Normalize to explicit gm/ro with transistor subscripts.
        # We use ro_{OUTN} as a representative single-device ro; the /2 or /4 constants
        # handle common mirror / single-ended / two-stage factors consistently with short-form rubrics.
        if "³" in correct_formula:
            correct_answer = "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})³/2"
            distractors = [
                # Close-but-wrong exponent/scale
                "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})³",
                "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})³/4",
                "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})²/2",
                "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})²",
                # Wrong subscripts
                "DC gain A0 ≈ (gm_{OUTN}·ro_{OUTN})³/2",
                "DC gain A0 ≈ (gm_{IN}·ro_{IN})³/2",
                "DC gain A0 ≈ (gm_{X1}·ro_{OUTN})³/2",
                "DC gain A0 ≈ (gm_{IN}·ro_{X2})³/2",
                # Wrong operation
                "DC gain A0 ≈ √(gm_{IN}·ro_{OUTN})",
                "DC gain A0 ≈ (gm_{IN}/ro_{OUTN})³/2",
                # Linear-ish distractor
                "DC gain A0 ≈ gm_{IN}·ro_{OUTN}/2",
            ]
        elif "²" in correct_formula and "/4" in correct_formula:
            correct_answer = "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})²/4"
            distractors = [
                "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})²/2",
                "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})²",
                "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})²/8",
                "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})³/2",
                "DC gain A0 ≈ (gm_{OUTN}·ro_{OUTN})²/4",
                "DC gain A0 ≈ (gm_{IN}·ro_{IN})²/4",
                "DC gain A0 ≈ (gm_{X1}·ro_{OUTN})²/4",
                "DC gain A0 ≈ (gm_{IN}·ro_{X2})²/4",
                "DC gain A0 ≈ √(gm_{IN}·ro_{OUTN})",
                "DC gain A0 ≈ gm_{IN}·ro_{OUTN}/2",
                "DC gain A0 ≈ gm_{IN}·ro_{OUTN}",
            ]
        elif "²" in correct_formula:
            correct_answer = "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})²/2"
            distractors = [
                "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})²",
                "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})²/4",
                "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})²/8",
                "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})³/2",
                "DC gain A0 ≈ (gm_{OUTN}·ro_{OUTN})²/2",
                "DC gain A0 ≈ (gm_{IN}·ro_{IN})²/2",
                "DC gain A0 ≈ (gm_{X1}·ro_{OUTN})²/2",
                "DC gain A0 ≈ (gm_{IN}·ro_{X2})²/2",
                "DC gain A0 ≈ √(gm_{IN}·ro_{OUTN})",
                "DC gain A0 ≈ gm_{IN}·ro_{OUTN}/2",
                "DC gain A0 ≈ gm_{IN}·ro_{OUTN}",
            ]
        else:
            # gm·ro/2 cases
            correct_answer = "DC gain A0 ≈ gm_{IN}·ro_{OUTN}/2"
            distractors = [
                "DC gain A0 ≈ gm_{IN}·ro_{OUTN}",
                "DC gain A0 ≈ gm_{IN}·ro_{OUTN}/4",
                "DC gain A0 ≈ 2·gm_{IN}·ro_{OUTN}",
                "DC gain A0 ≈ gm_{OUTN}·ro_{OUTN}/2",
                "DC gain A0 ≈ gm_{IN}·ro_{IN}/2",
                "DC gain A0 ≈ gm_{X1}·ro_{OUTN}/2",
                "DC gain A0 ≈ gm_{IN}·ro_{X2}/2",
                "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})²/2",
                "DC gain A0 ≈ gm_{IN}/ro_{OUTN}",
                "DC gain A0 ≈ √(gm_{IN}·ro_{OUTN})",
                "DC gain A0 ≈ (gm_{IN}·ro_{OUTN})³/2",
            ]
        
    elif track == "analysis" and aspect == "gbw":
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
        # Express PSRR+ in terms of transistor-tagged small-signal parameters where possible.
        correct_formula = ANALYSIS_OTA_PSRR.get(item_id, "PSRR+ ≈ (gm·ro)")
        if "²" in correct_formula and "³" not in correct_formula:
            correct_answer = "PSRR+ ≈ (gm_{IN}·ro_{OUTN})²"
            distractors = [
                "PSRR+ ≈ gm_{IN}·ro_{OUTN}",
                "PSRR+ ≈ (gm_{OUTN}·ro_{OUTN})²",
                "PSRR+ ≈ (gm_{IN}·ro_{OUTN})³",
                "PSRR+ ≈ (ro_{OUTN})²",
                "PSRR+ ≈ (gm_{IN})²·ro_{OUTN}",
                "PSRR+ ≈ (gm_{IN}·ro_{OUTN})²/2",
                "PSRR+ ≈ √(gm_{IN}·ro_{OUTN})",
                "PSRR+ ≈ (gm_{IN}·ro_{OUTN})",
                "PSRR+ ≈ (gm_{IN}·ro_{OUTN})² + 1",
            ]
        elif "³" in correct_formula:
            correct_answer = "PSRR+ ≈ (gm_{IN}·ro_{OUTN})³"
            distractors = [
                "PSRR+ ≈ (gm_{IN}·ro_{OUTN})²",
                "PSRR+ ≈ gm_{IN}·ro_{OUTN}",
                "PSRR+ ≈ (gm_{OUTP}·ro_{OUTN})³",
                "PSRR+ ≈ (ro_{OUTN})³",
                "PSRR+ ≈ (gm_{IN})³·ro_{OUTN}",
                "PSRR+ ≈ (gm_{IN}·ro_{OUTN})³/2",
                "PSRR+ ≈ (gm_{IN}·ro_{OUTN})²/2",
                "PSRR+ ≈ √(gm_{IN}·ro_{OUTN})",
                "PSRR+ ≈ (gm_{IN}·ro_{OUTN})³ + 1",
            ]
        else:
            correct_answer = "PSRR+ ≈ gm_{IN}·ro_{OUTN}"
            distractors = [
                "PSRR+ ≈ gm_{OUTN}·ro_{OUTN}",
                "PSRR+ ≈ gm_{IN}·ro_{IN}",
                "PSRR+ ≈ gm_{X1}·ro_{OUTN}",
                "PSRR+ ≈ gm_{IN}·ro_{X2}",
                "PSRR+ ≈ (gm_{IN}·ro_{OUTN})²",
                "PSRR+ ≈ ro_{OUTN}",
                "PSRR+ ≈ (gm_{IN})²·ro_{OUTN}",
                "PSRR+ ≈ gm_{IN}/ro_{OUTN}",
                "PSRR+ ≈ 2·gm_{IN}·ro_{OUTN}",
                "PSRR+ ≈ √(gm_{IN}·ro_{OUTN})",
                "PSRR+ ≈ gm_{IN}·ro_{OUTN}/2",
            ]

    elif track == "analysis" and aspect == "rout":
        # Use ro subscripts at output devices; keep expression simple and plausible.
        correct_formula = ANALYSIS_OTA_ROUT.get(item_id, "rout ≈ ro")
        if "(gm·ro)²·ro" in correct_formula:
            correct_answer = "rout ≈ (gm_{IN}·ro_{OUTN})²·ro_{OUTN}"
            distractors = [
                "rout ≈ (gm_{IN}·ro_{OUTN})·ro_{OUTN}",
                "rout ≈ (gm_{IN}·ro_{OUTN})²",
                "rout ≈ (gm_{OUTN}·ro_{OUTN})²·ro_{OUTN}",
                "rout ≈ ro_{OUTN}",
                "rout ≈ (gm_{IN})²·ro_{OUTN}",
                "rout ≈ (gm_{IN}·ro_{OUTN})³·ro_{OUTN}",
                "rout ≈ (gm_{IN}·ro_{OUTN})²·ro_{IN}",
                "rout ≈ 2·ro_{OUTN}",
                "rout ≈ ro_{OUTN}/2",
            ]
        elif "(gm·ro)·ro" in correct_formula:
            correct_answer = "rout ≈ (gm_{IN}·ro_{OUTN})·ro_{OUTN}"
            distractors = [
                "rout ≈ (gm_{IN}·ro_{OUTN})²·ro_{OUTN}",
                "rout ≈ gm_{IN}·ro_{OUTN}",
                "rout ≈ (gm_{OUTP}·ro_{OUTN})·ro_{OUTN}",
                "rout ≈ ro_{OUTN}",
                "rout ≈ (gm_{IN})²·ro_{OUTN}",
                "rout ≈ (gm_{IN}·ro_{OUTN})·ro_{IN}",
                "rout ≈ ro_{OUTN} + ro_{OUTN}",
                "rout ≈ ro_{OUTN}·ro_{OUTN}",
                "rout ≈ √(ro_{OUTN})",
            ]
        else:
            correct_answer = "rout ≈ ro_{OUTN}"
            distractors = [
                "rout ≈ ro_{OUTN}/2",
                "rout ≈ 2·ro_{OUTN}",
                "rout ≈ (gm_{IN}·ro_{OUTN})·ro_{OUTN}",
                "rout ≈ gm_{IN}·ro_{OUTN}",
                "rout ≈ ro_{IN}",
                "rout ≈ ro_{OUTP}",
                "rout ≈ ro_{X1}",
                "rout ≈ ro_{OUTN} + ro_{OUTP}",
                "rout ≈ ro_{OUTN}·ro_{OUTP}",
                "rout ≈ √(ro_{OUTN})",
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
        correct_formula = ANALYSIS_OTA_POWER.get(item_id, "P = VDD·Itail")
        correct_answer = correct_formula
        distractors = generate_formula_distractors(correct_formula, "power")

    elif track == "analysis" and aspect == "noise_white":
        # Put gm subscripts anywhere gm corresponds to a specific transistor.
        correct_formula = ANALYSIS_OTA_NOISE.get(item_id, "Vn,out² ≈ 8kT/(3gm)")
        # Default: dominated by input pair.
        if "gmn/gmp" in correct_formula:
            correct_answer = "Vn,out² ≈ 8kT/(3gm_{IN})·(1 + gm_{OUTN}/gm_{OUTP})"
            distractors = [
                "Vn,out² ≈ 8kT/(3gm_{IN})·(1 + gm_{OUTP}/gm_{OUTN})",
                "Vn,out² ≈ 8kT/(3gm_{OUTN})·(1 + gm_{OUTN}/gm_{OUTP})",
                "Vn,out² ≈ 8kT/(3gm_{IN})·(1 + gm_{OUTN}·gm_{OUTP})",
                "Vn,out² ≈ 8kT/(3gm_{IN})·(1 - gm_{OUTN}/gm_{OUTP})",
                "Vn,out² ≈ 16kT/(3gm_{IN})·(1 + gm_{OUTN}/gm_{OUTP})",
                "Vn,out² ≈ 8kT/(gm_{IN})",
                "Vn,out² ≈ 8kT·gm_{IN}",
                "Vn,out² ≈ 8kT/(3gm_{IN})·(1 + gm_{IN}/gm_{OUTP})",
                "Vn,out² ≈ 8kT/(3gm_{IN})·(1 + gm_{OUTN}/gm_{IN})",
            ]
        else:
            correct_answer = "Vn,out² ≈ 8kT/(3gm_{IN})"
            distractors = [
                "Vn,out² ≈ 16kT/(3gm_{IN})",
                "Vn,out² ≈ 8kT/(3gm_{OUTN})",
                "Vn,out² ≈ 8kT/(3gm_{X1})",
                "Vn,out² ≈ 8kT/(gm_{IN})",
                "Vn,out² ≈ 8kT·gm_{IN}",
                "Vn,out² ≈ √(8kT/(3gm_{IN}))",
                "Vn,out² ≈ 8kT/(3gm_{IN}²)",
                "Vn,out² ≈ 4kT/(gm_{IN}·(ro_{OUTN} || ro_{OUTP}))",
                "Vn,out² ≈ 8kT/(gm_{IN}·√3)",
                "Vn,out² ≈ 4kT/gm_{IN}",
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
        correct_answer = _apply_symbol_map_tokens(correct_formula, sym_map)

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
        distractors = [_apply_symbol_map_tokens(d, sym_map) for d in distractors]
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
        "aspect": aspect
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

