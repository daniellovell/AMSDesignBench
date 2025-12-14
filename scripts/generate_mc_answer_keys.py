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
    "ota001": "gm·ro",
    "ota002": "(gm·ro)²",
    "ota003": "(gm·ro)²",
    "ota004": "gm·ro",
    "ota005": "(gm·ro)²",
    "ota006": "(gm·ro)²",
    "ota007": "(gm·ro)³",
    "ota008": "(gm·ro)³",
    "ota009": "gm·ro",
    "ota010": "(gm·ro)²",
    "ota011": "(gm·ro)²",
    "ota012": "gm·ro",
}

ANALYSIS_OTA_GBW = {
    "ota001": "gm/CL",
    "ota002": "gm/CL",
    "ota003": "gm1/Cc",
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
    "feedback001": "T = A0",
    "feedback002": "T = A0",
    "feedback003": "T = A0",
    "feedback004": "T = A0",
}

ANALYSIS_FEEDBACK_BETA = {
    "feedback001": "β = 1",
    "feedback002": "β = 1",
    "feedback003": "β = R1/(R1+R2)",
    "feedback004": "β = R1/(R1+R2)",
}

ANALYSIS_FEEDBACK_CL_GAIN = {
    "feedback001": "Vout/Iin = -R1",
    "feedback002": "Vout/Iin = -R1/(1+sR1C1)",
    "feedback003": "Vout/Vin = 1 + R2/R1",
    "feedback004": "Vout/Vin = -R2/R1",
}

ANALYSIS_FILTER_TF = {
    "filter001": "H(s) = 1/(1+sRC) or H(s) = ωc/(s+ωc) where ωc = 1/RC",
    "filter002": "H(s) = sRC/(1+sRC) or H(s) = s/(s+ωc) where ωc = 1/RC",
    "filter003": "H(s) = (s/ωc)²/[1 + (s/ωc)/Q + (s/ωc)²] (second-order bandpass)",
    "filter004": "H(s) = H0·(s/ω0)/[s²/ω0² + (s/ω0)/Q + 1] (RLC bandpass)",
    "filter005": "H(s) = 1/[1 + s/ωc + (s/ωc)²] (second-order low-pass)",
    "filter006": "H(s) = (s/ωc)²/[1 + s/ωc + (s/ωc)²] (second-order high-pass)",
    "filter007": "H(s) = [1 - (s/ωn)²]/[1 + s/(Qωn) + (s/ωn)²] (notch filter)",
    "filter008": "H(s) = [s² - ωn²]/[s² + s·ωn/Q + ωn²] (all-pass with notch)",
    "filter009": "H(s) = 1/[1 + (s/ωc)²] (second-order Butterworth LP)",
    "filter010": "H(s) = (s/ωc)²/[1 + (s/ωc)²] (second-order Butterworth HP)",
    "filter011": "H(s) = H0·s/(s² + s·ω0/Q + ω0²) (active MFB bandpass)",
    "filter012": "H(s) = (s·ω0/Q)/(s² + s·ω0/Q + ω0²) (state-variable bandpass)",
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
        alternatives = [
            "gm·ro²",
            "gm²·ro",
            "(gm·ro)²/2",
            "2·gm·ro",
            "gm/ro",
            "gm·(ro/2)",
            "(gm·ro)³",
            "√(gm·ro)",
            "gm·(ron || rop)",
        ]
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
            "H(s) = 1/(1+s)",
            "H(s) = ωc/(s+2ωc)",
            "H(s) = s/(1+sRC)",
            "H(s) = 1/(1+sRC)²",
            "H(s) = (1+sRC)/s",
            "H(s) = ωc²/(s²+sωc+ωc²)",
            "H(s) = s²/(s²+√2·sωc+ωc²)",
            "H(s) = ωc/(s²+sωc)",
            "H(s) = 1/(s+ωc)²",
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
        ]
    else:
        alternatives = ["Alternative " + chr(65+i) for i in range(9)]
    
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
        
    elif track == "analysis" and "gain_dc" in aspect:
        correct_formula = ANALYSIS_OTA_DC_GAIN.get(item_id, "gm·ro")
        correct_answer = f"DC gain A0 ≈ {correct_formula}"
        distractors = [f"DC gain A0 ≈ {d}" for d in generate_formula_distractors(correct_formula, "dc_gain")]
        
    elif track == "analysis" and "gbw" in aspect:
        correct_formula = ANALYSIS_OTA_GBW.get(item_id, "gm/CL")
        correct_answer = f"GBW ≈ {correct_formula}"
        distractors = [f"GBW ≈ {d}" for d in generate_formula_distractors(correct_formula, "gbw")]
        
    elif track == "analysis" and "loop_gain" in aspect:
        correct_formula = ANALYSIS_FEEDBACK_LOOP_GAIN.get(item_id, "T = A0")
        correct_answer = correct_formula
        
        distractors = generate_formula_distractors(correct_formula, "loop_gain")
        
    elif track == "analysis" and "beta" in aspect:
        correct_formula = ANALYSIS_FEEDBACK_BETA.get(item_id, "β = 1")
        correct_answer = correct_formula
        
        distractors = generate_formula_distractors(correct_formula, "beta")
        
    elif track == "analysis" and "closed_loop" in aspect or "gain" in aspect:
        correct_formula = ANALYSIS_FEEDBACK_CL_GAIN.get(item_id, "Vout/Vin = -R2/R1")
        correct_answer = correct_formula
        
        distractors = generate_formula_distractors(correct_formula, "cl_gain")
        
    elif track == "analysis" and "identify_tf" in aspect:
        correct_formula = ANALYSIS_FILTER_TF.get(item_id, "H(s) = 1/(1+sRC)")
        correct_answer = f"Transfer function: {correct_formula}"
        distractors = [f"Transfer function: {d}" for d in generate_formula_distractors(correct_formula, "filter_tf")]
        
    elif track == "analysis" and "psrr" in aspect:
        correct_formula = ANALYSIS_OTA_PSRR.get(item_id, "PSRR+ ≈ gm·ro")
        correct_answer = correct_formula
        
        distractors = generate_formula_distractors(correct_formula, "psrr")
        
    elif track == "analysis" and "rout" in aspect:
        correct_formula = ANALYSIS_OTA_ROUT.get(item_id, "rout ≈ ro")
        correct_answer = correct_formula
        
        distractors = generate_formula_distractors(correct_formula, "rout")
        
    elif track == "analysis" and "swing" in aspect:
        correct_formula = ANALYSIS_OTA_SWING.get(item_id, "Max swing ≈ VDD - 2·|VDsat|")
        correct_answer = correct_formula
        
        distractors = generate_formula_distractors(correct_formula, "swing")
        
    elif track == "analysis" and "power" in aspect:
        correct_formula = ANALYSIS_OTA_POWER.get(item_id, "P = VDD·Itail")
        correct_answer = correct_formula
        
        distractors = generate_formula_distractors(correct_formula, "power")
        
    elif track == "analysis" and "noise" in aspect:
        correct_formula = ANALYSIS_OTA_NOISE.get(item_id, "Vn,out² ≈ 8kT/(3gm)")
        correct_answer = correct_formula
        
        distractors = generate_formula_distractors(correct_formula, "noise")
        
    else:
        # Generic fallback
        correct_answer = "Correct answer for " + question_id
        distractors = [f"Distractor {i} for {question_id}" for i in range(1, 10)]
    
    # Shuffle and assign A-J
    all_choices = [correct_answer] + distractors[:9]
    random.shuffle(all_choices)
    
    # Find correct letter
    correct_letter = chr(65 + all_choices.index(correct_answer))
    
    choices = {chr(65+i): all_choices[i] for i in range(min(10, len(all_choices)))}
    
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

