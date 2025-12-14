#!/usr/bin/env python3
"""
Generate multiple-choice answer keys for design verification tasks.
For design tasks, the MC question is about identifying which spec was NOT met.
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Any

random.seed(42)

# Spec names for different design families
OTA_SPECS = ["dc_gain_db", "unity_gain_freq_hz", "phase_margin_deg", "power_w"]
FILTER_SPECS = ["cutoff_frequency", "center_frequency", "quality_factor", "passband_gain", "stopband_attenuation", "power_w"]
FEEDBACK_SPECS = ["transimpedance", "gain", "bandwidth", "phase_margin"]


def generate_design_mc_key(item_id: str, family: str) -> Dict[str, Any]:
    """Generate MC answer key for design verification questions."""
    
    if family == "ota":
        specs = OTA_SPECS
        question_id = f"{item_id}_design_verification"
    elif family == "filters":
        specs = FILTER_SPECS
        question_id = f"{item_id}_design_verification"
    elif family == "feedback":
        specs = FEEDBACK_SPECS
        question_id = f"{item_id}_design_verification"
    else:
        return {}
    
    # For design tasks, we ask "Which specification did the design fail to meet?"
    # The correct answer depends on the actual design_spec.json, so we'll make this generic
    
    # Create choices - one for each possible failing spec
    all_choices = [
        f"The design meets all specifications",
        f"DC gain is below the minimum requirement",
        f"Unity-gain frequency (GBW) is too low",
        f"Phase margin is insufficient for stability",
        f"Power consumption exceeds the maximum limit",
        f"Cutoff frequency is outside the tolerance range",
        f"Center frequency deviates from target by >10%",
        f"Quality factor Q is too low",
        f"Passband gain does not meet the target",
        f"Stopband attenuation is insufficient",
    ]
    
    # Shuffle
    random.shuffle(all_choices)
    choices = {chr(65+i): all_choices[i] for i in range(min(10, len(all_choices)))}
    
    # For now, we'll say the correct answer is "A" (placeholder - needs real spec check)
    correct_answer = "A"
    
    return {
        "question_id": question_id,
        "correct_answer": correct_answer,
        "answer_text": "Design verification MC - requires ngspice simulation to determine actual failing specs",
        "choices": choices,
        "track": "design",
        "family": family,
        "note": "Design MC questions require runtime simulation - correct answer is determined dynamically"
    }


def main():
    data_dir = Path(__file__).parent.parent / "data" / "dev" / "design"
    
    # OTA design tasks
    for i in range(1, 13):
        ota_id = f"ota{i:03d}"
        item_dir = data_dir / "ota" / ota_id
        if item_dir.exists():
            mc_key = generate_design_mc_key(ota_id, "ota")
            output_file = item_dir / "mc_answer_key_design.json"
            with open(output_file, 'w') as f:
                json.dump(mc_key, f, indent=2)
            print(f"Generated {output_file}")
    
    # Filter design tasks
    for i in range(1, 13):
        filter_id = f"filter{i:03d}"
        item_dir = data_dir / "filters" / filter_id
        if item_dir.exists():
            mc_key = generate_design_mc_key(filter_id, "filters")
            output_file = item_dir / "mc_answer_key_design.json"
            with open(output_file, 'w') as f:
                json.dump(mc_key, f, indent=2)
            print(f"Generated {output_file}")
    
    # Feedback design tasks
    for i in range(1, 5):
        fb_id = f"feedback{i:03d}"
        item_dir = data_dir / "feedback" / fb_id
        if item_dir.exists():
            mc_key = generate_design_mc_key(fb_id, "feedback")
            output_file = item_dir / "mc_answer_key_design.json"
            with open(output_file, 'w') as f:
                json.dump(mc_key, f, indent=2)
            print(f"Generated {output_file}")
    
    print("\nNote: Design MC keys are placeholders. The actual correct answer")
    print("depends on ngspice simulation results and must be determined at runtime.")


if __name__ == "__main__":
    main()

